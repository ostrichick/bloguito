"""Demand-evidence scoring and automation gate for candidate Bloguito topics.

The score is a production-priority heuristic, not a prediction of rankings,
traffic, revenue, or editorial correctness.  Only explicit measured evidence is
counted as demand.  Search Console relevance is derived from the private P1
growth report and only from candidate-provided ``gsc_terms``; the module does
not invent semantic matches.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile
import unicodedata


class TopicScoringError(ValueError):
    """Fail-closed candidate, policy, score-report, or storage error."""


CONFIDENCE_ORDER = {"low": 0, "medium": 1, "high": 2}
LEVELS = {"low", "medium", "high"}
BRIEF_INTENT_TYPES = {
    "guide", "lookup", "application", "calculator", "comparison",
    "decision", "troubleshooting",
}
DEMAND_METRICS = {
    "keyword_planner": {"avg_monthly_searches"},
    "google_trends": {"relative_interest"},
    "naver_datalab": {"relative_interest"},
}
REVIEW_DISPOSITIONS = {"active", "duplicate_existing"}


def _canonical_digest(value) -> str:
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _parse_date(value, *, code: str) -> date:
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        raise TopicScoringError(code) from None


def _normal_text(value: str) -> str:
    text = unicodedata.normalize("NFC", str(value)).casefold()
    return re.sub(r"[^0-9a-z가-힣]+", "", text)


def _topic_gate(policy: dict) -> dict:
    gate = policy.get("topic_gate") if isinstance(policy, dict) else None
    if not isinstance(gate, dict):
        raise TopicScoringError("topic_gate_policy_missing")
    required = {
        "min_score", "min_confidence", "max_score_age_days",
        "max_gsc_report_age_days", "max_demand_evidence_age_days",
        "min_useful_lifetime_days", "require_added_value", "weights",
        "allowed_demand_sources", "recognized_added_value",
    }
    if not required.issubset(gate):
        raise TopicScoringError("invalid_topic_gate_policy")
    weights = gate["weights"]
    expected_weights = {
        "demand_evidence", "gsc_relevance", "click_need", "ai_resilience",
        "added_value", "cluster_fit", "useful_lifetime",
        "competition_differentiation",
    }
    if not isinstance(weights, dict) or set(weights) != expected_weights:
        raise TopicScoringError("invalid_topic_gate_weights")
    if any(type(value) is not int or value < 0 for value in weights.values()):
        raise TopicScoringError("invalid_topic_gate_weights")
    if sum(weights.values()) != 100:
        raise TopicScoringError("topic_gate_weights_must_total_100")
    if gate["min_confidence"] not in CONFIDENCE_ORDER:
        raise TopicScoringError("invalid_topic_gate_min_confidence")
    return gate


def topic_gate_digest(policy: dict) -> str:
    """Bind score reports to the exact current topic-gate policy, not just a version label."""
    return _canonical_digest(_topic_gate(policy))


def brief_value_gate_reasons(brief: dict, policy: dict) -> list[str]:
    """Validate value-first metadata for scheduler automation only.

    The caller decides whether to enforce these reasons. Manual editorial flows
    intentionally do not call this gate, so a user-requested post is never held
    merely because growth/value metadata is absent or incomplete.
    """
    if not isinstance(brief, dict):
        return ["invalid_brief_value_metadata"]
    gate = _topic_gate(policy)
    intent = brief.get("intent_type")
    answerability = brief.get("ai_answerability")
    added = brief.get("added_value")
    reasons = []
    if intent not in BRIEF_INTENT_TYPES:
        reasons.append("brief_intent_type_missing_or_invalid")
    if answerability not in LEVELS:
        reasons.append("brief_ai_answerability_missing_or_invalid")
    recognized = set(gate["recognized_added_value"])
    if (not isinstance(added, list)
            or any(value not in recognized for value in added)
            or len(set(added)) != len(added)):
        reasons.append("brief_added_value_missing_or_invalid")
    elif answerability == "high" and not added:
        reasons.append("high_ai_answerability_without_added_value")
    return reasons


def _validate_candidate(candidate: dict, gate: dict) -> None:
    if not isinstance(candidate, dict):
        raise TopicScoringError("invalid_topic_candidate")
    required_text = ("id", "brief_id", "category_key", "topic", "primary_keyword")
    if any(not isinstance(candidate.get(key), str) or not candidate[key].strip()
           for key in required_text):
        raise TopicScoringError("invalid_topic_candidate_identity")
    disposition = candidate.get("review_disposition", "active")
    if disposition not in REVIEW_DISPOSITIONS:
        raise TopicScoringError("invalid_topic_candidate_review_disposition")
    if disposition == "duplicate_existing":
        if type(candidate.get("duplicate_post_id")) is not int or candidate["duplicate_post_id"] <= 0:
            raise TopicScoringError("invalid_topic_candidate_duplicate_post_id")
        _parse_date(candidate.get("reviewed_at"), code="invalid_topic_candidate_reviewed_at")
    for key in ("click_need", "ai_answerability", "cluster_fit",
                "competition_differentiation"):
        if candidate.get(key) not in LEVELS:
            raise TopicScoringError("invalid_topic_candidate_" + key)
    lifetime = candidate.get("useful_lifetime_days")
    if type(lifetime) is not int or not 0 <= lifetime <= 3650:
        raise TopicScoringError("invalid_topic_candidate_useful_lifetime_days")

    gsc_terms = candidate.get("gsc_terms", [])
    if (not isinstance(gsc_terms, list)
            or any(not isinstance(term, str) or not term.strip() for term in gsc_terms)
            or len(set(gsc_terms)) != len(gsc_terms)):
        raise TopicScoringError("invalid_topic_candidate_gsc_terms")

    added = candidate.get("added_value")
    recognized = set(gate["recognized_added_value"])
    if (not isinstance(added, list)
            or any(value not in recognized for value in added)
            or len(set(added)) != len(added)):
        raise TopicScoringError("invalid_topic_candidate_added_value")

    evidence = candidate.get("demand_evidence")
    allowed_sources = set(gate["allowed_demand_sources"])
    if not isinstance(evidence, list):
        raise TopicScoringError("invalid_topic_candidate_demand_evidence")
    for row in evidence:
        if not isinstance(row, dict):
            raise TopicScoringError("invalid_topic_candidate_demand_evidence")
        if row.get("source") not in allowed_sources:
            raise TopicScoringError("unsupported_topic_demand_source")
        if row.get("measured") is not True:
            raise TopicScoringError("topic_demand_evidence_must_be_measured")
        metric = row.get("metric")
        if not isinstance(metric, str) or not metric.strip():
            raise TopicScoringError("invalid_topic_demand_metric")
        if metric not in DEMAND_METRICS.get(row["source"], set()):
            raise TopicScoringError("unsupported_topic_demand_metric")
        value = row.get("value")
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(float(value)) or value < 0):
            raise TopicScoringError("invalid_topic_demand_value")
        _parse_date(row.get("collected_at"), code="invalid_topic_demand_collected_at")


def _fresh_external_evidence(candidate: dict, gate: dict, as_of: date) -> tuple[list[dict], list[dict]]:
    fresh = []
    stale = []
    max_age = int(gate["max_demand_evidence_age_days"])
    for row in candidate["demand_evidence"]:
        collected = _parse_date(row["collected_at"], code="invalid_topic_demand_collected_at")
        age = (as_of - collected).days
        item = dict(row, age_days=age)
        if age < 0 or age > max_age:
            stale.append(item)
        else:
            fresh.append(item)
    return fresh, stale


def _gsc_relevance(candidate: dict, growth_report: dict, gate: dict,
                   as_of: date, policy: dict) -> dict:
    if not isinstance(growth_report, dict):
        raise TopicScoringError("invalid_growth_opportunity_report")
    period = growth_report.get("period")
    if growth_report.get("schema_version") != 1 or not isinstance(period, dict):
        raise TopicScoringError("invalid_growth_opportunity_report")
    end = _parse_date(period.get("end"), code="invalid_growth_report_period")
    report_age = (as_of - end).days
    if report_age < 0 or report_age > int(gate["max_gsc_report_age_days"]):
        return {
            "fresh": False,
            "report_end": end.isoformat(),
            "report_age_days": report_age,
            "matched_queries": [],
            "clicks": 0,
            "impressions": 0,
        }

    terms = {_normal_text(term) for term in candidate.get("gsc_terms", []) if _normal_text(term)}
    matched = []
    for row in growth_report.get("top_queries_global", []):
        if not isinstance(row, dict) or not isinstance(row.get("query"), str):
            continue
        query_norm = _normal_text(row["query"])
        if terms and any(term in query_norm for term in terms):
            matched.append(row)
    clicks = sum(int(row.get("clicks") or 0) for row in matched)
    impressions = sum(int(row.get("impressions") or 0) for row in matched)
    return {
        "fresh": True,
        "report_end": end.isoformat(),
        "report_age_days": report_age,
        "matched_queries": [
            {
                "query": row["query"],
                "clicks": int(row.get("clicks") or 0),
                "impressions": int(row.get("impressions") or 0),
                "position": row.get("position"),
            }
            for row in matched
        ],
        "clicks": clicks,
        "impressions": impressions,
    }


def _scaled(weight: int, ratio: float) -> int:
    return min(weight, max(0, round(weight * ratio)))


def _component_scores(candidate: dict, fresh_evidence: list[dict], gsc: dict,
                      gate: dict, policy: dict) -> dict[str, int]:
    weights = gate["weights"]
    sources = {row["source"] for row in fresh_evidence if float(row["value"]) > 0}
    has_absolute_volume = any(
        row["source"] == "keyword_planner"
        and row["metric"] == "avg_monthly_searches"
        and float(row["value"]) > 0
        for row in fresh_evidence
    )
    demand = 0
    if sources:
        demand += _scaled(weights["demand_evidence"], 0.4)
    if has_absolute_volume:
        demand += _scaled(weights["demand_evidence"], 0.4)
    if len(sources) >= 2:
        demand += weights["demand_evidence"] - _scaled(weights["demand_evidence"], 0.8)
    demand = min(weights["demand_evidence"], demand)

    gsc_score = 0
    impressions = int(gsc["impressions"])
    clicks = int(gsc["clicks"])
    if gsc["fresh"] and impressions > 0:
        medium = int(policy["confidence"]["medium_impressions"])
        high = int(policy["confidence"]["high_impressions"])
        if impressions >= high:
            gsc_score = weights["gsc_relevance"]
        elif impressions >= medium or clicks > 0:
            gsc_score = _scaled(weights["gsc_relevance"], 0.8)
        else:
            gsc_score = _scaled(weights["gsc_relevance"], 0.5)

    level_ratio = {"high": 1.0, "medium": 0.55, "low": 0.0}
    inverse_ai_ratio = {"low": 1.0, "medium": 0.5, "high": 0.0}
    added_count = len(candidate["added_value"])
    added_ratio = 0.0 if added_count == 0 else 0.55 if added_count == 1 else 0.8 if added_count == 2 else 1.0
    lifetime = candidate["useful_lifetime_days"]
    lifetime_ratio = 1.0 if lifetime >= 180 else 0.6 if lifetime >= int(gate["min_useful_lifetime_days"]) else 0.0
    competition_ratio = {"high": 1.0, "medium": 0.6, "low": 0.0}
    return {
        "demand_evidence": demand,
        "gsc_relevance": gsc_score,
        "click_need": _scaled(weights["click_need"], level_ratio[candidate["click_need"]]),
        "ai_resilience": _scaled(weights["ai_resilience"], inverse_ai_ratio[candidate["ai_answerability"]]),
        "added_value": _scaled(weights["added_value"], added_ratio),
        "cluster_fit": _scaled(weights["cluster_fit"], level_ratio[candidate["cluster_fit"]]),
        "useful_lifetime": _scaled(weights["useful_lifetime"], lifetime_ratio),
        "competition_differentiation": _scaled(
            weights["competition_differentiation"],
            competition_ratio[candidate["competition_differentiation"]],
        ),
    }


def _confidence(fresh_evidence: list[dict], gsc: dict) -> str:
    positive = [row for row in fresh_evidence if float(row["value"]) > 0]
    sources = {row["source"] for row in positive}
    absolute = any(
        row["source"] == "keyword_planner"
        and row["metric"] == "avg_monthly_searches"
        and float(row["value"]) > 0
        for row in positive
    )
    gsc_present = gsc["fresh"] and int(gsc["impressions"]) > 0
    if (absolute and gsc_present) or len(sources) >= 2:
        return "high"
    if positive or gsc_present:
        return "medium"
    return "low"


def score_candidate(candidate: dict, growth_report: dict, policy: dict,
                    *, as_of: date) -> dict:
    gate = _topic_gate(policy)
    _validate_candidate(candidate, gate)
    fresh_evidence, stale_evidence = _fresh_external_evidence(candidate, gate, as_of)
    gsc = _gsc_relevance(candidate, growth_report, gate, as_of, policy)
    components = _component_scores(candidate, fresh_evidence, gsc, gate, policy)
    score = sum(components.values())
    confidence = _confidence(fresh_evidence, gsc)
    external_positive = any(float(row["value"]) > 0 for row in fresh_evidence)
    measured_demand_present = external_positive or (gsc["fresh"] and gsc["impressions"] > 0)

    reasons = []
    if not measured_demand_present:
        reasons.append("no_fresh_measured_demand_evidence")
    if score < int(gate["min_score"]):
        reasons.append("score_below_automation_threshold")
    if CONFIDENCE_ORDER[confidence] < CONFIDENCE_ORDER[gate["min_confidence"]]:
        reasons.append("confidence_below_automation_threshold")
    if candidate["useful_lifetime_days"] < int(gate["min_useful_lifetime_days"]):
        reasons.append("useful_lifetime_below_automation_minimum")
    if gate["require_added_value"] and not candidate["added_value"]:
        reasons.append("added_value_required")
    if stale_evidence:
        reasons.append("stale_external_demand_evidence_ignored")
    if not gsc["fresh"]:
        reasons.append("stale_gsc_report_ignored")
    if candidate.get("review_disposition", "active") == "duplicate_existing":
        reasons.append("duplicate_existing_post")

    eligible = not any(reason in reasons for reason in (
        "no_fresh_measured_demand_evidence",
        "score_below_automation_threshold",
        "confidence_below_automation_threshold",
        "useful_lifetime_below_automation_minimum",
        "added_value_required",
        "duplicate_existing_post",
    ))
    return {
        "id": candidate["id"],
        "brief_id": candidate["brief_id"],
        "category_key": candidate["category_key"],
        "topic": candidate["topic"],
        "primary_keyword": candidate["primary_keyword"],
        "review_disposition": candidate.get("review_disposition", "active"),
        "duplicate_post_id": candidate.get("duplicate_post_id"),
        "candidate_digest": _canonical_digest(candidate),
        "score": score,
        "confidence": confidence,
        "measured_demand_present": measured_demand_present,
        "eligible_for_automation": eligible,
        "components": components,
        "evidence_summary": {
            "fresh_external": fresh_evidence,
            "stale_external": stale_evidence,
            "gsc_related": gsc,
        },
        "reasons": reasons,
    }


def score_candidates(candidate_document: dict, growth_report: dict, policy: dict,
                     *, as_of: date) -> dict:
    gate = _topic_gate(policy)
    if (not isinstance(candidate_document, dict)
            or candidate_document.get("schema_version") != 1
            or not isinstance(candidate_document.get("candidates"), list)):
        raise TopicScoringError("invalid_topic_candidates_document")
    candidates = candidate_document["candidates"]
    ids = [candidate.get("id") for candidate in candidates if isinstance(candidate, dict)]
    brief_ids = [candidate.get("brief_id") for candidate in candidates if isinstance(candidate, dict)]
    if len(ids) != len(set(ids)) or len(brief_ids) != len(set(brief_ids)):
        raise TopicScoringError("duplicate_topic_candidate_identity")

    scored = [score_candidate(candidate, growth_report, policy, as_of=as_of)
              for candidate in candidates]
    scored.sort(key=lambda row: (-int(row["eligible_for_automation"]), -row["score"], row["id"]))
    eligible = sum(1 for row in scored if row["eligible_for_automation"])
    return {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "as_of_date": as_of.isoformat(),
        "policy_version": policy.get("version"),
        "topic_gate_digest": topic_gate_digest(policy),
        "growth_period_end": growth_report.get("period", {}).get("end"),
        "gate": {
            "min_score": int(gate["min_score"]),
            "min_confidence": gate["min_confidence"],
            "max_score_age_days": int(gate["max_score_age_days"]),
            "min_useful_lifetime_days": int(gate["min_useful_lifetime_days"]),
        },
        "summary": {
            "candidates": len(scored),
            "eligible_for_automation": eligible,
            "held": len(scored) - eligible,
        },
        "candidates": scored,
        "limitations": [
            "Topic scores are production-priority heuristics, not traffic, ranking, or revenue forecasts.",
            "Only explicitly measured fresh external evidence or matched fresh Search Console queries count as demand.",
            "Search Console query matching uses explicit candidate gsc_terms; no semantic similarity is inferred.",
            "Eligibility does not replace duplicate, official-source, lifecycle, semantic-review, or draft-only checks.",
        ],
    }


def brief_growth_gate_reasons(brief: dict, score_report: dict, policy: dict,
                              *, today: date) -> list[str]:
    """Return reasons an automatic scheduler must reject one reviewed brief."""
    gate = _topic_gate(policy)
    if not isinstance(score_report, dict) or score_report.get("schema_version") != 1:
        return ["growth_score_report_unavailable_or_invalid"]
    if score_report.get("policy_version") != policy.get("version"):
        return ["growth_score_policy_version_mismatch"]
    if score_report.get("topic_gate_digest") != topic_gate_digest(policy):
        return ["growth_score_policy_digest_mismatch"]
    try:
        scored_on = _parse_date(score_report.get("as_of_date"), code="invalid_topic_score_date")
    except TopicScoringError:
        return ["growth_score_report_unavailable_or_invalid"]
    age = (today - scored_on).days
    if age < 0 or age > int(gate["max_score_age_days"]):
        return ["growth_score_report_stale"]
    rows = score_report.get("candidates")
    if not isinstance(rows, list):
        return ["growth_score_report_unavailable_or_invalid"]
    matches = [row for row in rows if isinstance(row, dict) and row.get("brief_id") == brief.get("id")]
    if len(matches) != 1:
        return ["growth_score_missing_for_brief"]
    row = matches[0]
    reasons = []
    if row.get("category_key") != brief.get("category_key"):
        reasons.append("growth_score_category_mismatch")
    if row.get("primary_keyword") != brief.get("primary_keyword"):
        reasons.append("growth_score_keyword_mismatch")
    if row.get("measured_demand_present") is not True:
        reasons.append("growth_score_has_no_measured_demand")
    try:
        score = int(row.get("score"))
    except (TypeError, ValueError):
        score = -1
    if score < int(gate["min_score"]):
        reasons.append("growth_score_below_threshold")
    confidence = row.get("confidence")
    if confidence not in CONFIDENCE_ORDER or CONFIDENCE_ORDER[confidence] < CONFIDENCE_ORDER[gate["min_confidence"]]:
        reasons.append("growth_score_confidence_below_threshold")
    if row.get("eligible_for_automation") is not True:
        reasons.append("growth_score_not_eligible_for_automation")
    return reasons


def save_topic_scores(report: dict, output_dir: str | Path) -> Path:
    """Atomically save private score state without following symlink targets."""
    directory = Path(output_dir).absolute()
    if directory.is_symlink():
        raise TopicScoringError("topic_score_output_directory_symlink_not_allowed")
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    if os.name == "posix" and directory.stat().st_mode & 0o077:
        raise TopicScoringError("topic_score_output_directory_permissions_too_open")
    target = directory / "topic-candidate-scores.json"
    if target.is_symlink():
        raise TopicScoringError("topic_score_output_target_symlink_not_allowed")
    temp = None
    try:
        with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=directory, prefix=".topic-score-",
                suffix=".tmp", delete=False) as handle:
            temp = Path(handle.name)
            if os.name == "posix":
                os.chmod(temp, 0o600)
            json.dump(report, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, target)
    finally:
        if temp is not None and temp.exists():
            temp.unlink()
    return target
