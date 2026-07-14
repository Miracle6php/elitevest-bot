from referral import referral_menu
from deposit import deposit_menu, handle_deposit_amount
from telegram.ext import CallbackQueryHandler
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
Application,
CommandHandler,
MessageHandler,
ContextTypes,
filters,
)

from invest import (
    investment_menu,
    create_investment,
    show_active_investments
)
from Withdrawal import (
    withdraw_menu,
    handle_withdraw_amount,
    handle_withdraw_confirmation,
    handle_wallet_address,
    approve_withdraw,
    reject_withdraw
)

import sqlite3
import random
import string


BOT_TOKEN="8938062623:AAE3kpa2erORsolY0QdyGd-F4Ykjx1IcAIc"

ADMIN_ID=8672271918


def create_database():
    conn = sqlite3.connect("elitevest.db")
    cursor = conn.cursor()

    # Users table
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

    # Active investments table
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

    conn.commit()
    conn.close()
      


def generate_account_id():
    while True:
        account_id = (
            ''.join(random.choices(string.digits, k=3))
            + ''.join(random.choices(string.ascii_uppercase, k=5))
        )

        conn = sqlite3.connect("elitevest.db")
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

    conn = sqlite3.connect("elitevest.db")
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
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    
    user = update.effective_user

    referrer_id = None

    if context.args:
       try:
           referrer_id = int(context.args[0])

           if referrer_id == user.id:
               referrer_id = None
       except:
            referrer_id = None

    register_user(user, referrer_id)

    keyboard = [
        ["💰 Invest Now", "💳 Deposit Funds"],
        ["📤 Withdraw Funds", "👤 My Account"],
        ["📈 Investment Plans", "💼 Active Investments"],
        ["📜 Transaction History", "👥 Referral Program"],
        ["🎁 Bonus Center", "🏆 VIP Membership"],
        ["🎯 Promotions", "🎉 Rewards"],
        ["📊 Market Updates", "💹 Crypto Prices"],
        ["📰 News & Insights", "📅 Investment Calendar"],
        ["⚙️ Settings", "❓ FAQ"],
        ["📞 Contact Support", "🌐 Official Channel"]
    ]

    reply_markup = ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True
    )

    await update.message.reply_text(
        "🏠 HOME\n\n"
        "👋 Welcome to EliteVest Trading Limited\n\n"
        "💼 Smart Digital Investment Platform\n"
        "🔒 Secure Transactions\n"
        "⚡ Fast Processing\n"
        "📊 Portfolio Tracking",
        reply_markup=reply_markup
    )

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):

    # Deposit flow
    if await handle_deposit_amount(update, context):
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

    elif text == "💼 Active Investments":
        await show_active_investments(update, context)

    elif text == "👥 Referral Program":
        await referral_menu(update, context)

    elif text == "💳 Deposit Funds":
        await deposit_menu(update, context)

    elif text == "📤 Withdraw Funds":
        await withdraw_menu(update, context)

    elif text == "🏠 Home":
        await show_home(update)

    elif text == "❌ Cancel":

        context.user_data.clear()

        await update.message.reply_text(
            "❌ Operation cancelled."
        )

        await show_home(update)

    elif text == "✅ Payment Sent":

        amount = context.user_data.get("deposit_amount")

        review_keyboard = ReplyKeyboardMarkup(
            [["📷 Attach Screenshot"]],
            resize_keyboard=True
        )

        await update.message.reply_text(
            f"⏳ Payment Under Review\n\n"
            f"Your payment of ${amount} is being reviewed.\n\n"
            f"You may attach a screenshot for faster confirmation.",
            reply_markup=review_keyboard
        )

    elif text == "📷 Attach Screenshot":

        context.user_data["waiting_for_screenshot"] = True

        await update.message.reply_text(
            "📷 Please send your payment screenshot as a photo."
        )

    elif text == "👤 My Account":

        user = update.effective_user

        conn = sqlite3.connect("elitevest.db")
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
async def show_home(update: Update):
    keyboard = [
        ["💰 Invest Now", "💳 Deposit Funds"],
        ["📤 Withdraw Funds", "👤 My Account"],
        ["📈 Investment Plans", "💼 Active Investments"],
        ["📜 Transaction History", "👥 Referral Program"],
        ["🎁 Bonus Center", "🏆 VIP Membership"],
        ["🎯 Promotions", "🎉 Rewards"],
        ["📊 Market Updates", "💹 Crypto Prices"],
        ["📰 News & Insights", "📅 Investment Calendar"],
        ["⚙️ Settings", "❓ FAQ"],
        ["📞 Contact Support", "🌐 Official Channel"]
    ]

    reply_markup = ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True
    )

    await update.message.reply_text(
        "🏠 Home",
        reply_markup=reply_markup
    )   
     
async def receive_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not context.user_data.get("waiting_for_screenshot"):
        return

    context.user_data["waiting_for_screenshot"] = False

    user = update.effective_user
    amount = context.user_data.get("deposit_amount", "Unknown")

    # Send notification to admin
    admin_keyboard = InlineKeyboardMarkup([
    [
        InlineKeyboardButton(
            "✅ Verify",
            callback_data=f"approve_{user.id}_{amount}"
        ),
        InlineKeyboardButton(
            "❌ Reject",
            callback_data=f"reject_{user.id}_{amount}"
        )
    ]
])

    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=(
            f"💰 New Deposit Request\n\n"
            f"👤 Username: @{user.username}\n"
            f"🆔 Telegram ID: {user.id}\n"
            f"💵 Amount: ${amount}"
        ),
        reply_markup=admin_keyboard
    )
   

    # Forward screenshot to admin
    if update.message.photo:
        await context.bot.forward_message(
            chat_id=ADMIN_ID,
            from_chat_id=update.effective_chat.id,
            message_id=update.message.message_id
        )

    await update.message.reply_text(
        "✅ Screenshot received successfully.\n\n"
        "Your payment proof has been submitted for review."
    )

    await show_home(update)
    
async def admin_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    action, user_id, amount = query.data.split("_")

    user_id = int(user_id)
    amount = float(amount)

    if action == "approve":

        conn = sqlite3.connect("elitevest.db")
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE users
            SET balance = balance + ?,
                deposited = deposited + ?
            WHERE telegram_id = ?
            """,
            (amount, amount, user_id)
        )

        conn.commit()
        conn.close()

        await context.bot.send_message(
            chat_id=user_id,
            text=(
                f"✅ Deposit Verified Successfully\n\n"
                f"💵 Amount Credited: ${amount}\n"
                f"💰 Your balance has been updated."
            )
        )

        await query.edit_message_text(
            query.message.text +
            f"\n\n✅ Deposit Approved\n"
            f"💵 Credited Amount: ${amount}"
        )

    elif action == "reject":

        await context.bot.send_message(
            chat_id=user_id,
            text=(
                "❌ Your payment was unsuccessful.\n\n"
                "Please contact support or submit a valid payment proof."
            )
        )

        await query.edit_message_text(
            query.message.text +
            "\n\n❌ Deposit Rejected"
        )
def main():
    create_database()

    app = Application.builder().token(BOT_TOKEN).build()

    # Start command
    app.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    # ==========================================
    # WITHDRAWAL CALLBACKS
    # ==========================================
    app.add_handler(
        CallbackQueryHandler(
            approve_withdraw,
            pattern=r"^approve_withdraw_"
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            reject_withdraw,
            pattern=r"^reject_withdraw_"
        )
    )

    # ==========================================
    # DEPOSIT CALLBACKS
    # ==========================================
    app.add_handler(
        CallbackQueryHandler(
            admin_actions,
            pattern=r"^(approve|reject)_[0-9]+_[0-9.]+$"
        )
    )

    # Screenshot handler
    app.add_handler(
        MessageHandler(
            filters.PHOTO,
            receive_screenshot
        )
    )

    # Text buttons and inputs
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_buttons
        )
    )

    print("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
