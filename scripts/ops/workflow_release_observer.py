#!/usr/bin/env python3
"""Read-only operating view of runtime workflow samples by installed release.

Never synthesizes workflow samples or runs WordPress. A remote read, if requested,
is restricted to cat of the canonical metrics JSONL file over batch SSH.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import statistics
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.summarize_workflow_metrics import percentile

REMOTE_LOG = '/home/ubuntu/agent-publisher/data/editorial_runs/workflow-metrics.jsonl'
RELEASE = re.compile(r'[0-9a-f]{40}\Z')
HOST = re.compile(r'[A-Za-z0-9_][A-Za-z0-9_.-]*\Z')
METRICS = ('total_ms', 'ssh_roundtrips', 'wp_roundtrips')


def read_rows(raw: bytes) -> list[dict]:
    rows = []
    for i, line in enumerate(raw.decode('utf-8-sig').splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f'invalid_metric_record_line_{i}') from exc
        if not isinstance(row, dict):
            raise ValueError(f'invalid_metric_object_line_{i}')
        rows.append(row)
    return rows


def metrics_bytes(path: Path | None = None, *, ssh_host: str | None = None) -> bytes:
    if ssh_host:
        if not HOST.fullmatch(ssh_host):
            raise ValueError('invalid_ssh_host')
        completed = subprocess.run(
            ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8', ssh_host,
             f'cat {REMOTE_LOG}'], check=True, timeout=25, capture_output=True)
        return completed.stdout
    if path is None:
        raise ValueError('local_metrics_path_required')
    return Path(path).read_bytes()


def _cohort_key(row: dict) -> tuple | None:
    """Only explicit matched runtime dimensions can prove timing comparisons.

    Workload signature is intentionally optional in old records, but its absence
    prevents the comparison. Do not mix image/no-image or varying source work.
    """
    fields = ('action', 'route', 'transport', 'workload_signature')
    values = tuple(row.get(field) for field in fields)
    if (any(not isinstance(x, str) or not x or x in ('unclassified', 'unknown')
            for x in values)):
        return None
    return values


def _counter(row: dict, name: str):
    if name == 'total_ms':
        value = row.get('total_ms')
    else:
        value = (row.get('counters') or {}).get(name)
    return float(value) if type(value) in (int, float) and value >= 0 else None


def _metrics(group: list[dict]) -> dict:
    result = {}
    for metric in METRICS:
        values = [_counter(x, metric) for x in group]
        if len(values) != len(group) or any(v is None for v in values):
            result[metric] = None
        elif metric == 'total_ms':
            result[metric] = {'median': round(statistics.median(values), 2),
                              'p90': round(percentile(values, 0.9), 2)}
        else:
            result[metric] = {'mean': round(statistics.mean(values), 2),
                              'p90': round(percentile(values, 0.9), 2)}
    return result


def release_report(rows: list[dict], installed_revision: str,
                   *, before_revision: str | None = None,
                   min_samples: int = 5) -> dict:
    if not isinstance(installed_revision, str) or not RELEASE.fullmatch(installed_revision):
        raise ValueError('invalid_installed_release_revision')
    if before_revision is not None and (not RELEASE.fullmatch(before_revision)
                                        or before_revision == installed_revision):
        raise ValueError('invalid_before_release_revision')
    if min_samples < 5:
        raise ValueError('minimum_five_samples_required')
    successes = [r for r in rows if r.get('run_context') == 'live' and r.get('status') == 'ok']
    installed = [r for r in successes if r.get('release_revision') == installed_revision]
    before = [r for r in successes if r.get('release_revision') == before_revision]
    partition = defaultdict(lambda: {'before': [], 'after': []})
    missing_dims = {'before': 0, 'after': 0}
    for phase, observed in (('before', before), ('after', installed)):
        for row in observed:
            key = _cohort_key(row)
            if key is None:
                missing_dims[phase] += 1
                continue
            partition[key][phase].append(row)
    comparisons = []
    for key, groups in sorted(partition.items()):
        a, b = groups['before'], groups['after']
        ready = len(a) >= min_samples and len(b) >= min_samples
        before_metrics = _metrics(a) if a else None
        after_metrics = _metrics(b) if b else None
        ratios = {}
        for metric in METRICS:
            old = before_metrics.get(metric) if before_metrics else None
            new = after_metrics.get(metric) if after_metrics else None
            unit = 'median' if metric == 'total_ms' else 'mean'
            ratios[metric] = (round(100 * (new[unit] - old[unit]) / old[unit], 2)
                              if ready and old and new and old[unit] > 0 else None)
        comparisons.append({'action': key[0], 'route': key[1], 'transport': key[2],
                            'workload_signature': key[3], 'before_count': len(a),
                            'after_count': len(b), 'comparison_ready': ready,
                            'before_metrics': before_metrics if ready else None,
                            'after_metrics': after_metrics if ready else None,
                            'change_percent': ratios})
    return {
        'installed_release_revision': installed_revision,
        'before_release_revision': before_revision,
        'raw_rows': len(rows), 'live_success_rows': len(successes),
        'installed_release_success_rows': len(installed),
        'previous_release_success_rows': len(before),
        'installed_release_last_observation': max((r.get('started_at','') for r in installed), default=None),
        'latest_log_observation': max((r.get('started_at','') for r in rows), default=None),
        'missing_comparison_dimensions': missing_dims,
        'comparable_cohort_count': sum(x['comparison_ready'] for x in comparisons),
        'comparisons': comparisons,
        'performance_claim': 'unmeasured' if not any(x['comparison_ready'] for x in comparisons)
                              else 'descriptive_noncausal',
        'not_observed': ['host_imagegen', 'human_review', 'browser_qa',
                         'next_scheduled_cron_success'],
        'read_only': True,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument('--file', type=Path)
    source.add_argument('--ssh-host')
    p.add_argument('--installed-revision', required=True)
    p.add_argument('--before-revision')
    p.add_argument('--output', type=Path)
    args = p.parse_args(argv)
    raw = metrics_bytes(args.file, ssh_host=args.ssh_host)
    result = release_report(read_rows(raw), args.installed_revision,
                            before_revision=args.before_revision)
    result['input_sha256'] = hashlib.sha256(raw).hexdigest()
    encoded = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding='utf-8')
    print(encoded)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
