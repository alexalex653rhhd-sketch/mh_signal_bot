import requests
import time
from datetime import datetime

# ==================================================
# TELEGRAM SETTINGS
# ==================================================

BOT_TOKEN = "PASTE_YOUR_BOT_TOKEN_HERE"
CHAT_ID = "PASTE_YOUR_CHAT_ID_HERE"

# ==================================================
# SETTINGS
# ==================================================

SIGNAL_INTERVAL = 120  # 2 minutes

PAIRS = {
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "USDJPY": "USDJPY=X",
    "EURJPY": "EURJPY=X",
    "AUDUSD": "AUDUSD=X",
    "USDCAD": "USDCAD=X",
    "NZDUSD": "NZDUSD=X",
    "GBPJPY": "GBPJPY=X",
    "EURGBP": "EURGBP=X",
    "USDCHF": "USDCHF=X"
}

last_update_id = 0


# ==================================================
# TELEGRAM SEND MESSAGE
# ==================================================

def send_message(text):

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    try:
        r = requests.post(
            url,
            data={
                "chat_id": CHAT_ID,
                "text": text
            },
            timeout=15
        )

        if r.status_code != 200:
            print("Telegram error:", r.text)

        else:
            print("Telegram message sent.")

    except Exception as e:
        print("Telegram connection error:", e)


# ==================================================
# GET TELEGRAM COMMANDS
# ==================================================

def check_commands():

    global last_update_id

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"

    try:

        r = requests.get(
            url,
            params={
                "offset": last_update_id + 1,
                "timeout": 5
            },
            timeout=10
        )

        data = r.json()

        if not data.get("ok"):
            return

        for update in data.get("result", []):

            last_update_id = update["update_id"]

            message = update.get("message")

            if not message:
                continue

            text = message.get("text", "").strip()

            user_chat_id = message["chat"]["id"]

            # -------------------------------
            # START
            # -------------------------------

            if text == "/start":

                send_to_chat(
                    user_chat_id,
                    "🤖 Happy Signal Bot is ONLINE!\n\n"
                    "Commands:\n"
                    "/signal - Get signal now\n"
                    "/start - Bot status\n\n"
                    "⏱️ Automatic signal every 2 minutes."
                )

            # -------------------------------
            # SIGNAL
            # -------------------------------

            elif text == "/signal":

                send_to_chat(
                    user_chat_id,
                    "⏳ Checking market...\nPlease wait."
                )

                message_text = generate_signals()

                send_to_chat(
                    user_chat_id,
                    message_text
                )

    except Exception as e:

        print("Command error:", e)


# ==================================================
# SEND TO SPECIFIC CHAT
# ==================================================

def send_to_chat(chat_id, text):

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    try:

        requests.post(
            url,
            data={
                "chat_id": chat_id,
                "text": text
            },
            timeout=15
        )

    except Exception as e:

        print("Send error:", e)


# ==================================================
# GET FOREX DATA FROM YAHOO FINANCE
# ==================================================

def get_prices(symbol):

    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"

    params = {
        "interval": "1m",
        "range": "1d"
    }

    try:

        r = requests.get(
            url,
            params=params,
            headers={
                "User-Agent": "Mozilla/5.0"
            },
            timeout=15
        )

        data = r.json()

        result = data["chart"]["result"]

        if not result:
            return []

        indicators = result[0]["indicators"]["quote"][0]

        closes = indicators.get("close", [])

        prices = [
            float(x)
            for x in closes
            if x is not None
        ]

        return prices

    except Exception as e:

        print("Market data error:", symbol, e)

        return []


# ==================================================
# EMA
# ==================================================

def ema(values, period):

    if len(values) < period:
        return None

    multiplier = 2 / (period + 1)

    ema_value = sum(values[:period]) / period

    for price in values[period:]:

        ema_value = (
            (price - ema_value) * multiplier
        ) + ema_value

    return ema_value


# ==================================================
# RSI
# ==================================================

def calculate_rsi(values, period=14):

    if len(values) < period + 1:
        return None

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

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(gains)):

        avg_gain = (
            (avg_gain * (period - 1)) + gains[i]
        ) / period

        avg_loss = (
            (avg_loss * (period - 1)) + losses[i]
        ) / period

    if avg_loss == 0:
        return 100

    rs = avg_gain / avg_loss

    rsi = 100 - (100 / (1 + rs))

    return rsi


# ==================================================
# ANALYZE PAIR
# ==================================================

def analyze_pair(pair, symbol):

    prices = get_prices(symbol)

    if len(prices) < 30:

        return {
            "pair": pair,
            "signal": "WAIT",
            "rsi": None,
            "reason": "Not enough data"
        }

    ema9 = ema(prices, 9)
    ema21 = ema(prices, 21)
    rsi = calculate_rsi(prices)

    if ema9 is None or ema21 is None or rsi is None:

        return {
            "pair": pair,
            "signal": "WAIT",
            "rsi": rsi,
            "reason": "Indicator error"
        }

    up_score = 0
    down_score = 0

    # --------------------------------
    # EMA TREND
    # --------------------------------

    if ema9 > ema21:
        up_score += 2

    elif ema9 < ema21:
        down_score += 2

    # --------------------------------
    # RSI
    # --------------------------------

    if rsi >= 55:
        up_score += 2

    elif rsi <= 45:
        down_score += 2

    elif rsi > 50:
        up_score += 1

    elif rsi < 50:
        down_score += 1

    # --------------------------------
    # FINAL SIGNAL
    # --------------------------------

    if up_score >= 3 and up_score > down_score:

        signal = "UP"

    elif down_score >= 3 and down_score > up_score:

        signal = "DOWN"

    else:

        signal = "WAIT"

    return {
        "pair": pair,
        "signal": signal,
        "rsi": rsi,
        "reason": f"UP={up_score} DOWN={down_score}"
    }


# ==================================================
# GENERATE ALL SIGNALS
# ==================================================

def generate_signals():

    now = datetime.now().strftime("%H:%M:%S")

    text = (
        "📊 2-MINUTE FOREX SIGNAL\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🕒 Time: {now}\n\n"
    )

    up_count = 0
    down_count = 0
    wait_count = 0

    for pair, symbol in PAIRS.items():

        print("Checking:", pair)

        result = analyze_pair(pair, symbol)

        signal = result["signal"]
        rsi = result["rsi"]

        if signal == "UP":

            emoji = "🟢"
            up_count += 1

        elif signal == "DOWN":

            emoji = "🔴"
            down_count += 1

        else:

            emoji = "⚪"
            wait_count += 1

        if rsi is None:
            rsi_text = "N/A"
        else:
            rsi_text = f"{rsi:.1f}"

        text += (
            f"{emoji} {pair}: {signal}\n"
            f"   RSI: {rsi_text}\n\n"
        )

        time.sleep(1)

    text += (
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🟢 UP: {up_count}\n"
        f"🔴 DOWN: {down_count}\n"
        f"⚪ WAIT: {wait_count}\n\n"
        "⏱️ Next signal: 2 minutes\n"
        "⚠️ Indicator-based signal only.\n"
        "❌ No signal is 100% guaranteed."
    )

    return text


# ==================================================
# MAIN BOT
# ==================================================

def main():

    print("======================================")
    print("      HAPPY SIGNAL BOT STARTED")
    print("======================================")

    send_message(
        "🤖 Happy Signal Bot is ONLINE!\n\n"
        "🟢 UP\n"
        "🔴 DOWN\n"
        "⚪ WAIT\n\n"
        "⏱️ Automatic signal every 2 minutes."
    )

    while True:

        try:

            # Check Telegram commands
            check_commands()

            print("\nGenerating automatic signals...")

            signal_message = generate_signals()

            send_message(signal_message)

            print("Signal sent.")
            print("Waiting 2 minutes...")

            # Wait 2 minutes
            for _ in range(120):

                check_commands()

                time.sleep(1)

        except KeyboardInterrupt:

            print("Bot stopped.")

            send_message(
                "🛑 Happy Signal Bot stopped."
            )

            break

        except Exception as e:

            print("MAIN ERROR:", e)

            time.sleep(30)


# ==================================================
# START
# ==================================================

if __name__ == "__main__":
    main()
