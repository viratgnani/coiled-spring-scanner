# Development Milestones & Roadmap

This document tracks the technical evolution of the Coiled Spring Scanner project, from initial concept to high-frequency production deployment.

## ✅ Phase 1: Core Engine Development
- [x] **Modular Architecture**: Built the `ccxt`-based engine to handle asynchronous market discovery.
- [x] **Statistical Filtering**: Implemented rolling standard deviation and Bollinger Band compression algorithms.
- [x] **Breakout Logic**: Developed the triple-confirmation trigger (Body spikes, Volume surge, 48h-High breach).
- [x] **Signal Integrity**: Added HTML-formatted Telegram alerting for real-time mobile monitoring.

## ✅ Phase 2: Live Deployment & Cloud Integration
- [x] **Infrastructure**: Configured AWS Ubuntu environment for 24/7 persistent scanning.
- [x] **Process Management**: Integrated PM2 for automatic zero-downtime restarts and log rotation.
- [x] **Connectivity**: Optimised rate-limit handling for high-frequency (every 5 min) market polling.

## ✅ Phase 3: Performance Overhaul (March 2026)
- [x] **The "Pure Sniper" Refactor**: Massively relaxed consolidation filters to adapt to high-volatility mid-cap environments.
- [x] **Post-Mortem Analysis**: Performed deep-dive data forensics on missed signals (e.g., COS, XAN, POLYX).
- [x] **Latency Reduction**: Refactored OHLCV fetch loops to reduce total scan cycle time by ~65%.

## 🚀 Future Roadmap
- [ ] **Multi-Exchange Scaling**: Extend scanning to OKX and Bybit using the same core logic.
- [ ] **Machine Learning Filter**: Add a LightGBM layer to predict "False Breakout" probability based on orderbook depth.
- [ ] **Automated Backtesting Suite**: Build a local module to replay historical data through the scanner for logic tuning.
