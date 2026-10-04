#!/usr/bin/env python3
"""Record completion of a planner-selected existing-page growth task."""

from __future__ import annotations

import argparse
from datetime import date, datetime
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
AGENT_ROOT = ROOT / "agent-publisher"
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from agents.growth_analysis import load_policy  # noqa: E402
from agents.growth_work_log import (  # noqa: E402
    GrowthWorkLogError,
    empty_work_log,
    record_existing_completion,
    save_work_log,
)
from agents.temporal_validation import KST  # noqa: E402


GROWTH_DIR = AGENT_ROOT / "data" / "growth"
DEFAULT_PLAN = GROWTH_DIR / "daily-growth-plan.json"
DEFAULT_LOG = GROWTH_DIR / "growth-work-log.json"
DEFAULT_POLICY = AGENT_ROOT / "growth_policy.json"


def _load(path: Path, code: str):
    try:
        if path.is_symlink():
            raise GrowthWorkLogError(code + "_symlink_not_allowed")
        return json.loads(path.read_text(encoding="utf-8"))
    except GrowthWorkLogError:
        raise
    except (OSError, ValueError):
        raise GrowthWorkLogError(code) from None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["complete-existing"])
    parser.add_argument("--post-id", type=int, required=True)
    parser.add_argument("--completed-on", help="YYYY-MM-DD; defaults to KST operator date")
    parser.add_argument("--note", default="", help="short operator note; do not put secrets here")
    parser.add_argument("--edit-receipt", type=Path, required=True,
                        help="JSON output from the successful canonical edit-post command")
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--work-log", type=Path, default=DEFAULT_LOG)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    args = parser.parse_args(argv)
    try:
        completed_on = (date.fromisoformat(args.completed_on) if args.completed_on
                        else datetime.now(KST).date())
        plan = _load(args.plan, "daily_growth_plan_unreadable")
        log = _load(args.work_log, "growth_work_log_unreadable") if args.work_log.exists() else empty_work_log()
        policy = load_policy(args.policy)
        edit_result = _load(args.edit_receipt, "growth_edit_receipt_unreadable")
        edit_receipt = edit_result.get("mutation_receipt") if isinstance(edit_result, dict) else None
        updated = record_existing_completion(
            log, plan, policy, post_id=args.post_id,
            completed_on=completed_on, edit_receipt=edit_receipt, note=args.note,
        )
        target = save_work_log(updated, args.work_log)
    except (ValueError, GrowthWorkLogError) as exc:
        print("growth_work_record_failed:" + (str(exc) or "invalid_growth_work_input"),
              file=sys.stderr)
        return 1
    matches = [row for row in updated["entries"]
               if row.get("post_id") == args.post_id
               and row.get("completed_on") == completed_on.isoformat()]
    row = matches[-1]
    print("growth_work_record_ok post_id=" + str(row["post_id"])
          + " recheck_after=" + row["recheck_after"] + " output=" + str(target))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
