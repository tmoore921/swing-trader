"""Tests for the order-quality gates in evaluate_ticker (monkeypatched, no network)."""

import numpy as np
import pytest

import src.evaluate as ev
from conftest import make_ohlcv


@pytest.fixture
def liquid_df():
    return make_ohlcv(np.full(250, 100.0), volumes=np.full(250, 3_000_000.0))


def _patch_common(monkeypatch, liquid_df, *, volume_ok=True, near_high=True, extended=False):
    monkeypatch.setattr(ev, "get_history", lambda *a, **k: liquid_df)
    monkeypatch.setattr(ev, "compute_rs", lambda *a, **k: {"rs_score": 10.0, "by_horizon": {}})
    monkeypatch.setattr(
        ev, "check_stage2",
        lambda *a, **k: {
            "ticker": "T", "passes": True, "price": 100.0, "sma50": 95.0,
            "within_25pct_of_52w_high": near_high,
        },
    )
    monkeypatch.setattr(
        ev, "detect_pattern",
        lambda *a, **k: {
            "pattern": "Flat Base", "pivot": 100.0, "extended": extended,
            "volume_confirmation": volume_ok,
        },
    )
    monkeypatch.setattr(ev, "atr_stop", lambda entry, df, **k: 96.0)
    monkeypatch.setattr(ev, "estimate_targets", lambda *a, **k: (115.0, 130.0))


def test_all_gates_pass_places_order(monkeypatch, liquid_df):
    _patch_common(monkeypatch, liquid_df)
    r = ev.evaluate_ticker("T")
    assert r["agent_action"] == "PLACE_ORDER"
    assert r["risk"]["valid"]
    assert r["rs"]["rs_score"] == 10.0


def test_missing_volume_demotes(monkeypatch, liquid_df):
    _patch_common(monkeypatch, liquid_df, volume_ok=False)
    r = ev.evaluate_ticker("T")
    assert r["agent_action"] == "ADD_TO_WATCHLIST"
    assert "volume" in r["skip_reason"]


def test_far_from_high_demotes(monkeypatch, liquid_df):
    _patch_common(monkeypatch, liquid_df, near_high=False)
    r = ev.evaluate_ticker("T")
    assert r["agent_action"] == "ADD_TO_WATCHLIST"
    assert "52w high" in r["skip_reason"]


def test_extended_demotes(monkeypatch, liquid_df):
    _patch_common(monkeypatch, liquid_df, extended=True)
    r = ev.evaluate_ticker("T")
    assert r["agent_action"] == "ADD_TO_WATCHLIST"
    assert "chase" in r["skip_reason"]


def test_illiquid_skips(monkeypatch):
    cheap = make_ohlcv(np.full(250, 2.0), volumes=np.full(250, 1000.0))
    monkeypatch.setattr(ev, "get_history", lambda *a, **k: cheap)
    monkeypatch.setattr(ev, "compute_rs", lambda *a, **k: {"rs_score": None, "by_horizon": {}})
    r = ev.evaluate_ticker("PENNY")
    assert r["agent_action"] == "SKIP"
    assert "Illiquid" in r["skip_reason"]


def test_no_data_verifies_via_websearch(monkeypatch):
    monkeypatch.setattr(ev, "get_history", lambda *a, **k: None)
    r = ev.evaluate_ticker("XYZ")
    assert r["agent_action"] == "VERIFY_VIA_WEBSEARCH"
