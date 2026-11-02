from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes

# Cancel buttons are handled in bot.py (clears the flow and returns home)
CANCEL_TEXTS = ("❌ Cancel", "❌ Cancel Deposit")


async def deposit_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["waiting_for_deposit_amount"] = True

    # Only one button while the user enters the amount
    cancel_keyboard = ReplyKeyboardMarkup(
        [["❌ Cancel Deposit"]],
        resize_keyboard=True
    )

    await update.message.reply_text(
        "💳 Deposit Funds\n\n"
        "Enter deposit amount:",
        reply_markup=cancel_keyboard
    )


async def handle_deposit_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not context.user_data.get("waiting_for_deposit_amount"):
        return False

    text = update.message.text.strip()

    # Let bot.py handle the cancel button
    if text in CANCEL_TEXTS:
        return False

    try:
        amount = float(text)

    except ValueError:
        await update.message.reply_text(
            "❌ Please enter a valid amount.\n\n"
            "Examples:\n"
            "100\n"
            "100.50"
        )
        return True

    if amount <= 0:
        await update.message.reply_text(
            "❌ Deposit amount must be greater than zero."
        )
        return True

    context.user_data["deposit_amount"] = amount
    context.user_data["waiting_for_deposit_amount"] = False

    payment_keyboard = ReplyKeyboardMarkup(
        [
            ["✅ Payment Sent"],
            ["❌ Cancel"]
        ],
        resize_keyboard=True
    )

    await update.message.reply_text(
        f"💳 Deposit Request\n\n"
        f"💵 Amount: ${amount}\n\n"
        f"Send payment to:\n\n"
        f"`TABK7j4y3NP5xSvjpnSKsFncNYX8RPtnFB`\n\n"
        f"Network: TRC20\n\n"
        f"After payment click ✅ Payment Sent",
        reply_markup=payment_keyboard,
        parse_mode="Markdown"
    )

    return True
