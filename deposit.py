import math
import sqlite3
from datetime import datetime

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes

from admin import notify_admin_deposit, get_user_code

DB = "elitevest.db"
MIN_DEPOSIT = 50
WALLET = "TABK7j4y3NP5xSvjpnSKsFncNYX8RPtnFB"

# Cancel buttons are handled in bot.py (clears the flow and returns home)
CANCEL_TEXTS = ("❌ Cancel", "❌ Cancel Deposit")


def init_deposit_table():
    """Call once at startup."""
    conn = sqlite3.connect(DB)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS deposits(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER,
            amount REAL,
            proof TEXT,
            proof_uid TEXT,
            status TEXT DEFAULT 'Pending',
            created_at TEXT
        )
        """
    )
    conn.commit()
    conn.close()


async def deposit_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["waiting_for_deposit_amount"] = True

    cancel_keyboard = ReplyKeyboardMarkup([["❌ Cancel Deposit"]], resize_keyboard=True)

    await update.message.reply_text(
        "💳 Deposit Funds\n\n"
        f"Minimum deposit: ${MIN_DEPOSIT}\n"
        "Enter deposit amount:",
        reply_markup=cancel_keyboard,
    )


async def handle_deposit_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("waiting_for_deposit_amount"):
        return False

    text = update.message.text.strip()
    if text in CANCEL_TEXTS:
        return False

    try:
        amount = float(text.replace(",", "").replace("$", ""))
    except ValueError:
        await update.message.reply_text(
            "❌ Please enter a valid amount.\n\nExamples:\n100\n100.50"
        )
        return True

    if not math.isfinite(amount) or amount < MIN_DEPOSIT:
        await update.message.reply_text(f"❌ Minimum deposit is ${MIN_DEPOSIT}.")
        return True

    amount = round(amount, 2)
    context.user_data["deposit_amount"] = amount
    context.user_data["waiting_for_deposit_amount"] = False

    payment_keyboard = ReplyKeyboardMarkup(
        [["✅ Payment Sent"], ["❌ Cancel"]], resize_keyboard=True
    )

    await update.message.reply_text(
        f"💳 Deposit Request\n\n"
        f"💵 Amount: ${amount:,.2f}\n\n"
        f"Send payment to:\n\n"
        f"`{WALLET}`\n\n"
        f"Network: TRC20\n\n"
        f"After payment click ✅ Payment Sent",
        reply_markup=payment_keyboard,
        parse_mode="Markdown",
    )
    return True


async def handle_payment_sent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Call when text == '✅ Payment Sent'"""
    if not context.user_data.get("deposit_amount"):
        await update.message.reply_text("❌ Start a deposit first.")
        return True

    context.user_data["waiting_for_screenshot"] = True
    await update.message.reply_text(
        "📸 Send a screenshot of your payment.",
        reply_markup=ReplyKeyboardMarkup([["❌ Cancel"]], resize_keyboard=True),
    )
    return True


async def handle_screenshot_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reminder if the user sends text instead of a photo."""
    if not context.user_data.get("waiting_for_screenshot"):
        return False
    if update.message.text.strip() in CANCEL_TEXTS:
        return False
    await update.message.reply_text("📸 Please send the payment screenshot as a photo.")
    return True


async def handle_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Register with MessageHandler(filters.PHOTO, handle_screenshot)."""
    if not context.user_data.get("waiting_for_screenshot"):
        return

    photo = update.message.photo[-1]
    user_id = update.effective_user.id
    amount = context.user_data["deposit_amount"]

    conn = sqlite3.connect(DB)
    cursor = conn.cursor()

    cursor.execute("SELECT 1 FROM deposits WHERE proof_uid=?", (photo.file_unique_id,))
    if cursor.fetchone():
        conn.close()
        await update.message.reply_text("❌ This screenshot was already submitted.")
        return

    cursor.execute(
        "INSERT INTO deposits(telegram_id, amount, proof, proof_uid, status, created_at) "
        "VALUES (?, ?, ?, ?, 'Pending', ?)",
        (user_id, amount, photo.file_id, photo.file_unique_id,
         datetime.now().strftime("%d %b %Y %H:%M")),
    )
    deposit_id = cursor.lastrowid
    conn.commit()
    conn.close()

    context.user_data.pop("waiting_for_screenshot", None)
    context.user_data.pop("deposit_amount", None)

    await update.message.reply_text(
        f"✅ Deposit Submitted\n\n"
        f"🆔 User ID: {get_user_code(user_id)}\n"
        f"🧾 Deposit: #{deposit_id}\n"
        f"💵 Amount: ${amount:,.2f}\n"
        f"⏳ Status: Pending verification"
    )

    await notify_admin_deposit(context, deposit_id, user_id, amount, photo.file_id)
