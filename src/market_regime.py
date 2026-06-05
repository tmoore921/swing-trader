"""Market regime check: SPY, QQQ trend structure + VIX level."""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta


def _analyze_etf(ticker: str) -> dict:
    hist = yf.Ticker(ticker).history(period="1y")
    if len(hist) < 200:
        raise ValueError(f"Insufficient history for {ticker}")

    close = hist["Close"]
    current = close.iloc[-1]
    sma50 = close.rolling(50).mean()
    sma200 = close.rolling(200).mean()

    return {
        "ticker": ticker,
        "price": round(float(current), 2),
        "sma50": round(float(sma50.iloc[-1]), 2),
        "sma200": round(float(sma200.iloc[-1]), 2),
        "above_sma50": bool(current > sma50.iloc[-1]),
        "sma50_above_sma200": bool(sma50.iloc[-1] > sma200.iloc[-1]),
        "sma50_sloping_up": bool(sma50.iloc[-1] > sma50.iloc[-5]),
    }


def check_market_regime() -> dict:
    """Return market stance and supporting data for SPY, QQQ, VIX."""
    spy = _analyze_etf("SPY")
    qqq = _analyze_etf("QQQ")

    vix_hist = yf.Ticker("^VIX").history(period="5d")
    vix = round(float(vix_hist["Close"].iloc[-1]), 2)

    conditions_met = sum([
        spy["above_sma50"],
        spy["sma50_above_sma200"],
        spy["sma50_sloping_up"],
        qqq["above_sma50"],
        qqq["sma50_above_sma200"],
        qqq["sma50_sloping_up"],
    ])

    if vix > 30:
        stance = "HALT"
    elif vix > 25:
        stance = "DEFENSIVE"
    elif conditions_met >= 5 and vix < 20:
        stance = "AGGRESSIVE"
    elif conditions_met >= 4:
        stance = "SELECTIVE"
    else:
        stance = "DEFENSIVE"

    return {
        "stance": stance,
        "vix": vix,
        "conditions_met": conditions_met,
        "spy": spy,
        "qqq": qqq,
    }
