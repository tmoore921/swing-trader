"""Sector rotation: rank sector ETFs by recent performance vs SPY."""

import yfinance as yf
from config import SECTOR_ETFS, SECTOR_NAMES


def get_leading_sectors(lookback_days: int = 28, top_n: int = 3) -> list[dict]:
    """Return top N sector ETFs ranked by performance over lookback period."""
    period = f"{lookback_days + 10}d"

    spy_hist = yf.Ticker("SPY").history(period=period)
    spy_ret = _pct_return(spy_hist)

    results = []
    for ticker in SECTOR_ETFS:
        try:
            hist = yf.Ticker(ticker).history(period=period)
            if len(hist) < 5:
                continue
            ret = _pct_return(hist)
            results.append({
                "ticker": ticker,
                "name": SECTOR_NAMES.get(ticker, ticker),
                "return_pct": round(ret, 2),
                "vs_spy_pct": round(ret - spy_ret, 2),
                "outperforming_spy": ret > spy_ret,
            })
        except Exception:
            continue

    results.sort(key=lambda x: x["return_pct"], reverse=True)
    return results[:top_n]


def _pct_return(hist) -> float:
    close = hist["Close"]
    return float((close.iloc[-1] / close.iloc[0] - 1) * 100)
