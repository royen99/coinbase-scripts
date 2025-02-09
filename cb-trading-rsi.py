import jwt
import requests
import time
import secrets
import json
import threading
import psycopg2
from cryptography.hazmat.primitives import serialization
from collections import deque

# Load API credentials & trading settings from config.json
with open("config.json", "r") as f:
    config = json.load(f)

key_name = config["name"]
key_secret = config["privateKey"]
crypto_symbols = config.get("crypto_symbols", ["ETH", "XRP", "DOGE", "SOL"])
quote_currency = "USDC"
buy_threshold = config.get("buy_percentage", -3)
sell_threshold = config.get("sell_percentage", 3)
trade_percentage = config.get("trade_percentage", 10)
stop_loss_percentage = config.get("stop_loss_percentage", -10)
volatility_window = config.get("volatility_window", 10)
trend_window = config.get("trend_window", 20)

# Initialize price history
price_history_maxlen = max(volatility_window, trend_window)
crypto_data = {symbol: {"price_history": deque(maxlen=price_history_maxlen)} for symbol in crypto_symbols}

db_config = config["database"]

def get_db_connection():
    return psycopg2.connect(
        dbname=db_config["dbname"],
        user=db_config["user"],
        password=db_config["password"],
        host=db_config["host"],
        port=db_config["port"]
    )

def api_request(method, path, body=None):
    """Send authenticated requests to the Coinbase API."""
    uri = f"{method} {path}"
    headers = {
        "Authorization": f"Bearer {key_secret}",
        "Content-Type": "application/json",
        "CB-VERSION": "2024-02-05"
    }
    url = f"https://api.coinbase.com{path}"
    response = requests.request(method, url, headers=headers, json=body)
    return response.json() if response.status_code == 200 else {"error": response.text}

def log_trade(symbol, side, price, amount):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS trades (
            id SERIAL PRIMARY KEY,
            symbol TEXT,
            side TEXT,
            price NUMERIC,
            amount NUMERIC,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cur.execute(
        "INSERT INTO trades (symbol, side, price, amount) VALUES (%s, %s, %s, %s)",
        (symbol, side, price, amount)
    )
    conn.commit()
    cur.close()
    conn.close()

def log_price(symbol, price):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS prices (
            id SERIAL PRIMARY KEY,
            symbol TEXT,
            price NUMERIC,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cur.execute(
        "INSERT INTO prices (symbol, price) VALUES (%s, %s)", (symbol, price)
    )
    conn.commit()
    cur.close()
    conn.close()

def calculate_moving_average(price_history):
    if len(price_history) < trend_window:
        return None
    return sum(price_history) / len(price_history)

def calculate_macd(price_history, short_window=12, long_window=26, signal_window=9):
    if len(price_history) < long_window:
        return None, None
    short_ema = sum(list(price_history)[-short_window:]) / short_window
    long_ema = sum(list(price_history)[-long_window:]) / long_window
    macd_line = short_ema - long_ema
    signal_line = sum([macd_line] * signal_window) / signal_window
    return macd_line, signal_line

def calculate_rsi(price_history, period=14):
    if len(price_history) < period:
        return None
    gains, losses = [], []
    for i in range(1, period + 1):
        change = price_history[-i] - price_history[-(i + 1)]
        if change >= 0:
            gains.append(change)
            losses.append(0)
        else:
            losses.append(abs(change))
            gains.append(0)
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def get_crypto_price(crypto_symbol):
    path = f"/api/v3/brokerage/products/{crypto_symbol}-{quote_currency}"
    data = api_request("GET", path)
    if "price" in data:
        price = float(data["price"])
        log_price(crypto_symbol, price)
        return price
    return None

def place_order(crypto_symbol, side, amount):
    path = "/api/v3/brokerage/orders"
    order_data = {"client_order_id": secrets.token_hex(16), "product_id": f"{crypto_symbol}-{quote_currency}", "side": side, "order_configuration": {"market_market_ioc": {}}}
    response = api_request("POST", path, order_data)
    if response.get("success", False):
        trade_price = get_crypto_price(crypto_symbol)
        log_trade(crypto_symbol, side, trade_price, amount)
    return response.get("success", False)

def trading_bot():
    global crypto_data
    while True:
        time.sleep(30)
        for symbol in crypto_symbols:
            current_price = get_crypto_price(symbol)
            if not current_price:
                continue
            crypto_data[symbol]["price_history"].append(current_price)
            macd_line, signal_line = calculate_macd(crypto_data[symbol]["price_history"])
            rsi = calculate_rsi(crypto_data[symbol]["price_history"])
            moving_avg = calculate_moving_average(crypto_data[symbol]["price_history"])
        save_state()

if __name__ == "__main__":
    trading_bot()
