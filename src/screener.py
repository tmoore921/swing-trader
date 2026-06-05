"""Stock screener: builds a universe from S&P 500 + 400, ranks by relative strength."""

import yfinance as yf
import pandas as pd
import requests
from config import MIN_PRICE, MIN_AVG_VOLUME, SCREENER_UNIVERSE_SIZE


def get_universe() -> list[str]:
    """Fetch S&P 500 + S&P 400 tickers from Wikipedia."""
    tickers = []
    try:
        sp500 = pd.read_html(
            "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies", flavor="lxml"
        )[0]["Symbol"].tolist()
        tickers.extend(sp500)
    except Exception:
        pass

    try:
        sp400 = pd.read_html(
            "https://en.wikipedia.org/wiki/List_of_S%26P_400_companies", flavor="lxml"
        )[0]["Ticker symbol"].tolist()
        tickers.extend(sp400)
    except Exception:
        pass

    # Clean ticker symbols (remove dots, fix BRK.B style)
    cleaned = []
    for t in tickers:
        t = str(t).strip().replace(".", "-")
        if t and t.isascii():
            cleaned.append(t)
    return list(dict.fromkeys(cleaned))  # deduplicate, preserve order


def rank_by_relative_strength(tickers: list[str], lookback_days: int = 63) -> list[dict]:
    """Download price history and rank by 3-month total return vs SPY."""
    period = f"{lookback_days + 15}d"

    spy_hist = yf.Ticker("SPY").history(period=period)
    spy_ret = float((spy_hist["Close"].iloc[-1] / spy_hist["Close"].iloc[0] - 1) * 100)

    # Batch download for speed
    batch_size = 100
    all_results = []

    for i in range(0, len(tickers), batch_size):
        batch = tickers[i : i + batch_size]
        try:
            data = yf.download(
                batch, period=period, progress=False, auto_adjust=True, threads=True
            )
            closes = data["Close"] if "Close" in data else data
            volumes = data["Volume"] if "Volume" in data else None

            for ticker in batch:
                try:
                    if ticker not in closes.columns:
                        continue
                    close = closes[ticker].dropna()
                    if len(close) < 10:
                        continue

                    current_price = float(close.iloc[-1])
                    if current_price < MIN_PRICE:
                        continue

                    avg_vol = None
                    if volumes is not None and ticker in volumes.columns:
                        avg_vol = float(volumes[ticker].dropna().iloc[-20:].mean())
                        if avg_vol < MIN_AVG_VOLUME:
                            continue

                    ret = float((close.iloc[-1] / close.iloc[0] - 1) * 100)
                    rs_vs_spy = round(ret - spy_ret, 2)

                    all_results.append({
                        "ticker": ticker,
                        "price": round(current_price, 2),
                        "avg_volume": int(avg_vol) if avg_vol else None,
                        "return_3m_pct": round(ret, 2),
                        "rs_vs_spy_pct": rs_vs_spy,
                    })
                except Exception:
                    continue
        except Exception:
            continue

    all_results.sort(key=lambda x: x["rs_vs_spy_pct"], reverse=True)
    return all_results[:SCREENER_UNIVERSE_SIZE]


def screen_stocks() -> list[dict]:
    """Full pipeline: build universe → rank by RS → return top candidates."""
    tickers = get_universe()
    if not tickers:
        return []
    return rank_by_relative_strength(tickers)
