import os
import asyncio
import threading
import json
import time
from urllib.request import urlopen, Request
from urllib.parse import urlencode
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes


# ==========================================
# BOT TOKEN
# ==========================================

TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise RuntimeError("BOT_TOKEN পাওয়া যায়নি!")


# ==========================================
# AVAILABLE FOREX PAIRS
# ==========================================

PAIRS = {
    "EURUSD": ("EUR/USD", "EURUSD=X"),
    "GBPUSD": ("GBP/USD", "GBPUSD=X"),
    "USDJPY": ("USD/JPY", "JPY=X"),
    "EURJPY": ("EUR/JPY", "EURJPY=X"),
    "AUDUSD": ("AUD/USD", "AUDUSD=X"),
    "USDCAD": ("USD/CAD", "CAD=X"),
    "NZDUSD": ("NZD/USD", "NZDUSD=X"),
    "GBPJPY": ("GBP/JPY", "GBPJPY=X"),
    "EURGBP": ("EUR/GBP", "EURGBP=X"),
    "USDCHF": ("USD/CHF", "CHF=X"),
}


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
# DOWNLOAD MARKET DATA
# ==========================================

def get_market_data(symbol):

    end_time = int(time.time())
    start_time = end_time - (60 * 60 * 24)

    params = urlencode({
        "period1": start_time,
        "period2": end_time,
        "interval": "5m",
        "events": "history",
        "includeAdjustedClose": "true"
    })

    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        + symbol
        + "?"
        + params
    )

    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )

    with urlopen(request, timeout=15) as response:

        raw = response.read().decode()

        result = json.loads(raw)

    chart = result.get("chart", {})

    if chart.get("error"):
        raise Exception(
            str(chart["error"])
        )

    results = chart.get("result")

    if not results:
        raise Exception("Yahoo Finance থেকে data পাওয়া যায়নি")

    result_data = results[0]

    timestamps = result_data.get("timestamp", [])
    quote = result_data.get("indicators", {}).get(
        "quote", []
    )

    if not quote:
        raise Exception("Price data পাওয়া যায়নি")

    closes = quote[0].get("close", [])

    clean_closes = []

    for value in closes:

        if value is not None:

            clean_closes.append(float(value))

    if len(clean_closes) < 30:

        raise Exception(
            "যথেষ্ট 5-minute candle পাওয়া যায়নি"
        )

    return clean_closes


# ==========================================
# EMA
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
# RSI
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

    avg_gain = sum(
        gains[-period:]
    ) / period

    avg_loss = sum(
        losses[-period:]
    ) / period

    if avg_loss == 0:
        return 100

    rs = avg_gain / avg_loss

    return 100 - (
        100 / (1 + rs)
    )


# ==========================================
# SIGNAL
# ==========================================

def calculate_signal(closes):

    price = closes[-1]
    previous_price = closes[-2]

    ema9 = calculate_ema(
        closes,
        9
    )

    ema21 = calculate_ema(
        closes,
        21
    )

    rsi = calculate_rsi(
        closes,
        14
    )

    # ======================================
    # UP
    # ======================================

    if (
        ema9 > ema21
        and rsi >= 55
        and price > previous_price
    ):

        signal = "🟢 UP"

    # ======================================
    # DOWN
    # ======================================

    elif (
        ema9 < ema21
        and rsi <= 45
        and price < previous_price
    ):

        signal = "🔴 DOWN"

    # ======================================
    # WAIT
    # ======================================

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
# /START
# ==========================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(

        "🤖 MH Quotex Signal Bot\n\n"

        "📊 /pairs → Available pairs\n\n"

        "উদাহরণ:\n"
        "/signal EURUSD\n"
        "/signal GBPUSD\n"
        "/signal USDJPY\n\n"

        "🟢 UP\n"
        "🔴 DOWN\n"
        "🟡 WAIT\n\n"

        "⏱️ Timeframe: 5 মিনিট"
    )


# ==========================================
# /PAIRS
# ==========================================

async def pairs(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    text = "📋 AVAILABLE PAIRS\n\n"

    for code, data in PAIRS.items():

        text += (
            f"• {code} = {data[0]}\n"
        )

    text += (
        "\nউদাহরণ:\n"
        "/signal EURUSD"
    )

    await update.message.reply_text(text)


# ==========================================
# /SIGNAL
# ==========================================

async def signal(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not context.args:

        await update.message.reply_text(

            "❗ Pair লিখুন।\n\n"

            "উদাহরণ:\n"
            "/signal EURUSD\n"
            "/signal GBPUSD\n"
            "/signal USDJPY\n\n"

            "সব pair দেখতে /pairs লিখুন।"
        )

        return


    code = context.args[0].upper()

    if code not in PAIRS:

        await update.message.reply_text(

            "❌ এই pair পাওয়া যায়নি।\n\n"
            "Available pair দেখতে /pairs লিখুন।"
        )

        return


    pair_name, yahoo_symbol = PAIRS[code]


    # ======================================
    # GET DATA
    # ======================================

    try:

        closes = get_market_data(
            yahoo_symbol
        )

        (
            price,
            ema9,
            ema21,
            rsi,
            result
        ) = calculate_signal(closes)


    except Exception as e:

        await update.message.reply_text(

            "❌ Market data পাওয়া যায়নি।\n\n"

            f"Pair: {pair_name}\n"
            "Source: Yahoo Finance\n\n"

            f"সমস্যা: {str(e)[:300]}"
        )

        return


    # ======================================
    # RESULT
    # ======================================

    message = (

        "📊 MH FOREX SIGNAL\n\n"

        f"💱 Pair: {pair_name}\n"

        "📡 Source: Yahoo Finance\n"

        "⏱️ Timeframe: 5 মিনিট\n\n"

        f"💰 Price: {price:.5f}\n"

        f"📈 EMA 9: {ema9:.5f}\n"

        f"📉 EMA 21: {ema21:.5f}\n"

        f"📊 RSI 14: {rsi:.2f}\n\n"

        f"🎯 SIGNAL: {result}\n\n"

        "━━━━━━━━━━━━━━\n"

        "⚠️ এটি indicator-based signal।\n"

        "Quotex-এর নিজস্ব chart/OTC price-এর "
        "সাথে মিলিয়ে নিন।\n\n"

        "❌ 100% নিশ্চিত signal নয়।"
    )


    await update.message.reply_text(
        message
    )


# ==========================================
# MAIN
# ==========================================

async def main():

    threading.Thread(
        target=web_server,
        daemon=True
    ).start()


    app = (
        Application
        .builder()
        .token(TOKEN)
        .build()
    )


    app.add_handler(
        CommandHandler(
            "start",
            start
        )
    )


    app.add_handler(
        CommandHandler(
            "pairs",
            pairs
        )
    )


    app.add_handler(
        CommandHandler(
            "signal",
            signal
        )
    )


    await app.initialize()

    await app.start()

    await app.updater.start_polling(
        drop_pending_updates=True
    )


    while True:

        await asyncio.sleep(3600)


# ==========================================
# RUN
# ==========================================

if __name__ == "__main__":

    asyncio.run(main())
