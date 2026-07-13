from telegram import Update
from telegram.ext import ContextTypes
import sqlite3


async def referral_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    conn = sqlite3.connect("elitevest.db")
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT referrals, referral_bonus
        FROM users
        WHERE telegram_id=?
        """,
        (user_id,)
    )

    data = cursor.fetchone()
    conn.close()

    referrals = data[0] if data else 0
    referral_bonus = data[1] if data else 0

    bot_username = (await context.bot.get_me()).username

    referral_link = (
        f"https://t.me/{bot_username}?start={user_id}"
    )

    await update.message.reply_text(
        f"👥 REFERRAL PROGRAM\n\n"
        f"🔗 Your Referral Link:\n"
        f"{referral_link}\n\n"
        f"👥 Total Referrals: {referrals}\n"
        f"🎁 Referral Bonus: ${referral_bonus}\n\n"
        f"Invite friends and earn rewards when they join and deposit."
    )