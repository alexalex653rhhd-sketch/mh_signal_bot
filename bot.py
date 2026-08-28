import os
import asyncio
import threading
import json
from urllib.request import urlopen
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes
)


# ==========================================
# BOT TOKEN
# ==========================================

TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise RuntimeError("BOT_TOKEN পাওয়া যায়নি!")


# ==========================================
# RENDER WEB SERVER
# ==========================================

class Handler(BaseHTTPRequestHandler):

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(
            b"MH Quotex Signal Bot is running!"
        )

    def log_message(self, format, *args):
        pass


def web_server():

    port = int(os.environ.get("PORT", "10000"))

    server = HTTPServer(
        ("0.0.0.0", port),
        Handler
    )

    server.serve_forever()


# ==========================================
# GET MARKET DATA
# ==========================================

def get_market_data():

    url = (
        "https://api.binance.com/api/v3/klines"
        "?symbol=BTCUSDT"
        "&interval=5m"
        "&limit=100"
    )

    with urlopen(url, timeout=10) as response:

        data = response.read().decode()

        return json.loads(data)


# ==========================================
# EMA CALCULATION
# ==========================================

def calculate_ema(closes, period):

    multiplier = 2 / (period + 1)

    ema = closes[0]

    for close in closes[1:]:

        ema = (
            (close - ema)
            * multiplier
            + ema
        )

    return ema


# ==========================================
# RSI CALCULATION
# ==========================================

def calculate_rsi(closes, period=14):

    gains = []
    losses = []

    for i in range(1, len(closes)):

        change = closes[i] - closes[i - 1]

        if change > 0:

            gains.append(change)
            losses.append(0)

        else:

            gains.append(0)
            losses.append(abs(change))

    if len(gains) < period:
        return 50

    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period

    if avg_loss == 0:

        return 100

    rs = avg_gain / avg_loss

    rsi = 100 - (
        100 / (1 + rs)
    )

    return rsi


# ==========================================
# CALCULATE SIGNAL
# ==========================================

def calculate_signal():

    data = get_market_data()

    if not data or len(data) < 30:
        raise Exception("Not enough market data")

    closes = [
        float(candle[4])
        for candle in data
    ]

    price = closes[-1]

    # EMA 9
    ema9 = calculate_ema(
        closes,
        9
    )

    # EMA 21
    ema21 = calculate_ema(
        closes,
        21
    )

    # RSI 14
    rsi = calculate_rsi(
        closes,
        14
    )

    # Recent price movement
    previous_price = closes[-2]

    # ======================================
    # SIGNAL RULES
    # ======================================

    if (
        ema9 > ema21
        and rsi >= 55
        and price > previous_price
    ):

        signal = "🟢 UP"

    elif (
        ema9 < ema21
        and rsi <= 45
        and price < previous_price
    ):

        signal = "🔴 DOWN"

    else:

        signal = "🟡 WAIT"

    return (
        price,
        ema9,
        ema21,
        rsi,
        signal
    )


# ==========================================
# /START COMMAND
# ==========================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(

        "🤖 MH Quotex Signal Bot চালু হয়েছে!\n\n"

        "📊 BTC/USDT signal দেখতে "
        "/signal লিখুন।\n\n"

        "🟢 UP = দাম উপরের দিকে যাওয়ার সম্ভাবনা\n"
        "🔴 DOWN = দাম নিচের দিকে যাওয়ার সম্ভাবনা\n"
        "🟡 WAIT = পরিষ্কার signal নেই\n\n"

        "⏱️ Timeframe: 5 মিনিট"
    )


# ==========================================
# /SIGNAL COMMAND
# ==========================================

async def signal(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    try:

        (
            price,
            ema9,
            ema21,
            rsi,
            result
        ) = calculate_signal()


        # ==================================
        # SIGNAL MESSAGE
        # ==================================

        message = (

            "📊 MH QUOTEX SIGNAL\n\n"

            f"💱 BTC/USDT: ${price:,.2f}\n\n"

            f"📈 EMA 9: {ema9:,.2f}\n"
            f"📉 EMA 21: {ema21:,.2f}\n"
            f"📊 RSI 14: {rsi:.2f}\n\n"

            f"🎯 SIGNAL: {result}\n\n"

            "⏱️ Timeframe: 5 মিনিট\n\n"

            "━━━━━━━━━━━━━━\n"

            "⚠️ এটি indicator-based signal।\n"
            "Quotex-এর chart/price-এর সাথে মিলিয়ে "
            "তারপর সিদ্ধান্ত নিন।\n\n"

            "❌ কোনো signal 100% নিশ্চিত নয়।"
        )


        await update.message.reply_text(message)


    except Exception as e:

        await update.message.reply_text(

            "❌ Market data পাওয়া যাচ্ছে না।\n\n"
            "কিছুক্ষণ পরে আবার /signal দিন।"
        )


# ==========================================
# MAIN
# ==========================================

async def main():

    # Render server
    threading.Thread(
        target=web_server,
        daemon=True
    ).start()


    # Telegram application
    app = (
        Application
        .builder()
        .token(TOKEN)
        .build()
    )


    # Commands
    app.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    app.add_handler(
        CommandHandler(
            "signal",
            signal
        )
    )


    # Start bot
    await app.initialize()

    await app.start()

    await app.updater.start_polling(
        drop_pending_updates=True
    )


    # Keep running
    while True:

        await asyncio.sleep(3600)


# ==========================================
# RUN
# ==========================================

if __name__ == "__main__":

    asyncio.run(main())
