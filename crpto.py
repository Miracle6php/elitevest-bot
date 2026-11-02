import asyncio
from datetime import datetime, timezone

import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest
from telegram.ext import ContextTypes

URL = "https://api.coingecko.com/api/v3/simple/price"

COINS = [
    ("bitcoin", "₿", "BTC"),
    ("ethereum", "Ξ", "ETH"),
    ("binancecoin", "🔶", "BNB"),
    ("solana", "◎", "SOL"),
    ("ripple", "✖", "XRP"),
]

KEYBOARD = InlineKeyboardMarkup(
    [[InlineKeyboardButton("🔄 Refresh", callback_data="crypto_refresh")]]
)


def fetch_prices():
    """Blocking request, run in a thread so the bot is not frozen."""
    params = {
        "ids": ",".join(coin_id for coin_id, _, _ in COINS),
        "vs_currencies": "usd",
        "include_24hr_change": "true",
    }
    response = requests.get(URL, params=params, timeout=10)
    response.raise_for_status()
    return response.json()


def build_message(data):
    lines = ["₿ CRYPTO MARKET", ""]

    for coin_id, icon, symbol in COINS:
        coin = data[coin_id]
        price = coin["usd"]
        change = coin.get("usd_24h_change") or 0
        arrow = "📈" if change >= 0 else "📉"

        lines.append(f"{icon} {symbol}/USD")
        lines.append(f"💵 ${price:,.2f}")
        lines.append(f"{arrow} {change:+.2f}% (24h)")
        lines.append("")

    now = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
    lines.append(f"🔄 Updated: {now}")

    return "\n".join(lines)


async def crypto_prices(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query

    if query:
        await query.answer()

    try:
        data = await asyncio.to_thread(fetch_prices)
        message = build_message(data)
    except Exception:
        message = (
            "⚠️ Could not load market prices right now.\n"
            "Please try again in a moment."
        )

    if query:
        try:
            await query.edit_message_text(message, reply_markup=KEYBOARD)
        except BadRequest:
            # Telegram rejects an edit when the text did not change
            pass
    else:
        await update.message.reply_text(message, reply_markup=KEYBOARD)
