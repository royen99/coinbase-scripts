# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Asynchronous Programming**: Integrated `aiohttp` and `asyncio` to make API requests concurrently, improving performance and responsiveness.
- **Concurrent Price Fetching**: Fetch prices for all cryptocurrencies simultaneously using `asyncio.gather`.

### Fixed
- **Missing `time` Module**: Added `import time` to resolve the `NameError` in the `build_jwt` function.

### Changed
- **API Requests**: Replaced `requests` with `aiohttp` for asynchronous HTTP requests.
- **Function Updates**: Converted `api_request`, `get_crypto_price`, `get_balances`, `place_order`, and `trading_bot` to asynchronous functions.

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
