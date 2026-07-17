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
# 📥 DATA (MEJORADA)
# =========================
def get_data(ticker):
    try:
        # Reduzco la espera para que no se acumule si son muchas peticiones
        time_module.sleep(random.uniform(0.5, 1.0))

        # Bajo 3 días en lugar de 5 para que sea más rápido
        df = yf.download(ticker, period="3d", interval="5m", progress=False)

        if df.empty or len(df) < 30:
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

        # ✅ NUEVO: Calculo la media de 20 periodos (EMA) y la de 50 para ver tendencia
        ema20 = close.ewm(span=20).mean().iloc[-1]
        ema50 = close.ewm(span=50).mean().iloc[-1]

        return {
            "ticker": ticker,
            "price": round(price, 2),
            "change_pct": round(change_pct, 2),
            "rsi": round(rsi, 2),
            "vol_ratio": round(vol_ratio, 2),
            "ema20": round(ema20, 2),
            "ema50": round(ema50, 2),
            "close_above_ema20": price > ema20,
            "close_above_ema50": price > ema50
        }

    except Exception as e:
        print(f"[ERROR] {ticker}: {e}")
        return None

# =========================
# 📊 MERCADO (MEJORADO)
# =========================
def market_bias():
    data = []
    for m in MARKET:
        d = get_data(m)
        if d:
            data.append(d)

    if not data:
        return "neutral"

    # Si SPY y QQQ suben y están por encima de su EMA50 -> Bull fuerte
    avg_change = sum(d["change_pct"] for d in data) / len(data)
    
    if avg_change > 0.2 and all(d["close_above_ema50"] for d in data):
        return "bull"
    elif avg_change < -0.2:
        return "bear"
    else:
        return "neutral"

# =========================
# 🚨 SEÑALES (MEJORADA)
# =========================
def evaluate(d, market_state):
    signals = []

    # ❌ Si el mercado está bajista, NO damos señales de compra (solo se puede hacer trading en largo aquí)
    if market_state == "bear":
        return signals

    # 📈 SEÑAL 1: MOMENTUM FUERTE + VOLUMEN + TREND
    # Condiciones más estrictas para evitar ruido:
    # - Subida > 0.6% (antes era 0.4%)
    # - Volumen 1.5x el promedio (antes 1.2x)
    # - Precio > EMA20 (tendencia alcista a corto)
    if (d["change_pct"] > 0.6 and 
        d["vol_ratio"] > 1.5 and 
        d["close_above_ema20"]):
        
        # ✅ NUEVO: Si además el RSI está entre 40 y 70, es más saludable
        if 40 < d["rsi"] < 70:
            action = "✅ COMPRA CONFIRMADA"
        else:
            action = "⚠️ COMPRA (RSI extremo, precaución)"

        # ✅ SL y TP más amplios para aguantar la volatilidad de ETFs apalancados
        signals.append({
            "type": "MOMENTUM",
            "action": action,
            "entry": d["price"],
            "sl": round(d["price"] * 0.97, 2),    # -3% de pérdida
            "tp": round(d["price"] * 1.04, 2)     # +4% de ganancia
        })

    # 📉 SEÑAL 2: REBOTE EN SOBREVENTA
    # Condiciones: RSI < 35 (antes 40) Y caída > -1% Y precio cerca de la EMA20
    if (d["rsi"] < 35 and 
        d["change_pct"] < -1.0 and 
        d["price"] > d["ema20"] * 0.99):  # Que no haya perforado la media violentamente
        
        signals.append({
            "type": "REBOTE",
            "action": "🔄 REBOTE TÉCNICO",
            "entry": d["price"],
            "sl": round(d["price"] * 0.975, 2),   # -2.5%
            "tp": round(d["price"] * 1.025, 2)    # +2.5%
        })

    return signals

# =========================
# 📝 MENSAJE (MEJORADO)
# =========================
def format_msg(results, market_state):
    now = datetime.now(pytz.timezone("America/Bogota")).strftime("%H:%M")
    fecha = datetime.now(pytz.timezone("America/Bogota")).strftime("%d/%m")

    msg = [f"🚀 *ARQ PRO — {fecha} {now}hs*"]
    msg.append(f"📊 Mercado: {market_state.upper()}\n")

    # ✅ Ahora recorre TODAS las señales, no solo 2
    for r in results:
        d = r["data"]
        s = r["signals"][0]  # Tomo la primera señal (si hay múltiples, se podrían expandir)

        msg.append(
            f"*{d['ticker']}* — ${d['price']} ({d['change_pct']:.2f}%)\n"
            f"{s['action']}\n"
            f"📈 RSI: {d['rsi']} | Vol: {d['vol_ratio']:.1f}x\n"
            f"🔴 SL: ${s['sl']} | 🟢 TP: ${s['tp']}\n"
            f"---"
        )

    msg.append("\n⚠️ Gestión: Máx 2% del capital por operación")

    return "\n".join(msg)

# =========================
# 📲 TELEGRAM (MEJORADO)
# =========================
def send(msg):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("📨 MENSAJE (simulado):")
        print(msg)
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": msg,
            "parse_mode": "Markdown"
        }, timeout=10)
    except Exception as e:
        print(f"Error enviando Telegram: {e}")

# =========================
# ⏰ HORARIO (MEJORADO)
# =========================
def mercado_abierto():
    et = pytz.timezone("America/New_York")
    now = datetime.now(et)
    # Cubrimos toda la sesión: desde las 9:45 (evitamos los primeros 15 min de locura) hasta las 15:45
    return now.weekday() < 5 and time(9, 45) <= now.time() <= time(15, 45)

# =========================
# 🚀 MAIN (MEJORADO)
# =========================
def main():
    print("🚀 ARQ PRO - Ejecución Horaria")

    if not mercado_abierto():
        # ✅ AHORA NO ENVÍA NADA POR TELEGRAM, solo lo imprime en consola (para no spamear)
        print("⏸ Fuera de horario de mercado. No se envía mensaje.")
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

    # ✅ Si no hay señales, NO ENVÍA NADA a Telegram (cero spam)
    if not results:
        print("✅ Escaneo completado. Sin señales válidas en esta hora.")
        return

    # Si hay señales, las envía
    msg = format_msg(results, market_state)
    send(msg)
    print("✅ Señales enviadas a Telegram.")

if __name__ == "__main__":
    main()