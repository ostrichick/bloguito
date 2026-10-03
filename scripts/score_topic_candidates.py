#!/usr/bin/env python3
"""Score private topic candidates and produce the automatic-scheduler gate report."""

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

from agents.growth_analysis import GrowthAnalysisError, load_policy  # noqa: E402
from agents.temporal_validation import KST  # noqa: E402
from agents.topic_scoring import (  # noqa: E402
    TopicScoringError,
    save_topic_scores,
    score_candidates,
)


DEFAULT_GROWTH_DIR = AGENT_ROOT / "data" / "growth"
DEFAULT_CANDIDATES = DEFAULT_GROWTH_DIR / "topic_candidates.json"
DEFAULT_OPPORTUNITIES = DEFAULT_GROWTH_DIR / "latest-opportunities.json"
DEFAULT_POLICY = AGENT_ROOT / "growth_policy.json"


def _load_json(path: Path, code: str):
    try:
        if path.is_symlink():
            raise TopicScoringError(code + "_symlink_not_allowed")
        return json.loads(path.read_text(encoding="utf-8"))
    except TopicScoringError:
        raise
    except (OSError, ValueError):
        raise TopicScoringError(code) from None


def _init_empty(path: Path) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"schema_version": 1, "candidates": []}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--opportunities", type=Path, default=DEFAULT_OPPORTUNITIES)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_GROWTH_DIR)
    parser.add_argument("--as-of-date", help="YYYY-MM-DD; defaults to local operator date")
    parser.add_argument(
        "--init-empty", action="store_true",
        help="create an empty private topic_candidates.json when no candidate file exists",
    )
    args = parser.parse_args(argv)
    try:
        if args.init_empty:
            _init_empty(args.candidates)
        as_of = (date.fromisoformat(args.as_of_date) if args.as_of_date
                 else datetime.now(KST).date())
        candidate_document = _load_json(args.candidates, "topic_candidates_unreadable")
        opportunities = _load_json(args.opportunities, "growth_opportunities_unreadable")
        policy = load_policy(args.policy)
        report = score_candidates(candidate_document, opportunities, policy, as_of=as_of)
        target = save_topic_scores(report, args.output_dir)
    except (ValueError, GrowthAnalysisError, TopicScoringError) as exc:
        code = str(exc) if str(exc) else "invalid_topic_score_input"
        print("topic_scoring_failed:" + code, file=sys.stderr)
        return 1
    summary = report["summary"]
    print(
        "topic_scoring_ok candidates=" + str(summary["candidates"])
        + " eligible=" + str(summary["eligible_for_automation"])
        + " held=" + str(summary["held"])
        + " output=" + str(target)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
