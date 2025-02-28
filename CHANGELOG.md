# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unversioned]

### Changed
- **Dynamic Thresholds**: To try and cope with strong trends, adjust the initial (reference) price for the running session.
                          Note that, fow now, a restart of the bot would fall back to the stored price in the database.
- **Less verbose**: Some loglines are now only shown when `DEBUG_MODE = True` is set.

### Fixed
- **Buy size**: Now properly calculates the amount in USDC when buying.
- **Profit Calculation**: Uses previous Buy actions and calculates the proper profit.


## [1.0.2]

### Fixed
- **Buy and Sell**: Conditions where inverted.
- **Quote Currency**: When buying, `buy_amount` should be in USDC, not the `symbol`.

### Added
- **Trades Table**: Created a `trades` table to store trade history.
- **Trade Logging**: Updated the bot to log trades in the `trades` table.
- **Coin precision**: Specify number of decimals per coin in the `config.json` file.
- **Bot status**: Preperations for a live DashBoard with extra functionality (work in progress).

### Changed
- **Refactored `get_balances`**: Updated `get_balances` to return balances data for use in logging and database updates.
- **Updated `update_balances`**: Modified `update_balances` to accept balances data as an argument.
- **Trend Window**: Price history in the database need at least 200 entries for an accurate calculation.
- **Rounding**: Display coin prices in full decimals, not rounded to to 2.
- **Increase Percentage**: When bought at a the threshold, double it for a next buy. 

### Improved
- **Efficiency**: Reduced API calls by reusing balances data for logging and database updates.
- **Dashboard**: Added support for displaying trade history from the `trades` table.
- **MACD Calculation**: Corrected the MACD calculation to produce more realistic values.
- **RSI Calculation**: Confirmed that RSI values are more accurate and meaningful.

---

## [1.0.1]

### Added
- **Asynchronous Programming**: Integrated `aiohttp` and `asyncio` to make API requests concurrently, improving performance and responsiveness.
- **Concurrent Price Fetching**: Fetch prices for all cryptocurrencies simultaneously using `asyncio.gather`.
- **MACD Indicator**: Added Moving Average Convergence Divergence (MACD) to identify trend direction and momentum.
- **RSI Indicator**: Added Relative Strength Index (RSI) to identify overbought and oversold conditions.
- **Enhanced Trading Logic**: Integrated MACD and RSI signals into the trading strategy.

### Fixed
- **Missing `time` Module**: Added `import time` to resolve the `NameError` in the `build_jwt` function.
- **MACD Calculation**: Corrected the MACD calculation to produce realistic values.
- **RSI Calculation**: Confirmed that RSI values are accurate and meaningful.

### Changed
- **API Requests**: Replaced `requests` with `aiohttp` for asynchronous HTTP requests.
- **Function Updates**: Converted `api_request`, `get_crypto_price`, `get_balances`, `place_order`, and `trading_bot` to asynchronous functions.
- **Configuration**: Added MACD and RSI settings to `config.json`

### Improved
- **Output Interpretation**: Added detailed explanations for MACD, RSI, and expected buy/sell prices.

### Removed
- **Synchronous Requests**: Removed dependency on the `requests` library.

---

## [1.0.0] - Initial Release

### Added
- **Core Trading Bot**: Implemented a crypto trading bot that interacts with the Coinbase API.
- **Multi-Coin Support**: Enabled trading for multiple cryptocurrencies with configurable settings.
- **Dynamic Thresholds**: Adjusted buy/sell thresholds based on market volatility.
- **Database Integration**: Added PostgreSQL support for saving and loading trading state.
- **Risk Management**: Implemented trade percentage and stop-loss thresholds.
- **Performance Tracking**: Tracked total trades and profit for each cryptocurrency.

### Fixed
- **Initial Release**: No known issues at the time of release.

---
