#!/usr/bin/env python3
"""Build a private, read-only Bloguito growth opportunity queue."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
AGENT_ROOT = ROOT / "agent-publisher"
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from agents.growth_analysis import (  # noqa: E402
    GrowthAnalysisError,
    analyze_growth,
    load_policy,
    save_opportunities,
)


DEFAULT_ANALYTICS_DIR = AGENT_ROOT / "data" / "analytics"
DEFAULT_CATALOG = AGENT_ROOT / "data" / "catalog_inventory.json"
DEFAULT_POLICY = AGENT_ROOT / "growth_policy.json"
DEFAULT_OUTPUT = AGENT_ROOT / "data" / "growth"
ANALYTICS_NAME = re.compile(r"^google-analytics-(\d{4}-\d{2}-\d{2})\.json$")


def latest_analytics_snapshot(directory: Path) -> Path:
    if not directory.is_dir():
        raise GrowthAnalysisError("analytics_directory_missing")
    candidates = []
    for path in directory.iterdir():
        match = ANALYTICS_NAME.fullmatch(path.name)
        if path.is_file() and not path.is_symlink() and match:
            candidates.append((match.group(1), path))
    if not candidates:
        raise GrowthAnalysisError("analytics_snapshot_missing")
    return max(candidates, key=lambda item: item[0])[1]


def _load_json(path: Path, code: str):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise GrowthAnalysisError(code) from None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analytics", type=Path,
                        help="explicit analytics snapshot; default uses newest private snapshot")
    parser.add_argument("--analytics-dir", type=Path, default=DEFAULT_ANALYTICS_DIR)
    parser.add_argument("--catalog-inventory", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    try:
        analytics_path = args.analytics or latest_analytics_snapshot(args.analytics_dir)
        if analytics_path.is_symlink():
            raise GrowthAnalysisError("analytics_snapshot_symlink_not_allowed")
        if args.catalog_inventory.is_symlink():
            raise GrowthAnalysisError("catalog_inventory_symlink_not_allowed")
        snapshot = _load_json(analytics_path, "analytics_snapshot_unreadable")
        catalog = _load_json(args.catalog_inventory, "catalog_inventory_unreadable")
        policy = load_policy(args.policy)
        report = analyze_growth(snapshot, catalog, policy)
        target = save_opportunities(report, args.output_dir)
    except GrowthAnalysisError as exc:
        print("growth_queue_failed:" + str(exc), file=sys.stderr)
        return 1
    counts = report["summary"]["classifications"]
    rendered = ",".join(f"{key}={counts[key]}" for key in sorted(counts))
    print("growth_queue_ok period_end=" + report["period"]["end"]
          + " published_posts=" + str(report["summary"]["published_posts"])
          + " mapped_gsc_pages=" + str(report["summary"]["mapped_gsc_pages"])
          + " output=" + str(target) + " classes=" + rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
