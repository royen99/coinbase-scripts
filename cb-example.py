import jwt
import requests
import time
import secrets
import json
from cryptography.hazmat.primitives import serialization

#################
# This script demonstrates how to authenticate with the Coinbase API using JWT and perform basic account operations.
# It includes functions to get account balances and fetch the ETH price.
#
# Sample output :
# 💰 Available Balance - ETH: 7.7431 | USDC: 812.44
# 📈 ETH Price: $4533.30
#################

# Load API credentials from config.json.
# Why JSON ? By default, when you create a new API key in Coinbase, it provides you with a similar JSON file containing your API credentials.
# Also, because it's a lightweight data interchange format that's easy to read and write for humans and machines and usable in almost any programming language.
#
# Sample config.json:
# {
#     "name": "organizations/{org_id}/apiKeys/{key_id}",
#     "privateKey": "-----BEGIN PRIVATE KEY-----\nYOUR_PRIVATE_KEY\n-----END PRIVATE KEY-----"
# }
#
# Remember: never share your API keys or private information *anywhere*.
# Official CoinBase Advanced Trade API documentation: https://docs.cdp.coinbase.com/api-reference/advanced-trade-api/rest-api/introduction
# Official CoinBase Discord: https://discord.gg/cdp

with open("config.json", "r") as f:
    config = json.load(f)

key_name = config["name"]
key_secret = config["privateKey"]
base_currency = "ETH"
quote_currency = "USDC"
request_host = "api.coinbase.com"

def build_jwt(uri):
    # Generate a JWT token for Coinbase API authentication.
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
    # Send authenticated requests to Coinbase API.
    uri = f"{method} {request_host}{path}"
    jwt_token = build_jwt(uri)

    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Content-Type": "application/json",
        "CB-VERSION": "2025-08-01"
    }

    url = f"https://{request_host}{path}"
    response = requests.request(method, url, headers=headers, json=body)

    return response.json() if response.status_code == 200 else {"error": response.text}

def get_balances():
    # Fetch and display balances for ETH and USDC.
    path = "/api/v3/brokerage/accounts"
    data = api_request("GET", path)
    
    balances = {"ETH": 0.0, "USDC": 0.0}

    if "accounts" in data:
        for account in data["accounts"]:
            if account["currency"] in balances:
                balances[account["currency"]] = float(account["available_balance"]["value"])
    
    print(f"💰 Available Balance - ETH: {balances['ETH']} | USDC: {balances['USDC']}")
    return balances

def get_eth_price():
    # Fetch ETH-USDC price from Coinbase.
    path = f"/api/v3/brokerage/products/{base_currency}-{quote_currency}"
    data = api_request("GET", path)
    
    if "price" in data:
        return float(data["price"])
    
    print(f"Error fetching ETH price: {data.get('error', 'Unknown error')}")
    return None

# Fetch and display balances
balances = get_balances()

# Fetch and display ETH price
current_price = get_eth_price()
if current_price:
    print(f"📈 ETH Price: ${current_price:.2f}")
