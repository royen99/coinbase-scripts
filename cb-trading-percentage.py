import jwt
import requests
import time
import secrets
import json
from cryptography.hazmat.primitives import serialization

# Load API credentials & trading settings from config.json
with open("config.json", "r") as f:
    config = json.load(f)

key_name = config["name"]
key_secret = config["privateKey"]
base_currency = "ETH"
quote_currency = "USDC"
buy_threshold = config.get("buy_percentage", -3)  # % drop to buy
sell_threshold = config.get("sell_percentage", 3)  # % rise to sell
trade_percentage = config.get("trade_percentage", 10)  # % of available balance to trade

request_host = "api.coinbase.com"

def build_jwt(uri):
    """Generate a JWT token for Coinbase API authentication."""
    private_key_bytes = key_secret.encode("utf-8")
    private_key = serialization.load_pem_private_key(private_key_bytes, password=None)

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
    """Send authenticated requests to Coinbase API."""
    uri = f"{method} {request_host}{path}"
    jwt_token = build_jwt(uri)

    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Content-Type": "application/json",
        "CB-VERSION": "2024-02-05"
    }

    url = f"https://{request_host}{path}"
    response = requests.request(method, url, headers=headers, json=body)

    return response.json() if response.status_code == 200 else {"error": response.text}

def get_eth_price():
    """Fetch ETH-USDC price from Coinbase."""
    path = f"/api/v3/brokerage/products/{base_currency}-{quote_currency}"
    data = api_request("GET", path)
    
    if "price" in data:
        return float(data["price"])
    
    print(f"Error fetching ETH price: {data.get('error', 'Unknown error')}")
    return None

def get_balances():
    """Fetch and display balances for ETH and USDC."""
    path = "/api/v3/brokerage/accounts"
    data = api_request("GET", path)
    
    balances = {"ETH": 0.0, "USDC": 0.0}

    if "accounts" in data:
        for account in data["accounts"]:
            if account["currency"] in balances:
                balances[account["currency"]] = float(account["available_balance"]["value"])
    
    print(f"💰 Available Balance - ETH: {balances['ETH']} | USDC: {balances['USDC']}")
    return balances

def place_order(side, amount):
    """Place a buy/sell order for ETH-USDC."""
    path = "/api/v3/brokerage/orders"
    
    order_data = {
        "client_order_id": secrets.token_hex(16),
        "product_id": f"{base_currency}-{quote_currency}",
        "side": side,
        "order_configuration": {
            "market_market_ioc": {}
        }
    }
    
    if side == "BUY":
        order_data["order_configuration"]["market_market_ioc"]["quote_size"] = str(amount)  # Amount in USDC
    else:  # SELL
        order_data["order_configuration"]["market_market_ioc"]["base_size"] = str(amount)  # Amount in ETH

    print(f"🛠️ Placing {side} order: {order_data}")  # Debugging: Print the full request payload

    response = api_request("POST", path, order_data)

    print(f"🔄 Raw Response: {response}")  # Debugging: Print the full response

    if "order_id" in response:
        print(f"✅ {side.upper()} Order Placed: {response['order_id']}")
    else:
        print(f"❌ Order Failed: {response.get('error', 'Unknown error')}")

def trading_bot():
    """Monitors ETH price and trades based on percentage changes, using % of available balance."""
    initial_price = get_eth_price()
    if not initial_price:
        print("🚨 Failed to fetch initial ETH price. Exiting.")
        return

    print(f"🔍 Monitoring ETH... Initial Price: ${initial_price:.2f}")

    while True:
        time.sleep(30)  # Wait before checking price again
        current_price = get_eth_price()
        if not current_price:
            continue

        price_change = ((current_price - initial_price) / initial_price) * 100
        print(f"📈 ETH Price: ${current_price:.2f} ({price_change:.2f}%)")

        balances = get_balances()  # Fetch and display balances

        if price_change <= buy_threshold and balances["USDC"] > 0:
            buy_amount = (trade_percentage / 100) * balances["USDC"] / current_price
            if buy_amount > 0:
                print(f"💰 Buying {buy_amount:.4f} ETH!")
                place_order("BUY", buy_amount)
                initial_price = current_price  # Reset reference price
            else:
                print("🚫 Not enough USDC to place order.")

        elif price_change >= sell_threshold and balances["ETH"] > 0:
            sell_amount = (trade_percentage / 100) * balances["ETH"]
            if sell_amount > 0:
                print(f"💵 Selling {sell_amount:.4f} ETH!")
                place_order("SELL", sell_amount)
                initial_price = current_price  # Reset reference price
            else:
                print("🚫 Not enough ETH to place order.")

if __name__ == "__main__":
    trading_bot()
