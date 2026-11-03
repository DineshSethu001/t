import yfinance as yf
import pandas as pd

# Download recent 5-minute Nifty 50 data
data = yf.download(
    "^NSEI",
    period="5d",
    interval="5m",
    auto_adjust=True,
    progress=False
)

if data.empty:
    raise SystemExit(
        "No intraday data received. "
        "Check your internet connection."
    )

# Handle different yfinance data formats
if isinstance(data.columns, pd.MultiIndex):
    data.columns = data.columns.get_level_values(0)

# Keep only the columns we need
data = data[["Open", "High", "Low", "Close", "Volume"]]

# Display the latest candles
print("\nNIFTY 50 - 5 MINUTE DATA")
print(data.tail(10).round(2).to_string())

# Save data
data.to_csv("intraday_data.csv")

print("\nIntraday data saved successfully!")
print(f"Total candles: {len(data)}")