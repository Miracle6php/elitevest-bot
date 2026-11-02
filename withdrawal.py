import math
import os
import re
import sqlite3
from datetime import datetime

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes

from admin import notify_admin_withdrawal

DB = os.getenv("DB_PATH", "elitevest.db")
MIN_WITHDRAW = 20

HOME_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["👤 My Account", "💳 Deposit Funds"],
        ["📤 Withdraw Funds", "💰 Invest Now"],
        ["💼 Active Investments", "👥 Referral Program"],
        ["📜 Transaction History", "💹 Crypto Prices"],
        ["📞 Contact Support"],
    ],
    resize_keyboard=True,
)

CANCEL_KEYBOARD = ReplyKeyboardMarkup([["❌ Cancel"]], resize_keyboard=True)

# TRON (TRC20) addresses start with T and are 34 characters long
TRC20_PATTERN = re.compile(r"^T[1-9A-HJ-NP-Za-km-z]{33}$")

WITHDRAW_KEYS = (
    "waiting_for_withdraw_amount",
    "confirm_withdraw",
    "waiting_for_wallet",
    "withdraw_amount",
)


def _clear_flow(context):
    for key in WITHDRAW_KEYS:
        context.user_data.pop(key, None)


def init_withdrawal_table():
    """Call once at startup (after the users table has been created)."""
    conn = sqlite3.connect(DB)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS withdrawals(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER,
            amount REAL,
            wallet TEXT,
            status TEXT DEFAULT 'Pending',
            created_at TEXT
        )
        """
    )

    # admin.py adds approved withdrawals to users.withdrawn; make sure it exists
    columns = [row[1] for row in conn.execute("PRAGMA table_info(users)")]
    if columns and "withdrawn" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN withdrawn REAL DEFAULT 0")

    conn.commit()
    conn.close()


async def withdraw_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["waiting_for_withdraw_amount"] = True

    await update.message.reply_text(
        "💸 Withdraw Funds\n\n"
        f"Minimum withdrawal: ${MIN_WITHDRAW}\n"
        "Enter withdrawal amount:",
        reply_markup=CANCEL_KEYBOARD,
    )


async def handle_withdraw_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("waiting_for_withdraw_amount"):
        return False

    text = update.message.text.strip()

    if text == "❌ Cancel":
        _clear_flow(context)
        await update.message.reply_text("❌ Withdrawal cancelled.", reply_markup=HOME_KEYBOARD)
        return True

    try:
        amount = float(text.replace(",", "").replace("$", ""))
    except ValueError:
        await update.message.reply_text("❌ Please enter a valid amount.")
        return True

    if not math.isfinite(amount) or amount < MIN_WITHDRAW:
        await update.message.reply_text(f"❌ Minimum withdrawal is ${MIN_WITHDRAW}.")
        return True

    amount = round(amount, 2)
    user_id = update.effective_user.id

    conn = sqlite3.connect(DB)
    result = conn.execute(
        "SELECT balance FROM users WHERE telegram_id=?", (user_id,)
    ).fetchone()
    conn.close()

    if not result:
        _clear_flow(context)
        await update.message.reply_text(
            "❌ Account not found.\n\nReturning to Home...", reply_markup=HOME_KEYBOARD
        )
        return True

    balance = result[0]

    if amount > balance:
        _clear_flow(context)
        await update.message.reply_text(
            f"❌ Insufficient Balance\n\n"
            f"💰 Available Balance: ${balance:,.2f}\n\n"
            f"Returning to Home...",
            reply_markup=HOME_KEYBOARD,
        )
        return True

    context.user_data["withdraw_amount"] = amount
    context.user_data["waiting_for_withdraw_amount"] = False
    context.user_data["confirm_withdraw"] = True

    await update.message.reply_text(
        f"💵 Withdrawal Amount: ${amount:,.2f}\n\nChoose an option below:",
        reply_markup=ReplyKeyboardMarkup(
            [["✅ Continue"], ["❌ Cancel"]], resize_keyboard=True
        ),
    )
    return True


async def handle_withdraw_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("confirm_withdraw"):
        return False

    text = update.message.text

    if text == "❌ Cancel":
        _clear_flow(context)
        await update.message.reply_text(
            "❌ Withdrawal cancelled.\n\nReturning to Home...", reply_markup=HOME_KEYBOARD
        )
        return True

    if text == "✅ Continue":
        context.user_data["confirm_withdraw"] = False
        context.user_data["waiting_for_wallet"] = True
        await update.message.reply_text(
            "🏦 Send your USDT TRC20 wallet address:", reply_markup=CANCEL_KEYBOARD
        )
        return True

    return False


async def handle_wallet_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("waiting_for_wallet"):
        return False

    wallet = update.message.text.strip()

    if wallet == "❌ Cancel":
        _clear_flow(context)
        await update.message.reply_text("❌ Withdrawal cancelled.", reply_markup=HOME_KEYBOARD)
        return True

    if not TRC20_PATTERN.match(wallet):
        await update.message.reply_text(
            "❌ Invalid wallet address.\n\n"
            "A TRC20 address starts with T and has 34 characters."
        )
        return True

    amount = context.user_data["withdraw_amount"]
    user = update.effective_user

    conn = sqlite3.connect(DB)
    cursor = conn.cursor()

    # Hold the money now: deduct only if the balance still covers it
    cursor.execute(
        "UPDATE users SET balance = balance - ? WHERE telegram_id=? AND balance >= ?",
        (amount, user.id, amount),
    )
    if cursor.rowcount == 0:
        conn.close()
        _clear_flow(context)
        await update.message.reply_text(
            "❌ Insufficient Balance.", reply_markup=HOME_KEYBOARD
        )
        return True

    cursor.execute(
        "INSERT INTO withdrawals(telegram_id, amount, wallet, status, created_at) "
        "VALUES (?, ?, ?, 'Pending', ?)",
        (user.id, amount, wallet, datetime.now().strftime("%d %b %Y %H:%M")),
    )
    withdrawal_id = cursor.lastrowid
    conn.commit()
    conn.close()

    _clear_flow(context)

    await notify_admin_withdrawal(context, withdrawal_id, user, amount, wallet)

    await update.message.reply_text(
        f"✅ Withdrawal request submitted.\n\n"
        f"🧾 Request: #{withdrawal_id}\n"
        f"💵 Amount: ${amount:,.2f}\n"
        f"⏳ Status: Pending admin approval",
        reply_markup=HOME_KEYBOARD,
    )
    return True
