import asyncio
import logging
import os
import time
from datetime import datetime, timezone

import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from admin import ADMIN_IDS

logger = logging.getLogger(__name__)

# Optional keys (set on Render > Environment). Both work without a key,
# but a free CoinGecko demo key avoids rate-limit errors.
CRYPTOCOMPARE_KEY = os.environ.get("CRYPTOCOMPARE_API_KEY")
COINGECKO_KEY = os.environ.get("COINGECKO_API_KEY")

CACHE_SECONDS = 45      # reuse a fresh result for this long
STALE_AFTER = 300       # warn users if the prices are older than this
_cache = {"time": 0.0, "data": None, "source": None, "error": None}

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


def fetch_coingecko():
    """Source 1: CoinGecko. Returns {SYMBOL: (price, change_pct)}."""
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


def fetch_cryptocompare():
    """Source 2 (backup): CryptoCompare. Returns {SYMBOL: (price, change_pct)}."""
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


def fetch_prices():
    """Try each source in order; blocking, so run it in a thread."""
    errors = []

    for name, source in (
        ("CoinGecko", fetch_coingecko),
        ("CryptoCompare", fetch_cryptocompare),
    ):
        try:
            return name, source()
        except Exception as error:
            logger.error("Price source %s failed: %s", name, error)
            errors.append(f"{name}: {type(error).__name__}: {error}")

    raise RuntimeError("\n".join(errors))


def get_prices_cached():
    """Return a snapshot dict: time, data, source, error."""
    now = time.time()

    if _cache["data"] and now - _cache["time"] < CACHE_SECONDS:
        return dict(_cache)

    try:
        source, data = fetch_prices()
        _cache.update(time=now, data=data, source=source, error=None)
    except Exception as error:
        if not _cache["data"]:
            raise
        # Keep the old prices, but remember they are old (shown to the user)
        _cache["error"] = str(error)

    return dict(_cache)


def build_message(snapshot):
    data = snapshot["data"]
    fetched = datetime.fromtimestamp(snapshot["time"], timezone.utc)
    age = time.time() - snapshot["time"]

    lines = ["₿ CRYPTO MARKET", ""]

    for _, icon, symbol in COINS:
        price, change = data[symbol]
        arrow = "📈" if change >= 0 else "📉"

        lines.append(f"{icon} {symbol}/USD")
        lines.append(f"💵 ${price:,.2f}")
        lines.append(f"{arrow} {change:+.2f}% (24h)")
        lines.append("")

    stamp = fetched.strftime("%H:%M:%S UTC")
    if age > STALE_AFTER:
        lines.append(f"⚠️ Live prices unavailable. Showing prices from {stamp}.")
    else:
        lines.append(f"🔄 Updated: {stamp}")
    lines.append(f"📡 Source: {snapshot['source']}")

    return "\n".join(lines)


async def crypto_prices(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query

    if query:
        await query.answer()

    debug = None

    try:
        snapshot = await asyncio.to_thread(get_prices_cached)
        message = build_message(snapshot)
        debug = snapshot["error"]
    except Exception as error:
        message = (
            "⚠️ Could not load market prices right now.\n"
            "Please try again in a moment."
        )
        debug = str(error)

    # Admin only: show the real reason so it can be fixed
    user = update.effective_user
    if debug and user and user.id in ADMIN_IDS:
        message += f"\n\n🛠 Debug (admin only):\n{debug[:600]}"

    if query:
        try:
            await query.edit_message_text(message, reply_markup=KEYBOARD)
        except BadRequest:
            # Telegram rejects an edit when the text did not change
            pass
    else:
        await update.message.reply_text(message, reply_markup=KEYBOARD)
