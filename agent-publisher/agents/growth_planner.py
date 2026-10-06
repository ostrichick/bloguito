"""Choose one conservative daily growth action from private P1/P2 state.

The planner never edits WordPress. It selects exactly one of
``existing_improvement``, ``new_draft``, or ``no_action``. Existing-page
opportunities are recommendations only; when both existing and new work are
eligible, the P5 completion-history mix chooses which side runs. A selected
existing improvement never mutates a public page automatically.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile

from agents.topic_scoring import CONFIDENCE_ORDER, topic_gate_digest
from agents.growth_work_log import (
    completed_new_brief_ids,
    empty_work_log,
    recent_work_mix,
    suppressed_post_ids,
    validate_work_log,
)


class GrowthPlannerError(ValueError):
    """Fail-closed planner input, policy, or storage error."""


def _canonical_digest(value) -> str:
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _parse_date(value, code: str) -> date:
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        raise GrowthPlannerError(code) from None


def _planner_policy(policy: dict) -> dict:
    planner = policy.get("daily_planner") if isinstance(policy, dict) else None
    if not isinstance(planner, dict):
        raise GrowthPlannerError("daily_planner_policy_missing")
    required = {
        "max_opportunity_age_days", "max_topic_score_age_days",
        "existing_recheck_days",
        "min_existing_confidence", "existing_class_priority",
        "prefer_existing_improvement", "work_mix_lookback_actions",
        "target_existing_ratio",
    }
    if not required.issubset(planner):
        raise GrowthPlannerError("invalid_daily_planner_policy")
    if planner["min_existing_confidence"] not in CONFIDENCE_ORDER:
        raise GrowthPlannerError("invalid_daily_planner_confidence")
    classes = planner["existing_class_priority"]
    if (not isinstance(classes, list) or not classes
            or any(value not in {"quick_win", "growth_candidate"} for value in classes)
            or len(set(classes)) != len(classes)):
        raise GrowthPlannerError("invalid_daily_planner_classes")
    for key in ("max_opportunity_age_days", "max_topic_score_age_days"):
        if type(planner[key]) is not int or planner[key] < 0:
            raise GrowthPlannerError("invalid_daily_planner_age")
    if type(planner["existing_recheck_days"]) is not int or planner["existing_recheck_days"] < 1:
        raise GrowthPlannerError("invalid_daily_planner_recheck_days")
    if type(planner["work_mix_lookback_actions"]) is not int or planner["work_mix_lookback_actions"] < 1:
        raise GrowthPlannerError("invalid_daily_planner_work_mix_lookback")
    ratio = planner["target_existing_ratio"]
    if type(ratio) not in {int, float} or not 0.0 < float(ratio) < 1.0:
        raise GrowthPlannerError("invalid_daily_planner_target_existing_ratio")
    if type(planner["prefer_existing_improvement"]) is not bool:
        raise GrowthPlannerError("invalid_daily_planner_preference")
    return planner


def daily_planner_digest(policy: dict) -> str:
    return _canonical_digest(_planner_policy(policy))


def _validate_opportunities(report: dict, policy: dict, as_of: date) -> tuple[bool, str]:
    if (not isinstance(report, dict) or report.get("schema_version") != 1
            or report.get("provenance_contract_version") != 1):
        return False, "opportunity_report_invalid"
    if report.get("policy_version") != policy.get("version"):
        return False, "opportunity_policy_version_mismatch"
    period = report.get("period")
    if not isinstance(period, dict) or not isinstance(report.get("pages"), list):
        return False, "opportunity_report_invalid"
    digest = report.get("opportunity_payload_sha256")
    if not isinstance(digest, str) or len(digest) != 64:
        return False, "opportunity_report_digest_missing"
    payload = {
        key: value for key, value in report.items()
        if key not in {"opportunity_payload_sha256", "refresh_id"}
    }
    if _canonical_digest(payload) != digest:
        return False, "opportunity_report_digest_mismatch"
    try:
        end = _parse_date(period.get("end"), "opportunity_report_period_invalid")
    except GrowthPlannerError:
        return False, "opportunity_report_period_invalid"
    age = (as_of - end).days
    maximum = int(_planner_policy(policy)["max_opportunity_age_days"])
    if age < 0 or age > maximum:
        return False, "opportunity_report_stale"
    return True, ""


def _validate_topic_scores(report: dict, policy: dict, as_of: date,
                           *, opportunity_period_end=None,
                           opportunity_payload_sha256=None) -> tuple[bool, str]:
    if not isinstance(report, dict) or report.get("schema_version") != 1:
        return False, "topic_score_report_invalid"
    if report.get("policy_version") != policy.get("version"):
        return False, "topic_score_policy_version_mismatch"
    if report.get("topic_gate_digest") != topic_gate_digest(policy):
        return False, "topic_score_policy_digest_mismatch"
    if not isinstance(report.get("candidates"), list):
        return False, "topic_score_report_invalid"
    if (opportunity_period_end is not None
            and report.get("growth_period_end") != opportunity_period_end):
        return False, "topic_score_growth_period_mismatch"
    if (opportunity_payload_sha256 is not None
            and report.get("opportunity_payload_sha256") != opportunity_payload_sha256):
        return False, "topic_score_opportunity_digest_mismatch"
    try:
        scored_on = _parse_date(report.get("as_of_date"), "topic_score_date_invalid")
    except GrowthPlannerError:
        return False, "topic_score_date_invalid"
    age = (as_of - scored_on).days
    maximum = int(_planner_policy(policy)["max_topic_score_age_days"])
    if age < 0 or age > maximum:
        return False, "topic_score_report_stale"
    return True, ""


def _allowed_category_slugs(category_keys, category_slug_map) -> set[str] | None:
    if category_keys is None:
        return None
    keys = set(category_keys)
    if not keys:
        return set()
    return {slug for key, slug in category_slug_map.items() if key in keys}


def _existing_candidates(opportunities: dict, policy: dict, *, work_log: dict,
                         as_of: date, category_keys=None, category_slug_map=None) -> list[dict]:
    planner = _planner_policy(policy)
    class_order = {name: idx for idx, name in enumerate(planner["existing_class_priority"])}
    min_confidence = CONFIDENCE_ORDER[planner["min_existing_confidence"]]
    allowed_slugs = _allowed_category_slugs(category_keys, category_slug_map or {})
    period_end = _parse_date(
        (opportunities.get("period") or {}).get("end"), "opportunity_report_period_invalid")
    suppressed = suppressed_post_ids(work_log, opportunity_period_end=period_end, as_of=as_of)
    result = []
    for row in opportunities["pages"]:
        if not isinstance(row, dict) or row.get("classification") not in class_order:
            continue
        confidence = row.get("confidence")
        if confidence not in CONFIDENCE_ORDER or CONFIDENCE_ORDER[confidence] < min_confidence:
            continue
        if row.get("post_id") in suppressed:
            continue
        provenance = row.get("editorial_provenance")
        valid_sha = lambda value: (
            isinstance(value, str) and len(value) == 64
            and all(ch in "0123456789abcdef" for ch in value)
        )
        if (not isinstance(provenance, dict)
                or provenance.get("classification") != "reviewed_exact"
                or provenance.get("auto_adoptable") is not True
                or provenance.get("live_status") != "publish"
                or not valid_sha(provenance.get("live_content_sha256"))
                or not valid_sha(provenance.get("review_digest"))
                or not valid_sha(provenance.get("bundle_digest"))
                or not isinstance(provenance.get("provenance_variant"), str)
                or not provenance["provenance_variant"]
                or not isinstance(provenance.get("canonical_category_key"), str)
                or not provenance["canonical_category_key"]):
            continue
        if allowed_slugs is not None:
            row_slugs = set(row.get("category_slugs") or [])
            if not row_slugs.intersection(allowed_slugs):
                continue
        metrics = row.get("search_console") if isinstance(row.get("search_console"), dict) else {}
        result.append(row)
    result.sort(key=lambda row: (
        class_order[row["classification"]],
        -CONFIDENCE_ORDER[row["confidence"]],
        -int((row.get("search_console") or {}).get("impressions") or 0),
        int(row.get("post_id") or 0),
    ))
    return result


def _new_candidates(topic_scores: dict, *, work_log: dict, as_of: date,
                    category_keys=None) -> list[dict]:
    allowed = set(category_keys) if category_keys is not None else None
    completed_briefs = completed_new_brief_ids(work_log, as_of=as_of)
    result = []
    for row in topic_scores["candidates"]:
        if not isinstance(row, dict) or row.get("eligible_for_automation") is not True:
            continue
        if row.get("brief_id") in completed_briefs:
            continue
        if allowed is not None and row.get("category_key") not in allowed:
            continue
        confidence = row.get("confidence")
        if confidence not in CONFIDENCE_ORDER:
            continue
        result.append(row)
    result.sort(key=lambda row: (
        -int(row.get("score") or 0),
        -CONFIDENCE_ORDER[row["confidence"]],
        str(row.get("brief_id") or ""),
    ))
    return result


def _existing_target(row: dict) -> dict:
    metrics = row.get("search_console") or {}
    provenance = row.get("editorial_provenance") or {}
    return {
        "post_id": row.get("post_id"),
        "title": row.get("title"),
        "permalink": row.get("permalink"),
        "classification": row.get("classification"),
        "confidence": row.get("confidence"),
        "recommended_action": row.get("recommended_action"),
        "editorial_provenance": {
            key: provenance.get(key)
            for key in (
                "classification", "auto_adoptable", "live_status",
                "live_content_sha256", "review_digest", "bundle_digest",
                "provenance_variant", "canonical_category_key",
            )
        },
        "search_console": {
            "clicks": int(metrics.get("clicks") or 0),
            "impressions": int(metrics.get("impressions") or 0),
            "ctr": float(metrics.get("ctr") or 0.0),
            "position": metrics.get("position"),
        },
    }


def _new_target(row: dict) -> dict:
    return {
        "brief_id": row.get("brief_id"),
        "candidate_id": row.get("id"),
        "category_key": row.get("category_key"),
        "topic": row.get("topic"),
        "primary_keyword": row.get("primary_keyword"),
        "score": int(row.get("score") or 0),
        "confidence": row.get("confidence"),
    }


def _choose_mixed_action(existing: list[dict], new: list[dict], planner: dict,
                         work_log: dict, as_of: date) -> tuple[str, str, dict]:
    """Choose the action that moves recent completed work closest to the target mix."""
    mix = recent_work_mix(
        work_log, as_of=as_of, limit=planner["work_mix_lookback_actions"])
    existing_count = mix["existing_improvement"]
    new_count = mix["new_draft"]
    total = existing_count + new_count
    target = float(planner["target_existing_ratio"])
    existing_distance = abs(((existing_count + 1) / (total + 1)) - target)
    new_distance = abs((existing_count / (total + 1)) - target)
    if abs(existing_distance - new_distance) <= 1e-12:
        last = mix.get("last_action")
        if last == "existing_improvement":
            return "new_draft", "work_mix_tie_rotate_after_existing", mix
        if last == "new_draft":
            return "existing_improvement", "work_mix_tie_rotate_after_new", mix
        if planner["prefer_existing_improvement"]:
            return "existing_improvement", "work_mix_tie_prefer_existing", mix
        return "new_draft", "work_mix_tie_prefer_new", mix
    if existing_distance < new_distance:
        return "existing_improvement", "work_mix_existing_deficit", mix
    if new_distance < existing_distance:
        return "new_draft", "work_mix_new_deficit", mix
    raise GrowthPlannerError("unreachable_work_mix_choice")


def decide_daily_action(opportunities: dict, topic_scores: dict, policy: dict, *,
                        as_of: date, work_log=None, category_keys=None,
                        category_slug_map=None) -> dict:
    """Return one read-only daily action.  Invalid or stale inputs yield no_action."""
    planner = _planner_policy(policy)
    opportunity_ok, opportunity_reason = _validate_opportunities(opportunities, policy, as_of)
    opportunity_period_end = (
        (opportunities.get("period") or {}).get("end")
        if isinstance(opportunities, dict) else None
    )
    topic_ok, topic_reason = _validate_topic_scores(
        topic_scores, policy, as_of, opportunity_period_end=opportunity_period_end,
        opportunity_payload_sha256=(
            opportunities.get("opportunity_payload_sha256")
            if isinstance(opportunities, dict) else None
        ))
    if work_log is None:
        work_log = empty_work_log()
    try:
        validate_work_log(work_log, as_of=as_of)
        work_log_reason = ""
    except ValueError:
        work_log_reason = "growth_work_log_invalid"
    base = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "as_of_date": as_of.isoformat(),
        "policy_version": policy.get("version"),
        "daily_planner_digest": daily_planner_digest(policy),
        "topic_gate_digest": topic_gate_digest(policy),
        "inputs": {
            "opportunity_period_end": (opportunities.get("period") or {}).get("end")
                if isinstance(opportunities, dict) else None,
            "topic_score_as_of_date": topic_scores.get("as_of_date")
                if isinstance(topic_scores, dict) else None,
            "work_log_entries": len(work_log.get("entries", [])) if isinstance(work_log, dict) else None,
        },
        "category_keys": list(category_keys) if category_keys is not None else None,
    }
    if not opportunity_ok or not topic_ok or work_log_reason:
        reasons = [reason for reason in (opportunity_reason, topic_reason, work_log_reason) if reason]
        return dict(base, action="no_action", target=None,
                    reason="growth_inputs_unavailable_or_stale", details=reasons)

    existing = _existing_candidates(
        opportunities, policy, work_log=work_log, as_of=as_of,
        category_keys=category_keys, category_slug_map=category_slug_map)
    new = _new_candidates(
        topic_scores, work_log=work_log, as_of=as_of, category_keys=category_keys)

    mix = recent_work_mix(
        work_log, as_of=as_of, limit=planner["work_mix_lookback_actions"])
    base["work_mix"] = {
        **mix,
        "target_existing_ratio": float(planner["target_existing_ratio"]),
    }

    if existing and new:
        action, reason, _ = _choose_mixed_action(existing, new, planner, work_log, as_of)
        if action == "existing_improvement":
            return dict(base, action=action, target=_existing_target(existing[0]),
                        reason=reason, details=[])
        return dict(base, action=action, target=_new_target(new[0]),
                    reason=reason, details=[])

    if new:
        return dict(base, action="new_draft", target=_new_target(new[0]),
                    reason="highest_eligible_new_topic", details=[])

    if existing:
        return dict(base, action="existing_improvement", target=_existing_target(existing[0]),
                    reason="existing_opportunity_only", details=[])

    return dict(base, action="no_action", target=None,
                reason="no_actionable_existing_or_eligible_new_topic", details=[])


def save_daily_plan(plan: dict, output_dir: str | Path) -> Path:
    directory = Path(output_dir).absolute()
    if directory.is_symlink():
        raise GrowthPlannerError("daily_plan_output_directory_symlink_not_allowed")
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    if os.name == "posix" and directory.stat().st_mode & 0o077:
        raise GrowthPlannerError("daily_plan_output_directory_permissions_too_open")
    target = directory / "daily-growth-plan.json"
    if target.is_symlink():
        raise GrowthPlannerError("daily_plan_output_target_symlink_not_allowed")
    temp = None
    try:
        with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=directory, prefix=".daily-plan-",
                suffix=".tmp", delete=False) as handle:
            temp = Path(handle.name)
            if os.name == "posix":
                os.chmod(temp, 0o600)
            json.dump(plan, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, target)
    finally:
        if temp is not None and temp.exists():
            temp.unlink()
    return target
