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


def summarize_cohorts(rows: list[dict], *, run_context: str = "live",
                      status: str = "ok") -> dict:
    """Do not average multiple releases, routes, and transports together.

    A cohort with fewer than five observations is descriptive only. Human
    review, imagegen and browser QA remain outside these runtime metrics.
    """
    selected = [row for row in rows
                if row.get("run_context") == run_context
                and (status == "any" or row.get("status") == status)]
    grouped = defaultdict(list)
    for row in selected:
        key = (
            str(row.get("action") or "unknown"),
            str(row.get("code_version") or "unversioned"),
            str(row.get("release_revision") or "release_unverified"),
            str(row.get("route") or "unclassified"),
            str(row.get("transport") or "unclassified"),
        )
        grouped[key].append(row)
    cohorts = []
    for (action, version, revision, route, transport), sample in sorted(grouped.items()):
        info = summarize(sample, run_context=run_context, status=status)
        cohorts.append({
            "action": action, "code_version": version,
            "release_revision": revision,
            "route": route, "transport": transport,
            **info["actions"][action],
            "comparison_ready": (len(sample) >= 5 and version != 'unversioned'
                                 and revision != 'release_unverified'),
        })
    return {
        "run_context": run_context, "status": status,
        "rows": len(selected), "cohorts": cohorts,
        "coverage_excludes": ["human_review", "host_imagegen", "candidate_selection",
                              "browser_qa"],
    }


def compare_code_versions(rows: list[dict], before: str, after: str,
                          *, run_context: str = 'live') -> dict:
    """Pair only like-for-like successful live action/route/transport cohorts.

    A missing sample or counter is unknown, not zero. Percentage changes are
    descriptive, not proof of a causal speedup after rollout.
    """
    if not before or not after or before == after:
        raise ValueError('two_distinct_code_versions_required')
    cohorts = summarize_cohorts(rows, run_context=run_context, status='ok')['cohorts']
    keyed = defaultdict(list)
    for cohort in cohorts:
        key = (cohort['action'], cohort['route'], cohort['transport'], cohort['code_version'])
        keyed[key].append(cohort)
    dimensions = sorted({(a, route, transport) for a, route, transport, version in keyed
                         if version in {before, after}})
    comparisons = []
    for action, route, transport in dimensions:
        before_matches = keyed.get((action, route, transport, before), [])
        after_matches = keyed.get((action, route, transport, after), [])
        left = before_matches[0] if len(before_matches) == 1 else None
        right = after_matches[0] if len(after_matches) == 1 else None
        ready = bool(left and right and left['comparison_ready'] and right['comparison_ready']
                     and left['total_ms_median'] is not None and right['total_ms_median'] is not None)
        def percent(metric):
            if not ready:
                return None
            old = left.get(metric)
            new = right.get(metric)
            if old is None or new is None or old <= 0:
                return None
            return round(100 * (new - old) / old, 2)
        comparisons.append({
            'action': action, 'route': route, 'transport': transport,
            'before_count': sum(x['count'] for x in before_matches),
            'after_count': sum(x['count'] for x in after_matches),
            'before_release_revision': left['release_revision'] if left else None,
            'after_release_revision': right['release_revision'] if right else None,
            'comparison_ready': ready,
            'reason': ('release_ambiguous' if len(before_matches) > 1 or len(after_matches) > 1
                       else 'insufficient_or_unverified_data' if not ready else None),
            'before_median_ms': left['total_ms_median'] if left else None,
            'after_median_ms': right['total_ms_median'] if right else None,
            'median_change_percent': percent('total_ms_median'),
            'before_p90_ms': left['total_ms_p90'] if left else None,
            'after_p90_ms': right['total_ms_p90'] if right else None,
            'p90_change_percent': percent('total_ms_p90'),
            'before_ssh_mean': left['ssh_roundtrips_mean'] if left else None,
            'after_ssh_mean': right['ssh_roundtrips_mean'] if right else None,
            'ssh_change_percent': percent('ssh_roundtrips_mean'),
            'before_wp_mean': left['wp_roundtrips_mean'] if left else None,
            'after_wp_mean': right['wp_roundtrips_mean'] if right else None,
            'wp_change_percent': percent('wp_roundtrips_mean'),
        })
    return {'before_code_version': before, 'after_code_version': after,
            'run_context': run_context, 'comparisons': comparisons,
            'coverage_excludes': ['human_review', 'host_imagegen', 'candidate_selection', 'browser_qa'],
            'interpretation': 'descriptive_observation_not_causal_speedup'}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=DEFAULT_METRICS)
    parser.add_argument("--context", choices=["live", "test"], default="live")
    parser.add_argument("--status", choices=["ok", "error", "any"], default="ok")
    parser.add_argument("--action", action="append", help="Limit output to one or more action names")
    parser.add_argument('--code-version', help='Compare only one measured runtime code version')
    parser.add_argument('--since', help='Include runs starting on or after YYYY-MM-DD')
    parser.add_argument('--cohorts', action='store_true',
                        help='Group matched runs by code version, route, transport and action')
    parser.add_argument('--compare-versions', nargs=2, metavar=('BEFORE', 'AFTER'),
                        help='Compare only matched successful action/route/transport cohorts with >=5 observations each')
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
    if args.compare_versions:
        if args.code_version or args.status != 'ok':
            parser.error('--compare-versions requires default --status ok and no --code-version')
        result = compare_code_versions(rows, *args.compare_versions, run_context=args.context)
    else:
        result = (summarize_cohorts(rows, run_context=args.context, status=args.status)
                  if args.cohorts else summarize(rows, run_context=args.context, status=args.status))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
