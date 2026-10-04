#!/usr/bin/env python3
"""Read-only reviewed/live provenance audit over a WordPress inventory snapshot."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import sync_post_catalog  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--inventory",
        type=Path,
        default=ROOT / "agent-publisher" / "data" / "catalog_inventory.json",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=ROOT / "agent-publisher" / "data",
    )
    args = parser.parse_args(argv)
    posts = json.loads(args.inventory.read_text(encoding="utf-8"))
    result = sync_post_catalog.audit_reviewed_provenance(posts, args.data_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 2 if result["unsafe"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
