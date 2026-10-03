#!/usr/bin/env python3
"""Build one private Bloguito daily growth decision without WordPress mutation."""

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
from agents.growth_planner import (  # noqa: E402
    GrowthPlannerError,
    decide_daily_action,
    save_daily_plan,
)
from agents.temporal_validation import KST  # noqa: E402
from config import CATEGORIES  # noqa: E402


DEFAULT_GROWTH_DIR = AGENT_ROOT / "data" / "growth"
DEFAULT_OPPORTUNITIES = DEFAULT_GROWTH_DIR / "latest-opportunities.json"
DEFAULT_TOPIC_SCORES = DEFAULT_GROWTH_DIR / "topic-candidate-scores.json"
DEFAULT_WORK_LOG = DEFAULT_GROWTH_DIR / "growth-work-log.json"
DEFAULT_POLICY = AGENT_ROOT / "growth_policy.json"


def _load_json(path: Path, code: str):
    try:
        if path.is_symlink():
            raise GrowthPlannerError(code + "_symlink_not_allowed")
        return json.loads(path.read_text(encoding="utf-8"))
    except GrowthPlannerError:
        raise
    except (OSError, ValueError):
        raise GrowthPlannerError(code) from None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--opportunities", type=Path, default=DEFAULT_OPPORTUNITIES)
    parser.add_argument("--topic-scores", type=Path, default=DEFAULT_TOPIC_SCORES)
    parser.add_argument("--work-log", type=Path, default=DEFAULT_WORK_LOG)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_GROWTH_DIR)
    parser.add_argument("--as-of-date", help="YYYY-MM-DD; defaults to local operator date")
    parser.add_argument("--category", action="append", choices=sorted(CATEGORIES),
                        help="limit planning to one active category; repeat as needed")
    args = parser.parse_args(argv)
    try:
        as_of = (date.fromisoformat(args.as_of_date) if args.as_of_date
                 else datetime.now(KST).date())
        opportunities = _load_json(args.opportunities, "growth_opportunities_unreadable")
        scores = _load_json(args.topic_scores, "topic_scores_unreadable")
        work_log = (_load_json(args.work_log, "growth_work_log_unreadable")
                    if args.work_log.exists() else {"schema_version": 1, "entries": []})
        policy = load_policy(args.policy)
        category_keys = args.category or list(CATEGORIES)
        slug_map = {key: value["slug"] for key, value in CATEGORIES.items()}
        plan = decide_daily_action(
            opportunities, scores, policy, as_of=as_of,
            work_log=work_log,
            category_keys=category_keys, category_slug_map=slug_map,
        )
        target = save_daily_plan(plan, args.output_dir)
    except (ValueError, GrowthPlannerError) as exc:
        print("daily_growth_plan_failed:" + (str(exc) or "invalid_daily_growth_input"),
              file=sys.stderr)
        return 1
    selected = plan.get("target") or {}
    subject = selected.get("post_id") or selected.get("brief_id") or "none"
    print("daily_growth_plan_ok action=" + plan["action"]
          + " subject=" + str(subject) + " output=" + str(target))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
