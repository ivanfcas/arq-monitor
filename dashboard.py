import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(page_title="ARQ Dashboard", layout="wide")
st.title("🚀 ARQ Monitor - Panel en Vivo")

tickers = ["QQQ", "TQQQ", "SOXL", "SPY"]
cols = st.columns(len(tickers))

for i, t in enumerate(tickers):
    with cols[i]:
        df = yf.download(t, period="1d", interval="5m", progress=False)
        price = df["Close"].iloc[-1]
        change = ((price - df["Close"].iloc[-2]) / df["Close"].iloc[-2]) * 100
        st.metric(t, f"${price:.2f}", f"{change:.2f}%")
        
        fig = go.Figure(data=[go.Candlestick(x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"])])
        fig.update_layout(height=300)
        st.plotly_chart(fig, use_container_width=True)