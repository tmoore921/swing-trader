"""Tests for regime data-failure handling and Stage 2 on synthetic trends."""

import numpy as np

import src.market_regime as mr
from src.stage2 import check_stage2
from conftest import make_ohlcv


def test_data_failure_forces_defensive_with_reason(monkeypatch):
    monkeypatch.setattr(mr, "get_history", lambda *a, **k: None)
    regime, spy = mr.regime_and_benchmark()
    assert regime["stance"] == "DEFENSIVE"
    assert regime["data_failure"] is True
    assert regime["blocked_reason"] == "market_data_unavailable"
    assert spy is None


def test_healthy_trend_is_not_data_failure(monkeypatch):
    up = make_ohlcv(np.linspace(50, 100, 300))

    def fake_get_history(ticker, outputsize=300):
        if ticker == "VIX":
            return None  # free tier
        return up

    monkeypatch.setattr(mr, "get_history", fake_get_history)
    regime, spy = mr.regime_and_benchmark()
    assert regime["data_failure"] is False
    assert regime["conditions_met"] == 6  # both ETFs fully aligned
    assert spy is not None


def test_stage2_passes_on_uptrend(uptrend_df):
    res = check_stage2("UP", df=uptrend_df)
    assert res["passes"] is True


def test_stage2_fails_on_downtrend(downtrend_df):
    res = check_stage2("DOWN", df=downtrend_df)
    assert res["passes"] is False
