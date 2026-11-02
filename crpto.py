import asyncio
import logging
import os
import time
from datetime import datetime, timezone

import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

URL = "https://api.coingecko.com/api/v3/simple/price"

# Optional free CoinGecko "Demo" key (set COINGECKO_API_KEY on Render).
# Helps a lot because shared cloud IPs are often rate-limited without a key.
API_KEY = os.environ.get("COINGECKO_API_KEY")

CACHE_SECONDS = 60
_cache = {"time": 0, "data": None}

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
    headers = {"accept": "application/json", "User-Agent": "elitevest-bot/1.0"}
    if API_KEY:
        headers["x-cg-demo-api-key"] = API_KEY

    response = requests.get(URL, params=params, headers=headers, timeout=10)

    if response.status_code != 200:
        # This line shows the real reason in the Render logs
        logger.error(
            "CoinGecko error %s: %s",
            response.status_code,
            response.text[:200],
        )
        response.raise_for_status()

    return response.json()


def get_prices_cached():
    now = time.time()

    # Reuse recent data so many users don't trigger rate limits
    if _cache["data"] and now - _cache["time"] < CACHE_SECONDS:
        return _cache["data"]

    try:
        data = fetch_prices()
        _cache["data"] = data
        _cache["time"] = now
        return data
    except Exception:
        logger.exception("Crypto price fetch failed")
        # Fall back to the last good data if we have any
        if _cache["data"]:
            return _cache["data"]
        raise


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
        data = await asyncio.to_thread(get_prices_cached)
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
