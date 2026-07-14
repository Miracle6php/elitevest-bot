from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import ContextTypes
import sqlite3

# Your Telegram ID
ADMIN_ID = 8672271918


async def withdraw_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["waiting_for_withdraw_amount"] = True

    await update.message.reply_text(
        "💸 Withdraw Funds\n\n"
        "Enter withdrawal amount:"
    )


async def handle_withdraw_amount(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not context.user_data.get("waiting_for_withdraw_amount"):
        return False

    try:
        amount = float(update.message.text.strip())
    except ValueError:
        await update.message.reply_text(
            "❌ Please enter a valid amount."
        )
        return True

    if amount <= 0:
        await update.message.reply_text(
            "❌ Amount must be greater than zero."
        )
        return True

    user_id = update.effective_user.id

    conn = sqlite3.connect("elitevest.db")
    cursor = conn.cursor()

    cursor.execute(
        "SELECT balance FROM users WHERE telegram_id=?",
        (user_id,)
    )

    result = cursor.fetchone()
    conn.close()

    if not result:
        await update.message.reply_text(
            "❌ Account not found."
        )
        return True

    balance = result[0]

    if amount > balance:
        await update.message.reply_text(
            f"❌ Insufficient balance.\n\n"
            f"Available Balance: ${balance}"
        )
        return True

    context.user_data["withdraw_amount"] = amount
    context.user_data["waiting_for_withdraw_amount"] = False
    context.user_data["waiting_for_wallet"] = True

    await update.message.reply_text(
        "🏦 Please send your USDT TRC20 wallet address:"
    )

    return True


async def handle_wallet_address(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not context.user_data.get("waiting_for_wallet"):
        return False

    wallet = update.message.text.strip()
    amount = context.user_data["withdraw_amount"]

    user = update.effective_user

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "✅ Approve",
                callback_data=f"approve_withdraw_{user.id}_{amount}"
            ),
            InlineKeyboardButton(
                "❌ Reject",
                callback_data=f"reject_withdraw_{user.id}_{amount}"
            )
        ]
    ])

    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=(
            f"🚨 New Withdrawal Request\n\n"
            f"👤 Username: @{user.username}\n"
            f"🆔 Telegram ID: {user.id}\n"
            f"💵 Amount: ${amount}\n"
            f"🏦 Wallet Address:\n{wallet}"
        ),
        reply_markup=keyboard
    )

    await update.message.reply_text(
        "✅ Withdrawal request submitted successfully.\n\n"
        "⏳ Waiting for admin approval."
    )

    context.user_data.pop("withdraw_amount", None)
    context.user_data.pop("waiting_for_wallet", None)

    return True


async def approve_withdraw(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query
    await query.answer()

    data = query.data.split("_")

    user_id = int(data[2])
    amount = float(data[3])

    conn = sqlite3.connect("elitevest.db")
    cursor = conn.cursor()

    cursor.execute(
        "SELECT balance FROM users WHERE telegram_id=?",
        (user_id,)
    )

    result = cursor.fetchone()

    if not result:
        conn.close()

        await query.edit_message_text(
            "❌ User account not found."
        )
        return

    balance = result[0]

    if balance < amount:
        conn.close()

        await context.bot.send_message(
            chat_id=user_id,
            text=(
                "❌ Withdrawal failed.\n\n"
                "Your account balance is no longer sufficient."
            )
        )

        await query.edit_message_text(
            "❌ Withdrawal failed due to insufficient balance."
        )
        return

    cursor.execute(
        """
        UPDATE users
        SET balance = balance - ?,
            withdrawn = withdrawn + ?
        WHERE telegram_id = ?
        """,
        (amount, amount, user_id)
    )

    conn.commit()
    conn.close()

    await context.bot.send_message(
        chat_id=user_id,
        text=(
            f"✅ Withdrawal Approved\n\n"
            f"💵 Amount: ${amount}\n\n"
            f"Your payment will be processed shortly."
        )
    )

    await query.edit_message_text(
        f"✅ Withdrawal Approved\n\n"
        f"👤 User ID: {user_id}\n"
        f"💵 Amount: ${amount}"
    )


async def reject_withdraw(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query
    await query.answer()

    data = query.data.split("_")

    user_id = int(data[2])
    amount = float(data[3])

    await context.bot.send_message(
        chat_id=user_id,
        text=(
            f"❌ Withdrawal Rejected\n\n"
            f"💵 Amount: ${amount}\n\n"
            f"Please contact support if you believe "
            f"this was a mistake."
        )
    )

    await query.edit_message_text(
        f"❌ Withdrawal Rejected\n\n"
        f"👤 User ID: {user_id}\n"
        f"💵 Amount: ${amount}"
    )