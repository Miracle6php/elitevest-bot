from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes


async def deposit_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["waiting_for_deposit_amount"] = True

    await update.message.reply_text(
        "💳 Deposit Funds\n\n"
        "Enter deposit amount:"
    )


async def handle_deposit_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not context.user_data.get("waiting_for_deposit_amount"):
        return False

    try:
        amount = float(update.message.text.strip())
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
        f"`YOUR_USDT_WALLET_ADDRESS`\n\n"
        f"Network: TRC20\n\n"
        f"After payment click ✅ Payment Sent",
        reply_markup=payment_keyboard,
        parse_mode="Markdown"
    )

    return True
