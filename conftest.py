"""Shared pytest fixtures and synthetic OHLCV builders (no network)."""

import numpy as np
import pandas as pd
import pytest


def make_ohlcv(closes, volumes=None, hl_spread=0.01):
    """Build an ascending daily OHLCV DataFrame from a close-price array.

    High/Low are derived as a small spread around close so ATR/pattern code has
    sane inputs. Index is business days ending today.
    """
    closes = np.asarray(closes, dtype=float)
    n = len(closes)
    idx = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=n)
    if volumes is None:
        volumes = np.full(n, 2_000_000.0)
    volumes = np.asarray(volumes, dtype=float)
    high = closes * (1 + hl_spread)
    low = closes * (1 - hl_spread)
    open_ = closes  # good enough for tests
    return pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": closes, "Volume": volumes},
        index=idx,
    )


@pytest.fixture
def uptrend_df():
    """260-day clean uptrend that passes the Stage 2 trend template."""
    closes = np.linspace(20, 100, 260)
    return make_ohlcv(closes, volumes=np.full(260, 3_000_000.0))


@pytest.fixture
def downtrend_df():
    """260-day downtrend that fails Stage 2."""
    closes = np.linspace(100, 40, 260)
    return make_ohlcv(closes)
