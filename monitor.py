import os
import time as time_module
import random
import requests
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, time, timedelta
import pytz
import json
import logging
import matplotlib.pyplot as plt
import mplfinance as mpf
from io import BytesIO
import pathlib

# =========================
# ⚙️ CONFIGURACIÓN
# =========================
ACTIVOS = ["QQQ", "TQQQ", "SOXL", "SPY"]
MARKET = ["SPY", "QQQ"]

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

HISTORIAL_FILE = "historial.json"
LOG_FILE = "arq_monitor.log"

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

# =========================
# 🗂️ HISTORIAL (Anti-spam)
# =========================
def cargar_historial():
    if os.path.exists(HISTORIAL_FILE):
        with open(HISTORIAL_FILE, "r") as f:
            return json.load(f)
    return {}

def guardar_historial(historial):
    with open(HISTORIAL_FILE, "w") as f:
        json.dump(historial, f, indent=2)

def señal_ya_enviada(ticker, historial):
    hoy = datetime.now().date().isoformat()
    if ticker not in historial:
        return False
    # Si la última señal fue hoy, no enviamos de nuevo
    if historial[ticker].get("fecha") == hoy:
        return True
    return False

def registrar_envio(ticker, price, historial):
    historial[ticker] = {
        "fecha": datetime.now().date().isoformat(),
        "precio": price,
        "hora": datetime.now().strftime("%H:%M")
    }
    guardar_historial(historial)

# =========================
# 📊 INDICADORES MEJORADOS
# =========================
def calcular_rsi(serie, periodos=14):
    delta = serie.diff()
    gain = delta.clip(lower=0).rolling(periodos).mean()
    loss = (-delta.clip(upper=0)).rolling(periodos).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calcular_atr(df, periodos=14):
    high = df["High"]
    low = df["Low"]
    close = df["Close"]
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(periodos).mean().iloc[-1]

# =========================
# 📥 DATA (Multi-timeframe)
# =========================
def get_data(ticker):
    try:
        time_module.sleep(random.uniform(0.5, 1.0))
        # Datos de 5m para señales intradía
        df = yf.download(ticker, period="3d", interval="5m", progress=False)
        if df.empty or len(df) < 30:
            return None

        close = df["Close"].squeeze()
        volume = df["Volume"].squeeze()

        price = float(close.iloc[-1])
        prev = float(close.iloc[-2])
        change_pct = (price - prev) / prev * 100

        rsi = calcular_rsi(close).iloc[-1]
        atr = calcular_atr(df)

        vol_now = float(volume.iloc[-1])
        vol_avg = float(volume.rolling(20).mean().iloc[-1])
        vol_ratio = vol_now / vol_avg if vol_avg > 0 else 0

        ema20 = close.ewm(span=20).mean().iloc[-1]
        ema50 = close.ewm(span=50).mean().iloc[-1]

        # 🔍 Análisis diario (EMA200)
        df_daily = yf.download(ticker, period="6mo", interval="1d", progress=False)
        ema200 = None
        if not df_daily.empty and len(df_daily) > 200:
            ema200 = df_daily["Close"].ewm(span=200).mean().iloc[-1]

        return {
            "ticker": ticker,
            "price": round(price, 2),
            "change_pct": round(change_pct, 2),
            "rsi": round(rsi, 2),
            "vol_ratio": round(vol_ratio, 2),
            "ema20": round(ema20, 2),
            "ema50": round(ema50, 2),
            "ema200": round(ema200, 2) if ema200 else None,
            "atr": round(atr, 2),
            "close_above_ema20": price > ema20,
            "close_above_ema50": price > ema50,
            "close_above_ema200": price > ema200 if ema200 else False,
            "df": df  # Guardamos el df para el gráfico
        }

    except Exception as e:
        logging.error(f"Error en get_data({ticker}): {e}")
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

    avg_change = sum(d["change_pct"] for d in data) / len(data)
    if avg_change > 0.2 and all(d["close_above_ema50"] for d in data):
        return "bull"
    elif avg_change < -0.2:
        return "bear"
    else:
        return "neutral"

# =========================
# 🚨 SEÑALES (Con ATR y multi-timeframe)
# =========================
def evaluate(d, market_state):
    signals = []

    # ❌ Si el mercado está bajista, no damos señales de compra
    if market_state == "bear":
        return signals

    # ❌ Si el precio está por debajo de la EMA200 diaria, no compramos (tendencia bajista general)
    if not d["close_above_ema200"]:
        return signals

    # 📈 SEÑAL 1: MOMENTUM
    if (d["change_pct"] > 0.6 and 
        d["vol_ratio"] > 1.5 and 
        d["close_above_ema20"] and
        40 < d["rsi"] < 70):
        
        # SL y TP basados en ATR (1.5x ATR para SL, 2x ATR para TP)
        sl = round(d["price"] - (d["atr"] * 1.5), 2)
        tp = round(d["price"] + (d["atr"] * 2.5), 2)
        
        signals.append({
            "type": "MOMENTUM",
            "action": "✅ COMPRA CONFIRMADA (Momentum)",
            "entry": d["price"],
            "sl": sl,
            "tp": tp
        })

    # 📉 SEÑAL 2: REBOTE
    if (d["rsi"] < 35 and 
        d["change_pct"] < -1.0 and 
        d["price"] > d["ema20"] * 0.99):
        
        sl = round(d["price"] - (d["atr"] * 1.2), 2)
        tp = round(d["price"] + (d["atr"] * 2.0), 2)
        
        signals.append({
            "type": "REBOTE",
            "action": "🔄 REBOTE TÉCNICO",
            "entry": d["price"],
            "sl": sl,
            "tp": tp
        })

    return signals

# =========================
# 📈 GENERADOR DE GRÁFICOS (Nuevo)
# =========================
def generar_grafico(d):
    try:
        df = d["df"].copy()
        ticker = d["ticker"]
        
        # Asegurar que el índice es DatetimeIndex
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)
        
        # Agregar medias móviles
        df["EMA20"] = df["Close"].ewm(span=20).mean()
        df["EMA50"] = df["Close"].ewm(span=50).mean()
        
        # Crear subplot para RSI
        apds = [
            mpf.make_addplot(df["EMA20"], color="blue", width=0.7),
            mpf.make_addplot(df["EMA50"], color="orange", width=0.7),
        ]
        
        # Configurar estilo
        mc = mpf.make_marketcolors(up="green", down="red", edge="inherit", wick="inherit")
        s = mpf.make_mpf_style(marketcolors=mc, gridstyle="dotted", y_on_right=False)
        
        # Guardar en buffer de memoria
        buffer = BytesIO()
        fig, axes = mpf.plot(
            df,
            type="candle",
            style=s,
            addplot=apds,
            volume=True,
            title=f"{ticker} - Señal de Trading",
            ylabel="Precio",
            ylabel_lower="Volumen",
            figsize=(10, 8),
            returnfig=True
        )
        
        # Guardar en buffer
        fig.savefig(buffer, format="png", dpi=100, bbox_inches="tight")
        buffer.seek(0)
        plt.close(fig)
        
        return buffer
    except Exception as e:
        logging.error(f"Error generando gráfico para {ticker}: {e}")
        return None

# =========================
# 📝 MENSAJE (Mejorado)
# =========================
def format_msg(results, market_state):
    now = datetime.now(pytz.timezone("America/Bogota")).strftime("%H:%M")
    fecha = datetime.now(pytz.timezone("America/Bogota")).strftime("%d/%m")

    emoji_market = "🐂" if market_state == "bull" else "🐻" if market_state == "bear" else "⚪"
    
    msg = [f"🚀 *ARQ PRO — {fecha} {now}hs*"]
    msg.append(f"📊 Mercado: {emoji_market} {market_state.upper()}\n")

    for r in results:
        d = r["data"]
        s = r["signals"][0]
        
        msg.append(
            f"*{d['ticker']}* — ${d['price']} ({d['change_pct']:.2f}%)\n"
            f"{s['action']}\n"
            f"📈 RSI: {d['rsi']} | Vol: {d['vol_ratio']:.1f}x\n"
            f"🔴 SL: ${s['sl']} | 🟢 TP: ${s['tp']}\n"
            f"📉 ATR: {d['atr']} | EMA200: ${d['ema200']}\n"
            f"---"
        )

    msg.append("\n⚠️ Gestión: Máx 2% del capital por operación")
    msg.append("📊 Gráfico adjunto 👇")
    
    return "\n".join(msg)

# =========================
# 📲 TELEGRAM (Con envío de foto)
# =========================
def send_text(msg):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logging.info("MENSAJE (simulado):\n" + msg)
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": msg,
            "parse_mode": "Markdown"
        }, timeout=10)
        logging.info("Mensaje de texto enviado")
    except Exception as e:
        logging.error(f"Error enviando texto: {e}")

def send_photo(buffer, caption=""):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logging.info("FOTO (simulada): " + caption)
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    try:
        files = {"photo": ("chart.png", buffer, "image/png")}
        data = {"chat_id": TELEGRAM_CHAT_ID, "caption": caption, "parse_mode": "Markdown"}
        requests.post(url, files=files, data=data, timeout=15)
        logging.info("Gráfico enviado")
    except Exception as e:
        logging.error(f"Error enviando foto: {e}")

# =========================
# 🌅 MENSAJE DE INICIO (Buenos días)
# =========================
def enviar_mensaje_inicio():
    fecha = datetime.now(pytz.timezone("America/Bogota")).strftime("%d/%m/%Y")
    msg = (
        f"🌅 *Buenos días, Bot activo!*\n"
        f"📅 {fecha}\n"
        f"📊 Monitoreando: {', '.join(ACTIVOS)}\n"
        f"⏰ Próximas alertas cada hora (en horario de mercado)"
    )
    send_text(msg)

# =========================
# ⏰ HORARIO
# =========================
def mercado_abierto():
    et = pytz.timezone("America/New_York")
    now = datetime.now(et)
    return now.weekday() < 5 and time(9, 45) <= now.time() <= time(15, 45)

# =========================
# 🚀 MAIN
# =========================
def main():
    logging.info("🚀 ARQ PRO - Ejecución Horaria")
    
    # Si es la primera ejecución del día (entre 9:45 y 10:00), enviamos mensaje de inicio
    hora_actual = datetime.now(pytz.timezone("America/New_York")).time()
    if time(9, 45) <= hora_actual <= time(10, 0):
        enviar_mensaje_inicio()

    if not mercado_abierto():
        logging.info("⏸ Fuera de horario de mercado.")
        return

    market_state = market_bias()
    historial = cargar_historial()
    results = []

    for t in ACTIVOS:
        d = get_data(t)
        if not d:
            continue

        # 🔍 Anti-spam: si ya se envió señal hoy, saltamos
        if señal_ya_enviada(t, historial):
            logging.info(f"⏭️ Señal para {t} ya enviada hoy. Saltando.")
            continue

        sigs = evaluate(d, market_state)
        if sigs:
            results.append({
                "data": d,
                "signals": sigs
            })
            # Registramos para no repetir
            registrar_envio(t, d["price"], historial)

    if not results:
        logging.info("✅ Escaneo completado. Sin señales nuevas en esta hora.")
        return

    # Enviar mensaje de texto
    msg = format_msg(results, market_state)
    send_text(msg)

    # Enviar gráfico del primer resultado (o de todos, pero limitamos a 1 para no saturar)
    if results:
        buffer = generar_grafico(results[0]["data"])
        if buffer:
            send_photo(buffer, caption=f"📊 {results[0]['data']['ticker']} - Señal detallada")
        else:
            logging.warning("No se pudo generar el gráfico")

    logging.info("✅ Señales enviadas a Telegram.")

if __name__ == "__main__":
    main()