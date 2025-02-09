import jwt
import requests
import time
import secrets
import json
import threading
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

request_host = "api.coinbase.com"
price_history_maxlen = max(volatility_window, trend_window)

# Caching for prices and balances
price_cache = {}
balance_cache = {}

state_file = "state.json"
try:
    with open(state_file, "r") as f:
        crypto_data = json.load(f)
        for symbol in crypto_symbols:
            if symbol in crypto_data:
                crypto_data[symbol]["price_history"] = deque(crypto_data[symbol]["price_history"], maxlen=price_history_maxlen)
except FileNotFoundError:
    crypto_data = {symbol: {"price_history": deque(maxlen=price_history_maxlen), "initial_price": None, "total_trades": 0, "total_profit": 0.0} for symbol in crypto_symbols}

def save_state():
    state_to_save = {symbol: {**data, "price_history": list(data["price_history"])} for symbol, data in crypto_data.items()}
    with open(state_file, "w") as f:
        json.dump(state_to_save, f, indent=2)

def build_jwt(uri):
    private_key_bytes = key_secret.encode("utf-8")
    private_key = serialization.load_pem_private_key(private_key_bytes, password=None)
    jwt_payload = {"sub": key_name, "iss": "cdp", "nbf": int(time.time()), "exp": int(time.time()) + 120, "uri": uri}
    jwt_token = jwt.encode(jwt_payload, private_key, algorithm="ES256", headers={"kid": key_name, "nonce": secrets.token_hex()})
    return jwt_token if isinstance(jwt_token, str) else jwt_token.decode("utf-8")

def api_request(method, path, body=None):
    uri = f"{method} {request_host}{path}"
    jwt_token = build_jwt(uri)
    headers = {"Authorization": f"Bearer {jwt_token}", "Content-Type": "application/json", "CB-VERSION": "2024-02-05"}
    url = f"https://{request_host}{path}"
    response = requests.request(method, url, headers=headers, json=body)
    return response.json() if response.status_code == 200 else {"error": response.text}

def get_crypto_price(crypto_symbol):
    global price_cache
    if crypto_symbol in price_cache:
        return price_cache[crypto_symbol]

    path = f"/api/v3/brokerage/products/{crypto_symbol}-{quote_currency}"
    data = api_request("GET", path)
    if "price" in data:
        price_cache[crypto_symbol] = float(data["price"])
        return price_cache[crypto_symbol]

    print(f"Error fetching {crypto_symbol} price: {data.get('error', 'Unknown error')}")
    return None

def get_balances():
    global balance_cache
    if balance_cache:
        return balance_cache

    path = "/api/v3/brokerage/accounts"
    data = api_request("GET", path)

    balances = {symbol: 0.0 for symbol in crypto_symbols}
    balances[quote_currency] = 0.0

    if "accounts" in data:
        for account in data["accounts"]:
            if account["currency"] in balances:
                balances[account["currency"]] = float(account["available_balance"]["value"])

    balance_cache = balances
    return balances

def place_order(crypto_symbol, side, amount):
    path = "/api/v3/brokerage/orders"
    order_data = {"client_order_id": secrets.token_hex(16), "product_id": f"{crypto_symbol}-{quote_currency}", "side": side, "order_configuration": {"market_market_ioc": {}}}

    if side == "BUY":
        rounded_amount = round(amount, 2)
        if rounded_amount < min_order_sizes[crypto_symbol]["buy"]:
            return False
        order_data["order_configuration"]["market_market_ioc"]["quote_size"] = str(rounded_amount)
    else:
        rounded_amount = round(amount, 6)
        if rounded_amount < min_order_sizes[crypto_symbol]["sell"]:
            return False
        order_data["order_configuration"]["market_market_ioc"]["base_size"] = str(rounded_amount)

    response = api_request("POST", path, order_data)
    return response.get("success", False)

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
