"""Durable trade journal — the feedback substrate the system was missing.

Every run appends one JSON line per recommendation to JOURNAL_PATH. This is the
only persistent record of what the system decided, and the raw material for any
future outcome-grading / threshold-tuning (the reflection loop). Writes go to a
real path (default: repo `journal/trades.jsonl`), never /tmp, which the sandbox
wipes between runs.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from config import JOURNAL_PATH


def record_run(
    mode: str,
    regime: dict,
    candidates: list[dict],
    path: str | None = None,
) -> int:
    """Append one journal line per candidate. Returns number of lines written.

    Failures are swallowed (logged to stderr) — journaling must never break a run.
    """
    target = Path(path or JOURNAL_PATH)
    ts = datetime.now(timezone.utc).isoformat()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        lines = []
        for c in candidates:
            risk = c.get("risk") or {}
            pattern = c.get("pattern") or {}
            rs = c.get("rs") or {}
            lines.append(
                json.dumps(
                    {
                        "ts": ts,
                        "mode": mode,
                        "stance": regime.get("stance"),
                        "ticker": c.get("ticker"),
                        "action": c.get("agent_action"),
                        "from_watchlist": c.get("from_watchlist"),
                        "pattern": pattern.get("pattern"),
                        "entry": risk.get("entry"),
                        "stop": risk.get("stop"),
                        "t1": risk.get("t1"),
                        "shares": risk.get("shares"),
                        "dollar_risk": risk.get("dollar_risk"),
                        "rr_t1": risk.get("rr_t1"),
                        "rs_score": rs.get("rs_score"),
                        "rs_rank": rs.get("rs_rank"),
                        "skip_reason": c.get("skip_reason"),
                        # outcome fields are filled in later by a grading pass
                        "outcome": None,
                    },
                    default=str,
                )
            )
        if lines:
            with target.open("a") as f:
                f.write("\n".join(lines) + "\n")
        return len(lines)
    except Exception as e:  # pragma: no cover - defensive
        import sys

        print(f"WARN — journal write failed: {e}", file=sys.stderr)
        return 0
