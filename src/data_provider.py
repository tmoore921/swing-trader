"""Market data provider — Twelve Data REST API.

Free tier: 800 requests/day, 8 requests/minute, no cost.
Set the API key via the TWELVEDATA_API_KEY environment variable.
Returns pandas DataFrames with Open/High/Low/Close/Volume indexed ascending by date,
so the rest of the codebase is provider-agnostic.
"""

import os
import sys
import time
import requests
import pandas as pd
from dotenv import load_dotenv

# Load .env if present (secondary path). The reliable path is an inline env var
# on the same command, e.g. `TWELVEDATA_API_KEY=... uv run python run_premarket.py`.
load_dotenv()

BASE_URL = "https://api.twelvedata.com"

# Stay under the 8 req/min free-tier limit (≈7.5s minimum spacing → use 8s).
_MIN_INTERVAL = float(os.getenv("TWELVEDATA_MIN_INTERVAL", "8"))
_last_call_ts = 0.0

# Transient-failure retry policy. A single network blip should not blank a whole
# trading day (a failed SPY/QQQ fetch forces the entire run DEFENSIVE).
_MAX_RETRIES = int(os.getenv("TWELVEDATA_MAX_RETRIES", "3"))
_RETRY_BACKOFF = float(os.getenv("TWELVEDATA_RETRY_BACKOFF", "2"))  # seconds, doubles each try
# Twelve Data error codes that are worth retrying (rate limit / server-side).
_TRANSIENT_CODES = {429, 500, 502, 503, 504}

# Last raw API error, for diagnostics
last_error: str | None = None

# Symbols that need remapping for Twelve Data
SYMBOL_MAP = {
    "^VIX": "VIX",
    "VIX": "VIX",
}


def _api_key() -> str:
    """Read the key at call time so callers can set it after import."""
    return os.getenv("TWELVEDATA_API_KEY", "demo")


def _throttle():
    global _last_call_ts
    elapsed = time.time() - _last_call_ts
    if elapsed < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - elapsed)
    _last_call_ts = time.time()


def get_history(ticker: str, outputsize: int = 500) -> pd.DataFrame | None:
    """Fetch daily OHLCV history. Returns ascending DataFrame or None on failure.

    outputsize=500 ≈ 2 trading years, enough for the 200-day SMA in Stage 2.
    On failure, the raw API message is stored in module-level `last_error`.
    """
    global last_error
    symbol = SYMBOL_MAP.get(ticker, ticker)

    for attempt in range(_MAX_RETRIES):
        _throttle()
        try:
            resp = requests.get(
                f"{BASE_URL}/time_series",
                params={
                    "symbol": symbol,
                    "interval": "1day",
                    "outputsize": outputsize,
                    "order": "ASC",
                    "apikey": _api_key(),
                },
                timeout=30,
            )
            data = resp.json()
            if data.get("status") != "ok" or "values" not in data:
                # Twelve Data returns {"code":..., "message":..., "status":"error"} on failure
                code = data.get("code")
                last_error = f"{ticker}: HTTP {resp.status_code} | {code} | {data.get('message') or data}"
                # Retry only transient (rate-limit / server-side) errors; a bad
                # symbol or bad key will never succeed on retry.
                if code in _TRANSIENT_CODES and attempt < _MAX_RETRIES - 1:
                    time.sleep(_RETRY_BACKOFF * (2 ** attempt))
                    continue
                return None

            df = pd.DataFrame(data["values"])
            if df.empty:
                return None

            rename = {
                "open": "Open", "high": "High", "low": "Low",
                "close": "Close", "volume": "Volume",
            }
            for src, dst in rename.items():
                if src in df.columns:
                    df[dst] = pd.to_numeric(df[src], errors="coerce")
                else:
                    df[dst] = pd.NA

            df["datetime"] = pd.to_datetime(df["datetime"])
            df = df.set_index("datetime").sort_index()
            return df[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"])
        except Exception as e:
            # Network-level failure — always transient, retry with backoff.
            last_error = f"{ticker}: request failed — {e}"
            if attempt < _MAX_RETRIES - 1:
                time.sleep(_RETRY_BACKOFF * (2 ** attempt))
                continue
            return None
    return None


def latest_close(ticker: str) -> float | None:
    """Convenience: most recent close price."""
    df = get_history(ticker, outputsize=5)
    if df is None or df.empty:
        return None
    return round(float(df["Close"].iloc[-1]), 2)


def api_key_configured() -> bool:
    return _api_key() not in ("", "demo", None)


if __name__ == "__main__":
    # Diagnostic self-test: `python -m src.data_provider [SYMBOL]`
    # Prints the raw outcome so we can tell a bad key from an unreachable API.
    sym = sys.argv[1] if len(sys.argv) > 1 else "SPY"
    key = _api_key()
    masked = (key[:4] + "…" + key[-4:]) if key and key != "demo" else key
    print(f"key in use: {masked}")
    df = get_history(sym, outputsize=10)
    if df is not None and not df.empty:
        print(f"OK — {sym} returned {len(df)} rows, last close {float(df['Close'].iloc[-1])}")
    else:
        print(f"FAILED — {sym} returned no data")
        print(f"reason: {last_error}")
