import yfinance as yf
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

st.set_page_config(page_title="Day Trading Assistant", layout="wide")

st.title("📈 Day Trading Assistant")
st.caption("Educational market analysis. Signals are not guaranteed buy/sell recommendations.")

# Download Nifty 50 data
@st.cache_data(ttl=300)
def get_market_data():
    return yf.download(
        "^NSEI",
        period="3mo",
        interval="1d",
        auto_adjust=True,
        progress=False,
    )

with st.spinner("Loading Nifty 50 data..."):
    data = get_market_data()

if data.empty:
    st.error("No market data received. Yahoo Finance may be temporarily limiting requests. Try again later.")
    st.stop()

# Handle different yfinance data formats
close = data["Close"]
if isinstance(close, pd.DataFrame):
    close = close.iloc[:, 0]

# Calculate indicators
df = pd.DataFrame({"Close": close})
df["SMA_5"] = df["Close"].rolling(5).mean()
df["SMA_20"] = df["Close"].rolling(20).mean()

delta = df["Close"].diff()
gain = delta.clip(lower=0)
loss = -delta.clip(upper=0)

avg_gain = gain.rolling(14).mean()
avg_loss = loss.rolling(14).mean().replace(0, float("nan"))
rs = avg_gain / avg_loss
df["RSI"] = 100 - (100 / (1 + rs))

df["Daily_Return"] = df["Close"].pct_change() * 100

# Generate a basic trend signal
df["Signal"] = "HOLD"
df.loc[
    (df["SMA_5"] > df["SMA_20"]) & (df["RSI"] > 50),
    "Signal",
] = "POTENTIAL BUY"

df.loc[
    (df["SMA_5"] < df["SMA_20"]) & (df["RSI"] < 50),
    "Signal",
] = "POTENTIAL SELL"

# Show latest values
latest = df.iloc[-1]
c1, c2, c3 = st.columns(3)
c1.metric("Latest close", f"{latest['Close']:,.2f}")
c2.metric("RSI", f"{latest['RSI']:.2f}" if pd.notna(latest["RSI"]) else "—")
c3.metric("Trend signal", latest["Signal"])

# Price and moving-average chart
st.subheader("Nifty 50 — price and moving averages")
fig = go.Figure()
fig.add_trace(go.Scatter(x=df.index, y=df["Close"], name="Close"))
fig.add_trace(go.Scatter(x=df.index, y=df["SMA_5"], name="SMA 5"))
fig.add_trace(go.Scatter(x=df.index, y=df["SMA_20"], name="SMA 20"))
fig.update_layout(height=450, xaxis_title="Date", yaxis_title="Price")
st.plotly_chart(fig, use_container_width=True)

# RSI chart
st.subheader("RSI (14)")
rsi_fig = go.Figure()
rsi_fig.add_trace(go.Scatter(x=df.index, y=df["RSI"], name="RSI"))
rsi_fig.add_hline(y=70, line_dash="dash")
rsi_fig.add_hline(y=30, line_dash="dash")
rsi_fig.update_layout(height=250, yaxis_range=[0, 100])
st.plotly_chart(rsi_fig, use_container_width=True)

# Data table and CSV download
st.subheader("Recent market analysis")
st.dataframe(df.tail(10).round(2), use_container_width=True)

st.download_button(
    "Download analysis CSV",
    data=df.to_csv().encode("utf-8"),
    file_name="nifty50_analysis.csv",
    mime="text/csv",
)