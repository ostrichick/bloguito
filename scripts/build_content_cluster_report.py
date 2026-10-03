#!/usr/bin/env python3
"""Build a read-only internal-link/orphan report for curated content clusters."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
AGENT_ROOT = ROOT / "agent-publisher"
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from agents.content_clusters import (  # noqa: E402
    CLUSTERS,
    ContentClusterError,
    cluster_link_report,
    load_clusters,
)
from agents.search_intent import INVENTORY  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, default=INVENTORY)
    parser.add_argument("--clusters", type=Path, default=CLUSTERS)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
        report = cluster_link_report(inventory, load_clusters(args.clusters))
    except (OSError, ValueError, ContentClusterError) as exc:
        print("content_cluster_report_failed:" + (str(exc) or "invalid_cluster_input"),
              file=sys.stderr)
        return 1
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
        print(f"content_cluster_report_ok output={args.output} orphan_candidates={report['orphan_candidates']}")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
