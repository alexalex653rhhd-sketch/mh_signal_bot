import os
import asyncio
import threading
import json
from urllib.request import urlopen
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")


# -------------------------
# Keep Render service alive
# -------------------------
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"MH Signal Bot is running!")

    def log_message(self, format, *args):
        pass


def web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), Handler)
    server.serve_forever()


# -------------------------
# Get real market data
# -------------------------
def get_market_data():
    url = (
        "https://api.binance.com/api/v3/klines"
        "?symbol=BTCUSDT&interval=5m&limit=100"
    )

    with urlopen(url, timeout=10) as response:
        return json.loads(response.read().decode())


# -------------------------
# Calculate signal
# -------------------------
def calculate_signal():

    data = get_market_data()

    closes = [float(x[4]) for x in data]

    price = closes[-1]

    # EMA 9
    ema9 = closes[0]
    multiplier9 = 2 / (9 + 1)

    for close in closes[1:]:
        ema9 = (close - ema9) * multiplier9 + ema9

    # EMA 21
    ema21 = closes[0]
    multiplier21 = 2 / (21 + 1)

    for close in closes[1:]:
        ema21 = (close - ema21) * multiplier21 + ema21

    # RSI 14
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

    avg_gain = sum(gains[-14:]) / 14
    avg_loss = sum(losses[-14:]) / 14

    if avg_loss == 0:
        rsi = 100
    else:
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

    # Signal
    if ema9 > ema21 and rsi > 50:
        signal = "🟢 BUY"
    elif ema9 < ema21 and rsi < 50:
        signal = "🔴 SELL"
    else:
        signal = "🟡 WAIT"

    return price, ema9, ema21, rsi, signal


# -------------------------
# Telegram commands
# -------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "🤖 MH Signal Bot চালু হয়েছে!\n\n"
        "📊 আসল BTC/USDT signal দেখতে /signal লিখুন।"
    )


async def signal(update: Update, context: ContextTypes.DEFAULT_TYPE):

    try:

        price, ema9, ema21, rsi, result = calculate_signal()

        message = (
            "📊 MH REAL SIGNAL\n\n"
            f"💰 BTC/USDT: ${price:,.2f}\n"
            f"📈 EMA 9: {ema9:,.2f}\n"
            f"📉 EMA 21: {ema21:,.2f}\n"
            f"📊 RSI: {rsi:.2f}\n\n"
            f"🎯 SIGNAL: {result}\n\n"
            "⏱️ Timeframe: 5 মিনিট\n"
            "⚠️ এটি indicator-based signal। "
            "নিজে যাচাই করে সিদ্ধান্ত নিন।"
        )

        await update.message.reply_text(message)

    except Exception as e:

        await update.message.reply_text(
            "❌ Market data পাওয়া যাচ্ছে না। একটু পরে আবার চেষ্টা করুন।"
        )


# -------------------------
# Main
# -------------------------
async def main():

    threading.Thread(
        target=web_server,
        daemon=True
    ).start()

    app = (
        Application.builder()
        .token(TOKEN)
        .build()
    )

    app.add_handler(
        CommandHandler("start", start)
    )

    app.add_handler(
        CommandHandler("signal", signal)
    )

    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main())
