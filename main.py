import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from streamlit_autorefresh import st_autorefresh


# -----------------------------
# Page setup
# -----------------------------
st.set_page_config(
    page_title="Day Trading Assistant",
    page_icon="📈",
    layout="wide",
)

st.title("📈 Day Trading Assistant")
st.caption(
    "Educational market-data dashboard. Signals and backtests are not "
    "financial advice or guarantees of future performance."
)

# Refresh the page every 60 seconds.
# Cached market data may remain unchanged until its cache expires.
st_autorefresh(interval=60_000, key="dashboard_refresh")


# -----------------------------
# Market selection
# -----------------------------
MARKETS = {
    "Nifty 50": "^NSEI",
    "Nifty Bank": "^NSEBANK",
    "Reliance": "RELIANCE.NS",
    "TCS": "TCS.NS",
    "Infosys": "INFY.NS",
    "HDFC Bank": "HDFCBANK.NS",
    "ICICI Bank": "ICICIBANK.NS",
    "SBI": "SBIN.NS",
    "ITC": "ITC.NS",
    "Wipro": "WIPRO.NS",
    "Tata Motors": "TATAMOTORS.NS",
    "Larsen & Toubro": "LT.NS",
}

with st.sidebar:
    st.header("Chart settings")

    market_name = st.selectbox(
        "Select market or stock",
        list(MARKETS.keys()),
    )

    custom_ticker = st.text_input(
        "Or enter a Yahoo Finance ticker",
        placeholder="Example: INFY.NS",
    ).strip().upper()

    ticker = custom_ticker if custom_ticker else MARKETS[market_name]

    interval = st.selectbox(
        "Candle interval",
        ["5m", "10m", "15m", "30m", "1h", "1d"],
        index=0,
    )

    # Yahoo Finance intraday history is limited.
    if interval in ["5m", "10m", "15m", "30m"]:
        period_options = ["1d", "5d", "1mo"]
    elif interval == "1h":
        period_options = ["5d", "1mo", "3mo", "6mo", "1y"]
    else:
        period_options = ["1mo", "3mo", "6mo", "1y", "2y", "5y"]

    period = st.selectbox(
        "Time period",
        period_options,
        index=min(1, len(period_options) - 1),
    )

    st.caption(
        "Intraday history availability depends on Yahoo Finance and the ticker."
    )


# -----------------------------
# Download and prepare data
# -----------------------------
@st.cache_data(ttl=300, show_spinner=False)
def get_market_data(symbol: str, selected_period: str, selected_interval: str):
    """
    Download market data from Yahoo Finance.

    For 10-minute candles, download 5-minute data and resample it,
    since Yahoo Finance may not provide 10-minute candles directly.
    """
    download_interval = "5m" if selected_interval == "10m" else selected_interval

    data = yf.download(
        tickers=symbol,
        period=selected_period,
        interval=download_interval,
        auto_adjust=True,
        progress=False,
        threads=False,
    )

    if data is None or data.empty:
        return pd.DataFrame()

    # Handle yfinance's possible MultiIndex columns.
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    data = data.copy()
    data = data.loc[:, ~data.columns.duplicated()]
    data = data.dropna(subset=["Open", "High", "Low", "Close"])

    # Convert 5-minute candles to 10-minute candles.
    if selected_interval == "10m":
        data = data.resample("10min").agg(
            {
                "Open": "first",
                "High": "max",
                "Low": "min",
                "Close": "last",
                "Volume": "sum",
            }
        )
        data = data.dropna(subset=["Open", "High", "Low", "Close"])

    # Indicators
    data["SMA 5"] = data["Close"].rolling(5).mean()
    data["SMA 20"] = data["Close"].rolling(20).mean()

    delta = data["Close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()

    rs = avg_gain / avg_loss.replace(0, pd.NA)
    data["RSI"] = 100 - (100 / (1 + rs))

    data["Daily Return %"] = data["Close"].pct_change() * 100

    return data


with st.spinner(f"Loading {ticker} market data..."):
    try:
        data = get_market_data(ticker, period, interval)
    except Exception as error:
        st.error(f"Could not download market data: {error}")
        data = pd.DataFrame()


if data.empty:
    st.warning(
        "No data was returned for this ticker, interval, and period. "
        "Try a shorter period, another ticker, or a different interval."
    )
    st.stop()


# -----------------------------
# Key metrics
# -----------------------------
latest_close = float(data["Close"].iloc[-1])
previous_close = (
    float(data["Close"].iloc[-2]) if len(data) > 1 else latest_close
)
change_pct = (
    ((latest_close - previous_close) / previous_close) * 100
    if previous_close
    else 0
)

latest_rsi = data["RSI"].dropna()
rsi_value = float(latest_rsi.iloc[-1]) if not latest_rsi.empty else None

col1, col2, col3, col4 = st.columns(4)

col1.metric("Latest close", f"{latest_close:,.2f}")
col2.metric("Change vs. previous candle", f"{change_pct:.2f}%")

if rsi_value is not None:
    col3.metric("RSI (14)", f"{rsi_value:.2f}")
else:
    col3.metric("RSI (14)", "Not available")

col4.metric("Candles loaded", f"{len(data):,}")


# -----------------------------
# Simple educational signal
# -----------------------------
last_row = data.iloc[-1]

if pd.notna(last_row["SMA 5"]) and pd.notna(last_row["SMA 20"]):
    if last_row["SMA 5"] > last_row["SMA 20"]:
        signal = "Potential upward trend"
    elif last_row["SMA 5"] < last_row["SMA 20"]:
        signal = "Potential downward trend"
    else:
        signal = "No clear trend"
else:
    signal = "Not enough data for trend"

st.info(
    f"Trend check: **{signal}**. "
    "This is a simple moving-average comparison, not a buy/sell recommendation."
)


# -----------------------------
# Candlestick chart
# -----------------------------
st.subheader(f"{ticker} — {interval} candles")

fig = make_subplots(
    rows=2,
    cols=1,
    shared_xaxes=True,
    vertical_spacing=0.06,
    row_heights=[0.72, 0.28],
    subplot_titles=("Price", "RSI (14)"),
)

fig.add_trace(
    go.Candlestick(
        x=data.index,
        open=data["Open"],
        high=data["High"],
        low=data["Low"],
        close=data["Close"],
        name="Candles",
    ),
    row=1,
    col=1,
)

fig.add_trace(
    go.Scatter(
        x=data.index,
        y=data["SMA 5"],
        mode="lines",
        name="SMA 5",
    ),
    row=1,
    col=1,
)

fig.add_trace(
    go.Scatter(
        x=data.index,
        y=data["SMA 20"],
        mode="lines",
        name="SMA 20",
    ),
    row=1,
    col=1,
)

fig.add_trace(
    go.Scatter(
        x=data.index,
        y=data["RSI"],
        mode="lines",
        name="RSI",
    ),
    row=2,
    col=1,
)

fig.add_hline(y=70, line_dash="dash", row=2, col=1)
fig.add_hline(y=30, line_dash="dash", row=2, col=1)

fig.update_layout(
    height=750,
    xaxis_rangeslider_visible=False,
    legend_orientation="h",
    legend_yanchor="bottom",
    legend_y=1.02,
    legend_xanchor="right",
    legend_x=1,
)

st.plotly_chart(fig, use_container_width=True)


# -----------------------------
# Download selected chart data
# -----------------------------
st.subheader("Download chart data")

download_data = data.reset_index()
download_data.columns = [
    "_".join(str(part) for part in column if part)
    if isinstance(column, tuple)
    else str(column)
    for column in download_data.columns
]

csv_data = download_data.to_csv(index=False).encode("utf-8")

safe_ticker = ticker.replace("^", "").replace("=", "_").replace("/", "_")
csv_filename = f"{safe_ticker}_{interval}_{period}.csv"

st.download_button(
    label=f"Download {interval} data for {period} as CSV",
    data=csv_data,
    file_name=csv_filename,
    mime="text/csv",
)


# -----------------------------
# Opening-range backtest
# -----------------------------
st.divider()
st.subheader("Opening-range breakout backtest")
st.caption(
    "A simplified historical simulation for learning. It does not model "
    "all market conditions, slippage, or execution delays."
)

with st.expander("Backtest settings", expanded=False):
    backtest_col1, backtest_col2, backtest_col3 = st.columns(3)

    with backtest_col1:
        opening_minutes = st.selectbox(
            "Opening range",
            [15, 30, 60],
            index=1,
        )

    with backtest_col2:
        quantity = st.number_input(
            "Quantity",
            min_value=1,
            value=1,
            step=1,
        )

    with backtest_col3:
        risk_reward = st.selectbox(
            "Risk/reward target",
            [1.0, 1.5, 2.0, 3.0],
            index=2,
        )

    run_backtest = st.button("Run backtest", type="primary")


def run_opening_range_backtest(
    candles: pd.DataFrame,
    opening_range_minutes: int,
    trade_quantity: int,
    reward_multiple: float,
):
    """
    Basic long-only opening-range breakout test.

    Uses 5-minute data. Entry is modeled at the next candle's open.
    Stop and target checks use candle high/low, so actual fills may differ.
    """
    if candles.empty:
        return pd.DataFrame()

    candles = candles.copy().dropna(subset=["Open", "High", "Low", "Close"])

    if candles.index.tz is not None:
        candles.index = candles.index.tz_convert("Asia/Kolkata")

    candles["session_date"] = candles.index.date
    trades = []

    for session_date, day_data in candles.groupby("session_date"):
        day_data = day_data.sort_index()

        if len(day_data) < 3:
            continue

        session_start = day_data.index[0]
        range_end = session_start + pd.Timedelta(minutes=opening_range_minutes)

        opening_data = day_data[day_data.index < range_end]
        after_range = day_data[day_data.index >= range_end]

        if opening_data.empty or after_range.empty:
            continue

        opening_high = float(opening_data["High"].max())
        opening_low = float(opening_data["Low"].min())

        breakout_positions = [
            position
            for position, (_, candle) in enumerate(after_range.iterrows())
            if float(candle["Close"]) > opening_high
        ]

        if not breakout_positions:
            continue

        breakout_position = breakout_positions[0]

        # Enter on the next candle's open.
        entry_position = breakout_position + 1
        if entry_position >= len(after_range):
            continue

        entry_time = after_range.index[entry_position]
        entry_price = float(after_range.iloc[entry_position]["Open"])

        risk_per_share = entry_price - opening_low
        if risk_per_share <= 0:
            continue

        stop_price = opening_low
        target_price = entry_price + (risk_per_share * reward_multiple)

        exit_time = after_range.index[-1]
        exit_price = float(after_range.iloc[-1]["Close"])
        exit_reason = "End of session"

        # Check candles after the entry candle.
        for candle_time, candle in after_range.iloc[entry_position + 1 :].iterrows():
            candle_low = float(candle["Low"])
            candle_high = float(candle["High"])

            # Conservative assumption: if both hit in one candle, stop first.
            if candle_low <= stop_price:
                exit_time = candle_time
                exit_price = stop_price
                exit_reason = "Stop loss"
                break

            if candle_high >= target_price:
                exit_time = candle_time
                exit_price = target_price
                exit_reason = "Target"
                break

        pnl = (exit_price - entry_price) * trade_quantity

        trades.append(
            {
                "Date": str(session_date),
                "Entry time": entry_time,
                "Exit time": exit_time,
                "Opening high": opening_high,
                "Opening low": opening_low,
                "Entry": entry_price,
                "Stop": stop_price,
                "Target": target_price,
                "Exit": exit_price,
                "Quantity": trade_quantity,
                "P&L before costs": pnl,
                "Exit reason": exit_reason,
            }
        )

    return pd.DataFrame(trades)


if run_backtest:
    try:
        # Backtest on 5-minute data; use a recent period.
        backtest_data = get_market_data(ticker, "5d", "5m")

        if backtest_data.empty:
            st.warning("No 5-minute data was available for the backtest.")
        else:
            trades = run_opening_range_backtest(
                candles=backtest_data,
                opening_range_minutes=opening_minutes,
                trade_quantity=int(quantity),
                reward_multiple=float(risk_reward),
            )

            if trades.empty:
                st.info("No qualifying breakout trades were found.")
            else:
                total_pnl = float(trades["P&L before costs"].sum())
                winning_trades = int((trades["P&L before costs"] > 0).sum())
                win_rate = (winning_trades / len(trades)) * 100

                metric1, metric2, metric3 = st.columns(3)
                metric1.metric("Trades", len(trades))
                metric2.metric("Win rate", f"{win_rate:.1f}%")
                metric3.metric("P&L before costs", f"{total_pnl:,.2f}")

                st.dataframe(trades, use_container_width=True)

                trade_csv = trades.to_csv(index=False).encode("utf-8")

                st.download_button(
                    "Download backtest trades as CSV",
                    data=trade_csv,
                    file_name=f"{safe_ticker}_opening_range_backtest.csv",
                    mime="text/csv",
                )

    except Exception as error:
        st.error(f"Backtest failed: {error}")