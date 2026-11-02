import html
import os
import sqlite3
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

DB = os.getenv("DB_PATH", "elitevest.db")

# Admin Telegram ID(s). Works with either ADMIN_IDS=111,222 or ADMIN_ID=111
_raw_admins = os.getenv("ADMIN_IDS") or os.getenv("ADMIN_ID", "")
ADMIN_IDS = [int(i) for i in _raw_admins.replace(" ", "").split(",") if i]


def get_user_code(telegram_id):
    """The generated User ID shown in My Profile (users.account_id)."""
    conn = sqlite3.connect(DB)
    row = conn.execute(
        "SELECT account_id FROM users WHERE telegram_id=?", (telegram_id,)
    ).fetchone()
    conn.close()
    return row[0] if row and row[0] else "N/A"


def _log_transaction(cursor, user_id, tx_type, amount, status):
    cursor.execute(
        "INSERT INTO transactions(telegram_id, type, amount, status, date) "
        "VALUES (?, ?, ?, ?, ?)",
        (user_id, tx_type, amount, status, datetime.now().strftime("%Y-%m-%d %H:%M")),
    )


# ------------------------------------------------------------------ deposits

def deposit_keyboard(deposit_id):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Approve", callback_data=f"dep_approve:{deposit_id}"),
        InlineKeyboardButton("❌ Reject", callback_data=f"dep_reject:{deposit_id}"),
    ]])


async def notify_admin_deposit(context, deposit_id, user_id, amount, file_id):
    caption = (
        f"🔔 New deposit #{deposit_id}\n"
        f"🆔 User ID: {get_user_code(user_id)}\n"
        f"💵 Amount: ${amount:,.2f}"
    )
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_photo(
                admin_id, file_id, caption=caption,
                reply_markup=deposit_keyboard(deposit_id),
            )
        except Exception:
            pass  # admin hasn't pressed Start on the bot yet


async def handle_deposit_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    if query.from_user.id not in ADMIN_IDS:
        await query.answer("Not allowed.", show_alert=True)
        return
    await query.answer()

    action, deposit_id = query.data.split(":")
    deposit_id = int(deposit_id)
    approve = action == "dep_approve"

    conn = sqlite3.connect(DB)
    cursor = conn.cursor()

    # Only a Pending deposit can be decided, so it can never be credited twice
    cursor.execute(
        "UPDATE deposits SET status=? WHERE id=? AND status='Pending'",
        ("Approved" if approve else "Rejected", deposit_id),
    )
    if cursor.rowcount == 0:
        conn.close()
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(f"⚠️ Deposit #{deposit_id} was already processed.")
        return

    cursor.execute("SELECT telegram_id, amount FROM deposits WHERE id=?", (deposit_id,))
    user_id, amount = cursor.fetchone()

    if approve:
        cursor.execute(
            "UPDATE users SET balance = balance + ?, deposited = deposited + ? "
            "WHERE telegram_id=?",
            (amount, amount, user_id),
        )
    _log_transaction(cursor, user_id, "Deposit", amount, "Approved" if approve else "Rejected")
    conn.commit()
    conn.close()

    status = "✅ APPROVED" if approve else "❌ REJECTED"
    await query.edit_message_caption(f"{query.message.caption}\n\n{status}")

    if approve:
        await context.bot.send_message(
            user_id,
            f"✅ Your deposit of ${amount:,.2f} has been approved and added to your balance.",
        )
    else:
        await context.bot.send_message(
            user_id,
            f"❌ Your deposit #{deposit_id} could not be verified. Contact support if you believe this is a mistake.",
        )


# ---------------------------------------------------------------- withdrawals

def withdraw_keyboard(withdrawal_id):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Approve", callback_data=f"wd_approve:{withdrawal_id}"),
        InlineKeyboardButton("❌ Reject", callback_data=f"wd_reject:{withdrawal_id}"),
    ]])


async def notify_admin_withdrawal(context, withdrawal_id, user, amount, wallet):
    username = f"@{html.escape(user.username)}" if user.username else "none"
    text = (
        f"💸 New Withdrawal Request #{withdrawal_id}\n\n"
        f"🆔 User ID: {get_user_code(user.id)}\n"
        f"👤 Username: {username}\n"
        f"💵 Amount: ${amount:,.2f}\n"
        f"🏦 Wallet (TRC20):\n<code>{wallet}</code>"
    )
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                admin_id, text,
                reply_markup=withdraw_keyboard(withdrawal_id),
                parse_mode="HTML",
            )
        except Exception:
            pass  # admin hasn't pressed Start on the bot yet


async def handle_withdraw_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    if query.from_user.id not in ADMIN_IDS:
        await query.answer("Not allowed.", show_alert=True)
        return
    await query.answer()

    action, withdrawal_id = query.data.split(":")
    withdrawal_id = int(withdrawal_id)
    approve = action == "wd_approve"

    conn = sqlite3.connect(DB)
    cursor = conn.cursor()

    # Only a Pending request can be decided, so it can't be processed twice
    cursor.execute(
        "UPDATE withdrawals SET status=? WHERE id=? AND status='Pending'",
        ("Approved" if approve else "Rejected", withdrawal_id),
    )
    if cursor.rowcount == 0:
        conn.close()
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(f"⚠️ Request #{withdrawal_id} was already processed.")
        return

    cursor.execute(
        "SELECT telegram_id, amount FROM withdrawals WHERE id=?", (withdrawal_id,)
    )
    user_id, amount = cursor.fetchone()

    if approve:
        cursor.execute(
            "UPDATE users SET withdrawn = withdrawn + ? WHERE telegram_id=?",
            (amount, user_id),
        )
    else:
        # Give the held money back
        cursor.execute(
            "UPDATE users SET balance = balance + ? WHERE telegram_id=?",
            (amount, user_id),
        )
    _log_transaction(cursor, user_id, "Withdrawal", amount, "Approved" if approve else "Rejected")
    conn.commit()
    conn.close()

    status = "✅ APPROVED (send the funds)" if approve else "❌ REJECTED (balance refunded)"
    await query.edit_message_text(f"{query.message.text}\n\n{status}")

    if approve:
        await context.bot.send_message(
            user_id, f"✅ Withdrawal Approved\n\n💵 Amount Sent: ${amount:,.2f}"
        )
    else:
        await context.bot.send_message(
            user_id,
            f"❌ Withdrawal Rejected\n\n💵 ${amount:,.2f} has been returned to your balance.\n"
            f"Please contact support for assistance.",
        )
