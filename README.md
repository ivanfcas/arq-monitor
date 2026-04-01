# 📡 ARQ Stock Monitor

Monitorea ETFs y acciones en tiempo real y recibe alertas en Telegram cuando hay señales de compra para operar en ARQ.

---

## ¿Qué detecta?

| Señal | Tipo | Indicador |
|-------|------|-----------|
| RSI < 35 (sobreventa) | Corto plazo | RSI 14 días |
| Caída > 3% en el día | Corto plazo | Precio diario |
| Volumen 2x el promedio + precio subiendo | Corto plazo | Volumen 63 días |
| Golden Cross (MA50 > MA200) + RSI < 60 | Largo plazo | Medias móviles |
| Precio > MA200 + RSI saludable | Largo plazo | Tendencia |
| RSI > 70 (sobrecompra) | ⚠️ Alerta | Evita comprar |

---

## Configuración paso a paso

### 1. Crear el bot de Telegram

1. Abre Telegram y busca **@BotFather**
2. Escribe `/newbot` y sigue las instrucciones
3. Copia el **token** que te da (formato: `123456789:ABCdef...`)
4. Busca **@userinfobot** en Telegram, escríbele cualquier cosa
5. Copia tu **Chat ID** (número que te responde)

### 2. Crear el repositorio en GitHub

```bash
# En tu máquina local
mkdir arq-monitor
cd arq-monitor
git init
# Copia aquí los archivos: monitor.py, requirements.txt, .github/workflows/stock_monitor.yml
git add .
git commit -m "Primer commit"
git remote add origin https://github.com/TU_USUARIO/arq-monitor.git
git push -u origin main
```

### 3. Agregar los secretos en GitHub

1. Ve a tu repositorio en GitHub
2. **Settings → Secrets and variables → Actions → New repository secret**
3. Agrega estos dos secretos:

| Nombre | Valor |
|--------|-------|
| `TELEGRAM_TOKEN` | El token de tu bot |
| `TELEGRAM_CHAT_ID` | Tu Chat ID numérico |

### 4. Activar GitHub Actions

1. Ve a la pestaña **Actions** en tu repositorio
2. Acepta habilitar los workflows
3. Puedes correrlo manualmente: **Actions → ARQ Stock Monitor → Run workflow**

---

## Personalizar activos

Edita la lista `ACTIVOS` en `monitor.py`:

```python
ACTIVOS = [
    "VOO",    # S&P 500
    "QQQ",    # Nasdaq 100
    "TQQQ",   # Nasdaq 3x corto plazo
    "NVDA",   # Nvidia
    # Agrega lo que quieras...
]
```

---

## Ejemplo de alerta en Telegram

```
📡 ARQ Monitor — 01/04/2026 10:30 COT
━━━━━━━━━━━━━━━━━━━━━━

*TQQQ* — $62.15 🔽 -3.8%
  🟢 [CORTO • FUERTE] RSI en zona de sobreventa (28.4)
  📉 [CORTO • MODERADA] Caída de -3.8% hoy — posible rebote

*VOO* — $498.20 🔼 +0.3%
  ⭐ [LARGO • FUERTE] Golden Cross activo (MA50=495 > MA200=471)

━━━━━━━━━━━━━━━━━━━━━━
No es asesoría financiera. Siempre verifica antes de operar.
```

---

## Costos

| Componente | Costo |
|------------|-------|
| GitHub Actions | **Gratis** (2,000 min/mes) |
| Yahoo Finance (yfinance) | **Gratis** |
| Telegram Bot | **Gratis** |
| **Total** | **$0** |

---

> ⚠️ **Disclaimer:** Las señales son indicadores técnicos, no garantía de ganancia.
> Siempre analiza antes de operar. No es asesoría financiera.
