#!/usr/bin/env python3
"""Email a report via the Resend API.

Usage:
    RESEND_API_KEY=re_... uv run python send_report.py \
        --subject "Swing Briefing — 2026-06-06" \
        --to you@example.com \
        --body-file /tmp/briefing.txt

The body file is sent as plain text. Pass RESEND_API_KEY inline on the command
(same pattern as the Twelve Data key — a fresh shell per Bash call means export
does not persist). Without a verified domain, Resend only delivers from
onboarding@resend.dev to the account owner's own email address.
"""

import os
import sys
import argparse
from pathlib import Path

import requests

RESEND_URL = "https://api.resend.com/emails"
DEFAULT_FROM = os.getenv("RESEND_FROM", "onboarding@resend.dev")


def send_email(subject: str, to: str, body: str, from_addr: str = DEFAULT_FROM) -> int:
    api_key = os.getenv("RESEND_API_KEY")
    if not api_key:
        print("FAILED — RESEND_API_KEY not set (pass inline: RESEND_API_KEY=re_... uv run ...)")
        return 1
    try:
        resp = requests.post(
            RESEND_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={"from": from_addr, "to": [to], "subject": subject, "text": body},
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
    parser.add_argument("--body-file", required=True)
    parser.add_argument("--from", dest="from_addr", default=DEFAULT_FROM)
    args = parser.parse_args()

    body_path = Path(args.body_file)
    if not body_path.exists():
        print(f"FAILED — body file not found: {args.body_file}")
        return 1

    return send_email(args.subject, args.to, body_path.read_text(), args.from_addr)


if __name__ == "__main__":
    sys.exit(main())
