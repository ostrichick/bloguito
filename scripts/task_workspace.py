"""Create/reuse and mark managed Bloguito scratch task workspaces."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / "agent-publisher"))

from agents.workspace_lifecycle import (  # noqa: E402
    ensure_task_workspace,
    load_workspace_manifest,
    mark_task_workspace,
    task_workspace_path,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    sub = parser.add_subparsers(dest="action", required=True)

    open_cmd = sub.add_parser("open", help="create or reuse a stable managed task workspace")
    open_cmd.add_argument("task_name")
    open_cmd.add_argument("--kind", default="general")

    mark_cmd = sub.add_parser("mark", help="mark an existing managed workspace lifecycle status")
    mark_cmd.add_argument("task_name")
    mark_cmd.add_argument("status", choices=["active", "completed", "failed", "preserved"])
    mark_cmd.add_argument("--reason")

    args = parser.parse_args()
    if args.action == "open":
        path = ensure_task_workspace(args.root, args.task_name, kind=args.kind)
    else:
        path = task_workspace_path(args.root, args.task_name)
        mark_task_workspace(path, args.status, preserve_reason=args.reason)
    print(json.dumps({"path": str(path), "manifest": load_workspace_manifest(path)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
