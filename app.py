import streamlit as st
import streamlit_autorefresh
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# ----------------------------
# Page setup and auto-refresh
# ----------------------------
st.set_page_config(
    page_title="Day Trading Assistant",
    page_icon="📈",
    layout="wide",
)

streamlit_autorefresh.st_autorefresh(
    interval=60_000,
    key="market_refresh",
)

st.title("📈 Day Trading Assistant")
st.caption("Educational market dashboard — data may be delayed and is not a trading recommendation.")

# ----------------------------
# Market and stock selection
# ----------------------------
MARKETS = {
    "Nifty 50": "^NSEI",
    "Bank Nifty": "^NSEBANK",
    "Reliance": "RELIANCE.NS",
    "TCS": "TCS.NS",
    "Infosys": "INFY.NS",
    "HDFC Bank": "HDFCBANK.NS",
    "ICICI Bank": "ICICIBANK.NS",
    "Tata Motors": "TATAMOTORS.NS",
    "ITC": "ITC.NS",
    "State Bank of India": "SBIN.NS",
    "Wipro": "WIPRO.NS",
    "Larsen & Toubro": "LT.NS",
}

left, right = st.columns([2, 2])

with left:
    selected_market = st.selectbox(
        "Choose an index or stock",
        list(MARKETS.keys()),
    )

with right:
    custom_ticker = st.text_input(
        "Or enter a Yahoo Finance ticker",
        placeholder="Example: SBIN.NS",
    ).strip().upper()

ticker = custom_ticker if custom_ticker else MARKETS[selected_market]
display_name = custom_ticker if custom_ticker else selected_market

# ----------------------------
# Chart settings
# ----------------------------
interval_options = {
    "5 minutes": "5m",
    "15 minutes": "15m",
    "30 minutes": "30m",
    "1 hour": "60m",
    "1 day": "1d",
}

period_options = {
    "1 day": "1d",
    "5 days": "5d",
    "1 month": "1mo",
    "3 months": "3mo",
    "6 months": "6mo",
    "1 year": "1y",
}

col1, col2 = st.columns(2)

with col1:
    selected_interval_label = st.selectbox(
        "Chart interval",
        list(interval_options.keys()),
        index=1,
    )

with col2:
    selected_period_label = st.selectbox(
        "Chart period",
        list(period_options.keys()),
        index=1,
    )

interval = interval_options[selected_interval_label]
period = period_options[selected_period_label]

# Yahoo Finance limits intraday history. Keep intraday requests short.
if interval in {"5m", "15m", "30m", "60m"} and period not in {"1d", "5d"}:
    st.info("Yahoo Finance intraday data is limited. Using the 5-day period for this interval.")
    period = "5d"

# ----------------------------
# Download and prepare data
# ----------------------------
@st.cache_data(ttl=55)
def get_market_data(symbol: str, requested_period: str, requested_interval: str):
    frame = yf.download(
        symbol,
        period=requested_period,
        interval=requested_interval,
        auto_adjust=True,
        progress=False,
    )

    if frame.empty:
        return frame

    # Flatten yfinance's MultiIndex columns, if present.
    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = frame.columns.get_level_values(0)

    frame = frame.loc[:, ~frame.columns.duplicated()].copy()
    frame.index = pd.to_datetime(frame.index)

    # Make sure the required price columns exist.
    required = {"Open", "High", "Low", "Close"}
    if not required.issubset(frame.columns):
        return pd.DataFrame()

    frame["SMA 5"] = frame["Close"].rolling(5).mean()
    frame["SMA 20"] = frame["Close"].rolling(20).mean()

    delta = frame["Close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean().replace(0, float("nan"))
    relative_strength = avg_gain / avg_loss
    frame["RSI 14"] = 100 - (100 / (1 + relative_strength))

    return frame


with st.spinner(f"Loading {display_name} data..."):
    data = get_market_data(ticker, period, interval)

if data.empty:
    st.error(
        f"No data returned for `{ticker}`. Check the ticker symbol or try another interval."
    )
    st.stop()

# ----------------------------
# Summary metrics
# ----------------------------
latest = data.iloc[-1]
previous_close = data["Close"].iloc[-2] if len(data) > 1 else latest["Close"]

change = latest["Close"] - previous_close
change_pct = (change / previous_close * 100) if previous_close else 0

m1, m2, m3, m4 = st.columns(4)

m1.metric("Latest close", f"{latest['Close']:,.2f}")
m2.metric("Change", f"{change:,.2f}", f"{change_pct:.2f}%")
m3.metric("SMA 5", f"{latest['SMA 5']:,.2f}" if pd.notna(latest["SMA 5"]) else "—")
m4.metric("RSI 14", f"{latest['RSI 14']:.2f}" if pd.notna(latest["RSI 14"]) else "—")

# ----------------------------
# Price chart
# ----------------------------
st.subheader(f"{display_name} price chart")

fig = go.Figure()

fig.add_trace(
    go.Candlestick(
        x=data.index,
        open=data["Open"],
        high=data["High"],
        low=data["Low"],
        close=data["Close"],
        name="Price",
    )
)

fig.add_trace(
    go.Scatter(
        x=data.index,
        y=data["SMA 5"],
        mode="lines",
        name="SMA 5",
    )
)

fig.add_trace(
    go.Scatter(
        x=data.index,
        y=data["SMA 20"],
        mode="lines",
        name="SMA 20",
    )
)

fig.update_layout(
    height=550,
    xaxis_title="Time",
    yaxis_title="Price",
    xaxis_rangeslider_visible=False,
    legend_title="Indicators",
)

st.plotly_chart(fig, use_container_width=True)

# ----------------------------
# RSI chart
# ----------------------------
st.subheader("RSI (14)")

rsi_fig = go.Figure()
rsi_fig.add_trace(
    go.Scatter(
        x=data.index,
        y=data["RSI 14"],
        mode="lines",
        name="RSI 14",
    )
)
rsi_fig.add_hline(y=70, line_dash="dash")
rsi_fig.add_hline(y=30, line_dash="dash")
rsi_fig.update_layout(height=250, yaxis_range=[0, 100])

st.plotly_chart(rsi_fig, use_container_width=True)

# ----------------------------
# Data table
# ----------------------------
with st.expander("Show price data"):
    st.dataframe(data.tail(100), use_container_width=True)

    csv_data = data.to_csv().encode("utf-8")
    st.download_button(
        "Download data as CSV",
        data=csv_data,
        file_name=f"{ticker.replace('.', '_')}_data.csv",
        mime="text/csv",
    )

# ----------------------------
# Basic opening-range backtest
# ----------------------------
st.divider()
st.header("Basic Opening-Range Backtest")
st.caption(
    "This is a simplified educational example using recent 5-minute data. "
    "It does not model slippage, taxes, or all execution risks."
)

with st.expander("Backtest settings", expanded=True):
    b1, b2, b3 = st.columns(3)

    with b1:
        starting_capital = st.number_input(
            "Starting capital (₹)",
            min_value=1000.0,
            value=10000.0,
            step=1000.0,
        )

    with b2:
        risk_pct = st.number_input(
            "Risk per trade (%)",
            min_value=0.1,
            max_value=5.0,
            value=1.0,
            step=0.1,
        )

    with b3:
        stop_pct = st.number_input(
            "Stop-loss distance (%)",
            min_value=0.1,
            max_value=5.0,
            value=0.5,
            step=0.1,
        )

    b4, b5 = st.columns(2)

    with b4:
        reward_risk = st.number_input(
            "Reward-to-risk target",
            min_value=0.5,
            max_value=5.0,
            value=2.0,
            step=0.5,
        )

    with b5:
        cost_pct = st.number_input(
            "Estimated cost per side (%)",
            min_value=0.0,
            max_value=1.0,
            value=0.05,
            step=0.01,
        )


def run_opening_range_backtest(
    frame: pd.DataFrame,
    capital: float,
    risk_percent: float,
    stop_percent: float,
    reward_risk_ratio: float,
    cost_percent: float,
):
    if frame.empty:
        return pd.DataFrame(), capital

    work = frame.copy()
    work = work.dropna(subset=["Open", "High", "Low", "Close"])

    # This example is designed for 5-minute intraday candles.
    work["TradingDate"] = work.index.date
    trades = []
    equity = capital

    for trading_date, day in work.groupby("TradingDate"):
        day = day.sort_index()

        # Use the first three candles as the opening range.
        if len(day) < 5:
            continue

        opening_range = day.iloc[:3]
        range_high = opening_range["High"].max()

        after_range = day.iloc[3:]
        breakout_positions = [
            pos
            for pos, (_, candle) in enumerate(after_range.iterrows())
            if candle["Close"] > range_high
        ]

        if not breakout_positions:
            continue

        breakout_pos = breakout_positions[0]

        # Enter at the next candle's open, if one exists.
        entry_pos = breakout_pos + 1
        if entry_pos >= len(after_range):
            continue

        entry_candle = after_range.iloc[entry_pos]
        entry_price = float(entry_candle["Open"])

        stop_price = entry_price * (1 - stop_percent / 100)
        risk_per_share = entry_price - stop_price

        if risk_per_share <= 0:
            continue

        target_price = entry_price + (risk_per_share * reward_risk_ratio)
        risk_amount = equity * (risk_percent / 100)
        quantity = int(risk_amount / risk_per_share)

        if quantity <= 0:
            continue

        exit_price = float(day.iloc[-1]["Close"])
        exit_reason = "End of session"

        # Check subsequent candles for stop or target.
        for _, candle in after_range.iloc[entry_pos + 1:].iterrows():
            hit_stop = float(candle["Low"]) <= stop_price
            hit_target = float(candle["High"]) >= target_price

            # Conservative assumption if both are touched in one candle.
            if hit_stop:
                exit_price = stop_price
                exit_reason = "Stop-loss"
                break

            if hit_target:
                exit_price = target_price
                exit_reason = "Target"
                break

        gross_pnl = (exit_price - entry_price) * quantity
        estimated_cost = (
            (entry_price + exit_price) * quantity * cost_percent / 100
        )
        net_pnl = gross_pnl - estimated_cost
        equity += net_pnl

        trades.append(
            {
                "Date": str(trading_date),
                "Entry": entry_price,
                "Exit": exit_price,
                "Quantity": quantity,
                "Exit reason": exit_reason,
                "Gross P&L": gross_pnl,
                "Estimated costs": estimated_cost,
                "Net P&L": net_pnl,
                "Equity after trade": equity,
            }
        )

    return pd.DataFrame(trades), equity


if st.button("Run backtest"):
    with st.spinner("Running backtest..."):
        backtest_data = get_market_data(ticker, "5d", "5m")

    if backtest_data.empty:
        st.error("Could not download 5-minute data for this ticker.")
    else:
        trades, ending_equity = run_opening_range_backtest(
            frame=backtest_data,
            capital=starting_capital,
            risk_percent=risk_pct,
            stop_percent=stop_pct,
            reward_risk_ratio=reward_risk,
            cost_percent=cost_pct,
        )

        if trades.empty:
            st.warning("No qualifying trades were found in the available data.")
        else:
            total_pnl = trades["Net P&L"].sum()
            return_pct = (ending_equity / starting_capital - 1) * 100

            r1, r2, r3 = st.columns(3)
            r1.metric("Ending equity", f"₹{ending_equity:,.2f}")
            r2.metric("Net P&L", f"₹{total_pnl:,.2f}")
            r3.metric("Return", f"{return_pct:.2f}%")

            st.dataframe(trades, use_container_width=True)

            st.download_button(
                "Download backtest trades",
                data=trades.to_csv(index=False).encode("utf-8"),
                file_name=f"{ticker.replace('.', '_')}_backtest.csv",
                mime="text/csv",
            )

st.caption(f"Last app refresh: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")