import jwt
import requests
import time
import secrets
import json
import threading
import psycopg2
import logging
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
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

def initialize_database():
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
        );
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS prices (
            id SERIAL PRIMARY KEY,
            symbol TEXT,
            price NUMERIC,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    conn.commit()
    cur.close()
    conn.close()

# Set up logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")

def log_price(symbol, price):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO prices (symbol, price) VALUES (%s, %s)", (symbol, price))
        conn.commit()
        cur.close()
        conn.close()
        logging.debug(f"✅ Logged Price: {symbol} - ${price}")
    except Exception as e:
        logging.error(f"❌ Error logging price for {symbol}: {e}")

def log_trade(symbol, side, price, amount):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO trades (symbol, side, price, amount) VALUES (%s, %s, %s, %s)", (symbol, side, price, amount))
        conn.commit()
        cur.close()
        conn.close()
        logging.debug(f"✅ Logged Trade: {symbol} {side} - ${price} | Amount: {amount}")
    except Exception as e:
        logging.error(f"❌ Error logging trade for {symbol}: {e}")


def build_jwt(uri):
    """Generate a JWT token for Coinbase API authentication."""
    private_key_bytes = key_secret.encode("utf-8")
    private_key = serialization.load_pem_private_key(private_key_bytes, password=None, backend=default_backend())

    jwt_payload = {
        "sub": key_name,
        "iss": "cdp",
        "nbf": int(time.time()),
        "exp": int(time.time()) + 120,
        "uri": uri,
    }

    jwt_token = jwt.encode(
        jwt_payload,
        private_key,
        algorithm="ES256",
        headers={"kid": key_name, "nonce": secrets.token_hex()},
    )
    return jwt_token if isinstance(jwt_token, str) else jwt_token.decode("utf-8")

def api_request(method, path, body=None):
    """Send authenticated requests to the Coinbase API."""
    uri = f"{method} {path}"
    jwt_token = build_jwt(uri)
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Content-Type": "application/json",
        "CB-VERSION": "2024-02-05"
    }
    url = f"https://api.coinbase.com{path}"
    response = requests.request(method, url, headers=headers, json=body)
    return response.json() if response.status_code == 200 else {"error": response.text}

def save_state():
    state_to_save = {symbol: {"price_history": list(data["price_history"])} for symbol, data in crypto_data.items()}
    with open("state.json", "w") as f:
        json.dump(state_to_save, f, indent=2)

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
        log_price(crypto_symbol, price)  # ✅ Debug: Log every price update
        return price
    logging.warning(f"⚠️ Failed to fetch price for {crypto_symbol}")
    return None

def trading_bot():
    global crypto_data
    initialize_database()
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
            
            if rsi is not None and macd_line is not None and signal_line is not None:
                logging.debug(f"📊 {symbol} - MACD: {macd_line:.2f} | Signal: {signal_line:.2f} | RSI: {rsi:.2f}")
                
                if rsi < 30 and macd_line > signal_line:
                    logging.info(f"🟢 BUY Signal Detected for {symbol} at ${current_price}")
                    log_trade(symbol, "BUY", current_price, trade_percentage)
                elif rsi > 70 and macd_line < signal_line:
                    logging.info(f"🔴 SELL Signal Detected for {symbol} at ${current_price}")
                    log_trade(symbol, "SELL", current_price, trade_percentage)

        save_state()

if __name__ == "__main__":
    trading_bot()
