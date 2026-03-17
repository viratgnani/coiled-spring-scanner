"""
Coiled Spring Scanner — Binance USDT Futures

A high-performance algorithmic scanner designed to detect explosive price 
and volume breakouts on Binance USDT Perpetual contracts.

Usage:
    python coiled_spring_scanner.py

Requirements:
    pip install ccxt numpy pandas
"""

import os
import sys
import time
import logging
import traceback
from datetime import datetime, timezone, timedelta
from typing import Optional

import ccxt
import numpy as np
import pandas as pd

# ==============================================================================
# CONFIGURATION
# ==============================================================================

# -- Scan Timing --
SCAN_INTERVAL_SECONDS    = 5 * 60           # 5 min cycle
CANDLE_TIMEFRAME         = "1h"
LOOKBACK_MIN_CANDLES     = 168              # 1 week baseline
LOOKBACK_MAX_CANDLES     = 720              # 30 day max history
BREAKOUT_LOOKBACK_HOURS  = 48               # 2-day breakout ceiling
HEARTBEAT_INTERVAL_HOURS = 12               # Status check

# -- Universe filters --
MIN_LISTING_AGE_DAYS     = 30              # Catch coins after 1 month
LISTING_CUTOFF_DATE      = datetime.now(tz=timezone.utc) - timedelta(days=MIN_LISTING_AGE_DAYS)

# Hard blacklist
BLACKLIST = {
    "KATUSDT", "COPPERUSDT", "OPNUSDT", "LOBSTERUSDT",
}

# -- Coiled Detection Thresholds --
STD_DEV_RETURNS_MAX      = 0.0500          # 5.0% - Allow some volatility
AVG_BODY_PCT_MAX         = 0.050           # 5.0% - Allow trending
BB_WIDTH_NEAR_LOW_FACTOR = 10.00          # BB compression factor
VOLUME_24H_MAX_USD       = 1_000_000_000  # $1B Limit
AVG_VOL_LOOKBACK         = 48             # Candles for baseline volume

# -- Trigger Thresholds --
TRIGGER_BODY_MULTIPLE    = 3.0            # Relative body spikes
TRIGGER_VOL_MULTIPLE     = 3.0            # Relative volume spikes
TRIGGER_CLOSE_ABOVE_HIGH = True           # Must break lookback high

# Reversal pattern
ALLOW_DUMP_THEN_PUMP     = True
DUMP_WICK_MIN_MULTIPLE   = 1.5           # Lower shadow requirement

# -- Indicators --
EMA_PERIOD               = 15

# -- Output --
SHOW_MAX_COILED          = 20
LOG_LEVEL                = logging.INFO

# -- Telegram --
TELEGRAM_TOKEN    = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID  = os.environ.get("TELEGRAM_CHAT_ID", "")
TELEGRAM_ENABLED  = bool(TELEGRAM_TOKEN and TELEGRAM_CHAT_ID)

# -- Rate Limiting --
OHLCV_DELAY_SECONDS      = 0.25          
FETCH_RETRY_ATTEMPTS     = 3             
FETCH_RETRY_DELAY        = 5.0

# ==============================================================================
# LOGGING SETUP
# ==============================================================================

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("coiled_spring.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("coiled_spring")

# ==============================================================================
# TELEGRAM SENDER
# ==============================================================================

def send_telegram(message: str) -> None:
    """Send a Telegram message via Bot API."""
    if not TELEGRAM_ENABLED:
        return
    try:
        import urllib.request
        import urllib.parse
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = urllib.parse.urlencode({
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": "true",
        }).encode()
        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status != 200:
                log.warning(f"Telegram send failed: status={resp.status}")
    except Exception as e:
        log.warning(f"Telegram error: {e}")

# ==============================================================================
# EXCHANGE SETUP
# ==============================================================================

def create_exchange() -> ccxt.binanceusdm:
    """Create and configure a ccxt Binance USDM futures instance."""
    exchange = ccxt.binanceusdm({
        "enableRateLimit": True,
        "options": {
            "defaultType": "future",
            "adjustForTimeDifference": True,
        },
    })
    exchange.load_markets()
    log.info(f"Exchange loaded: {len(exchange.markets)} markets total.")
    return exchange

# ==============================================================================
# UNIVERSE FILTERING
# ==============================================================================

def listing_date_from_market(market: dict) -> Optional[datetime]:
    info = market.get("info", {})
    for key in ("onboardDate", "deliveryDate", "listingDate"):
        val = info.get(key)
        if val:
            try:
                ts = int(val)
                if ts > 1e12:
                    ts //= 1000
                return datetime.fromtimestamp(ts, tz=timezone.utc)
            except Exception:
                pass
    return None

def get_valid_symbols(exchange: ccxt.binanceusdm) -> list:
    """Filter market universe based on age, type, and blacklist."""
    valid = []
    for symbol, market in exchange.markets.items():
        if not market.get("active", False) or not market.get("linear", False):
            continue
        if market.get("type") not in ("swap", "future"):
            continue
        if market.get("quote", "") != "USDT" or market.get("settle", "") not in ("USDT", ""):
            continue
        if not symbol.endswith("/USDT:USDT") and not symbol.endswith("USDT"):
            continue

        base = market.get("base", "")
        raw_id = market.get("id", "").upper()
        ticker_key = f"{base}USDT"
        if ticker_key in BLACKLIST or raw_id in BLACKLIST:
            continue

        listing_dt = listing_date_from_market(market)
        if listing_dt and listing_dt > LISTING_CUTOFF_DATE:
            continue
        
        valid.append(symbol)

    valid.sort()
    log.info(f"Universe: {len(valid)} eligible symbols after filtering.")
    return valid

# ==============================================================================
# DATA FETCHING
# ==============================================================================

def fetch_ohlcv_safe(
    exchange: ccxt.binanceusdm,
    symbol: str,
    timeframe: str = "1h",
    limit: int = LOOKBACK_MAX_CANDLES + 5,
) -> Optional[pd.DataFrame]:
    """Fetch OHLCV candles with retry logic."""
    for attempt in range(1, FETCH_RETRY_ATTEMPTS + 1):
        try:
            raw = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
            if not raw or len(raw) < LOOKBACK_MIN_CANDLES + 2:
                return None
            df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
            for col in ["open", "high", "low", "close", "volume"]:
                df[col] = df[col].astype(float)
            df = df.sort_values("timestamp").reset_index(drop=True)
            return df
        except ccxt.RateLimitExceeded:
            time.sleep(FETCH_RETRY_DELAY * attempt)
        except Exception:
            time.sleep(FETCH_RETRY_DELAY)
    return None

# ==============================================================================
# TECHNICALS
# ==============================================================================

def ema(series: np.ndarray, period: int) -> np.ndarray:
    result = np.empty_like(series, dtype=float)
    if len(series) == 0: return result
    k = 2.0 / (period + 1)
    result[0] = series[0]
    for i in range(1, len(series)):
        result[i] = series[i] * k + result[i - 1] * (1 - k)
    return result

def bollinger_bands(closes: np.ndarray, period: int = 20, std_mult: float = 2.0):
    widths = np.full(len(closes), np.nan)
    for i in range(period - 1, len(closes)):
        window = closes[i - period + 1 : i + 1]
        mid, std = np.mean(window), np.std(window)
        if mid > 0: widths[i] = (2 * std_mult * std) / mid
    return widths

# ==============================================================================
# ANALYSIS ENGINE
# ==============================================================================

class AnalysisResult:
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.is_coiled = False
        self.triggered = False
        self.is_dump_then_pump = False
        self.flat_candles = 0
        self.std_dev_returns = 0.0
        self.avg_body_pct = 0.0
        self.bb_width_ratio = 0.0
        self.avg_volume_usd = 0.0
        self.flat_high = 0.0
        self.flat_low = 0.0
        self.last_close = 0.0
        self.last_volume_usd = 0.0
        self.trigger_body_multiple = 0.0
        self.trigger_vol_multiple = 0.0
        self.trigger_close_pct_above_high = 0.0
        self.ema15 = 0.0

def analyze_symbol(df: pd.DataFrame, symbol: str) -> AnalysisResult:
    result = AnalysisResult(symbol)
    if len(df) < LOOKBACK_MIN_CANDLES + 2: return result

    trigger_row = df.iloc[-1]
    flat_df = df.iloc[-(LOOKBACK_MAX_CANDLES + 1):-1].iloc[-LOOKBACK_MAX_CANDLES:]
    
    closes, opens, highs, lows, vols = \
        flat_df["close"].values, flat_df["open"].values, flat_df["high"].values, flat_df["low"].values, flat_df["volume"].values

    returns = np.diff(closes) / closes[:-1]
    std_ret = float(np.std(returns, ddof=1))
    result.std_dev_returns = std_ret
    if std_ret > STD_DEV_RETURNS_MAX: return result

    bodies_pct = np.abs(closes - opens) / np.where(opens > 0, opens, 1.0) * 100.0
    avg_body = float(np.mean(bodies_pct))
    result.avg_body_pct = avg_body
    if avg_body > AVG_BODY_PCT_MAX * 100: return result

    avg_close = float(np.mean(closes[-AVG_VOL_LOOKBACK:]))
    avg_vol_flat = float(np.mean(vols[-AVG_VOL_LOOKBACK:]))
    avg_vol_usd = avg_vol_flat * avg_close
    result.avg_volume_usd = avg_vol_usd
    if avg_vol_usd * 24 > VOLUME_24H_MAX_USD: return result

    result.is_coiled = True
    result.flat_candles = len(flat_df)
    result.flat_high = float(np.max(df.iloc[-(BREAKOUT_LOOKBACK_HOURS + 1):-1]["high"].values))
    result.flat_low = float(np.min(lows))
    result.last_close = float(trigger_row["close"])
    result.ema15 = float(ema(df["close"].values, EMA_PERIOD)[-1])

    t_open, t_close, t_vol = float(trigger_row["open"]), float(trigger_row["close"]), float(trigger_row["volume"])
    t_vol_usd = t_vol * t_close
    t_body_pct = abs(t_close - t_open) / (t_open if t_open > 0 else 1.0) * 100.0
    
    result.trigger_body_multiple = t_body_pct / avg_body if avg_body > 0 else 0.0
    result.trigger_vol_multiple = t_vol_usd / avg_vol_usd if avg_vol_usd > 0 else 0.0
    result.trigger_close_pct_above_high = (t_close - result.flat_high) / result.flat_high * 100.0

    body_ok = result.trigger_body_multiple >= TRIGGER_BODY_MULTIPLE
    vol_ok = result.trigger_vol_multiple >= TRIGGER_VOL_MULTIPLE
    high_ok = (not TRIGGER_CLOSE_ABOVE_HIGH) or (t_close > result.flat_high)

    if (t_close > t_open) and body_ok and vol_ok and high_ok:
        result.triggered = True
    elif ALLOW_DUMP_THEN_PUMP:
        prev = flat_df.iloc[-1]
        p_o, p_c, p_l = float(prev["open"]), float(prev["close"]), float(prev["low"])
        if abs(p_c - p_o) > 0 and (min(p_o, p_c) - p_l) / abs(p_c - p_o) >= DUMP_WICK_MIN_MULTIPLE:
            if t_close > t_open and vol_ok and body_ok:
                result.triggered, result.is_dump_then_pump = True, True

    return result

# ==============================================================================
# MAIN LOOP
# ==============================================================================

def run_forever():
    log.info("Starting Coiled Spring Sniper...")
    exchange, last_market_reload, last_heartbeat = None, 0.0, 0.0

    while True:
        now = time.time()
        try:
            if (now - last_heartbeat) > (HEARTBEAT_INTERVAL_HOURS * 3600):
                send_telegram(f"🛰️ <b>Sniper Heartbeat</b>\nStatus: Online\nCycle: {SCAN_INTERVAL_SECONDS/60:.1f}m")
                last_heartbeat = now

            if exchange is None or (now - last_market_reload) > 21600:
                exchange = create_exchange()
                symbols = get_valid_symbols(exchange)
                last_market_reload = now

            coiled, triggered = [], []
            for idx, symbol in enumerate(symbols, 1):
                if idx % 50 == 0: log.info(f"Progress: {idx}/{len(symbols)}")
                df = fetch_ohlcv_safe(exchange, symbol)
                if df is not None:
                    res = analyze_symbol(df, symbol)
                    if res.triggered:
                        triggered.append(res)
                        print(f"🚨 TRIGGER: {symbol} @ {res.last_close}")
                        # Simple Telegram Alert
                        send_telegram(f"🚨 <b>{symbol} TRIGGER</b>\nPrice: {res.last_close}\nVol: {res.trigger_vol_multiple:.1f}x")
                    elif res.is_coiled:
                        coiled.append(res)
                time.sleep(OHLCV_DELAY_SECONDS)

            log.info(f"Scan complete. {len(coiled)} coiled, {len(triggered)} triggered.")
            time.sleep(max(0, SCAN_INTERVAL_SECONDS - (time.time() - now)))

        except Exception as e:
            log.error(f"Loop Error: {e}")
            time.sleep(60)

if __name__ == "__main__":
    run_forever()
