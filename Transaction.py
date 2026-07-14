import sqlite3
from telegram import Update
from telegram.ext import ContextTypes


async def transaction_history(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    conn = sqlite3.connect("elitevest.db")
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT type, amount, status, date
        FROM transactions
        WHERE telegram_id=?
        ORDER BY id DESC
        LIMIT 10
        """,
        (user.id,)
    )

    records = cursor.fetchall()
    conn.close()

    if not records:
        await update.message.reply_text(
            "📜 No transaction history found."
        )
        return

    message = "📜 Transaction History\n\n"

    for item in records:
        message += (
            f"🔹 {item[0]}\n"
            f"💵 Amount: ${item[1]}\n"
            f"📌 Status: {item[2]}\n"
            f"📅 Date: {item[3]}\n\n"
        )

    await update.message.reply_text(message)