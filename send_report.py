#!/usr/bin/env python3
"""Email a swing-trading report via the Resend API (HTML + plain-text fallback).

Usage:
    RESEND_API_KEY=re_... uv run python send_report.py \
        --subject "Pre-Market — SELECTIVE · 0 orders · 1 watchlist" \
        --to you@example.com \
        --json /tmp/swing_premarket.json \
        --body-file /tmp/briefing.txt

--json      structured script output; renders the stance header + candidates table
--body-file the agent's execution narrative (orders placed, watchlist changes, cash),
            shown below the table and used as the plain-text fallback
Either may be omitted. Pass RESEND_API_KEY inline (a fresh shell per Bash call means
export does not persist). Without a verified Resend domain it sends from
onboarding@resend.dev to the account owner's own email only.
"""

import os
import sys
import json
import html
import argparse
from pathlib import Path

import requests

RESEND_URL = "https://api.resend.com/emails"
DEFAULT_FROM = os.getenv("RESEND_FROM", "onboarding@resend.dev")

STANCE_COLORS = {
    "AGGRESSIVE": "#15803d",
    "AGGRESSIVE_PENDING_VIX": "#15803d",
    "SELECTIVE": "#b45309",
    "DEFENSIVE": "#b91c1c",
    "HALT": "#b91c1c",
}
ACTION_COLORS = {
    "PLACE_ORDER": "#15803d",
    "ADD_TO_WATCHLIST": "#b45309",
    "VERIFY_VIA_WEBSEARCH": "#6b7280",
    "SKIP": "#9ca3af",
}


def _esc(v) -> str:
    return html.escape(str(v)) if v is not None else "—"


def render_html(data: dict | None, narrative: str) -> str:
    parts = ['<div style="font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;'
             'max-width:640px;margin:0 auto;color:#111;">']

    if data:
        regime = data.get("market_regime", {}) or {}
        stance = regime.get("stance", "UNKNOWN")
        color = STANCE_COLORS.get(stance, "#374151")
        spy = regime.get("spy") or {}
        qqq = regime.get("qqq") or {}
        mode = data.get("mode", "").replace("eod", "End-of-Day").replace("premarket", "Pre-Market") or "Briefing"

        parts.append(f'<h2 style="margin:0 0 4px;">{_esc(mode)} Briefing</h2>')
        parts.append(f'<div style="margin:0 0 12px;font-size:13px;color:#555;">{_esc(data.get("generated_at","")[:19])}</div>')
        parts.append(
            f'<span style="display:inline-block;padding:4px 12px;border-radius:14px;'
            f'background:{color};color:#fff;font-weight:600;font-size:13px;">{_esc(stance)}</span>'
        )
        parts.append(
            f'<div style="margin:10px 0 18px;font-size:14px;color:#333;">'
            f'VIX: {_esc(regime.get("vix"))} &nbsp;|&nbsp; conditions {_esc(regime.get("conditions_met"))}/6 '
            f'&nbsp;|&nbsp; SPY {"above" if spy.get("above_sma50") else "below/NA"} 50SMA '
            f'&nbsp;|&nbsp; QQQ {"above" if qqq.get("above_sma50") else "below/NA"} 50SMA</div>'
        )

        candidates = data.get("candidates", [])
        if candidates:
            parts.append('<table style="border-collapse:collapse;width:100%;font-size:13px;">')
            parts.append(
                '<tr style="background:#f3f4f6;text-align:left;">'
                '<th style="padding:6px 8px;border-bottom:1px solid #e5e7eb;">Ticker</th>'
                '<th style="padding:6px 8px;border-bottom:1px solid #e5e7eb;">Src</th>'
                '<th style="padding:6px 8px;border-bottom:1px solid #e5e7eb;">Pattern</th>'
                '<th style="padding:6px 8px;border-bottom:1px solid #e5e7eb;">Pivot</th>'
                '<th style="padding:6px 8px;border-bottom:1px solid #e5e7eb;">R:R</th>'
                '<th style="padding:6px 8px;border-bottom:1px solid #e5e7eb;">Action</th></tr>'
            )
            for c in candidates:
                pat = c.get("pattern", {}) or {}
                risk = c.get("risk", {}) or {}
                action = c.get("agent_action", "?")
                ac = ACTION_COLORS.get(action, "#374151")
                src = "WL" if c.get("from_watchlist") else "new"
                pivot = f"${pat.get('pivot')}" if pat.get("pivot") else "—"
                rr = risk.get("rr_t1") or "—"
                parts.append(
                    '<tr>'
                    f'<td style="padding:6px 8px;border-bottom:1px solid #f0f0f0;font-weight:600;">{_esc(c.get("ticker"))}</td>'
                    f'<td style="padding:6px 8px;border-bottom:1px solid #f0f0f0;color:#666;">{_esc(src)}</td>'
                    f'<td style="padding:6px 8px;border-bottom:1px solid #f0f0f0;">{_esc(pat.get("pattern","—"))}</td>'
                    f'<td style="padding:6px 8px;border-bottom:1px solid #f0f0f0;">{_esc(pivot)}</td>'
                    f'<td style="padding:6px 8px;border-bottom:1px solid #f0f0f0;">{_esc(rr)}</td>'
                    f'<td style="padding:6px 8px;border-bottom:1px solid #f0f0f0;color:{ac};font-weight:600;">{_esc(action)}</td>'
                    '</tr>'
                )
            parts.append('</table>')

    if narrative.strip():
        parts.append('<h3 style="margin:20px 0 6px;font-size:14px;">Execution summary</h3>')
        parts.append(
            f'<pre style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:6px;'
            f'padding:12px;font-size:13px;white-space:pre-wrap;overflow-x:auto;">{_esc(narrative)}</pre>'
        )

    parts.append('</div>')
    return "".join(parts)


def send_email(subject: str, to: str, html_body: str, text_body: str, from_addr: str = DEFAULT_FROM) -> int:
    api_key = os.getenv("RESEND_API_KEY")
    if not api_key:
        print("FAILED — RESEND_API_KEY not set (pass inline: RESEND_API_KEY=re_... uv run ...)")
        return 1
    try:
        resp = requests.post(
            RESEND_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"from": from_addr, "to": [to], "subject": subject,
                  "html": html_body, "text": text_body or " "},
            timeout=30,
        )
        if resp.status_code in (200, 201):
            print(f"OK — email sent to {to} (id {resp.json().get('id')})")
            return 0
        print(f"FAILED — HTTP {resp.status_code}: {resp.text}")
        return 1
    except Exception as e:
        print(f"FAILED — request error: {e}")
        return 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--subject", required=True)
    parser.add_argument("--to", required=True)
    parser.add_argument("--json", dest="json_file", default=None, help="Script JSON output for the table")
    parser.add_argument("--body-file", default=None, help="Agent narrative / execution summary")
    parser.add_argument("--from", dest="from_addr", default=DEFAULT_FROM)
    args = parser.parse_args()

    data = None
    if args.json_file and Path(args.json_file).exists():
        try:
            data = json.loads(Path(args.json_file).read_text())
        except Exception:
            data = None

    narrative = ""
    if args.body_file and Path(args.body_file).exists():
        narrative = Path(args.body_file).read_text()

    html_body = render_html(data, narrative)
    return send_email(args.subject, args.to, html_body, narrative, args.from_addr)


if __name__ == "__main__":
    sys.exit(main())
