#!/usr/bin/env python3
"""Plan and run only the Bloguito regression tests relevant to one change."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENT_ROOT = ROOT / "agent-publisher"
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from agents.validation_router import build_validation_plan
from agents.validation_runner import run_validation_plan, selected_test_files


def _load(path: Path | None):
    return json.loads(path.read_text(encoding="utf-8")) if path else None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", type=Path, help="reviewed bundle before the edit")
    parser.add_argument("--after", type=Path, help="candidate bundle after the edit")
    parser.add_argument("--image-changed", action="store_true")
    parser.add_argument("--target-status", choices=["draft", "publish"], default="draft")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--changed-file", action="append", default=[],
                        help="repository path changed by a code/docs task; repeat as needed")
    parser.add_argument("--post-id", type=int)
    parser.add_argument("--expected-content-sha256")
    parser.add_argument("--route", choices=["auto", "fast", "standard", "image-only", "repository"],
                        default="auto")
    parser.add_argument("--run", action="store_true",
                        help="execute the selected tests; without this flag only print the plan")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    if bool(args.before) != bool(args.after):
        parser.error("--before and --after must be provided together")
    if not args.before and not args.image_changed and not args.changed_file:
        parser.error("provide bundle pair, --image-changed, or --changed-file")
    for path in (args.before, args.after):
        if path is not None and not path.is_file():
            parser.error(f"bundle file not found: {path}")

    plan = build_validation_plan(
        _load(args.before),
        _load(args.after),
        image_changed=args.image_changed,
        target_status=args.target_status,
        changed_files=args.changed_file,
        resume=args.resume,
        route=args.route,
        post_id=args.post_id,
        expected_content_sha256=args.expected_content_sha256,
    )
    selected = selected_test_files(plan)
    if not args.run:
        payload = {"plan": plan, "selected_test_files": selected, "validation": None}
    else:
        receipt = run_validation_plan(plan)
        payload = {"plan": plan, "selected_test_files": selected, "validation": receipt}
        if receipt["status"] != "passed":
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            if args.output:
                args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            return 1
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
