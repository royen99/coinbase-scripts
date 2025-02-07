# coinbase-scripts
Coinbase crypto trading API scripts.

As it's still under development it currently is based only on ETH (vs USDC). Support for other, or even multiple, crypto might be added later.

✅ Directly makes the API request.\
✅ Handles API responses & errors, printing available balances or errors properly.\
✅ Uses config.json for credentials, keeping them separate from the script.

## How It Works

### cb-trading-percentage.py
Monitors ETH price every 30 sec\
If ETH drops by buy_percentage (-3%) → BUYS ETH\
If ETH rises by sell_percentage (3%) → SELLS ETH\
Uses market orders for instant execution.

✔ Displays ETH & USDC Balances 💰\
✔ Prevents Trades if You Have No Balance 🚫\
✔ Still Trades ETH & USDC Based on Price Changes 📊\
✔ Trades a percentage of your available ETH or USDC balance.
✔ *Minimum Order*: Makes sure an order meets Coinbase's minimum amounts.

### cb-trading-advanced.py
Similar as the `cb-trading-percentage.py` but also includes:\

✔ *Dynamic Thresholds*: The buy/sell thresholds are adjusted based on recent price volatility.\
✔ *Trend Filter*: Trades are only executed if the price is close to the moving average, avoiding trades during strong trends.\
✔ *Stop-Loss*: A stop-loss mechanism is added to limit losses if the price drops significantly.\
✔ *Performance Tracking*: Tracks the total number of trades and cumulative profit/loss.

### cb-trading-multiple.py
Similar as the `cb-trading-advanced.py` but also includes:\

✔ *Supports Multiple Cryptocurrencies*: The script monitors and trades all cryptocurrencies specified in the `crypto_symbols` list.\
✔ *Independent Tracking for Each Cryptocurrency*: Each cryptocurrency has its own `price_history`, `initial_price`, `total_trades`, and `total_profit` tracking.\
✔ *Keeps State*: Can reuse values like `initial_price`, `price_history`, `total_trades`, and `total_profit` if it gets restarted.

To keep state, a `state.json` is created (if none exists) as:
```json
{
  "ETH": {
    "price_history": [2000.0, 1980.0, 1990.0],
    "initial_price": 2000.0,
    "total_trades": 2,
    "total_profit": 20.0
  },
  "XRP": {
    "price_history": [0.5, 0.49, 0.48],
    "initial_price": 0.5,
    "total_trades": 1,
    "total_profit": -0.02
  }
}
```

### Config Example (config.json)
```
{
    "name": "organizations/{org_id}/apiKeys/{key_id}",
    "privateKey": "-----BEGIN EC PRIVATE KEY-----\nYOUR PRIVATE KEY\n-----END EC PRIVATE KEY-----\n",
    "buy_percentage": -3,
    "sell_percentage": 3,
    "crypto_symbols": ["ETH", "XRP", "DOGE", "SOL"],
    "trade_percentage": 10,
    "stop_loss_percentage": -10,
    "volatility_window": 10,
    "trend_window": 20
}
```

**Ensure the `config.json` is safelyly stored.**
You can adjust `trade_percentage` to control how much of your balance gets traded. 😘💸\
**Fine-Tune Parameters**: Adjust the `volatility_window`, `trend_window`, and `stop_loss_percentage` to suit your risk tolerance and market conditions. 📊

## Example Outputs
```
🔍 Monitoring ETH... Initial Price: $3000.00
💰 Available Balance - ETH: 1.5 | USDC: 1000.00
📈 ETH Price: $2910.00 (-3.00%)
🚫 Buy order too small: $0.01 (minimum: $0.01)
💰 Buying 0.0344 ETH!
✅ BUY Order Placed: abc1234

💰 Available Balance - ETH: 1.6 | USDC: 970.00
📈 ETH Price: $3090.00 (3.00%)
💵 Selling 0.1600 ETH!
✅ SELL Order Placed: xyz5678
🚫 Sell order too small: 0.000050 ETH (minimum: 0.000100 ETH)
🚨 Stop-loss triggered! Selling 0.2739 ETH!
📊 Total Trades: 12 | Total Profit: $541.20

💰 Available Balances:
  - ETH: 730.041680797387629226
  - XRP: 40.2
  - DOGE: 640.5
  - SOL: 210.1
  - USDC: 79.3424226884312

📈 ETH Price: $1980.00 (-1.00%)
📊 Expected Buy Price for ETH: $1940.00
📊 Expected Sell Price for ETH: $2060.00
```
