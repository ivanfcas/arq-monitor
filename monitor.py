"""
ARQ PRO Intraday Monitor - Ivan
Versión optimizada para trading intradía con señales accionables
"""

import os
import time as time_module
import random
import requests
import yfinance as yf
import pandas as pd
from datetime import datetime, time
import pytz

# 🔥 Activos optimizados (volátiles)
ACTIVOS = ["TSLA", "NVDA", "AMD", "SOXL", "TQQQ", "AAPL"]

# 📊 Mercado referencia
MARKET = ["SPY", "QQQ"]

RSI_SOBREVENTA = 35
RSI_SOBRECOMPRA = 70

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")


def calcular_rsi(serie, periodos=14):
    delta = serie.diff()
    gain = delta.clip(lower=0).rolling(periodos).mean()
    loss = (-delta.clip(upper=0)).rolling(periodos).mean()
    rs = gain / loss
    return round(100 - (100 / (1 + rs)).iloc[-1], 2)


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
    except:
        return None


def market_is_bullish():
    data = []
    for m in MARKET:
        d = get_data(m)
        if d:
            data.append(d)
    return all(d["change_pct"] > 0 for d in data)


def evaluate(d, market_ok):
    signals = []

    # 🚀 Momentum (clave)
    if d["change_pct"] > 1 and d["vol_ratio"] > 1.5 and market_ok:
        signals.append({
            "type": "MOMENTUM",
            "strength": "FUERTE",
            "entry": d["price"],
            "sl": round(d["price"] * 0.98, 2),
            "tp": round(d["price"] * 1.04, 2),
            "msg": "Ruptura con volumen (continuación)"
        })

    # 📉 Rebote técnico
    if d["rsi"] < 35 and d["vol_ratio"] > 1.2:
        signals.append({
            "type": "REBOTE",
            "strength": "MODERADA",
            "entry": d["price"],
            "sl": round(d["price"] * 0.97, 2),
            "tp": round(d["price"] * 1.03, 2),
            "msg": "Sobreventa + volumen (rebote probable)"
        })

    # 🔴 Evitar
    if d["rsi"] > 70:
        signals.append({
            "type": "ALERTA",
            "strength": "CUIDADO",
            "msg": "Sobrecompra - no entrar"
        })

    return signals


def format_msg(results):
    now = datetime.now(pytz.timezone("America/Bogota")).strftime("%H:%M")
    msg = [f"🚀 *ARQ PRO — {now}*"]
    
    for r in results:
        d, sigs = r["data"], r["signals"]
        if not sigs:
            continue

        msg.append(f"\n*{d['ticker']}* — ${d['price']} ({d['change_pct']}%)")

        for s in sigs:
            if s["type"] != "ALERTA":
                msg.append(
                    f"👉 {s['type']} [{s['strength']}]\n"
                    f"Entrada: ${s['entry']} | SL: ${s['sl']} | TP: ${s['tp']}\n"
                    f"{s['msg']}"
                )
            else:
                msg.append(f"⚠️ {s['msg']}")

    return "\n".join(msg)


def send(msg):
    if not TELEGRAM_TOKEN:
        print(msg)
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": msg,
        "parse_mode": "Markdown"
    })


def mercado_abierto():
    et = pytz.timezone("America/New_York")
    now = datetime.now(et)
    return now.weekday() < 5 and time(9, 30) <= now.time() <= time(16, 0)


def main():
    print("Iniciando ARQ PRO...")

    market_ok = market_is_bullish()

    results = []
    for t in ACTIVOS:
        d = get_data(t)
        if not d:
            continue

        sigs = evaluate(d, market_ok)

        # 🔥 filtro PRO: solo señales útiles
        if any(s["strength"] == "FUERTE" for s in sigs):
            results.append({"data": d, "signals": sigs})

    results.sort(key=lambda x: len(x["signals"]), reverse=True)

    msg = format_msg(results)
    send(msg)


if __name__ == "__main__":
    main()