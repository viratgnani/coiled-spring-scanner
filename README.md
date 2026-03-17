# Coiled Spring Scanner — Binance USDT Futures

A high-performance algorithmic scanner designed to detect explosive price and volume breakouts on Binance USDT Perpetual contracts.

The scanner focuses on identifying "coiled" price action—characterised by consolidation—followed by a significant expansion in both price and volume. This version features the **Pure Sniper Mode**, which prioritizes responsiveness to sudden market volatility and explosive reversals over strict consolidation filters.

## 🚀 Key Features

- **Real-time Scanning**: Monitors the entire Binance USDT-M market (500+ symbols) every few minutes.
- **Pure Sniper Logic**: Optimized to catch explosive 3x-10x volume spikes breaking through 48-hour price ceilings.
- **Dynamic Thresholding**: Compares current candle metrics against a 7-day rolling baseline for accurate anomaly detection.
- **Telegram Integration**: Instant HTML-formatted alerts delivered to your Telegram bot.
- **Safety Filters**: Automatic exclusion of recently listed symbols (<30 days) and highly illiquid assets.
- **Zero Configuration Discovery**: Automatically fetches and filters the valid trading universe from the exchange.

## 📈 The Logic: Pure Sniper Mode

Unlike traditional Bollinger Band scanners that require "perfect flatness," the Pure Sniper algorithm is designed for the modern crypto market. It focuses on the **Relative Intensity** of a breakout:

1.  **Volume Surge**: Filters for symbols where volume is at least 3x higher than the average volume of the previous week.
2.  **Price Expansion**: Requires the candle body to be at least 3x the average candle size of the consolidation period.
3.  **Recent Ceiling Break**: Validates the move by ensuring the close is above the highest high of the last 48 hours.

## 🛠️ Setup & Installation

### 1. Prerequisites
- Python 3.8+
- Active Telegram Bot (optional for alerts)

### 2. Install Dependencies
```bash
pip install ccxt numpy pandas
```

### 3. Environment Variables (Optional)
To receive alerts via Telegram, set the following environment variables:
- `TELEGRAM_TOKEN`: Your Bot API Token.
- `TELEGRAM_CHAT_ID`: Your Telegram Chat or Group ID.

## 🚀 Usage

Simply run the scanner:
```bash
python coiled_spring_scanner.py
```

The scanner will perform an initial universe load and then enter its persistent monitoring loop.

## 🛡️ Disclaimer
This tool is for **informational and research purposes only**. It does not execute trades. Cryptocurrency trading involves significant risk. Always perform your own due diligence before making any financial decisions.
