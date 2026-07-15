import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes


async def crypto_prices(update: Update, context: ContextTypes.DEFAULT_TYPE):

    url = "https://api.coingecko.com/api/v3/simple/price"

    params = {
        "ids": "bitcoin,ethereum,binancecoin,solana,ripple",
        "vs_currencies": "usd",
        "include_24hr_change": "true"
    }

    response = requests.get(url, params=params)
    data = response.json()

    message = f"""
₿ CRYPTO MARKET

₿ BTC/USDT
💵 ${data['bitcoin']['usd']}
📈 {data['bitcoin']['usd_24h_change']:.2f}%

Ξ ETH/USDT
💵 ${data['ethereum']['usd']}
📈 {data['ethereum']['usd_24h_change']:.2f}%

🔶 BNB/USDT
💵 ${data['binancecoin']['usd']}
📈 {data['binancecoin']['usd_24h_change']:.2f}%

◎ SOL/USDT
💵 ${data['solana']['usd']}
📈 {data['solana']['usd_24h_change']:.2f}%

✖ XRP/USDT
💵 ${data['ripple']['usd']}
📈 {data['ripple']['usd_24h_change']:.2f}%

🔄 Updated live market data
"""

    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton(
            "🔄 Refresh",
            callback_data="crypto_refresh"
        )]]
    )

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            message,
            reply_markup=keyboard
        )
    else:
        await update.message.reply_text(
            message,
            reply_markup=keyboard
        )