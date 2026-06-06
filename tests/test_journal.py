"""Tests for the durable trade journal."""

import json

from src.journal import record_run


def test_record_run_writes_one_line_per_candidate(tmp_path):
    path = tmp_path / "trades.jsonl"
    regime = {"stance": "SELECTIVE"}
    candidates = [
        {
            "ticker": "AAA",
            "agent_action": "PLACE_ORDER",
            "from_watchlist": True,
            "pattern": {"pattern": "Flat Base"},
            "rs": {"rs_score": 12.3, "rs_rank": 1},
            "risk": {"entry": 100, "stop": 95, "t1": 110, "shares": 1, "dollar_risk": 5, "rr_t1": 2.0},
        },
        {"ticker": "BBB", "agent_action": "SKIP", "skip_reason": "Stage 2 failed"},
    ]
    n = record_run("premarket", regime, candidates, path=str(path))
    assert n == 2

    lines = path.read_text().strip().splitlines()
    assert len(lines) == 2
    rec0 = json.loads(lines[0])
    assert rec0["ticker"] == "AAA"
    assert rec0["action"] == "PLACE_ORDER"
    assert rec0["stance"] == "SELECTIVE"
    assert rec0["rs_rank"] == 1
    assert rec0["outcome"] is None


def test_record_run_appends(tmp_path):
    path = tmp_path / "trades.jsonl"
    regime = {"stance": "AGGRESSIVE"}
    c = [{"ticker": "X", "agent_action": "SKIP"}]
    record_run("eod", regime, c, path=str(path))
    record_run("eod", regime, c, path=str(path))
    assert len(path.read_text().strip().splitlines()) == 2
