import os
from datetime import datetime, timezone, timedelta

# ==============================================================================
# SCANNER CORE CONFIGURATION
# ==============================================================================

# -- Scan Timing --
SCAN_INTERVAL_SECONDS    = 5 * 60           # 5 min cycle
CANDLE_TIMEFRAME         = "1h"
LOOKBACK_MIN_CANDLES     = 168              # 1 week baseline
LOOKBACK_MAX_CANDLES     = 720              # 30 day max history
BREAKOUT_LOOKBACK_HOURS  = 48               # 2-day breakout ceiling
HEARTBEAT_INTERVAL_HOURS = 12               # Status check

# -- Universe filters --
MIN_LISTING_AGE_DAYS     = 30              
LISTING_CUTOFF_DATE      = datetime.now(tz=timezone.utc) - timedelta(days=MIN_LISTING_AGE_DAYS)

# Symbols/Tickers to ignore
BLACKLIST = {
    "KATUSDT", "COPPERUSDT", "OPNUSDT", "LOBSTERUSDT",
}

# -- Coiled Detection (Pre-Filter) Thresholds --
STD_DEV_RETURNS_MAX      = 0.0500          # 5.0% - Volatility ceiling
AVG_BODY_PCT_MAX         = 0.050           # 5.0% - Candle body average
BB_WIDTH_NEAR_LOW_FACTOR = 10.00          # Bollinger compression
VOLUME_24H_MAX_USD       = 1_000_000_000  # $1B Limit
AVG_VOL_LOOKBACK         = 48             # Candles for volume floor

# -- Trigger Logic (The Sniper) --
TRIGGER_BODY_MULTIPLE    = 3.0            # Trigger candle vs Average
TRIGGER_VOL_MULTIPLE     = 3.0            # Volume surge vs Average
TRIGGER_CLOSE_ABOVE_HIGH = True           # Must break resistance

# Reversal candle detection
ALLOW_DUMP_THEN_PUMP     = True
DUMP_WICK_MIN_MULTIPLE   = 1.5           # Shadow vs Body ratio

# -- Indicators --
EMA_PERIOD               = 15

# ==============================================================================
# SYSTEM & INTEGRATION
# ==============================================================================

# -- Logging & Display --
SHOW_MAX_COILED          = 20
LOG_LEVEL                = "INFO"

# -- API Rate Limiting --
OHLCV_DELAY_SECONDS      = 0.25          
FETCH_RETRY_ATTEMPTS     = 3             
FETCH_RETRY_DELAY        = 5.0

# -- Telegram Alerts --
TELEGRAM_TOKEN    = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID  = os.environ.get("TELEGRAM_CHAT_ID", "")
TELEGRAM_ENABLED  = bool(TELEGRAM_TOKEN and TELEGRAM_CHAT_ID)
