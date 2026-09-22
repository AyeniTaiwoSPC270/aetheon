"""Scans sandbox/wrapper_run.log and prints a Gauntlet soak scorecard row
per run_once() invocation (BUILD_PLAN.md Section 13, Gate 2). Auto-fills
what the wrapper's own event log records -- chapter number, revision
loops, whether a CRITICAL issue leaked to delivery (needs_author_eyes),
halts, and crashes. Voice score, stale-hook review, and the Nessa Croft
Ch.17 flag are not logged anywhere and must stay manual fields filled in
by the author each morning -- this script does not invent them.

Usage:
    uv run python scripts/soak_scorecard.py                 # all runs
    uv run python scripts/soak_scorecard.py --since 2026-09-23
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = REPO_ROOT / "sandbox" / "wrapper_run.log"

RUN_START_EVENTS = {"halt", "snapshot"}


def load_events(log_path: Path) -> list[dict[str, Any]]:
    if not log_path.exists():
        return []
    return [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def group_into_runs(events: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    runs: list[list[dict[str, Any]]] = []
    for event in events:
        if event.get("event") in RUN_START_EVENTS:
            runs.append([event])
        elif runs:
            runs[-1].append(event)
    return runs


def summarize_run(run: list[dict[str, Any]]) -> dict[str, Any]:
    first = run[0]
    timestamp = first["timestamp"]

    if first["event"] == "halt":
        return {
            "timestamp": timestamp,
            "outcome": "halted",
            "detail": f"{first['check']}: {first.get('detail', '')}",
        }

    draft = next((e for e in run if e["event"] == "draft"), None)
    delivered = next((e for e in run if e["event"] == "delivered"), None)
    exception = next((e for e in run if e["event"] == "exception"), None)
    canon_proposals = [e for e in run if e["event"] == "canon_proposal" and e.get("written")]

    if delivered is not None:
        return {
            "timestamp": timestamp,
            "outcome": "delivered",
            "chapter": delivered["chapter"],
            "revision_loops": delivered["revision_loops"],
            "critical_leak": delivered["needs_author_eyes"],
            "canon_proposals": len(canon_proposals),
        }

    if exception is not None:
        return {
            "timestamp": timestamp,
            "outcome": "crashed",
            "chapter": draft["chapter"] if draft else None,
            "error": exception["error"],
        }

    return {"timestamp": timestamp, "outcome": "incomplete (no delivered/exception event found)"}


def format_row(summary: dict[str, Any]) -> str:
    date = datetime.fromisoformat(summary["timestamp"]).date().isoformat()
    if summary["outcome"] == "halted":
        return f"| {date} | -- | halted | -- | -- | {summary['detail']} |"
    if summary["outcome"] == "delivered":
        leak = "YES" if summary["critical_leak"] else "no"
        return (
            f"| {date} | {summary['chapter']} | delivered | "
            f"{summary['revision_loops']} | {leak} | "
            f"{summary['canon_proposals']} canon proposal(s) |"
        )
    if summary["outcome"] == "crashed":
        chapter = summary.get("chapter") or "--"
        return f"| {date} | {chapter} | CRASHED | -- | -- | {summary['error']} |"
    return f"| {date} | -- | {summary['outcome']} | -- | -- | -- |"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since", help="Only show runs on or after this ISO date (YYYY-MM-DD)")
    args = parser.parse_args()

    events = load_events(LOG_PATH)
    runs = group_into_runs(events)
    summaries = [summarize_run(run) for run in runs]

    if args.since:
        since_date = datetime.fromisoformat(args.since).date()
        summaries = [
            s for s in summaries
            if datetime.fromisoformat(s["timestamp"]).date() >= since_date
        ]

    print("| Date | Chapter | Outcome | Revision loops | CRITICAL leak | Notes |")
    print("|---|---|---|---|---|---|")
    for summary in summaries:
        print(format_row(summary))

    print()
    print(
        "Manual fields NOT covered above -- fill these in by hand in "
        "sandbox/gauntlet_soak_scorecard.md: voice score (run `inkos eval "
        "aethon <chapter>` or read manually), stale hooks (>5 chapters "
        "unscheduled -- check books/aethon/story/pending_hooks.md), and "
        "whether the Nessa Croft Ch.11-vs-Ch.17 flag was surfaced at the "
        "Ch.17 brief (only relevant the night Ch.17 drafts)."
    )


if __name__ == "__main__":
    main()
