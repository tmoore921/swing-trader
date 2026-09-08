"""Tests for the deterministic options-play blueprint (no network, no chain data)."""

import config
from src.options import build_options_play


def test_blueprint_has_core_structure():
    op = build_options_play(entry=100.0, stop=96.0, t1=115.0, t2=130.0, price=100.0)
    assert op["strategy"] == "long_call"
    assert op["direction"] == "bullish"
    assert op["strike"]["target_strike"] == 100.0
    assert op["strike"]["target_delta"] == config.OPTIONS_TARGET_DELTA
    assert op["expiry"]["min_dte"] == config.OPTIONS_MIN_DTE
    assert op["expiry"]["max_dte"] == config.OPTIONS_MAX_DTE
    # Exit is tied to the underlying stop, not expiry.
    assert op["underlying_stop_ref"] == 96.0
    assert "96.0" in op["exit_rule"]


def test_premium_budget_caps_to_account_pct():
    op = build_options_play(entry=100.0, stop=96.0, t1=115.0, t2=130.0, price=100.0)
    assert op["max_premium_dollars"] == round(config.ACCOUNT_SIZE * config.OPTIONS_MAX_PREMIUM_PCT, 2)


def test_premium_budget_caps_to_cash_when_lower():
    op = build_options_play(
        entry=100.0, stop=96.0, t1=115.0, t2=130.0, price=100.0, cash_available=20.0
    )
    assert op["max_premium_dollars"] == 20.0


def test_invalid_stop_returns_none():
    assert build_options_play(entry=100.0, stop=100.0, t1=115.0, t2=130.0, price=100.0) is None
    assert build_options_play(entry=0.0, stop=-1.0, t1=1.0, t2=2.0, price=0.0) is None


def test_disabled_returns_none(monkeypatch):
    monkeypatch.setattr("src.options.OPTIONS_ENABLED", False)
    assert build_options_play(entry=100.0, stop=96.0, t1=115.0, t2=130.0, price=100.0) is None
