from telegram import Update, ReplyKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
import sqlite3
from datetime import datetime, timedelta

DB = "elitevest.db"

# One place to edit all plan details
PLANS = {
    "🥉 Bronze Plan": {"name": "Bronze Plan", "emoji": "🥉", "min": 500,   "days": 7, "rate": 10.0},
    "🥈 Silver Plan": {"name": "Silver Plan", "emoji": "🥈", "min": 2000,  "days": 7, "rate": 15.0},
    "🥇 Gold Plan":   {"name": "Gold Plan",   "emoji": "🥇", "min": 7000,  "days": 7, "rate": 16.8},
    "💎 Elite Plan":  {"name": "Elite Plan",  "emoji": "💎", "min": 20000, "days": 7, "rate": 19.5},
}


def fmt(n):
    """500 -> 500, 16.8 -> 16.8"""
    return f"{n:g}"


async def investment_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):

    keyboard = ReplyKeyboardMarkup(
        [
            ["🥉 Bronze Plan"],
            ["🥈 Silver Plan"],
            ["🥇 Gold Plan"],
            ["💎 Elite Plan"],
            ["❌ Cancel"],
        ],
        resize_keyboard=True,
    )

    message = "💰 <b><u>INVESTMENT PLANS</u></b>\n\n"

    for p in PLANS.values():
        message += (
            f"{p['emoji']} <b><i>{p['name']}</i></b>\n"
            f"💵 <i>Minimum:</i> <b>${p['min']:,}</b>\n"
            f"⏳ <i>Duration:</i> <b>{p['days']} Days</b>\n"
            f"📈 <i>Profit Target:</i> <code> {fmt(p['rate'])}% </code>\n"
            f"──────────────\n"
        )

    message += "\n💎 <i>Select a plan to continue.</i>"

    await update.message.reply_text(
        message,
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML,
    )


async def create_investment(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = update.message.text
    user_id = update.effective_user.id

    if text not in PLANS:
        return False

    plan = PLANS[text]
    amount = plan["min"]
    profit_target = round(amount * plan["rate"] / 100, 2)

    conn = sqlite3.connect(DB)
    cursor = conn.cursor()

    try:
        cursor.execute(
            "SELECT balance, referred_by FROM users WHERE telegram_id=?",
            (user_id,),
        )
        user = cursor.fetchone()

        if not user:
            return True

        balance, referrer_id = user

        if balance < amount:
            await update.message.reply_text(
                f"❌ Insufficient balance.\n\n"
                f"Required: ${amount:,}\n"
                f"Available Balance: ${balance:,.2f}"
            )
            return True

        start_date = datetime.now()
        end_date = start_date + timedelta(days=plan["days"])

        # Deduct from account balance (WHERE guard prevents going negative)
        cursor.execute(
            """
            UPDATE users
            SET balance = balance - ?,
                investments = investments + 1
            WHERE telegram_id=? AND balance >= ?
            """,
            (amount, user_id, amount),
        )

        if cursor.rowcount == 0:
            conn.rollback()
            await update.message.reply_text("❌ Insufficient balance.")
            return True

        # Investment record
        cursor.execute(
            """
            INSERT INTO active_investments(
                telegram_id, plan, amount, start_date,
                end_date, profit_target, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                text,
                amount,
                start_date.strftime("%d %b %Y"),
                end_date.strftime("%d %b %Y"),
                profit_target,
                "Active",
            ),
        )

        # Referral bonus 10%
        if referrer_id:
            referral_bonus = amount * 0.10
            cursor.execute(
                """
                UPDATE users
                SET referral_bonus = referral_bonus + ?,
                    balance = balance + ?
                WHERE telegram_id=?
                """,
                (referral_bonus, referral_bonus, referrer_id),
            )

        conn.commit()

        new_balance = balance - amount

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    await update.message.reply_text(
        f"✅ <b>Investment Created Successfully</b>\n\n"
        f"📊 Plan: {text}\n"
        f"💵 Amount Invested: <b>${amount:,}</b>\n"
        f"📈 Profit Target: <b>{fmt(plan['rate'])}%</b> (${profit_target:,.2f})\n"
        f"📅 Start Date: {start_date.strftime('%d %b %Y')}\n"
        f"📅 End Date: {end_date.strftime('%d %b %Y')}\n"
        f"⏳ Duration: {plan['days']} Days\n"
        f"💳 New Balance: ${new_balance:,.2f}",
        parse_mode=ParseMode.HTML,
    )

    return True


async def show_active_investments(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    conn = sqlite3.connect(DB)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT plan, amount, start_date, end_date, profit_target, status
        FROM active_investments
        WHERE telegram_id=? AND status='Active'
        """,
        (user_id,),
    )

    investments = cursor.fetchall()
    conn.close()

    if not investments:
        await update.message.reply_text(
            "💼 Active Investments\n\n"
            "You currently have no active investments."
        )
        return

    message = "💼 Active Investments\n\n"

    for index, inv in enumerate(investments, start=1):
        plan, amount, start_date, end_date, profit_target, status = inv
        message += (
            f"{index}️⃣ {plan}\n"
            f"💵 Amount: ${amount:,}\n"
            f"📅 Started: {start_date}\n"
            f"⏳ Ends: {end_date}\n"
            f"📈 Profit Target: ${profit_target:,.2f}\n"
            f"🟢 Status: {status}\n\n"
        )

    await update.message.reply_text(message)