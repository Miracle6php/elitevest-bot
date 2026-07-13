from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
import sqlite3
from datetime import datetime, timedelta


async def investment_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):

    keyboard = ReplyKeyboardMarkup(
        [
            ["🥉 Bronze Plan"],
            ["🥈 Silver Plan"],
            ["🥇 Gold Plan"],
            ["💎 Elite Plan"],
            ["❌ Cancel"]
        ],
        resize_keyboard=True
    )

    await update.message.reply_text(
        "💰 INVESTMENT PLANS\n\n"

        "🥉 Bronze Plan\n"
        "💵 Minimum: $200\n"
        "⏳ Duration: 30 Days\n\n"

        "🥈 Silver Plan\n"
        "💵 Minimum: $500\n"
        "⏳ Duration: 30 Days\n\n"

        "🥇 Gold Plan\n"
        "💵 Minimum: $2000\n"
        "⏳ Duration: 30 Days\n\n"

        "💎 Elite Plan\n"
        "💵 Minimum: $10000\n"
        "⏳ Duration: 30 Days\n\n"

        "📈 Profit Target: 14%\n\n"

        "Select a plan to continue.",
        reply_markup=keyboard
    )


async def create_investment(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = update.message.text
    user_id = update.effective_user.id

    plans = {
        "🥉 Bronze Plan": 200,
        "🥈 Silver Plan": 500,
        "🥇 Gold Plan": 2000,
        "💎 Elite Plan": 10000
    }

    if text not in plans:
        return False


    amount = plans[text]

    conn = sqlite3.connect("elitevest.db")
    cursor = conn.cursor()


    cursor.execute(
        """
        SELECT balance
        FROM users
        WHERE telegram_id=?
        """,
        (user_id,)
    )

    user = cursor.fetchone()


    if not user:
        conn.close()
        return True


    balance = user[0]


    if balance < amount:

        conn.close()

        await update.message.reply_text(
            f"❌ Insufficient balance.\n\n"
            f"Required: ${amount}\n"
            f"Available Balance: ${balance}"
        )

        return True


    # Get referrer
    cursor.execute(
        """
        SELECT referred_by
        FROM users
        WHERE telegram_id=?
        """,
        (user_id,)
    )

    referrer = cursor.fetchone()


    profit_target = amount * 0.14


    start_date = datetime.now()
    end_date = start_date + timedelta(days=30)


    # Deduct investment amount
    cursor.execute(
        """
        UPDATE users
        SET balance = balance - ?,
            investments = investments + 1
        WHERE telegram_id=?
        """,
        (
            amount,
            user_id
        )
    )


    # Create investment record
    cursor.execute(
        """
        INSERT INTO active_investments(
            telegram_id,
            plan,
            amount,
            start_date,
            end_date,
            profit_target,
            status
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
            "Active"
        )
    )


    # Referral bonus 10%
    if referrer and referrer[0]:

        referrer_id = referrer[0]

        referral_bonus = amount * 0.10


        cursor.execute(
            """
            UPDATE users
            SET referral_bonus = referral_bonus + ?,
                balance = balance + ?
            WHERE telegram_id=?
            """,
            (
                referral_bonus,
                referral_bonus,
                referrer_id
            )
        )


    conn.commit()
    conn.close()


    await update.message.reply_text(
        f"✅ Investment Created Successfully\n\n"
        f"📊 Plan: {text}\n"
        f"💵 Amount Invested: ${amount}\n"
        f"📈 Profit Target: ${profit_target:.2f}\n"
        f"📅 Start Date: {start_date.strftime('%d %b %Y')}\n"
        f"📅 End Date: {end_date.strftime('%d %b %Y')}\n"
        f"⏳ Duration: 30 Days"
    )

    return True



async def show_active_investments(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    conn = sqlite3.connect("elitevest.db")
    cursor = conn.cursor()


    cursor.execute(
        """
        SELECT plan,
               amount,
               start_date,
               end_date,
               profit_target,
               status
        FROM active_investments
        WHERE telegram_id=?
        AND status='Active'
        """,
        (user_id,)
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
            f"💵 Amount: ${amount}\n"
            f"📅 Started: {start_date}\n"
            f"⏳ Ends: {end_date}\n"
            f"📈 Profit Target: ${profit_target:.2f}\n"
            f"🟢 Status: {status}\n\n"
        )


    await update.message.reply_text(message)