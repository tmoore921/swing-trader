"""Fundamental quality screen: EPS growth, revenue growth, relative strength."""

import yfinance as yf


def check_fundamentals(ticker: str) -> dict:
    """Score EPS growth, revenue growth, and 6-month RS vs SPY."""
    try:
        t = yf.Ticker(ticker)
        info = t.info or {}

        eps_growth = _eps_growth_yoy(t)
        rev_growth = _revenue_growth_yoy(t)
        rs_6m = _rs_vs_spy_6m(ticker)

        eps_rating = _rate(eps_growth, pass_thresh=25, marginal_thresh=15)
        rev_rating = _rate(rev_growth, pass_thresh=20, marginal_thresh=10)
        rs_rating = "PASS" if (rs_6m is not None and rs_6m > 15) else "FAIL"

        fails = sum([eps_rating == "FAIL", rev_rating == "FAIL"])
        passes = sum([eps_rating == "PASS", rev_rating == "PASS", rs_rating == "PASS"])

        if fails >= 2:
            quality = "DISQUALIFIED"
        elif passes >= 3:
            quality = "HIGH"
        elif passes >= 2:
            quality = "MODERATE"
        else:
            quality = "MODERATE"  # marginals everywhere — let the agent judge

        return {
            "ticker": ticker,
            "quality": quality,
            "disqualified": fails >= 2,
            "eps_growth_pct": round(eps_growth, 1) if eps_growth is not None else None,
            "rev_growth_pct": round(rev_growth, 1) if rev_growth is not None else None,
            "rs_vs_spy_6m": rs_6m,
            "eps_rating": eps_rating,
            "rev_rating": rev_rating,
            "rs_rating": rs_rating,
        }
    except Exception as e:
        return {"ticker": ticker, "quality": "UNKNOWN", "disqualified": False, "error": str(e)}


def _eps_growth_yoy(t) -> float | None:
    try:
        earnings = t.quarterly_earnings
        if earnings is None or len(earnings) < 5:
            return None
        recent = float(earnings["Earnings"].iloc[0])
        year_ago = float(earnings["Earnings"].iloc[4])
        if year_ago == 0:
            return None
        return (recent / abs(year_ago) - 1) * 100
    except Exception:
        return None


def _revenue_growth_yoy(t) -> float | None:
    try:
        fin = t.quarterly_financials
        if fin is None or "Total Revenue" not in fin.index or len(fin.columns) < 5:
            return None
        recent = float(fin.loc["Total Revenue"].iloc[0])
        year_ago = float(fin.loc["Total Revenue"].iloc[4])
        if year_ago == 0:
            return None
        return (recent / year_ago - 1) * 100
    except Exception:
        return None


def _rs_vs_spy_6m(ticker: str) -> float | None:
    try:
        import yfinance as yf
        stock = yf.Ticker(ticker).history(period="6mo")
        spy = yf.Ticker("SPY").history(period="6mo")
        if len(stock) < 5 or len(spy) < 5:
            return None
        stock_ret = float((stock["Close"].iloc[-1] / stock["Close"].iloc[0] - 1) * 100)
        spy_ret = float((spy["Close"].iloc[-1] / spy["Close"].iloc[0] - 1) * 100)
        return round(stock_ret - spy_ret, 1)
    except Exception:
        return None


def _rate(value: float | None, pass_thresh: float, marginal_thresh: float) -> str:
    if value is None:
        return "UNKNOWN"
    if value >= pass_thresh:
        return "PASS"
    if value >= marginal_thresh:
        return "MARGINAL"
    return "FAIL"
