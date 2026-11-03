
import yfinance as yf
import pandas as pd

# 1. Download historical Nifty 50 data
data = yf.download(
    "^NSEI",
    period="2y",
    interval="1d",
    auto_adjust=True,
    progress=False
)

if data.empty:
    raise SystemExit("No market data received.")

close = data["Close"]

if isinstance(close, pd.DataFrame):
    close = close.iloc[:, 0]

df = pd.DataFrame({"Close": close})

# 2. Calculate indicators
df["SMA_5"] = df["Close"].rolling(5).mean()
df["SMA_20"] = df["Close"].rolling(20).mean()

delta = df["Close"].diff()
gain = delta.clip(lower=0)
loss = -delta.clip(upper=0)

avg_gain = gain.rolling(14).mean()
avg_loss = loss.rolling(14).mean()

rs = avg_gain / avg_loss
df["RSI"] = 100 - (100 / (1 + rs))

# 3. Generate trading signals
buy = (
    (df["SMA_5"] > df["SMA_20"]) &
    (df["RSI"] > 50)
)

sell = (
    (df["SMA_5"] < df["SMA_20"]) &
    (df["RSI"] < 50)
)

df["Signal"] = 0
df.loc[buy, "Signal"] = 1
df.loc[sell, "Signal"] = 0

# 4. Apply signals on the next trading day
df["Position"] = df["Signal"].shift(1).fillna(0)

df["Market_Return"] = df["Close"].pct_change()

# 5. Calculate transaction costs
cost_rate = 0.001

df["Trade_Cost"] = (
    df["Position"].diff().abs().fillna(0)
    * cost_rate
)

# Returns before transaction costs
df["Gross_Return"] = (
    df["Position"] * df["Market_Return"]
)

# Returns after transaction costs
df["Strategy_Return"] = (
    df["Gross_Return"] - df["Trade_Cost"]
)
# 6. Calculate cumulative returns
df["Strategy_Equity"] = (
    1 + df["Strategy_Return"]
).cumprod()

df["Buy_Hold_Equity"] = (
    1 + df["Market_Return"].fillna(0)
).cumprod()

# 7. Calculate maximum drawdown
df["Peak"] = df["Strategy_Equity"].cummax()

df["Drawdown"] = (
    df["Strategy_Equity"] / df["Peak"] - 1
)

# 8. Performance metrics
strategy_return = df["Strategy_Equity"].iloc[-1] - 1
buy_hold_return = df["Buy_Hold_Equity"].iloc[-1] - 1

max_drawdown = df["Drawdown"].min()

total_trades = int(
    df["Position"].diff().abs().fillna(0).sum()
)

days_in_market = int(df["Position"].sum())
gross_return = (
    (1 + df["Gross_Return"]).prod() - 1
)

print(f"Gross return: {gross_return:.2%}")
print(f"Net return: {strategy_return:.2%}")
# 9. Display results
print("\nBACKTEST PERFORMANCE")

print(
    f"Test period: {df.index.min().date()} "
    f"to {df.index.max().date()}"
)

print(f"Strategy return: {strategy_return:.2%}")
print(f"Buy-and-hold return: {buy_hold_return:.2%}")
print(f"Maximum drawdown: {max_drawdown:.2%}")
print(f"Position changes: {total_trades}")
print(f"Days in market: {days_in_market}")

# 10. Save results
df.to_csv("backtest_results.csv")

print("\nResults saved to backtest_results.csv")
