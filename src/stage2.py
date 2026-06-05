"""Stage 2 trend template: all 5 conditions must pass."""

import yfinance as yf


def check_stage2(ticker: str) -> dict:
    """Return pass/fail for each of the 5 Stage 2 conditions."""
    try:
        hist = yf.Ticker(ticker).history(period="2y")
        if len(hist) < 210:
            return {"passes": False, "reason": "insufficient_history", "ticker": ticker}

        close = hist["Close"]
        current = float(close.iloc[-1])

        sma50 = float(close.rolling(50).mean().iloc[-1])
        sma150 = float(close.rolling(150).mean().iloc[-1])
        sma200 = float(close.rolling(200).mean().iloc[-1])
        sma200_30d_ago = float(close.rolling(200).mean().iloc[-22])

        low_52w = float(close.iloc[-252:].min())
        high_52w = float(close.iloc[-252:].max())

        c1 = current > sma150 and current > sma200
        c2 = sma150 > sma200
        c3 = sma200 > sma200_30d_ago
        c4 = sma50 > sma150 and sma50 > sma200
        c5 = current >= low_52w * 1.30

        failed = []
        if not c1: failed.append("price_below_sma150_or_200")
        if not c2: failed.append("sma150_below_sma200")
        if not c3: failed.append("sma200_not_trending_up")
        if not c4: failed.append("sma50_below_sma150_or_200")
        if not c5: failed.append("price_not_30pct_above_52w_low")

        return {
            "ticker": ticker,
            "passes": len(failed) == 0,
            "failed_conditions": failed,
            "price": round(current, 2),
            "sma50": round(sma50, 2),
            "sma150": round(sma150, 2),
            "sma200": round(sma200, 2),
            "low_52w": round(low_52w, 2),
            "high_52w": round(high_52w, 2),
            "pct_above_52w_low": round((current / low_52w - 1) * 100, 1),
            "within_25pct_of_52w_high": current >= high_52w * 0.75,
        }
    except Exception as e:
        return {"ticker": ticker, "passes": False, "reason": str(e)}
