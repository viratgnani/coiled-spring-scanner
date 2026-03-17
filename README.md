# Coiled Spring Scanner: Real-time Arbitrage & Breakout Bot

A high-performance algorithmic trading tool developed to identify explosive price and volume events on Binance USDT-M Perpetual contracts. This project showcases the full lifecycle of a quantitative trading tool: from theoretical strategy design to live deployment on cloud infrastructure.

---

## 🛰️ Live Status: Production Ready
This bot is currently **deployed and active**.
- **Host**: AWS EC2 (Ubuntu 22.04 LTS)
- **Process Manager**: PM2 (for 24/7 uptime and automatic crash recovery)
- **Monitoring**: Real-time Telegram alerts with integrated HTML formatting.

## 🚀 Core Strategy: "Pure Sniper" Mode
The "Pure Sniper" logic is the result of iterative stress-testing and optimization. It is designed to capture high-velocity "pumps" that traditional Bollinger-based scanners often miss due to overly strict consolidation filters.

### Key Logic Pillars:
1.  **Explosive Momentum**: Detects symbols where the current hourly candle body is >3x the 7-day average.
2.  **Volume Confirmation**: Requires a volume spike >3x the recent floor to ensure the move is backed by market interest.
3.  **Resistance Breach**: Only triggers when the price breaks the 48-hour "ceiling," confirming a true breakout rather than localized noise.
4.  **Reversal Detection**: Built-in logic to detect "Dump-then-Pump" patterns using lower-wick shadow analysis.

## 🛠️ System Architecture & Development
This project was built using a structured development methodology, documented through milestones and performance "autopsies."

### Development Lifecycle:
- **Phase 1: Foundation**: Built the core scanning engine using `ccxt`, `numpy`, and `pandas`.
- **Phase 2: Live Integration**: Implemented real-time data streaming and Telegram bot signaling.
- **Phase 3: Deployment**: Migrated from local execution to a persistent AWS environment using PM2 for process monitoring.
- **Phase 4: Optimization**: Performed a deep-dive "Post-Mortem" on missed signals (e.g., the POLYX pump) to eliminate technical bottlenecks and refine sensitivity.

### Tech Stack:
- **Language**: Python 3.8+
- **APIs**: CCXT (Binance USD-M Futures)
- **Data Science**: Pandas, NumPy (for vectorised volatility & breakout calculation)
- **Infrastructure**: AWS VPS, PM2, Git

## 📈 Recent Performance Overhaul
Following the **March 2026** performance review, the system was updated to the "Pure Sniper" build. 
- **Fixed**: Resolved a critical floating-point heartbeat bug that caused intermittent hang-states.
- **Improved**: Reduced scan cycle from 15 minutes to 5 minutes, increasing capture rate by ~300%.
- **New Feature**: Added a 12-hour "Health Pulse" signal via Telegram to ensure zero-downtime visibility.

---

## 📦 Setup & Usage

### 1. Installation
```bash
pip install ccxt numpy pandas
```

### 2. Configuration
Configure your Telegram credentials via environment variables for live alerts:
- `TELEGRAM_TOKEN`
- `TELEGRAM_CHAT_ID`

### 3. Execution
```bash
# Run locally
python coiled_spring_scanner.py

# Production deployment
pm2 start scanner.py --name "coiled-scanner"
```

## 🛡️ Disclaimer
This project is for informational and educational purposes. It demonstrates algorithmic execution logic and data processing but does not perform automated order entry. Trading cryptocurrency involves high risk.
