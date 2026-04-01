"""
ARQ Stock Monitor - Ivan Caseres
Monitorea ETFs y acciones con señales de compra corto/largo plazo.
Envía alertas por Telegram cuando se detecta una oportunidad.
"""

import os
import json
import requests
import yfinance as yf
import pandas as pd
from datetime import datetime, time
import pytz
import time
import random

# ─────────────────────────────────────────────
#  CONFIGURACIÓN — edita esta sección
# ─────────────────────────────────────────────

ACTIVOS = [
    # ETFs
    "VOO",   # S&P 500
    "QQQ",   # Nasdaq 100
    "TQQQ",  # Nasdaq 3x (corto plazo)
    "SOXL",  # Semiconductores 3x (corto plazo)
    "SCHD",  # Dividendos (largo plazo)
    # Acciones individuales — agrega las que quieras
    "AAPL",
    "NVDA",
    "MSFT",
]

# Umbrales de señales
RSI_SOBREVENTA      = 35    # RSI por debajo → posible compra
RSI_SOBRECOMPRA     = 70    # RSI por encima → evitar compra
CAIDA_DIA_PCT       = -3.0  # Caída % en el día → posible rebote corto plazo
VOLUMEN_MULT        = 2.0   # Volumen X veces el promedio → momentum
GOLDEN_CROSS_DIAS   = (50, 200)  # Medias móviles para largo plazo

# Credenciales (se leen como variables de entorno / GitHub Secrets)
TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# ─────────────────────────────────────────────
#  FUNCIONES PRINCIPALES
# ─────────────────────────────────────────────

def calcular_rsi(serie: pd.Series, periodos: int = 14) -> float:
    """RSI clásico de Wilder."""
    delta = serie.diff()
    ganancia = delta.clip(lower=0).ewm(com=periodos - 1, adjust=False).mean()
    perdida  = (-delta.clip(upper=0)).ewm(com=periodos - 1, adjust=False).mean()
    rs = ganancia / perdida
    rsi = 100 - (100 / (1 + rs))
    return round(rsi.iloc[-1], 2)


def analizar(ticker: str) -> dict | None:
    """Descarga datos y calcula indicadores para un ticker."""
    try:
        # Pausa aleatoria para evitar rate limit
        time.sleep(random.uniform(2, 4))
        
        datos = yf.download(
            ticker, 
            period="1y", 
            interval="1d", 
            progress=False, 
            auto_adjust=True,
        )
        if datos.empty or len(datos) < 60:
            return None

        cierre   = datos["Close"].squeeze()
        volumen  = datos["Volume"].squeeze()

        precio_actual  = float(cierre.iloc[-1])
        precio_ayer    = float(cierre.iloc[-2])
        cambio_dia_pct = round((precio_actual - precio_ayer) / precio_ayer * 100, 2)

        rsi = calcular_rsi(cierre)

        ma50  = float(cierre.rolling(50).mean().iloc[-1])
        ma200 = float(cierre.rolling(200).mean().iloc[-1])
        golden_cross = ma50 > ma200

        vol_hoy      = float(volumen.iloc[-1])
        vol_prom_3m  = float(volumen.rolling(63).mean().iloc[-1])
        vol_ratio    = round(vol_hoy / vol_prom_3m, 2) if vol_prom_3m > 0 else 0

        return {
            "ticker":       ticker,
            "precio":       round(precio_actual, 2),
            "cambio_pct":   cambio_dia_pct,
            "rsi":          rsi,
            "ma50":         round(ma50, 2),
            "ma200":        round(ma200, 2),
            "golden_cross": golden_cross,
            "vol_ratio":    vol_ratio,
        }
    except Exception as e:
        print(f"[ERROR] {ticker}: {e}")
        return None


def evaluar_senales(d: dict) -> list[dict]:
    """Evalúa señales de compra corto y largo plazo."""
    senales = []

    # ── CORTO PLAZO ──────────────────────────
    if d["rsi"] < RSI_SOBREVENTA:
        senales.append({
            "tipo":   "CORTO",
            "fuerza": "FUERTE" if d["rsi"] < 30 else "MODERADA",
            "razon":  f"RSI en zona de sobreventa ({d['rsi']})",
            "emoji":  "🟢",
        })

    if d["cambio_pct"] <= CAIDA_DIA_PCT:
        senales.append({
            "tipo":   "CORTO",
            "fuerza": "MODERADA",
            "razon":  f"Caída de {d['cambio_pct']}% hoy — posible rebote",
            "emoji":  "📉",
        })

    if d["vol_ratio"] >= VOLUMEN_MULT and d["cambio_pct"] > 0:
        senales.append({
            "tipo":   "CORTO",
            "fuerza": "MODERADA",
            "razon":  f"Volumen {d['vol_ratio']}x el promedio con precio subiendo",
            "emoji":  "📊",
        })

    # ── LARGO PLAZO ──────────────────────────
    if d["golden_cross"] and d["rsi"] < 60:
        senales.append({
            "tipo":   "LARGO",
            "fuerza": "FUERTE",
            "razon":  f"Golden Cross activo (MA50={d['ma50']} > MA200={d['ma200']})",
            "emoji":  "⭐",
        })

    if d["precio"] > d["ma200"] and d["rsi"] < RSI_SOBREVENTA + 10:
        senales.append({
            "tipo":   "LARGO",
            "fuerza": "MODERADA",
            "razon":  f"Precio sobre MA200 con RSI saludable ({d['rsi']})",
            "emoji":  "📈",
        })

    # ── ADVERTENCIAS ─────────────────────────
    if d["rsi"] > RSI_SOBRECOMPRA:
        senales.append({
            "tipo":   "ALERTA",
            "fuerza": "CUIDADO",
            "razon":  f"RSI sobrecomprado ({d['rsi']}) — evita comprar ahora",
            "emoji":  "🔴",
        })

    return senales


def formatear_mensaje(resultados: list[dict]) -> str:
    """Construye el mensaje Telegram con todas las alertas."""
    ahora = datetime.now(pytz.timezone("America/Bogota")).strftime("%d/%m/%Y %H:%M")
    lineas = [
        f"📡 *ARQ Monitor — {ahora} COT*",
        "━━━━━━━━━━━━━━━━━━━━━━",
    ]

    hay_alertas = False
    for item in resultados:
        d, senales = item["datos"], item["senales"]
        if not senales:
            continue
        hay_alertas = True

        cambio_emoji = "🔼" if d["cambio_pct"] >= 0 else "🔽"
        lineas.append(
            f"\n*{d['ticker']}* — ${d['precio']} "
            f"{cambio_emoji} {d['cambio_pct']:+.2f}%"
        )
        for s in senales:
            lineas.append(
                f"  {s['emoji']} [{s['tipo']} • {s['fuerza']}] {s['razon']}"
            )

    if not hay_alertas:
        lineas.append("\n✅ Sin señales relevantes en este momento.")
        lineas.append("Mercado en zona neutral — espera mejor entrada.")

    lineas.append("\n━━━━━━━━━━━━━━━━━━━━━━")
    lineas.append("_No es asesoría financiera. Siempre verifica antes de operar._")
    return "\n".join(lineas)


def enviar_telegram(mensaje: str) -> bool:
    """Envía el mensaje al bot de Telegram."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("[WARN] Credenciales de Telegram no configuradas.")
        print(mensaje)
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    resp = requests.post(url, json={
        "chat_id":    TELEGRAM_CHAT_ID,
        "text":       mensaje,
        "parse_mode": "Markdown",
    }, timeout=10)

    if resp.status_code == 200:
        print("[OK] Mensaje enviado a Telegram.")
        return True
    else:
        print(f"[ERROR] Telegram: {resp.status_code} — {resp.text}")
        return False


def mercado_abierto() -> bool:
    """Verifica si el mercado de NY está abierto (lun-vie, 9:30–16:00 ET)."""
    et = pytz.timezone("America/New_York")
    ahora = datetime.now(et)
    if ahora.weekday() >= 5:  # sábado o domingo
        return False
    apertura = time(9, 30)
    cierre   = time(16, 0)
    return apertura <= ahora.time() <= cierre


# ─────────────────────────────────────────────
#  EJECUCIÓN PRINCIPAL
# ─────────────────────────────────────────────

def main():
    print(f"[INFO] Iniciando análisis — {datetime.now()}")

    if not mercado_abierto():
        print("[INFO] Mercado cerrado. El análisis usa el último cierre.")

    resultados = []
    for ticker in ACTIVOS:
        print(f"  → Analizando {ticker}...")
        datos = analizar(ticker)
        if datos:
            senales = evaluar_senales(datos)
            resultados.append({"datos": datos, "senales": senales})

    # Solo envía si hay al menos una señal
    tiene_senales = any(r["senales"] for r in resultados)

    if tiene_senales:
        mensaje = formatear_mensaje(resultados)
        enviar_telegram(mensaje)
    else:
        print("[INFO] Sin señales relevantes — no se envía mensaje.")
        # Descomenta la siguiente línea si quieres recibir reporte aunque no haya señales:
        # enviar_telegram(formatear_mensaje(resultados))


if __name__ == "__main__":
    main()
