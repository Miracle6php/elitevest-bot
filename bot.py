import os
import sqlite3
import random
import string
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

from referral import referral_menu
from deposit import (
    init_deposit_table,
    deposit_menu,
    handle_deposit_amount,
    handle_payment_sent,
    handle_screenshot_text,
    handle_screenshot,
)
from crpto import crypto_prices
from Transaction import transaction_history
from invest import (
    investment_menu,
    create_investment,
    show_active_investments
)
from withdrawal import (
    init_withdrawal_table,
    withdraw_menu,
    handle_withdraw_amount,
    handle_withdraw_confirmation,
    handle_wallet_address,
)
from admin import handle_deposit_decision, handle_withdraw_decision


# ==========================================
# SETTINGS (set these in Render > Environment)
# ==========================================
BOT_TOKEN = os.environ["BOT_TOKEN"]
DB = os.getenv("DB_PATH", "elitevest.db")


HOME_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["👤 My Account", "💳 Deposit Funds"],
        ["📤 Withdraw Funds", "💰 Invest Now"],
        ["💼 Active Investments", "👥 Referral Program"],
        ["📜 Transaction History", "💹 Crypto Prices"],
        ["ℹ️ About", "❓ FAQ"],
        ["📞 Contact Support"]
    ],
    resize_keyboard=True
)


# ==========================================
# KEEP-ALIVE WEB SERVER (so Render sees an open port)
# ==========================================
class PingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, *args):
        pass


def run_web():
    port = int(os.environ.get("PORT", 10000))
    HTTPServer(("0.0.0.0", port), PingHandler).serve_forever()


# ==========================================
# DATABASE
# ==========================================
def create_database():
    conn = sqlite3.connect(DB)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users(
        telegram_id INTEGER PRIMARY KEY,
        account_id TEXT UNIQUE,
        username TEXT,
        balance REAL DEFAULT 0,
        deposited REAL DEFAULT 0,
        withdrawn REAL DEFAULT 0,
        investments INTEGER DEFAULT 0,
        referral_bonus REAL DEFAULT 0,
        referrals INTEGER DEFAULT 0,
        referred_by INTEGER DEFAULT NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS active_investments(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER,
        plan TEXT,
        amount REAL,
        start_date TEXT,
        end_date TEXT,
        profit_target REAL,
        status TEXT DEFAULT 'Active'
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS transactions(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER,
        type TEXT,
        amount REAL,
        status TEXT,
        date TEXT
    )
    """)

    conn.commit()
    conn.close()


def generate_account_id():
    while True:
        account_id = (
            ''.join(random.choices(string.digits, k=3))
            + ''.join(random.choices(string.ascii_uppercase, k=5))
        )

        conn = sqlite3.connect(DB)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT account_id FROM users WHERE account_id=?",
            (account_id,)
        )
        exists = cursor.fetchone()
        conn.close()

        if not exists:
            return account_id


def register_user(user, referred_by=None):

    conn = sqlite3.connect(DB)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM users WHERE telegram_id=?",
        (user.id,)
    )

    exists = cursor.fetchone()

    if not exists:

        account_id = generate_account_id()

        cursor.execute(
            """
            INSERT INTO users(
                telegram_id,
                account_id,
                username,
                referred_by
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                user.id,
                account_id,
                user.username,
                referred_by
            )
        )

        # Add referral count to referrer
        if referred_by:
            cursor.execute(
                """
                UPDATE users
                SET referrals = referrals + 1
                WHERE telegram_id=?
                """,
                (referred_by,)
            )

        conn.commit()

    conn.close()


# ==========================================
# HANDLERS
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    referrer_id = None

    if context.args:
        try:
            referrer_id = int(context.args[0])

            if referrer_id == user.id:
                referrer_id = None
        except Exception:
            referrer_id = None

    register_user(user, referrer_id)

    await update.message.reply_text(
        "🏠 HOME\n\n"
        "👋 Welcome to EliteVest Trading Limited\n\n"
        "💼 Smart Digital Investment Platform\n"
        "🔒 Secure Transactions\n"
        "⚡ Fast Processing\n"
        "📊 Portfolio Tracking",
        reply_markup=HOME_KEYBOARD
    )


async def show_home(update: Update):
    await update.message.reply_text(
        "🏠 HOME",
        reply_markup=HOME_KEYBOARD
    )


async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):

    # Deposit flow
    if await handle_deposit_amount(update, context):
        return

    if await handle_screenshot_text(update, context):
        return

    # Withdrawal flow
    if await handle_withdraw_amount(update, context):
        return

    if await handle_withdraw_confirmation(update, context):
        return

    if await handle_wallet_address(update, context):
        return

    # Investment flow
    if await create_investment(update, context):
        return

    text = update.message.text

    if text == "💰 Invest Now":
        await investment_menu(update, context)
        return

    elif text == "💼 Active Investments":
        await show_active_investments(update, context)
        return

    elif text == "📜 Transaction History":
        await transaction_history(update, context)
        return

    elif text == "💹 Crypto Prices":
        await crypto_prices(update, context)
        return

    elif text == "👥 Referral Program":
        await referral_menu(update, context)
        return

    elif text == "ℹ️ About":

        about_text = (
            "🏢 EliteVest Trading Limited\n\n"
            "EliteVest Trading Limited is a professional investment "
            "and trading company committed to providing secure, "
            "transparent, and innovative financial solutions.\n\n"
            "📈 We offer structured investment plans with target "
            "returns depending on the selected investment plan.\n\n"
            "🎯 Our mission is to provide reliable service, "
            "responsible risk management, and excellent customer support."
        )

        await update.message.reply_photo(
            photo="https://raw.githubusercontent.com/Miracle6php/elitevest-bot/1be87ddc40c0cebd20a6e043eed0cdee0e8dd5db/IMG-20260711-WA0010(1).jpg",
            caption=about_text
        )

        await show_home(update)
        return

    elif text == "❓ FAQ":

        await update.message.reply_text(
            "❓ Frequently Asked Questions\n\n"
            "1️⃣ How do I deposit funds?\n"
            "➡ Tap 💳 Deposit Funds and follow instructions.\n\n"

            "2️⃣ How long does deposit verification take?\n"
            "➡ Deposits are verified after admin approval.\n\n"

            "3️⃣ How do I withdraw funds?\n"
            "➡ Tap 📤 Withdraw Funds and enter your details.\n\n"

            "4️⃣ How long do withdrawals take?\n"
            "➡ Withdrawals are processed after approval.\n\n"

            "5️⃣ Can I have multiple investments?\n"
            "➡ Yes, multiple investments are allowed.\n\n"

            "6️⃣ How does referral work?\n"
            "➡ Share your referral link and earn bonuses."
        )

        await show_home(update)
        return

    elif text == "📞 Contact Support":

        await update.message.reply_text(
            "📞 Contact Support\n\n"
            "📧 Email: elitevest.tradinglimited@gmail.com\n\n"
            "🕒 Support Hours: 24/7\n\n"
            "Our support team is always available."
        )

        await show_home(update)
        return

    elif text == "💳 Deposit Funds":
        await deposit_menu(update, context)
        return

    elif text == "✅ Payment Sent":
        await handle_payment_sent(update, context)
        return

    elif text == "📤 Withdraw Funds":
        await withdraw_menu(update, context)
        return

    elif text == "🏠 Home":
        await show_home(update)
        return

    elif text in ("❌ Cancel", "❌ Cancel Deposit"):

        context.user_data.clear()

        await update.message.reply_text(
            "❌ Operation cancelled."
        )

        await show_home(update)
        return

    elif text == "👤 My Account":

        user = update.effective_user

        conn = sqlite3.connect(DB)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT account_id,
                   balance,
                   investments,
                   withdrawn,
                   deposited,
                   referrals,
                   referral_bonus
            FROM users
            WHERE telegram_id=?
            """,
            (user.id,)
        )

        data = cursor.fetchone()

        conn.close()

        if data:

            account_id, balance, investments, withdrawn, deposited, referrals, referral_bonus = data

            await update.message.reply_text(
                f"👤 My Profile\n\n"
                f"🆔 User ID: {account_id}\n"
                f"💰 Available Balance: ${balance}\n"
                f"📈 Active Investments: {investments}\n"
                f"📤 Total Withdrawn: ${withdrawn}\n"
                f"💳 Total Deposited: ${deposited}\n"
                f"👥 Referrals: {referrals}\n"
                f"🎁 Referral Bonus: ${referral_bonus}"
            )

        else:

            await update.message.reply_text(
                "❌ Account not found."
            )

        return


# ==========================================
# MAIN
# ==========================================
def main():
    create_database()
    init_deposit_table()
    init_withdrawal_table()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    # Crypto refresh callback
    app.add_handler(
        CallbackQueryHandler(crypto_prices, pattern=r"^crypto_refresh$")
    )

    # Admin approve / reject buttons
    app.add_handler(
        CallbackQueryHandler(handle_deposit_decision, pattern=r"^dep_(approve|reject):\d+$")
    )
    app.add_handler(
        CallbackQueryHandler(handle_withdraw_decision, pattern=r"^wd_(approve|reject):\d+$")
    )

    # Payment screenshot
    app.add_handler(MessageHandler(filters.PHOTO, handle_screenshot))

    # Text buttons and inputs
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_buttons)
    )

    # Start the keep-alive web server for Render
    threading.Thread(target=run_web, daemon=True).start()

    print("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
