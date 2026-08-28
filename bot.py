import time
import requests
import pandas as pd
import yfinance as yf
from datetime import datetime

# ==============================
# TELEGRAM SETTINGS
# ==============================

BOT_TOKEN =8637932469:AAFP_9CT0trr87XeVliTYVjPquK83ujQ7Tc
CHAT_ID =8760497927

# ==============================
# SETTINGS
# ==============================

PAIRS = {
    "USDJPY": "JPY=X",
    "EURJPY": "EURJPY=X",
    "AUDUSD": "AUDUSD=X",
    "USDCAD": "CAD=X",
    "GBPJPY": "GBPJPY=X",
    "EURGBP": "EURGBP=X"
}

TIMEFRAME = "1m"
PERIOD = "1d"

# নতুন signal প্রতি 2 মিনিটে
SIGNAL_INTERVAL = 120


# ==============================
# TELEGRAM
# ==============================

def send_message(message):

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    data = {
        "chat_id": CHAT_ID,
        "text": message
    }

    try:
        response = requests.post(url, data=data, timeout=15)

        if response.status_code != 200:
            print("Telegram error:", response.text)

    except Exception as e:
        print("Telegram connection error:", e)


# ==============================
# RSI
# ==============================

def calculate_rsi(series, period=14):

    delta = series.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss

    rsi = 100 - (100 / (1 + rs))

    return rsi


# ==============================
# GET DATA
# ==============================

def get_data(symbol):

    try:

        data = yf.download(
            symbol,
            period=PERIOD,
            interval=TIMEFRAME,
            progress=False,
            auto_adjust=False
        )

        if data.empty:
            return None

        # কিছু yfinance version-এ MultiIndex থাকে
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        data = data.dropna()

        if len(data) < 30:
            return None

        return data

    except Exception as e:

        print(symbol, "data error:", e)

        return None


# ==============================
# SIGNAL
# ==============================

def generate_signal(data):

    close = data["Close"]

    ema9 = close.ewm(span=9, adjust=False).mean()
    ema21 = close.ewm(span=21, adjust=False).mean()

    rsi = calculate_rsi(close)

    price = float(close.iloc[-1])
    e9 = float(ema9.iloc[-1])
    e21 = float(ema21.iloc[-1])
    r = float(rsi.iloc[-1])

    # --------------------------
    # UP condition
    # --------------------------

    up_score = 0

    if e9 > e21:
        up_score += 1

    if price > e9:
        up_score += 1

    if r > 50:
        up_score += 1

    # --------------------------
    # DOWN condition
    # --------------------------

    down_score = 0

    if e9 < e21:
        down_score += 1

    if price < e9:
        down_score += 1

    if r < 50:
        down_score += 1

    # --------------------------
    # Signal
    # --------------------------

    if up_score >= 2 and up_score > down_score:

        signal = "🟢 UP"

    elif down_score >= 2 and down_score > up_score:

        signal = "🔴 DOWN"

    else:

        signal = "⚪ NO SIGNAL"

    return signal, price, r, e9, e21


# ==============================
# CREATE SIGNAL MESSAGE
# ==============================

def create_message():

    now = datetime.now().strftime("%H:%M:%S")

    message = (
        "📡 SIGNAL UPDATE\n\n"
        "📊 Timeframe: 1 minute\n"
        f"⏰ Time: {now}\n"
        "🔄 New signal every 2 minutes\n\n"
    )

    found = False

    for pair, symbol in PAIRS.items():

        data = get_data(symbol)

        if data is None:

            message += (
                f"💱 {pair}\n"
                "⚪ NO DATA\n\n"
            )

            continue

        try:

            signal, price, rsi, ema9, ema21 = generate_signal(data)

            found = True

            message += (
                f"💱 {pair}\n"
                f"💰 Price: {price:.5f}\n"
                f"📊 RSI: {rsi:.2f}\n"
                f"📈 EMA9: {ema9:.5f}\n"
                f"📉 EMA21: {ema21:.5f}\n"
                f"🎯 {signal}\n\n"
            )

        except Exception as e:

            print(pair, "signal error:", e)

            message += (
                f"💱 {pair}\n"
                "⚪ NO SIGNAL\n\n"
            )

    message += (
        "⚠️ Indicator-based signal only.\n"
        "Quotex/OTC price may differ from the data source.\n"
        "❌ No signal is 100% guaranteed."
    )

    return message


# ==============================
# MAIN LOOP
# ==============================

def main():

    print("================================")
    print("Telegram Signal Bot Started")
    print("Timeframe: 1 minute")
    print("Signal interval: 2 minutes")
    print("================================")

    send_message(
        "🤖 Signal Bot Started!\n\n"
        "📊 Timeframe: 1 minute\n"
        "🔄 New signal every 2 minutes\n\n"
        "Waiting for signal..."
    )

    while True:

        try:

            print("\nGenerating new signals...")

            message = create_message()

            send_message(message)

            print("Signal sent successfully.")

        except Exception as e:

            print("Main error:", e)

        print("Waiting 2 minutes...")

        time.sleep(SIGNAL_INTERVAL)


# ==============================
# START
# ==============================

if __name__ == "__main__":
    main()
