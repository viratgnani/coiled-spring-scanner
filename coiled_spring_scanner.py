"""
Coiled Spring Scanner — Binance USDT Futures

Detects explosive price and volume breakouts on Binance USDT Perpetual contracts.
Sends real-time Telegram alerts.

Usage:
    python coiled_spring_scanner.py
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

SCAN_INTERVAL_SECONDS    = 5 * 60
LOOKBACK_MIN_CANDLES     = 168
LOOKBACK_MAX_CANDLES     = 720
BREAKOUT_LOOKBACK_HOURS  = 48
HEARTBEAT_INTERVAL_HOURS = 12
MIN_LISTING_AGE_DAYS     = 30
LISTING_CUTOFF_DATE      = datetime.now(tz=timezone.utc) - timedelta(days=MIN_LISTING_AGE_DAYS)

BLACKLIST = {"KATUSDT", "COPPERUSDT", "OPNUSDT", "LOBSTERUSDT"}

STD_DEV_RETURNS_MAX      = 0.0500
AVG_BODY_PCT_MAX         = 0.050
VOLUME_24H_MAX_USD       = 1_000_000_000
AVG_VOL_LOOKBACK         = 48
TRIGGER_BODY_MULTIPLE    = 3.0
TRIGGER_VOL_MULTIPLE     = 3.0
TRIGGER_CLOSE_ABOVE_HIGH = True
ALLOW_DUMP_THEN_PUMP     = True
DUMP_WICK_MIN_MULTIPLE   = 1.5
EMA_PERIOD               = 15

TELEGRAM_TOKEN           = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID         = os.environ.get("TELEGRAM_CHAT_ID", "")
TELEGRAM_ENABLED         = bool(TELEGRAM_TOKEN and TELEGRAM_CHAT_ID)

OHLCV_DELAY_SECONDS      = 0.25
FETCH_RETRY_ATTEMPTS     = 3
FETCH_RETRY_DELAY        = 5.0

# ==============================================================================
# LOGGING
# ==============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("coiled_spring.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("coiled_spring")

# ==============================================================================
# TELEGRAM
# ==============================================================================

def send_telegram(message: str) -> None:
    if not TELEGRAM_ENABLED:
        return
    try:
        import urllib.request, urllib.parse
        url  = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = urllib.parse.urlencode({
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": "true",
        }).encode()
        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status != 200:
                log.warning(f"Telegram failed: {resp.status}")
    except Exception as e:
        log.warning(f"Telegram error: {e}")

# ==============================================================================
# EXCHANGE
# ==============================================================================

def create_exchange() -> ccxt.binanceusdm:
    exchange = ccxt.binanceusdm({
        "enableRateLimit": True,
        "options": {"defaultType": "future", "adjustForTimeDifference": True},
    })
    exchange.load_markets()
    log.info(f"Markets loaded: {len(exchange.markets)}")
    return exchange

# ==============================================================================
# UNIVERSE
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
    valid = []
    for symbol, market in exchange.markets.items():
        if not market.get("active", False) or not market.get("linear", False):
            continue
        if market.get("type") not in ("swap", "future"):
            continue
        if market.get("quote", "") != "USDT" or market.get("settle", "") not in ("USDT", ""):
            continue
        if not (symbol.endswith("/USDT:USDT") or symbol.endswith("USDT")):
            continue

        base     = market.get("base", "")
        raw_id   = market.get("id", "").upper()
        tick_key = f"{base}USDT"
        if tick_key in BLACKLIST or raw_id in BLACKLIST:
            continue

        listing_dt = listing_date_from_market(market)
        if listing_dt and listing_dt > LISTING_CUTOFF_DATE:
            continue

        created = market.get("created")
        if listing_dt is None and created:
            try:
                dt = datetime.fromtimestamp(created / 1000, tz=timezone.utc)
                if dt > LISTING_CUTOFF_DATE:
                    continue
            except Exception:
                pass

        valid.append(symbol)

    valid.sort()
    log.info(f"Universe: {len(valid)} symbols")
    return valid

# ==============================================================================
# DATA FETCHING
# ==============================================================================

def fetch_ohlcv_safe(exchange, symbol) -> Optional[pd.DataFrame]:
    limit = LOOKBACK_MAX_CANDLES + 5
    for attempt in range(1, FETCH_RETRY_ATTEMPTS + 1):
        try:
            raw = exchange.fetch_ohlcv(symbol, timeframe="1h", limit=limit)
            if not raw or len(raw) < LOOKBACK_MIN_CANDLES + 2:
                return None
            df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
            for col in ["open", "high", "low", "close", "volume"]:
                df[col] = df[col].astype(float)
            return df.sort_values("timestamp").reset_index(drop=True)
        except ccxt.RateLimitExceeded:
            time.sleep(FETCH_RETRY_DELAY * attempt)
        except Exception:
            time.sleep(FETCH_RETRY_DELAY)
    return None

# ==============================================================================
# INDICATORS
# ==============================================================================

def ema(series: np.ndarray, period: int) -> np.ndarray:
    result = np.empty_like(series, dtype=float)
    if len(series) == 0:
        return result
    k = 2.0 / (period + 1)
    result[0] = series[0]
    for i in range(1, len(series)):
        result[i] = series[i] * k + result[i - 1] * (1 - k)
    return result

# ==============================================================================
# ANALYSIS
# ==============================================================================

class AnalysisResult:
    def __init__(self, symbol):
        self.symbol = symbol
        self.is_coiled = self.triggered = self.is_dump_then_pump = False
        self.flat_candles = 0
        self.std_dev_returns = self.avg_body_pct = 0.0
        self.avg_volume_usd = self.flat_high = self.flat_low = 0.0
        self.last_close = self.last_volume_usd = 0.0
        self.trigger_body_multiple = self.trigger_vol_multiple = 0.0
        self.trigger_close_pct_above_high = self.ema15 = 0.0

def analyze_symbol(df: pd.DataFrame, symbol: str) -> AnalysisResult:
    result = AnalysisResult(symbol)
    if len(df) < LOOKBACK_MIN_CANDLES + 2:
        return result

    trigger_row = df.iloc[-1]
    flat_df = df.iloc[-(LOOKBACK_MAX_CANDLES + 1):-1].iloc[-LOOKBACK_MAX_CANDLES:]

    closes = flat_df["close"].values
    opens  = flat_df["open"].values
    highs  = flat_df["high"].values
    lows   = flat_df["low"].values
    vols   = flat_df["volume"].values

    # Volatility filter
    returns = np.diff(closes) / closes[:-1]
    std_ret = float(np.std(returns, ddof=1))
    result.std_dev_returns = std_ret
    if std_ret > STD_DEV_RETURNS_MAX:
        return result

    # Body size filter
    bodies_pct = np.abs(closes - opens) / np.where(opens > 0, opens, 1.0) * 100.0
    avg_body = float(np.mean(bodies_pct))
    result.avg_body_pct = avg_body
    if avg_body > AVG_BODY_PCT_MAX * 100:
        return result

    # Volume filter
    avg_close   = float(np.mean(closes[-AVG_VOL_LOOKBACK:]))
    avg_vol_usd = float(np.mean(vols[-AVG_VOL_LOOKBACK:])) * avg_close
    result.avg_volume_usd = avg_vol_usd
    if avg_vol_usd * 24 > VOLUME_24H_MAX_USD:
        return result

    result.is_coiled    = True
    result.flat_candles = len(flat_df)
    result.flat_high    = float(np.max(df.iloc[-(BREAKOUT_LOOKBACK_HOURS + 1):-1]["high"].values))
    result.flat_low     = float(np.min(lows))
    result.last_close   = float(trigger_row["close"])
    result.ema15        = float(ema(df["close"].values, EMA_PERIOD)[-1])

    t_open  = float(trigger_row["open"])
    t_close = float(trigger_row["close"])
    t_vol   = float(trigger_row["volume"])
    t_vol_usd = t_vol * t_close
    t_body_pct = abs(t_close - t_open) / (t_open if t_open > 0 else 1.0) * 100.0

    result.trigger_body_multiple = t_body_pct / avg_body if avg_body > 0 else 0.0
    result.trigger_vol_multiple  = t_vol_usd / avg_vol_usd if avg_vol_usd > 0 else 0.0
    result.trigger_close_pct_above_high = (t_close - result.flat_high) / result.flat_high * 100.0

    body_ok = result.trigger_body_multiple >= TRIGGER_BODY_MULTIPLE
    vol_ok  = result.trigger_vol_multiple  >= TRIGGER_VOL_MULTIPLE
    high_ok = (not TRIGGER_CLOSE_ABOVE_HIGH) or (t_close > result.flat_high)

    if t_close > t_open and body_ok and vol_ok and high_ok:
        result.triggered = True
    elif ALLOW_DUMP_THEN_PUMP:
        prev = flat_df.iloc[-1]
        p_o, p_c, p_l = float(prev["open"]), float(prev["close"]), float(prev["low"])
        p_body = abs(p_c - p_o)
        if p_body > 0 and (min(p_o, p_c) - p_l) / p_body >= DUMP_WICK_MIN_MULTIPLE:
            if t_close > t_open and vol_ok and body_ok:
                result.triggered = result.is_dump_then_pump = True

    return result

# ==============================================================================
# ALERT
# ==============================================================================

def format_alert(r: AnalysisResult) -> str:
    pattern = "🔄 DUMP→PUMP" if r.is_dump_then_pump else "🟢 PUMP"
    stop = round(min(r.flat_low * 0.995, r.ema15 * 0.995), 6)
    return (
        f"🚨 <b>COILED SPRING TRIGGER</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"<b>{r.symbol}</b> | {pattern}\n"
        f"<b>Price:</b> {r.last_close:.6f} USDT\n"
        f"<b>Break above floor:</b> {r.trigger_close_pct_above_high:+.2f}%\n"
        f"<b>Body spike:</b> {r.trigger_body_multiple:.1f}×\n"
        f"<b>Volume spike:</b> {r.trigger_vol_multiple:.1f}×\n"
        f"<b>Flat:</b> {round(r.flat_candles/24,1)}d | Range: {r.flat_low:.6f}–{r.flat_high:.6f}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📈 Entry: above <code>{r.flat_high:.6f}</code>\n"
        f"🛑 Stop: ~<code>{stop:.6f}</code>\n"
        f"⚠️ 1–2% risk | partials at 2×R and 4×R"
    )

# ==============================================================================
# MAIN LOOP
# ==============================================================================

def run_forever():
    log.info("=" * 60)
    log.info("  COILED SPRING SCANNER  —  Binance USDT Perps")
    log.info(f"  Scan interval: {SCAN_INTERVAL_SECONDS // 60} min | Telegram: {'ON' if TELEGRAM_ENABLED else 'off'}")
    log.info("=" * 60)

    send_telegram("🛰️ <b>Coiled Spring Scanner ONLINE</b>\nMonitoring Binance USDT Futures every 5 minutes.")

    exchange = None
    last_market_reload = 0.0
    last_heartbeat = 0.0

    while True:
        now = time.time()
        try:
            # Heartbeat every 12h
            if (now - last_heartbeat) > (HEARTBEAT_INTERVAL_HOURS * 3600):
                send_telegram(f"🛰️ <b>Sniper Heartbeat</b>\nStatus: 🟢 Online\nCycle: {SCAN_INTERVAL_SECONDS//60}m")
                last_heartbeat = now

            # Reload markets every 6h
            if exchange is None or (now - last_market_reload) > 21600:
                log.info("Loading markets...")
                exchange = create_exchange()
                symbols = get_valid_symbols(exchange)
                last_market_reload = now

            if not symbols:
                log.error("No valid symbols — check filters.")
                time.sleep(300)
                continue

            coiled, triggered = [], []
            total = len(symbols)

            for idx, symbol in enumerate(symbols, 1):
                if idx % 50 == 0 or idx == total:
                    log.info(f"  Progress: {idx}/{total}")

                df = fetch_ohlcv_safe(exchange, symbol)
                if df is not None:
                    res = analyze_symbol(df, symbol)
                    if res.triggered:
                        triggered.append(res)
                    elif res.is_coiled:
                        coiled.append(res)

                time.sleep(OHLCV_DELAY_SECONDS)

            log.info(f"Scan complete → {len(coiled)} coiled | {len(triggered)} triggered")

            for r in triggered:
                log.info(f"🚨 TRIGGER: {r.symbol} @ {r.last_close}")
                print(format_alert(r))
                send_telegram(format_alert(r))

            if not triggered:
                log.info("No triggers this cycle.")

            sleep_for = max(0, SCAN_INTERVAL_SECONDS - (time.time() - now))
            log.info(f"Next scan in {sleep_for:.0f}s")
            time.sleep(sleep_for)

        except KeyboardInterrupt:
            log.info("Stopped by user.")
            sys.exit(0)
        except Exception as e:
            log.error(f"Loop error: {e}")
            log.debug(traceback.format_exc())
            time.sleep(60)

if __name__ == "__main__":
    run_forever()
