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
✔ Trades a percentage of your available ETH or USDC balance

### cb-trading-advanced.py
Similar as the `cb-trading-percentage.py` but also includes:\

✔ *Dynamic Thresholds*: The buy/sell thresholds are adjusted based on recent price volatility.\
✔ *Trend Filter*: Trades are only executed if the price is close to the moving average, avoiding trades during strong trends.\
✔ *Stop-Loss*: A stop-loss mechanism is added to limit losses if the price drops significantly.\
✔ *Performance Tracking*: Tracks the total number of trades and cumulative profit/loss.

### Config Example (config.json)
```
{
    "name": "organizations/{org_id}/apiKeys/{key_id}",
    "privateKey": "-----BEGIN EC PRIVATE KEY-----\nYOUR PRIVATE KEY\n-----END EC PRIVATE KEY-----\n",
    "buy_percentage": -3,
    "sell_percentage": 3,
    "trade_percentage": 10,
    "stop_loss_percentage": -10,
    "volatility_window": 10,
    "trend_window": 20
}
```

**Ensure the `config.json` is safelyly stored.**
You can adjust `trade_percentage` to control how much of your balance gets traded. 😘💸\
**Fine-Tune Parameters**: Adjust the `volatility_window`, `trend_window`, and `stop_loss_percentage` to suit your risk tolerance and market conditions. 📊

## Example Output
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
```
