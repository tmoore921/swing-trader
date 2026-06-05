"""Chart pattern detection using OHLCV data.

Detects: VCP, Bull Flag, Flat Base, Pullback to 20 EMA.
Cup & Handle requires longer visual inspection — flagged for agent review.
Priority order (highest conviction first): VCP > Bull Flag > Flat Base > Pullback to 20 EMA.
"""

import yfinance as yf
import numpy as np
from config import EXTENDED_ABOVE_PIVOT_PCT, BUY_SIGNAL_THRESHOLD_PCT

PATTERN_PRIORITY = ["VCP", "Bull Flag", "Flat Base", "Pullback to 20 EMA"]


def detect_pattern(ticker: str) -> dict:
    """Return the highest-conviction pattern found, or NO SETUP."""
    try:
        hist = yf.Ticker(ticker).history(period="1y")
        if len(hist) < 60:
            return {"pattern": "INSUFFICIENT_DATA", "pivot": None, "extended": False}

        close = hist["Close"].astype(float)
        high = hist["High"].astype(float)
        low = hist["Low"].astype(float)
        volume = hist["Volume"].astype(float)
        ema20 = close.ewm(span=20, adjust=False).mean()
        current = float(close.iloc[-1])

        candidates = []
        for name, fn in [
            ("VCP", _check_vcp),
            ("Bull Flag", _check_bull_flag),
            ("Flat Base", _check_flat_base),
            ("Pullback to 20 EMA", _check_pullback_ema),
        ]:
            result = fn(close, high, low, volume, ema20)
            if result.get("detected"):
                candidates.append((name, result))

        if not candidates:
            return {
                "pattern": "NO SETUP",
                "pivot": None,
                "extended": False,
                "note": "No actionable pattern detected — watch for future base formation",
            }

        best_name, best = min(
            candidates, key=lambda x: PATTERN_PRIORITY.index(x[0]) if x[0] in PATTERN_PRIORITY else 99
        )
        pivot = best.get("pivot")
        extended = bool(pivot and current > pivot * (1 + EXTENDED_ABOVE_PIVOT_PCT))
        ready_to_buy = bool(pivot and not extended and current >= pivot * (1 - 0.01))
        pct_from_pivot = round((current / pivot - 1) * 100, 2) if pivot else None

        return {
            "pattern": best_name,
            "pivot": round(float(pivot), 2) if pivot else None,
            "extended": extended,
            "ready_to_buy": ready_to_buy,
            "pct_from_pivot": pct_from_pivot,
            "volume_confirmation": best.get("volume_ok", False),
            "details": {k: v for k, v in best.items() if k not in ("detected",)},
            "all_detected": [n for n, _ in candidates],
        }
    except Exception as e:
        return {"pattern": "ERROR", "pivot": None, "extended": False, "error": str(e)}


def _check_vcp(close, high, low, volume, ema20) -> dict:
    """VCP: 3+ successive weekly contractions in range and volume."""
    if len(close) < 30:
        return {"detected": False}

    weekly_ranges = []
    weekly_vols = []
    for i in range(6):
        s = -(i + 1) * 5
        e = -i * 5 if i > 0 else None
        if abs(s) > len(close):
            break
        seg_h = float(high.iloc[s:e].max())
        seg_l = float(low.iloc[s:e].min())
        weekly_ranges.append((seg_h - seg_l) / seg_l * 100)
        weekly_vols.append(float(volume.iloc[s:e].mean()))

    if len(weekly_ranges) < 3:
        return {"detected": False}

    contractions = sum(1 for i in range(len(weekly_ranges) - 1) if weekly_ranges[i] < weekly_ranges[i + 1])
    vol_contracting = all(
        weekly_vols[i] < weekly_vols[i + 1] for i in range(min(2, len(weekly_vols) - 1))
    )
    detected = contractions >= 2 and weekly_ranges[0] < weekly_ranges[1]

    return {
        "detected": detected,
        "pivot": float(high.iloc[-5:].max()) if detected else None,
        "contractions": contractions,
        "weekly_ranges": [round(r, 1) for r in weekly_ranges],
        "volume_ok": vol_contracting,
    }


def _check_bull_flag(close, high, low, volume, ema20) -> dict:
    """Bull Flag: sharp 15%+ advance, then 3–15 day tight pullback 5–15% on declining volume."""
    lookback = min(20, len(close) - 1)
    pole_start = float(close.iloc[-(lookback + 1)])
    pole_high = float(close.iloc[-lookback:].max())
    pole_advance = (pole_high / pole_start - 1) * 100

    if pole_advance < 15:
        return {"detected": False}

    pole_high_idx = int(close.iloc[-lookback:].argmax())
    days_since_peak = lookback - pole_high_idx

    if not (3 <= days_since_peak <= 15):
        return {"detected": False}

    current = float(close.iloc[-1])
    flag_pullback = (pole_high - current) / pole_high * 100

    if not (5 <= flag_pullback <= 15):
        return {"detected": False}

    flag_vol = float(volume.iloc[-days_since_peak:].mean())
    pole_vol = float(volume.iloc[-lookback:-days_since_peak].mean()) if days_since_peak < lookback else flag_vol
    vol_declining = flag_vol < pole_vol

    pivot = float(high.iloc[-days_since_peak:].max())

    return {
        "detected": True,
        "pivot": pivot,
        "pole_advance_pct": round(pole_advance, 1),
        "flag_pullback_pct": round(flag_pullback, 1),
        "days_in_flag": days_since_peak,
        "volume_ok": vol_declining,
    }


def _check_flat_base(close, high, low, volume, ema20) -> dict:
    """Flat Base: 5–15 weeks, total range <15%, volume contracting."""
    for weeks in range(5, 16):
        days = weeks * 5
        if days > len(close):
            break
        seg_high = float(high.iloc[-days:].max())
        seg_low = float(low.iloc[-days:].min())
        range_pct = (seg_high / seg_low - 1) * 100

        if range_pct < 15:
            mid = days // 2
            first_vol = float(volume.iloc[-days:-mid].mean())
            second_vol = float(volume.iloc[-mid:].mean())
            return {
                "detected": True,
                "pivot": round(seg_high + 0.10, 2),
                "base_weeks": weeks,
                "range_pct": round(range_pct, 1),
                "volume_ok": second_vol < first_vol,
            }

    return {"detected": False}


def _check_pullback_ema(close, high, low, volume, ema20) -> dict:
    """Pullback to 20 EMA: near EMA in uptrend, volume declining on pullback."""
    current = float(close.iloc[-1])
    ema_now = float(ema20.iloc[-1])
    pct_from_ema = (current / ema_now - 1) * 100

    near_ema = abs(pct_from_ema) < 2.0
    above_ema_count = int((close.iloc[-60:].values > ema20.iloc[-60:].values).sum())
    in_uptrend = above_ema_count > 40

    recent_vol = float(volume.iloc[-5:].mean())
    prior_vol = float(volume.iloc[-20:-5].mean())
    vol_declining = recent_vol < prior_vol

    pivot = float(high.iloc[-3:].max())

    return {
        "detected": near_ema and in_uptrend and vol_declining,
        "pivot": pivot if (near_ema and in_uptrend) else None,
        "pct_from_ema": round(pct_from_ema, 2),
        "volume_ok": vol_declining,
        "days_above_ema_of_60": above_ema_count,
    }
