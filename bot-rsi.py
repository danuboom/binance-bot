import os
from dotenv import load_dotenv
from binance.client import Client
import pandas as pd
from ta.momentum import RSIIndicator
import streamlit as st
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

load_dotenv()

api_key = os.getenv('BINANCE_API_KEY')
api_secret = os.getenv('BINANCE_API_SECRET')

client = Client(api_key, api_secret, testnet=True)
client.API_URL = 'https://testnet.binance.vision/api'

symbol = "BTCUSDT"
interval = "15m"
rsi_period = 14

st.title("🚀 Binance Testnet BTC/USDT RSI Bot with Dynamic Sizing")
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
    rsi = RSIIndicator(df['close'], window=period).rsi()
    return rsi

def get_balances():
    usdt = client.get_asset_balance('USDT')
    btc = client.get_asset_balance('BTC')
    usdt_free = float(usdt['free']) if usdt else 0.0
    btc_free = float(btc['free']) if btc else 0.0
    return usdt_free, btc_free

def get_price():
    ticker = client.get_symbol_ticker(symbol=symbol)
    return float(ticker['price'])

def round_step_size(quantity, step_size):
    import math
    precision = int(round(-math.log10(float(step_size))))
    return round(quantity, precision)

# Get step size from Binance
@st.cache_resource
def get_step_size(symbol):
    info = client.get_symbol_info(symbol)
    step = next(f for f in info['filters'] if f['filterType'] == 'LOT_SIZE')['stepSize']
    return step

def place_order(action, qty):
    try:
        if qty <= 0:
            return {"error": "Quantity must be positive"}
        if action == "BUY":
            order = client.create_order(
                symbol=symbol,
                side='BUY',
                type='MARKET',
                quantity=qty
            )
        elif action == "SELL":
            order = client.create_order(
                symbol=symbol,
                side='SELL',
                type='MARKET',
                quantity=qty
            )
        else:
            return {"error": "Invalid action"}
        return order
    except Exception as e:
        return {"error": str(e)}

def determine_signal(rsi_value):
    if rsi_value < 40:
        return "BUY (Oversold)"
    elif rsi_value > 60:
        return "SELL (Overbought)"
    else:
        return "HOLD (Neutral)"


if 'trade_log' not in st.session_state:
    st.session_state.trade_log = []

def main():
    usdt_balance, btc_balance = get_balances()
    price = get_price()
    df = fetch_klines(symbol, interval)
    rsi_series = calculate_rsi(df, rsi_period)
    current_rsi = rsi_series.iloc[-1]
    signal = determine_signal(current_rsi)
    action_result = "No action taken"

    step_size = get_step_size(symbol)

    usdt_to_use = usdt_balance * 0.15
    btc_to_use = btc_balance * 0.15

    btc_qty_to_buy = round_step_size(usdt_to_use / price, step_size)
    btc_qty_to_sell = round_step_size(btc_to_use, step_size)
    min_qty = 0.0001

    if btc_balance < min_qty and usdt_balance >= usdt_to_use and btc_qty_to_buy >= min_qty:
        res = place_order("BUY", btc_qty_to_buy)
        if "error" in res:
            action_result = f"Initial BUY failed: {res['error']}"
        else:
            action_result = f"Initial BUY order placed: {btc_qty_to_buy} BTC"
            st.session_state.trade_log.append(f"{datetime.now()} - Initial BUY {btc_qty_to_buy} BTC at ~{price}")
    else:
        if signal.startswith("BUY") and btc_qty_to_buy >= min_qty:
            res = place_order("BUY", btc_qty_to_buy)
            if "error" in res:
                action_result = f"BUY order failed: {res['error']}"
            else:
                action_result = f"BUY order placed: {btc_qty_to_buy} BTC"
                st.session_state.trade_log.append(f"{datetime.now()} - BUY {btc_qty_to_buy} BTC at ~{price}")
        elif signal.startswith("SELL") and btc_qty_to_sell >= min_qty:
            res = place_order("SELL", btc_qty_to_sell)
            if "error" in res:
                action_result = f"SELL order failed: {res['error']}"
            else:
                action_result = f"SELL order placed: {btc_qty_to_sell} BTC"
                st.session_state.trade_log.append(f"{datetime.now()} - SELL {btc_qty_to_sell} BTC at ~{price}")

    st.markdown(f"Starting fund")
    st.markdown(f"BTC/USDT: $108,000")
    st.markdown(f"BTC: 1.00")
    
    st.markdown(f"Current balance")
    st.markdown(f"**BTC/USDT Price:** ${price:,.2f}")
    st.markdown(f"**USDT Balance:** {usdt_balance:,.4f}")
    st.markdown(f"**BTC Balance:** {btc_balance:,.6f}")
    st.markdown(f"**Current RSI ({rsi_period}):** {current_rsi:.2f}")
    st.markdown(f"### Signal: {signal}")
    st.markdown(f"### Action: {action_result}")
    st.line_chart(rsi_series)

    if st.session_state.trade_log:
        st.markdown("---")
        st.markdown("### Trade Log (Last 10 Trades):")
        for entry in reversed(st.session_state.trade_log[-10:]):
            st.code(entry)

if __name__ == "__main__":
    main()
