"""Market regime check: SPY, QQQ trend structure + VIX level.

Degrades gracefully if VIX is unavailable on the data plan — the agent is told
to confirm VIX via web search in that case.
"""

from src.data_provider import get_history


def _analyze_etf(ticker: str) -> dict | None:
    hist = get_history(ticker, outputsize=300)
    if hist is None or len(hist) < 200:
        return None

    close = hist["Close"]
    current = float(close.iloc[-1])
    sma50 = close.rolling(50).mean()
    sma200 = close.rolling(200).mean()

    return {
        "ticker": ticker,
        "price": round(current, 2),
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

    vix = None
    vix_hist = get_history("VIX", outputsize=5)
    if vix_hist is not None and not vix_hist.empty:
        vix = round(float(vix_hist["Close"].iloc[-1]), 2)

    notes = []
    if spy is None or qqq is None:
        notes.append("SPY/QQQ data unavailable — agent must verify market trend via web search")
    if vix is None:
        notes.append("VIX unavailable on data plan — agent must web search VIX and apply: >25 DEFENSIVE, >30 HALT")

    conditions_met = 0
    if spy:
        conditions_met += sum([spy["above_sma50"], spy["sma50_above_sma200"], spy["sma50_sloping_up"]])
    if qqq:
        conditions_met += sum([qqq["above_sma50"], qqq["sma50_above_sma200"], qqq["sma50_sloping_up"]])

    # Stance — uses VIX when known, otherwise leans on SMA structure and flags for agent.
    if vix is not None and vix > 30:
        stance = "HALT"
    elif vix is not None and vix > 25:
        stance = "DEFENSIVE"
    elif conditions_met >= 5 and (vix is None or vix < 20):
        stance = "AGGRESSIVE" if vix is not None else "AGGRESSIVE_PENDING_VIX"
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
        "notes": notes,
    }
