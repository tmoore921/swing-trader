"""Tests for relative-strength scoring and ranking."""

import numpy as np

from src.rs import compute_rs, rank_candidates
from conftest import make_ohlcv


def test_outperformer_has_positive_rs():
    spy = make_ohlcv(np.linspace(100, 110, 200))      # +10%
    strong = make_ohlcv(np.linspace(50, 80, 200))     # +60%
    rs = compute_rs(strong, spy)
    assert rs["rs_score"] is not None
    assert rs["rs_score"] > 0
    assert rs["by_horizon"]  # populated


def test_underperformer_has_negative_rs():
    spy = make_ohlcv(np.linspace(100, 130, 200))      # +30%
    weak = make_ohlcv(np.linspace(100, 105, 200))     # +5%
    rs = compute_rs(weak, spy)
    assert rs["rs_score"] < 0


def test_missing_spy_returns_none():
    t = make_ohlcv(np.linspace(50, 80, 200))
    assert compute_rs(t, None)["rs_score"] is None


def test_rank_candidates_orders_by_score():
    cands = [
        {"ticker": "A", "rs": {"rs_score": 5.0}},
        {"ticker": "B", "rs": {"rs_score": 25.0}},
        {"ticker": "C", "rs": {"rs_score": -3.0}},
        {"ticker": "D", "rs": {"rs_score": None}},
    ]
    rank_candidates(cands)
    by = {c["ticker"]: c["rs"].get("rs_rank") for c in cands}
    assert by["B"] == 1
    assert by["A"] == 2
    assert by["C"] == 3
    assert by["D"] is None
