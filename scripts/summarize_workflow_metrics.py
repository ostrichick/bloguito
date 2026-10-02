#!/usr/bin/env python3
"""Summarize Bloguito workflow-metrics JSONL without ad-hoc analysis scripts."""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_METRICS = ROOT / "agent-publisher" / "data" / "editorial_runs" / "workflow-metrics.jsonl"


def percentile(values: list[float], ratio: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(round((len(ordered) - 1) * ratio))))
    return ordered[index]


def load_metrics(path: Path) -> list[dict]:
    rows = []
    if not path.is_file():
        return rows
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        raw = raw.strip()
        if not raw:
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid_metrics_json:{line_number}") from exc
        if isinstance(row, dict):
            rows.append(row)
    return rows


def summarize(rows: list[dict], *, run_context: str = "live", status: str = "ok") -> dict:
    selected = [
        row for row in rows
        if row.get("run_context") == run_context and (status == "any" or row.get("status") == status)
    ]
    actions = defaultdict(list)
    for row in selected:
        actions[str(row.get("action") or "unknown")].append(row)

    action_summary = {}
    for action, action_rows in sorted(actions.items()):
        totals = [float(row["total_ms"]) for row in action_rows if isinstance(row.get("total_ms"), (int, float))]
        wp = [
            float(row["counters"]["wp_roundtrips"])
            for row in action_rows
            if isinstance((row.get("counters") or {}).get("wp_roundtrips"), (int, float))
        ]
        ssh = [float(row['counters']['ssh_roundtrips']) for row in action_rows
               if isinstance((row.get('counters') or {}).get('ssh_roundtrips'), (int, float))]
        timing_totals = defaultdict(float)
        timing_counts = Counter()
        for row in action_rows:
            for key, value in (row.get("timings_ms") or {}).items():
                if isinstance(value, (int, float)):
                    timing_totals[key] += float(value)
                    timing_counts[key] += 1
        action_summary[action] = {
            "count": len(action_rows),
            "total_ms_median": round(statistics.median(totals), 2) if totals else None,
            "total_ms_p90": round(percentile(totals, 0.90), 2) if totals else None,
            "wp_roundtrips_mean": round(statistics.mean(wp), 2) if wp else None,
            "ssh_roundtrips_mean": round(statistics.mean(ssh), 2) if ssh else None,
            "timings_ms_mean": {
                key: round(timing_totals[key] / timing_counts[key], 2)
                for key in sorted(timing_totals)
            },
        }
    return {
        "run_context": run_context,
        "status": status,
        "rows": len(selected),
        "code_versions": dict(Counter(row['code_version'] for row in selected if row.get('code_version'))),
        "unversioned_rows": sum(not row.get('code_version') for row in selected),
        "actions": action_summary,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=DEFAULT_METRICS)
    parser.add_argument("--context", choices=["live", "test"], default="live")
    parser.add_argument("--status", choices=["ok", "error", "any"], default="ok")
    parser.add_argument("--action", action="append", help="Limit output to one or more action names")
    parser.add_argument('--code-version', help='Compare only one measured runtime code version')
    parser.add_argument('--since', help='Include runs starting on or after YYYY-MM-DD')
    args = parser.parse_args(argv)

    rows = load_metrics(args.file)
    if args.code_version:
        rows = [row for row in rows if row.get('code_version') == args.code_version]
    if args.since:
        from datetime import date
        date.fromisoformat(args.since)
        rows = [row for row in rows if str(row.get('started_at', ''))[:10] >= args.since]
    if args.action:
        wanted = set(args.action)
        rows = [row for row in rows if row.get("action") in wanted]
    print(json.dumps(summarize(rows, run_context=args.context, status=args.status), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
