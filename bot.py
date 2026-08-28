
import os
import json
import asyncio
import threading
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from http.server import BaseHTTPRequestHandler, HTTPServer
from concurrent.futures import ThreadPoolExecutor

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)


# =========================================================
# CONFIG
# =========================================================

TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is missing.")


# Yahoo Finance symbols
PAIRS = {
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "USDJPY": "JPY=X",
    "EURJPY": "EURJPY=X",
    "AUDUSD": "AUDUSD=X",
    "USDCAD": "CAD=X",
    "NZDUSD": "NZDUSD=X",
    "GBPJPY": "GBPJPY=X",
    "EURGBP": "EURGBP=X",
    "USDCHF": "CHF=X",
}


# =========================================================
# KEEP RENDER SERVICE ALIVE
# =========================================================

class HealthHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"MH Signal Bot is running.")

    def log_message(self, format, *args):
        pass


def web_server():
    port = int(os.environ.get("PORT", 10000))

    server = HTTPServer(
        ("0.0.0.0", port),
        HealthHandler
    )

    print(f"Web server running on port {port}")
    server.serve_forever()


# =========================================================
# GET MARKET DATA
# =========================================================

def get_market_data(pair):
    """
    Get 5-minute forex candles from Yahoo Finance.
    """

    if pair not in PAIRS:
        raise ValueError("Unsupported pair.")

    symbol = PAIRS[pair]

    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        + symbol
        + "?interval=5m&range=1d"
    )

    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )

    try:
        with urlopen(request, timeout=15) as response:
            data = json.loads(
                response.read().decode("utf-8")
            )

        result = data["chart"]["result"]

        if not result:
            raise RuntimeError("Yahoo Finance returned no data.")

        result = result[0]

        quote = result["indicators"]["quote"][0]

        closes = quote.get("close", [])

        clean_closes = [
            float(x)
            for x in closes
            if x is not None
        ]

        if len(clean_closes) < 30:
            raise RuntimeError(
                "Not enough market candles."
            )

        return clean_closes

    except HTTPError as e:
        raise RuntimeError(
            f"Yahoo Finance HTTP error: {e.code}"
        )

    except URLError:
        raise RuntimeError(
            "Market data connection failed."
        )

    except Exception as e:
        raise RuntimeError(
            f"Market data error: {str(e)}"
        )


# =========================================================
# EMA
# =========================================================

def calculate_ema(values, period):

    if len(values) < period:
        raise ValueError("Not enough data for EMA.")

    multiplier = 2 / (period + 1)

    ema = sum(values[:period]) / period

    for price in values[period:]:
        ema = (
            (price - ema) * multiplier
            + ema
        )

    return ema


# =========================================================
# RSI
# =========================================================

def calculate_rsi(values, period=14):

    if len(values) < period + 1:
        raise ValueError("Not enough data for RSI.")

    gains = []
    losses = []

    for i in range(1, len(values)):

        change = values[i] - values[i - 1]

        if change > 0:
            gains.append(change)
            losses.append(0)

        else:
            gains.append(0)
            losses.append(abs(change))

    recent_gains = gains[-period:]
    recent_losses = losses[-period:]

    avg_gain = sum(recent_gains) / period
    avg_loss = sum(recent_losses) / period

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss

    rsi = 100 - (
        100 / (1 + rs)
    )

    return rsi


# =========================================================
# CALCULATE SIGNAL
# =========================================================

def calculate_signal(pair):

    closes = get_market_data(pair)

    price = closes[-1]

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

    # -----------------------------------------
    # SIGNAL RULE
    # -----------------------------------------

    # Stronger UP condition
    if ema9 > ema21 and rsi >= 55:
        signal = "🟢 UP"

    # Stronger DOWN condition
    elif ema9 < ema21 and rsi <= 45:
        signal = "🔴 DOWN"

    # No clear direction
    else:
        signal = "🟡 WAIT"

    return {
        "pair": pair,
        "price": price,
        "ema9": ema9,
        "ema21": ema21,
        "rsi": rsi,
        "signal": signal,
    }


# =========================================================
# FORMAT SIGNAL
# =========================================================

def format_signal(data):

    return (
        "📊 MH FOREX SIGNAL\n\n"

        f"💱 Pair: {data['pair']}\n"
        "⏱️ Timeframe: 5 মিনিট\n"
        "📡 Source: Yahoo Finance\n\n"

        f"💰 Price: {data['price']:.5f}\n"
        f"📈 EMA 9: {data['ema9']:.5f}\n"
        f"📉 EMA 21: {data['ema21']:.5f}\n"
        f"📊 RSI 14: {data['rsi']:.2f}\n\n"

        f"🎯 SIGNAL: {data['signal']}\n\n"

        "⚠️ Indicator-based signal.\n"
        "Quotex-এর chart/OTC price-এর সাথে মিলিয়ে নিন।\n\n"

        "❌ 100% নিশ্চিত signal নয়।"
    )


# =========================================================
# /START
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "🤖 MH Signal Bot চালু হয়েছে!\n\n"

        "📊 একটি pair-এর signal দেখতে:\n"
        "/signal EURUSD\n"
        "/signal GBPUSD\n"
        "/signal USDJPY\n\n"

        "📋 সব pair দেখতে:\n"
        "/pairs\n\n"

        "🚀 সব pair-এর UP/DOWN signal দেখতে:\n"
        "/signals"
    )


# =========================================================
# /PAIRS
# =========================================================

async def pairs(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    text = "📋 AVAILABLE PAIRS\n\n"

    for pair in PAIRS:
        text += f"• {pair}\n"

    text += (
        "\nউদাহরণ:\n"
        "/signal EURUSD\n\n"
        "সব signal:\n"
        "/signals"
    )

    await update.message.reply_text(text)


# =========================================================
# /SIGNAL
# =========================================================

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

    pair = context.args[0].upper()

    if pair not in PAIRS:

        await update.message.reply_text(
            "❌ এই pair পাওয়া যায়নি।\n\n"
            "সব available pair দেখতে:\n"
            "/pairs"
        )

        return

    # Loading message
    loading = await update.message.reply_text(
        f"⏳ {pair} market data পরীক্ষা করছি..."
    )

    try:

        data = await asyncio.to_thread(
            calculate_signal,
            pair
        )

        message = format_signal(data)

        await loading.edit_text(message)

    except Exception as e:

        await loading.edit_text(
            "❌ Market data পাওয়া যাচ্ছে না।\n\n"
            "কিছুক্ষণ পরে আবার চেষ্টা করুন।"
        )

        print(
            f"Signal error for {pair}: {e}"
        )


# =========================================================
# CHECK ONE PAIR FOR /SIGNALS
# =========================================================

def check_pair(pair):

    try:
        data = calculate_signal(pair)

        if (
            data["signal"] == "🟢 UP"
            or data["signal"] == "🔴 DOWN"
        ):
            return data

    except Exception as e:

        print(
            f"Error checking {pair}: {e}"
        )

    return None


# =========================================================
# /SIGNALS
# =========================================================

async def signals(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    loading = await update.message.reply_text(
        "🔎 সব pair-এর market data পরীক্ষা করছি...\n"
        "একটু অপেক্ষা করুন।"
    )

    try:

        # Check pairs in parallel
        with ThreadPoolExecutor(
            max_workers=5
        ) as executor:

            results = list(
                executor.map(
                    check_pair,
                    PAIRS.keys()
                )
            )

        valid_signals = [
            x for x in results
            if x is not None
        ]

        # -----------------------------------------
        # NO SIGNAL
        # -----------------------------------------

        if not valid_signals:

            await loading.edit_text(
                "🟡 এখন কোনো পরিষ্কার UP/DOWN signal পাওয়া যায়নি।\n\n"
                "সব pair-এ WAIT/market-data সমস্যা আছে।\n\n"
                "কিছুক্ষণ পরে আবার /signals দিন।"
            )

            return

        # -----------------------------------------
        # BUILD MESSAGE
        # -----------------------------------------

        message = (
            "🚨 MH LIVE SIGNALS\n\n"
            "⏱️ Timeframe: 5 মিনিট\n"
            "📡 Source: Yahoo Finance\n\n"
        )

        for data in valid_signals:

            message += (
                f"💱 {data['pair']}\n"
                f"💰 Price: {data['price']:.5f}\n"
                f"📊 RSI: {data['rsi']:.2f}\n"
                f"📈 EMA9: {data['ema9']:.5f}\n"
                f"📉 EMA21: {data['ema21']:.5f}\n"
                f"🎯 {data['signal']}\n\n"
            )

        message += (
            "⚠️ এগুলো indicator-based signal।\n"
            "Quotex-এর chart/OTC price-এর সাথে মিলিয়ে নিন।\n\n"
            "❌ 100% নিশ্চিত signal নয়।"
        )

        await loading.edit_text(
            message
        )

    except Exception as e:

        await loading.edit_text(
            "❌ Signal scan করতে সমস্যা হয়েছে।\n"
            "কিছুক্ষণ পরে আবার /signals দিন।"
        )

        print(
            f"All signals error: {e}"
        )


# =========================================================
# MAIN
# =========================================================

async def main():

    # Render keep-alive server
    threading.Thread(
        target=web_server,
        daemon=True
    ).start()

    print("🚀 MH Signal Bot starting...")

    application = (
        Application.builder()
        .token(TOKEN)
        .build()
    )

    # Commands
    application.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    application.add_handler(
        CommandHandler(
            "pairs",
            pairs
        )
    )

    application.add_handler(
        CommandHandler(
            "signal",
            signal
        )
    )

    application.add_handler(
        CommandHandler(
            "signals",
            signals
        )
    )

    print("✅ Bot is ready!")

    await application.initialize()

    await application.start()

    await application.updater.start_polling()

    try:

        while True:
            await asyncio.sleep(3600)

    except asyncio.CancelledError:
        pass

    finally:

        await application.updater.stop()
        await application.stop()
        await application.shutdown()


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    asyncio.run(main())
