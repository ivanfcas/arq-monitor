"""
ARQ PRO Intraday Monitor - Ivan
Versión PRO optimizada para señales reales (no ruido)
"""

import os
import time as time_module
import random
import requests
import yfinance as yf
import pandas as pd
from datetime import datetime, time
import pytz

# 🔥 Activos (alta volatilidad)
ACTIVOS = ["TSLA", "NVDA", "AMD", "SOXL", "TQQQ", "AAPL"]

# 📊 Mercado referencia
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
    return round(100 - (100 / (1 + rs)).iloc[-1], 2)


# =========================
# 📥 DATA
# =========================
def get_data(ticker):
    try:
        time_module.sleep(random.uniform(1, 2))

        df = yf.download(
            ticker,
            period="5d",
            interval="5m",
            progress=False
        )

        if df.empty or len(df) < 50:
            return None

        close = df["Close"].squeeze()
        volume = df["Volume"].squeeze()

        price = float(close.iloc[-1])
        prev = float(close.iloc[-2])

        change_pct = round((price - prev) / prev * 100, 2)
        rsi = calcular_rsi(close)

        vol_now = float(volume.iloc[-1])
        vol_avg = float(volume.rolling(20).mean().iloc[-1])
        vol_ratio = round(vol_now / vol_avg, 2) if vol_avg > 0 else 0

        ma20 = float(close.rolling(20).mean().iloc[-1])

        return {
            "ticker": ticker,
            "price": round(price, 2),
            "change_pct": change_pct,
            "rsi": rsi,
            "vol_ratio": vol_ratio,
            "ma20": round(ma20, 2)
        }

    except Exception as e:
        print(f"[ERROR] {ticker}: {e}")
        return None


# =========================
# 📊 MERCADO GLOBAL
# =========================
def market_is_bullish():
    data = []

    for m in MARKET:
        d = get_data(m)
        if d:
            data.append(d)

    if len(data) < 2:
        return False

    return all(d["change_pct"] > 0 for d in data)


# =========================
# 🚨 SEÑALES PRO
# =========================
def evaluate(d, market_ok):
    signals = []
    score = 0

    # 🚀 MOMENTUM (mejor setup intradía)
    if d["change_pct"] > 1 and d["vol_ratio"] > 1.5 and market_ok:
        score += 2
        signals.append({
            "type": "MOMENTUM",
            "strength": "FUERTE",
            "entry": d["price"],
            "sl": round(d["price"] * 0.98, 2),
            "tp": round(d["price"] * 1.04, 2),
            "msg": "Ruptura con volumen (continuación)"
        })

    # 📉 REBOTE CONFLUENTE
    if d["rsi"] < 35 and d["change_pct"] < -1 and d["vol_ratio"] > 1.3:
        score += 1
        signals.append({
            "type": "REBOTE",
            "strength": "MODERADA",
            "entry": d["price"],
            "sl": round(d["price"] * 0.97, 2),
            "tp": round(d["price"] * 1.03, 2),
            "msg": "Sobreventa + caída + volumen"
        })

    return signals, score


# =========================
# 📝 MENSAJE
# =========================
def format_msg(results):
    now = datetime.now(pytz.timezone("America/Bogota")).strftime("%H:%M")

    msg = [f"🚀 *ARQ PRO — {now}*"]
    msg.append("🔥 Mejores oportunidades:\n")

    top = results[:3]

    for r in top:
        d = r["data"]
        s = r["signals"][0]

        msg.append(
            f"*{d['ticker']}* — ${d['price']} ({d['change_pct']}%)\n"
            f"👉 {s['type']} [{s['strength']}]\n"
            f"Entrada: ${s['entry']}\n"
            f"SL: ${s['sl']} | TP: ${s['tp']}\n"
            f"{s['msg']}\n"
        )

    return "\n".join(msg)


# =========================
# 📲 TELEGRAM
# =========================
def send(msg):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("[WARN] Sin credenciales, mostrando mensaje:")
        print(msg)
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    try:
        resp = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": msg,
            "parse_mode": "Markdown"
        }, timeout=10)

        if resp.status_code == 200:
            print("[OK] Enviado a Telegram")
        else:
            print(f"[ERROR] Telegram: {resp.status_code} {resp.text}")

    except Exception as e:
        print(f"[ERROR] Envío Telegram: {e}")


# =========================
# ⏰ MERCADO
# =========================
def mercado_abierto():
    et = pytz.timezone("America/New_York")
    now = datetime.now(et)
    return now.weekday() < 5 and time(9, 30) <= now.time() <= time(16, 0)


# =========================
# 🚀 MAIN
# =========================
def main():
    print("🚀 Iniciando ARQ PRO...")

    market_ok = market_is_bullish()
    print(f"[INFO] Mercado alcista: {market_ok}")

    results = []

    for t in ACTIVOS:
        print(f"Analizando {t}...")
        d = get_data(t)

        if not d:
            continue

        sigs, score = evaluate(d, market_ok)

        if score > 0:
            results.append({
                "data": d,
                "signals": sigs,
                "score": score
            })

    # 🔥 ordenar mejores primero
    results.sort(key=lambda x: x["score"], reverse=True)

    # 🚫 NO SPAM
    if not results:
        print("❌ Sin oportunidades reales.")
        return

    msg = format_msg(results)
    send(msg)


if __name__ == "__main__":
    main()