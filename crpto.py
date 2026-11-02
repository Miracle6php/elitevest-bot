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

# Optional keys (set on Render > Environment). Both work without a key.
CRYPTOCOMPARE_KEY = os.environ.get("CRYPTOCOMPARE_API_KEY")
COINGECKO_KEY = os.environ.get("COINGECKO_API_KEY")

CACHE_SECONDS = 45
_cache = {"time": 0, "data": None}

# (coingecko id, icon, symbol)
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

HEADERS = {"accept": "application/json", "User-Agent": "elitevest-bot/1.0"}


def fetch_cryptocompare():
    """Source 1: CryptoCompare. Returns {SYMBOL: (price, change_pct)}."""
    symbols = ",".join(symbol for _, _, symbol in COINS)
    headers = dict(HEADERS)
    if CRYPTOCOMPARE_KEY:
        headers["authorization"] = f"Apikey {CRYPTOCOMPARE_KEY}"

    response = requests.get(
        "https://min-api.cryptocompare.com/data/pricemultifull",
        params={"fsyms": symbols, "tsyms": "USD"},
        headers=headers,
        timeout=10,
    )
    response.raise_for_status()
    raw = response.json()["RAW"]

    result = {}
    for _, _, symbol in COINS:
        usd = raw[symbol]["USD"]
        result[symbol] = (usd["PRICE"], usd.get("CHANGEPCT24HOUR") or 0)
    return result


def fetch_coingecko():
    """Source 2 (backup): CoinGecko. Returns {SYMBOL: (price, change_pct)}."""
    headers = dict(HEADERS)
    if COINGECKO_KEY:
        headers["x-cg-demo-api-key"] = COINGECKO_KEY

    response = requests.get(
        "https://api.coingecko.com/api/v3/simple/price",
        params={
            "ids": ",".join(coin_id for coin_id, _, _ in COINS),
            "vs_currencies": "usd",
            "include_24hr_change": "true",
        },
        headers=headers,
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()

    result = {}
    for coin_id, _, symbol in COINS:
        result[symbol] = (
            data[coin_id]["usd"],
            data[coin_id].get("usd_24h_change") or 0,
        )
    return result


def fetch_prices():
    """Try each source in order; blocking, so run it in a thread."""
    for name, source in (
        ("CryptoCompare", fetch_cryptocompare),
        ("CoinGecko", fetch_coingecko),
    ):
        try:
            return source()
        except Exception as error:
            logger.error("Price source %s failed: %s", name, error)

    raise RuntimeError("All price sources failed")


def get_prices_cached():
    now = time.time()

    if _cache["data"] and now - _cache["time"] < CACHE_SECONDS:
        return _cache["data"]

    try:
        data = fetch_prices()
        _cache["data"] = data
        _cache["time"] = now
        return data
    except Exception:
        # Show the last good prices if we have them
        if _cache["data"]:
            return _cache["data"]
        raise


def build_message(data):
    lines = ["₿ CRYPTO MARKET", ""]

    for _, icon, symbol in COINS:
        price, change = data[symbol]
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
