
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import logging

def backtest(ticker, start_date="2024-01-01", end_date="2024-12-31"):
    df = yf.download(ticker, start=start_date, end=end_date, interval="1d")
    capital = 10000
    posicion = 0
    operaciones = []

    for i in range(50, len(df)):
        # Simular RSI y EMA
        close = df["Close"]
        rsi = calcular_rsi(close).iloc[i]
        ema20 = close.ewm(span=20).mean().iloc[i]
        price = close.iloc[i]

        # Señal de compra (simplificada)
        if rsi < 35 and price > ema20 * 0.99 and posicion == 0:
            posicion = capital / price
            capital = 0
            operaciones.append({"fecha": df.index[i], "tipo": "COMPRA", "precio": price})
        
        # Señal de venta (TP 5% o SL 3%)
        if posicion > 0:
            if price >= operaciones[-1]["precio"] * 1.05 or price <= operaciones[-1]["precio"] * 0.97:
                capital = posicion * price
                posicion = 0
                operaciones.append({"fecha": df.index[i], "tipo": "VENTA", "precio": price})

    print(f"Backtest {ticker}: Capital final ${capital:.2f}")
    return operaciones

if __name__ == "__main__":
    backtest("QQQ")