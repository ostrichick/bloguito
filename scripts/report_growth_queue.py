#!/usr/bin/env python3
"""Read-only, provenance-aware Bloguito growth queue and editorial hold report.

This is a diagnostic report, never a writer or automatic publication trigger.
The supplied artifacts are local private runtime inputs; their content remains
on the operator's machine. Does not invent unmeasured search demand.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIR = ROOT / "agent-publisher" / "data" / "growth"

NEXT_ACTION = {
    "no_fresh_measured_demand_evidence": "collect_measured_demand",
    "score_below_automation_threshold": "improve_topic_differentiation",
    "confidence_below_automation_threshold": "collect_additional_evidence",
    "duplicate_existing_post": "review_existing_content",
    "stale_gsc_report_ignored": "refresh_gsc",
    "stale_external_demand_evidence_ignored": "refresh_external_demand",
    "useful_lifetime_below_automation_minimum": "review_lifecycle_or_hold",
    "added_value_required": "define_reader_added_value",
}


def load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    if not path.is_file() or path.is_symlink():
        raise ValueError("growth_report_source_unsafe")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("growth_report_source_invalid")
    return value


def report_queue(opportunities: dict | None, scores: dict | None,
                 plan: dict | None, work_log: dict | None) -> dict:
    if scores is not None and (scores.get("schema_version") != 1
                               or not isinstance(scores.get("candidates"), list)):
        raise ValueError("growth_score_report_invalid")
    if opportunities is not None and (opportunities.get("schema_version") != 1
                                      or not isinstance(opportunities.get("pages"), list)):
        raise ValueError("growth_opportunity_report_invalid")
    if plan is not None and (plan.get("schema_version") != 1
                             or plan.get("action") not in {
                                 "new_draft", "existing_improvement", "no_action"}):
        raise ValueError("growth_daily_plan_invalid")
    if work_log is not None and (work_log.get("schema_version") != 1
                                 or not isinstance(work_log.get("entries"), list)):
        raise ValueError("growth_work_log_invalid")
    # Do not present an apparently unified growth queue if the input pair was
    # refreshed from different GSC/GA4 source observations.
    status = "complete"
    if any(v is None for v in (opportunities, scores, plan, work_log)):
        status = "incomplete_inputs"
    elif (opportunities.get("provenance_contract_version") != 1
          or not opportunities.get("refresh_id")
          or scores.get("refresh_id") != opportunities.get("refresh_id")
          or scores.get("opportunity_payload_sha256")
          != opportunities.get("opportunity_payload_sha256")
          or scores.get("growth_period_end") != (opportunities.get("period") or {}).get("end")):
        status = "provenance_mismatch"
    candidates = []
    reason_counts = Counter()
    for row in scores.get("candidates", []) if scores else []:
        if not isinstance(row, dict) or type(row.get("eligible_for_automation")) is not bool:
            raise ValueError("growth_candidate_invalid")
        reasons = row.get("reasons")
        if not isinstance(reasons, list) or any(not isinstance(r, str) for r in reasons):
            raise ValueError("growth_candidate_invalid")
        if not row["eligible_for_automation"]:
            reason_counts.update(reasons or ["unclassified_hold"])
        candidates.append({
            "id": row.get("id"), "brief_id": row.get("brief_id"),
            "topic": row.get("topic"), "score": row.get("score"),
            "confidence": row.get("confidence"),
            "measured_demand_present": row.get("measured_demand_present") is True,
            "eligible_for_automation": row["eligible_for_automation"],
            "hold_reasons": reasons if not row["eligible_for_automation"] else [],
            "next_actions": sorted({NEXT_ACTION.get(r, "editorial_review")
                                    for r in reasons}) if not row["eligible_for_automation"] else [],
        })
    return {
        "status": status,
        "data_labels": {
            "search_demand": "measured_only_when_evidence_exists",
            "priority_score": "heuristic_not_traffic_forecast",
        },
        "source_dates": {
            "opportunity_period_end": (
                (opportunities.get("period") or {}).get("end") if opportunities else None),
            "scores_as_of": scores.get("as_of_date") if scores else None,
            "plan_as_of": plan.get("as_of_date") if plan else None,
        },
        "daily_plan": {
            "action": plan.get("action") if plan else None,
            "reason": plan.get("reason") if plan else "missing",
            "details": plan.get("details", []) if plan else [],
            "target": plan.get("target") if plan and status == "complete" else None,
        },
        "summary": {
            "candidates": len(candidates),
            "eligible": sum(x["eligible_for_automation"] for x in candidates),
            "held_reasons": dict(sorted(reason_counts.items())),
            "completed_growth_actions": len(work_log["entries"]) if work_log else None,
        },
        "candidates": candidates,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_DIR)
    args = parser.parse_args(argv)
    source = args.input_dir
    if not source.is_dir() or source.is_symlink():
        raise SystemExit("growth_input_dir_missing_or_unsafe")
    result = report_queue(
        load_json(source / "latest-opportunities.json"),
        load_json(source / "topic-candidate-scores.json"),
        load_json(source / "daily-growth-plan.json"),
        load_json(source / "growth-work-log.json"),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
