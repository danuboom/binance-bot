from dotenv import load_dotenv
import os
from binance.client import Client

load_dotenv()

api_key = os.getenv('BINANCE_API_KEY')
api_secret = os.getenv('BINANCE_API_SECRET')

# Connect to testnet (spot)
client = Client(api_key, api_secret, testnet=True)
client.API_URL = 'https://testnet.binance.vision/api'

def main():
    usdt_balance = client.get_asset_balance('USDT')
    btc_balance = client.get_asset_balance('BTC')
    
    print(f"USDT Balance: {usdt_balance['free'] if usdt_balance else 0}")
    print(f"BTC Balance: {btc_balance['free'] if btc_balance else 0}")
    
    ticker = client.get_symbol_ticker(symbol="BTCUSDT")
    print(f"BTCUSDT Price: {ticker['price']}")

if __name__ == "__main__":
    main()
