import yfinance as yf
import pandas as pd
import streamlit as st

st.title("Day Trading Assistant")
st.write("The Streamlit page is rendering.")
# Download Nifty 50 data
data = yf.download(
    "^NSEI",
    period="3mo",
    interval="1d",
    auto_adjust=True,
    progress=False
)

if data.empty:
    print("No market data received.")
    raise SystemExit

# Handle different yfinance data formats
close = data["Close"]

if isinstance(close, pd.DataFrame):
    close = close.iloc[:, 0]

# Calculate indicators
df = pd.DataFrame({"Close": close})

df["SMA_5"] = df["Close"].rolling(5).mean()
df["SMA_20"] = df["Close"].rolling(20).mean()

# Calculate RSI
delta = df["Close"].diff()

gain = delta.clip(lower=0)
loss = -delta.clip(upper=0)

avg_gain = gain.rolling(14).mean()
avg_loss = loss.rolling(14).mean()

rs = avg_gain / avg_loss

df["RSI"] = 100 - (100 / (1 + rs))

# Calculate daily percentage change
df["Daily_Return"] = df["Close"].pct_change() * 100

# Generate a basic trend signal
df["Signal"] = "HOLD"

df.loc[
    (df["SMA_5"] > df["SMA_20"]) &
    (df["RSI"] > 50),
    "Signal"
] = "POTENTIAL BUY"

df.loc[
    (df["SMA_5"] < df["SMA_20"]) &
    (df["RSI"] < 50),
    "Signal"
] = "POTENTIAL SELL"

# Display results
print("\nNIFTY 50 MARKET ANALYSIS")
print(df.tail(10).round(2).to_string())

# Save results
df.to_csv("nifty50_analysis.csv")

print("\nAnalysis saved to nifty50_analysis.csv")