import os
from dotenv import load_dotenv
from binance.client import Client
import pandas as pd
from ta.momentum import RSIIndicator
import streamlit as st
from datetime import datetime
from streamlit_autorefresh import st_autorefresh
import math

load_dotenv()

api_key = os.getenv('BINANCE_API_KEY')
api_secret = os.getenv('BINANCE_API_SECRET')

client = Client(api_key, api_secret, testnet=True)
client.API_URL = 'https://testnet.binance.vision/api'

symbol = "BTCUSDT"
interval = "15m"
rsi_period = 14
trade_fraction = 0.05  # 5% per trade for mild risk

st.title("🚀 Binance Testnet BTC/USDT RSI Bot (Mild Risk) 1.0")

with st.expander("📘 Strategy Explanation"):
    st.markdown("""
### ⚙️ Strategy: RSI Cross with Mild Risk

This bot trades based on **RSI (Relative Strength Index)** behavior on the **15-minute BTC/USDT chart**.

#### 🔍 Trade Logic:
- **Buy:** When RSI crosses **below 40** → Signals potential market rebound.
- **Sell:** When RSI crosses **above 60** → Signals potential overbought condition.
- Crossing detection reduces noise compared to using fixed RSI levels (like 30/70).

#### 💼 Risk Management:
- Trades only **5% of your balance** (BTC or USDT) per signal.
- Helps preserve capital during sideways markets.

#### 📊 Execution:
- Evaluated once per minute.
- Market orders placed instantly if signal and balance thresholds are met.
    """)

# Auto refresh every minute
count = st_autorefresh(interval=60 * 1000, limit=None, key="refresh")

@st.cache_data(ttl=60)
def fetch_klines(symbol, interval, limit=100):
    klines = client.get_klines(symbol=symbol, interval=interval, limit=limit)
    df = pd.DataFrame(klines, columns=[
        'open_time', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_asset_volume', 'number_of_trades',
        'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
    ])
    df['close'] = df['close'].astype(float)
    df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
    return df

def calculate_rsi(df, period):
    return RSIIndicator(df['close'], window=period).rsi()

def get_balances():
    usdt = client.get_asset_balance('USDT')
    btc = client.get_asset_balance('BTC')
    usdt_free = float(usdt['free']) if usdt else 0.0
    btc_free = float(btc['free']) if btc else 0.0
    return usdt_free, btc_free

def get_price():
    ticker = client.get_symbol_ticker(symbol=symbol)
    return float(ticker['price'])

@st.cache_resource
def get_step_size(symbol):
    info = client.get_symbol_info(symbol)
    step = next(f for f in info['filters'] if f['filterType'] == 'LOT_SIZE')['stepSize']
    return step

def round_step_size(quantity, step_size):
    precision = int(round(-math.log10(float(step_size))))
    return round(quantity, precision)

def place_order(action, qty):
    if qty <= 0:
        return {"error": "Quantity must be positive"}
    try:
        order = client.create_order(
            symbol=symbol,
            side=action,
            type='MARKET',
            quantity=qty
        )
        return order
    except Exception as e:
        return {"error": str(e)}

def determine_signal(rsi_series):
    # Use RSI crossing logic (mild risk)
    prev_rsi = rsi_series.iloc[-2]
    current_rsi = rsi_series.iloc[-1]

    if prev_rsi >= 40 and current_rsi < 40:
        return "BUY"
    elif prev_rsi <= 60 and current_rsi > 60:
        return "SELL"
    else:
        return "HOLD"

def calculate_portfolio_value(usdt, btc, price):
    return usdt + btc * price

if 'trade_log' not in st.session_state:
    st.session_state.trade_log = []

if 'initial_portfolio_value' not in st.session_state:
    usdt_init, btc_init = get_balances()
    price_init = get_price()
    st.session_state.initial_portfolio_value = calculate_portfolio_value(usdt_init, btc_init, price_init)

def main():
    usdt_balance, btc_balance = get_balances()
    price = get_price()
    df = fetch_klines(symbol, interval)
    rsi_series = calculate_rsi(df, rsi_period)
    signal = determine_signal(rsi_series)

    step_size = get_step_size(symbol)
    min_qty = 0.0001

    action_result = "No action taken"

    # Trade amount (5% of available balance)
    usdt_to_use = usdt_balance * trade_fraction
    btc_to_use = btc_balance * trade_fraction

    btc_qty_to_buy = round_step_size(usdt_to_use / price, step_size)
    btc_qty_to_sell = round_step_size(btc_to_use, step_size)

    if signal == "BUY" and btc_qty_to_buy >= min_qty and usdt_to_use >= price * min_qty:
        res = place_order("BUY", btc_qty_to_buy)
        if "error" in res:
            action_result = f"BUY order failed: {res['error']}"
        else:
            action_result = f"BUY order placed: {btc_qty_to_buy:.6f} BTC"
        log_entry = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Signal: BUY | {action_result} | Price: {price:.2f}"
        st.session_state.trade_log.append(log_entry)

    elif signal == "SELL" and btc_qty_to_sell >= min_qty:
        res = place_order("SELL", btc_qty_to_sell)
        if "error" in res:
            action_result = f"SELL order failed: {res['error']}"
        else:
            action_result = f"SELL order placed: {btc_qty_to_sell:.6f} BTC"
        log_entry = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Signal: SELL | {action_result} | Price: {price:.2f}"
        st.session_state.trade_log.append(log_entry)

    else:
        action_result = "No action taken"
        log_entry = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Signal: HOLD | No action taken | Price: {price:.2f}"
        st.session_state.trade_log.append(log_entry)

    # Calculate ROI
    current_portfolio_value = calculate_portfolio_value(usdt_balance, btc_balance, price)
    roi = (current_portfolio_value - st.session_state.initial_portfolio_value) / st.session_state.initial_portfolio_value * 100

    # Display info
    st.markdown("## Current Portfolio Status")
    st.markdown(f"**BTC/USDT Price:** ${price:,.2f}")
    st.markdown(f"**USDT Balance:** {usdt_balance:,.4f}")
    st.markdown(f"**BTC Balance:** {btc_balance:,.6f}")
    st.markdown(f"**Current RSI ({rsi_period}):** {rsi_series.iloc[-1]:.2f}")
    st.markdown(f"**ROI:** {roi:.2f}%")

    col1, col2 = st.columns(2)
    if signal == "BUY":
        col1.success(f"Signal: BUY (RSI crossed below 40)")
    elif signal == "SELL":
        col1.error(f"Signal: SELL (RSI crossed above 60)")
    else:
        col1.info("Signal: HOLD")

    if st.session_state.trade_log:
        last_action = st.session_state.trade_log[-1]
        if "BUY" in last_action:
            col2.success(f"Last Action: {last_action}")
        elif "SELL" in last_action:
            col2.error(f"Last Action: {last_action}")
        else:
            col2.info(f"Last Action: {last_action}")

    # Keep track of portfolio value over time for chart
    if 'balance_history' not in st.session_state:
        st.session_state.balance_history = []
    st.session_state.balance_history.append({
        'time': datetime.now(),
        'portfolio_value': current_portfolio_value,
        'price': price
    })

    history_df = pd.DataFrame(st.session_state.balance_history)
    history_df.set_index('time', inplace=True)

    # Calculate percentage change from first value
    df_pct = history_df.copy()
    df_pct['portfolio_pct_change'] = (df_pct['portfolio_value'] / df_pct['portfolio_value'].iloc[0] - 1) * 100
    df_pct['price_pct_change'] = (df_pct['price'] / df_pct['price'].iloc[0] - 1) * 100

    st.markdown("### Portfolio and BTC Price % Change Since Start")
    st.line_chart(df_pct[['portfolio_pct_change', 'price_pct_change']])

    st.markdown("---")
    st.markdown("### Trade Log (Last 10):")
    for entry in reversed(st.session_state.trade_log[-10:]):
        st.code(entry)

if __name__ == "__main__":
    main()
