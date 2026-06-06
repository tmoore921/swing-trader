"""Tests for position sizing, the C3 clamp, ATR, and R:R."""

import pytest

from config import ACCOUNT_SIZE, RISK_PER_TRADE, MAX_POSITION_PCT
from src.risk_engine import calculate_position, atr, atr_stop
from conftest import make_ohlcv
import numpy as np


def test_basic_sizing_and_rr():
    # entry 100, stop 95 -> risk/share 5 -> shares = $5/$5 = 1
    pos = calculate_position(entry=100, stop=95, t1=110, t2=120, account_size=500)
    assert pos["valid"]
    assert pos["shares"] == pytest.approx(1.0, abs=1e-6)
    assert pos["dollar_risk"] == pytest.approx(5.0, abs=1e-6)
    assert pos["rr_t1"] == pytest.approx(2.0)
    assert pos["meets_min_rr"] is True
    assert pos["clamped"] is False


def test_tight_stop_is_clamped_to_max_position_pct():
    # entry 100, stop 99.5 -> risk/share 0.50 -> risk-based shares = 10 ($1000 = 200%!)
    pos = calculate_position(entry=100, stop=99.5, t1=110, account_size=500)
    assert pos["valid"]
    # Must be clamped to MAX_POSITION_PCT of the account, never 200%.
    assert pos["clamped"] is True
    assert pos["position_pct_of_account"] <= MAX_POSITION_PCT * 100 + 1e-6
    assert pos["position_size"] == pytest.approx(500 * MAX_POSITION_PCT, abs=1e-6)
    # Dollar risk recomputed from clamped shares -> well under the nominal $5.
    assert pos["dollar_risk"] < RISK_PER_TRADE
    assert pos["oversized_warning"] is False


def test_cash_cap_binds_when_smaller_than_pct_cap():
    # Only $30 cash available; pct cap would allow $100. Cash wins.
    pos = calculate_position(entry=100, stop=90, account_size=500, cash_available=30)
    assert pos["valid"]
    assert pos["position_size"] <= 30 + 1e-6
    assert pos["clamp_reason"] == "cash_available"


def test_stop_at_or_above_entry_invalid():
    assert calculate_position(entry=100, stop=100)["valid"] is False
    assert calculate_position(entry=100, stop=105)["valid"] is False


def test_insufficient_capital_returns_invalid():
    pos = calculate_position(entry=100, stop=90, account_size=500, cash_available=0.5)
    assert pos["valid"] is False
    assert pos["reason"] == "insufficient_capital_for_min_position"


def test_atr_and_atr_stop():
    closes = np.linspace(50, 70, 60)
    df = make_ohlcv(closes, hl_spread=0.02)
    a = atr(df)
    assert a is not None and a > 0
    stop = atr_stop(entry=70, df=df)
    assert stop is not None and stop < 70


def test_atr_none_on_short_history():
    df = make_ohlcv(np.linspace(50, 55, 5))
    assert atr(df) is None
    assert atr_stop(70, df) is None
