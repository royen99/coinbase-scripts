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

min_order_sizes = {
    "ETH": {"buy": 0.01, "sell": 0.0001},
    "XRP": {"buy": 0.01, "sell": 1},
    "DOGE": {"buy": 0.01, "sell": 1},
    "SOL": {"buy": 0.01, "sell": 0.01},
}

db_config = config["database"]

def get_db_connection():
    return psycopg2.connect(
        dbname=db_config["dbname"],
        user=db_config["user"],
        password=db_config["password"],
        host=db_config["host"],
        port=db_config["port"]
    )

def log_trade(symbol, side, price, amount):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id SERIAL PRIMARY KEY,
            symbol TEXT,
            side TEXT,
            price NUMERIC,
            amount NUMERIC,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""
    )
    cur.execute("INSERT INTO trades (symbol, side, price, amount) VALUES (%s, %s, %s, %s)", (symbol, side, price, amount))
    conn.commit()
    cur.close()
    conn.close()

def log_price(symbol, price):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS prices (
            id SERIAL PRIMARY KEY,
            symbol TEXT,
            price NUMERIC,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""
    )
    cur.execute("INSERT INTO prices (symbol, price) VALUES (%s, %s)", (symbol, price))
    conn.commit()
    cur.close()
    conn.close()

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
    order_data = {"client_order_id": secrets.token_hex(16), "product_id": f"{crypto_symbol}-USDC", "side": side, "order_configuration": {"market_market_ioc": {}}}
    response = api_request("POST", path, order_data)
    if response.get("success", False):
        trade_price = get_crypto_price(crypto_symbol)
        log_trade(crypto_symbol, side, trade_price, amount)
    return response.get("success", False)

def fetch_prices_concurrently():
    threads = []
    for symbol in crypto_symbols:
        thread = threading.Thread(target=get_crypto_price, args=(symbol,))
        thread.start()
        threads.append(thread)
    for thread in threads:
        thread.join()

def trading_bot():
    global crypto_data
    for symbol in crypto_symbols:
        if crypto_data[symbol]["initial_price"] is None:
            initial_price = get_crypto_price(symbol)
            if not initial_price:
                continue
            crypto_data[symbol]["initial_price"] = initial_price

    while True:
        time.sleep(30)
        fetch_prices_concurrently()
        balances = get_balances()

        for symbol in crypto_symbols:
            current_price = get_crypto_price(symbol)
            if not current_price:
                continue

            crypto_data[symbol]["price_history"].append(current_price)
            price_change = ((current_price - crypto_data[symbol]["initial_price"]) / crypto_data[symbol]["initial_price"]) * 100

            macd_line, signal_line = calculate_macd(crypto_data[symbol]["price_history"])
            rsi = calculate_rsi(crypto_data[symbol]["price_history"])

            if macd_line and signal_line and rsi:
                if rsi < 30 and macd_line > signal_line and price_change <= buy_threshold and balances[quote_currency] > 0:
                    buy_amount = (trade_percentage / 100) * balances[quote_currency] / current_price
                    place_order(symbol, "BUY", buy_amount)
                elif rsi > 70 and macd_line < signal_line and price_change >= sell_threshold and balances[symbol] > min_order_sizes[symbol]["sell"]:
                    sell_amount = (trade_percentage / 100) * balances[symbol]
                    place_order(symbol, "SELL", sell_amount)

        save_state()

if __name__ == "__main__":
    trading_bot()
