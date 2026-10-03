#!/usr/bin/env python3
"""Collect official measured demand for reviewed private topic candidates."""

from __future__ import annotations

import argparse
from datetime import date, datetime
import json
import os
from pathlib import Path
import sys

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
AGENT_ROOT = ROOT / "agent-publisher"
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

# Keep operator credentials in the ignored agent-publisher/.env file, matching
# the rest of the application.  Cron/shell callers should not have to export
# the NAVER API HUB keys into their process environment manually.
load_dotenv(AGENT_ROOT / ".env")

from agents.growth_analysis import GrowthAnalysisError, load_policy  # noqa: E402
from agents.temporal_validation import KST  # noqa: E402
from agents.topic_demand import (  # noqa: E402
    TopicDemandError,
    collect_naver_datalab,
    naver_datalab_requester,
    save_candidate_document,
    select_measurement_candidates,
)
from agents.topic_scoring import TopicScoringError, score_candidates  # noqa: E402


DEFAULT_GROWTH_DIR = AGENT_ROOT / "data" / "growth"
DEFAULT_CANDIDATES = DEFAULT_GROWTH_DIR / "topic_candidates.json"
DEFAULT_OPPORTUNITIES = DEFAULT_GROWTH_DIR / "latest-opportunities.json"
DEFAULT_POLICY = AGENT_ROOT / "growth_policy.json"


def _load_json(path: Path, code: str):
    try:
        if path.is_symlink():
            raise TopicDemandError(code + "_symlink_not_allowed")
        return json.loads(path.read_text(encoding="utf-8"))
    except TopicDemandError:
        raise
    except (OSError, ValueError):
        raise TopicDemandError(code) from None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--opportunities", type=Path, default=DEFAULT_OPPORTUNITIES)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--as-of-date", help="YYYY-MM-DD; defaults to local operator date")
    parser.add_argument("--window-days", type=int, default=90)
    parser.add_argument("--time-unit", choices=("date", "week", "month"), default="week")
    parser.add_argument(
        "--include-unseeded", action="store_true",
        help="also measure reviewed candidates with no literal fresh GSC query match",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="perform provider measurement and validation without replacing topic_candidates.json",
    )
    args = parser.parse_args(argv)
    try:
        as_of = (date.fromisoformat(args.as_of_date) if args.as_of_date
                 else datetime.now(KST).date())
        candidates = _load_json(args.candidates, "topic_candidates_unreadable")
        opportunities = _load_json(args.opportunities, "growth_opportunities_unreadable")
        policy = load_policy(args.policy)
        score_candidates(candidates, opportunities, policy, as_of=as_of)
        max_gsc_age = int(policy["topic_gate"]["max_gsc_report_age_days"])
        selected, selection_reason = select_measurement_candidates(
            candidates, opportunities, as_of=as_of, max_gsc_age_days=max_gsc_age,
            require_gsc_seed=not args.include_unseeded,
        )
        if not selected:
            print(
                "topic_demand_collection_ok provider=naver_datalab selected=0 measured=0 "
                + "reason=" + str(selection_reason or "no_measurement_candidates")
            )
            return 0
        requester = naver_datalab_requester(
            os.environ.get("NAVER_API_HUB_CLIENT_ID")
            or os.environ.get("NAVER_DATALAB_CLIENT_ID", ""),
            os.environ.get("NAVER_API_HUB_CLIENT_SECRET")
            or os.environ.get("NAVER_DATALAB_CLIENT_SECRET", ""),
        )
        updated, summary = collect_naver_datalab(
            candidates, opportunities, requester, collected_on=as_of,
            max_gsc_age_days=max_gsc_age,
            require_gsc_seed=not args.include_unseeded,
            window_days=args.window_days, time_unit=args.time_unit,
        )
        if not args.dry_run and summary["measured"]:
            save_candidate_document(updated, args.candidates)
    except (ValueError, GrowthAnalysisError, TopicDemandError, TopicScoringError) as exc:
        code = str(exc) if str(exc) else "topic_demand_collection_failed"
        print("topic_demand_collection_failed:" + code, file=sys.stderr)
        return 1
    print(
        "topic_demand_collection_ok provider=naver_datalab"
        + " selected=" + str(summary["selected"])
        + " measured=" + str(summary["measured"])
        + " unavailable=" + str(len(summary["unavailable"]))
        + " requests=" + str(summary["requests_made"])
        + " write=" + ("no" if args.dry_run or not summary["measured"] else "yes")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
