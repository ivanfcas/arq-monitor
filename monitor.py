import os
import time as time_module
import random
import requests
import yfinance as yf
import pandas as pd
from datetime import datetime, time
import pytz

# =========================
# 🚀 CONFIG
# =========================
ACTIVOS = ["QQQ", "TQQQ", "SOXL", "SPY"]
MARKET = ["SPY", "QQQ"]

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# =========================
# 📊 INDICADORES
# =========================
def calcular_rsi(serie, periodos=14):
    delta = serie.diff()
    gain = delta.clip(lower=0).rolling(periodos).mean()
    loss = (-delta.clip(upper=0)).rolling(periodos).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# =========================
# 📥 DATA
# =========================
def get_data(ticker):
    try:
        time_module.sleep(random.uniform(1, 2))

        df = yf.download(ticker, period="5d", interval="5m", progress=False)

        if df.empty or len(df) < 50:
            return None

        close = df["Close"].squeeze()
        volume = df["Volume"].squeeze()

        price = float(close.iloc[-1])
        prev = float(close.iloc[-2])

        change_pct = (price - prev) / prev * 100
        rsi = calcular_rsi(close).iloc[-1]

        vol_now = float(volume.iloc[-1])
        vol_avg = float(volume.rolling(20).mean().iloc[-1])
        vol_ratio = vol_now / vol_avg if vol_avg > 0 else 0

        ema20 = close.ewm(span=20).mean().iloc[-1]

        return {
            "ticker": ticker,
            "price": round(price, 2),
            "change_pct": round(change_pct, 2),
            "rsi": round(rsi, 2),
            "vol_ratio": round(vol_ratio, 2),
            "ema20": round(ema20, 2)
        }

    except Exception as e:
        print(f"[ERROR] {ticker}: {e}")
        return None

# =========================
# 📊 MERCADO
# =========================
def market_bias():
    data = []

    for m in MARKET:
        d = get_data(m)
        if d:
            data.append(d)

    if not data:
        return "neutral"

    positives = sum(1 for d in data if d["change_pct"] > 0)

    if positives == len(data):
        return "bull"
    elif positives == 0:
        return "bear"
    else:
        return "neutral"

# =========================
# 🚨 SEÑALES NIVEL 2
# =========================
def evaluate(d, market_state):
    signals = []

    # 🚀 MOMENTUM + TENDENCIA
    if d["change_pct"] > 0.4 and d["vol_ratio"] > 1.2:
        if d["price"] > d["ema20"]:
            action = "ENTRAR AHORA 🚀"
        else:
            action = "ESPERAR RETROCESO ⏳"

        signals.append({
            "type": "MOMENTUM",
            "action": action,
            "entry": d["price"],
            "sl": round(d["price"] * 0.985, 2),
            "tp": round(d["price"] * 1.02, 2)
        })

    # 📉 REBOTE CONTROLADO
    if d["rsi"] < 40 and d["change_pct"] < -0.5:
        signals.append({
            "type": "REBOTE",
            "action": "ENTRADA CONSERVADORA",
            "entry": d["price"],
            "sl": round(d["price"] * 0.98, 2),
            "tp": round(d["price"] * 1.02, 2)
        })

    return signals

# =========================
# 📝 MENSAJE
# =========================
def format_msg(results, market_state):
    now = datetime.now(pytz.timezone("America/Bogota")).strftime("%H:%M")

    msg = [f"🚀 *ARQ PRO — {now}*"]
    msg.append(f"📊 Mercado: {market_state.upper()}\n")

    for r in results[:2]:
        d = r["data"]
        s = r["signals"][0]

        msg.append(
            f"*{d['ticker']}* — ${d['price']} ({d['change_pct']}%)\n"
            f"{s['action']}\n"
            f"SL: ${s['sl']} | TP: ${s['tp']}\n"
        )

    msg.append("\n⚠️ Máx $10–$20 por trade")

    return "\n".join(msg)

# =========================
# 📲 TELEGRAM
# =========================
def send(msg):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print(msg)
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    requests.post(url, json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": msg,
        "parse_mode": "Markdown"
    })

# =========================
# ⏰ HORARIO
# =========================
def mercado_abierto():
    et = pytz.timezone("America/New_York")
    now = datetime.now(et)

    # evitar primera media hora (ruido)
    return now.weekday() < 5 and time(10, 0) <= now.time() <= time(15, 30)

# =========================
# 🚀 MAIN
# =========================
def main():
    print("🚀 ARQ PRO NIVEL 2")

    if not mercado_abierto():
        send("⏸ Fuera de horario óptimo")
        return

    market_state = market_bias()

    results = []

    for t in ACTIVOS:
        d = get_data(t)
        if not d:
            continue

        sigs = evaluate(d, market_state)

        if sigs:
            results.append({
                "data": d,
                "signals": sigs
            })

    if not results:
        send("🟡 Mercado lento — no operar")
        return

    msg = format_msg(results, market_state)
    send(msg)


if __name__ == "__main__":
    main()