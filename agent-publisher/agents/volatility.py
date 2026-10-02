"""Volatility metadata and read-only migration helpers.

The first rollout is deliberately additive. Existing briefs without explicit
volatility metadata keep the legacy content_type/category freshness contract.
Migration helpers only return suggestions; they never mutate briefs, manifests,
WordPress state or approval windows.
"""

from __future__ import annotations

import copy
import re
from datetime import date
from typing import Iterable


VOLATILITY_VALUES = frozenset({
    "timeless-procedure",
    "policy-current",
    "annual-policy",
    "seasonal",
    "one-off",
})
VOLATILITY_CONTRACT_VERSION = 1

_LIVE_TEXT = re.compile(
    r"(?:현재|지금|예매|판매|접수|신청\s*가능|재고|잔여|좌석|금리|운영\s*중|마감\s*임박)"
)


def metadata_reasons(brief: dict) -> list[str]:
    """Validate only explicitly supplied volatility metadata.

    Missing metadata is valid for compatibility. Invalid explicit metadata is
    fail-closed so a typo cannot silently weaken freshness handling.
    """
    if not isinstance(brief, dict):
        return ["malformed_topic"]
    reasons = []
    if "volatility" in brief and brief.get("volatility") not in VOLATILITY_VALUES:
        reasons.append("invalid_volatility")
    if "requires_live_state" in brief and type(brief.get("requires_live_state")) is not bool:
        reasons.append("invalid_requires_live_state")
    if ("requires_current_value_period" in brief
            and type(brief.get("requires_current_value_period")) is not bool):
        reasons.append("invalid_requires_current_value_period")
    return reasons


def lifecycle_reasons(brief: dict) -> list[str]:
    """Additive lifecycle checks for explicit metadata only.

    These rules intentionally sit on top of the legacy topic rules. They do not
    grant an exception from content_type, useful_until, category or temporal
    evidence requirements.
    """
    reasons = metadata_reasons(brief)
    volatility = brief.get("volatility") if isinstance(brief, dict) else None
    if volatility not in VOLATILITY_VALUES:
        return reasons
    content_type = brief.get("content_type")
    useful_until = brief.get("useful_until")
    if volatility == "timeless-procedure":
        if content_type != "evergreen" or useful_until is not None:
            reasons.append("timeless_procedure_requires_evergreen")
    elif volatility in {"annual-policy", "seasonal", "one-off"}:
        if content_type != "dated" or not useful_until:
            reasons.append("bounded_volatility_requires_dated_lifetime")
    combined = " ".join(str(brief.get(key) or "") for key in (
        "primary_keyword", "question", "angle", "evergreen_reason"
    ))
    if _LIVE_TEXT.search(combined) and brief.get("requires_live_state") is not True:
        reasons.append("live_state_claim_requires_live_refresh")
    if brief.get("requires_current_value_period") is True:
        if (volatility != "policy-current" or content_type != "evergreen"
                or useful_until is not None):
            reasons.append("current_value_period_requires_policy_current_evergreen")
        if brief.get("requires_live_state") is not True:
            reasons.append("current_value_period_requires_live_refresh")
    # policy-current intentionally adds no deadline exemption. The legacy
    # content_type/category rules remain authoritative during the fallback
    # release, so either current legacy shape may coexist with this label.
    return sorted(set(reasons))


def temporal_contract_reasons(bundle: dict) -> list[str]:
    """Validate temporal mode compatibility for explicit lifecycle metadata."""
    if not isinstance(bundle, dict):
        return []
    brief = bundle.get("brief") if isinstance(bundle.get("brief"), dict) else {}
    volatility = brief.get("volatility")
    if volatility not in VOLATILITY_VALUES:
        return []
    temporal = bundle.get("temporal_source") if isinstance(bundle.get("temporal_source"), dict) else {}
    reasons = []
    if volatility == "annual-policy":
        if not (temporal.get("reference_period") or temporal.get("legacy_reference_period")):
            reasons.append("annual_policy_reference_period_required")
    if volatility == "timeless-procedure":
        dated_modes = (
            "reference_period",
            "legacy_reference_period",
            "legacy_followup",
            "multi_event_schedule",
            "schedule_listing_only",
        )
        if any(temporal.get(key) for key in dated_modes) or bool(temporal.get("evidence")):
            reasons.append("timeless_procedure_temporal_contract_conflict")
    if temporal.get("current_value_period") is not None:
        if (volatility != "policy-current"
                or brief.get("content_type") != "evergreen"
                or brief.get("useful_until") is not None):
            reasons.append("current_value_period_requires_policy_current_evergreen")
        if brief.get("requires_live_state") is not True:
            reasons.append("current_value_period_requires_live_refresh")
    return reasons


def explicit_contract(brief: dict) -> dict | None:
    """Return the fingerprint payload only when metadata was explicitly set."""
    if not isinstance(brief, dict):
        return None
    if ("volatility" not in brief and "requires_live_state" not in brief
            and "requires_current_value_period" not in brief):
        return None
    return {
        "version": VOLATILITY_CONTRACT_VERSION,
        "volatility": brief.get("volatility"),
        "requires_live_state": brief.get("requires_live_state", False),
        "requires_current_value_period": brief.get("requires_current_value_period", False),
        "allowed_volatility": sorted(VOLATILITY_VALUES),
    }


def requires_live_refresh(brief: dict | None) -> bool:
    """Return whether explicit metadata requires a network recheck.

    Post-level true is conservative and refreshes every reviewed source. The
    existing text regex remains an independent fallback in source cache code.
    """
    return isinstance(brief, dict) and brief.get("requires_live_state") is True


def migration_candidate(brief: dict, *, today: date | None = None) -> dict:
    """Return a deterministic, non-mutating migration suggestion for one brief."""
    today = today or date.today()
    original = copy.deepcopy(brief)
    brief_id = str(brief.get("id") or "")
    category = brief.get("category_key")
    content_type = brief.get("content_type")
    combined = " ".join(str(brief.get(key) or "") for key in (
        "id", "entity", "primary_keyword", "question", "angle", "evergreen_reason"
    ))
    signals = []
    conflicts = []
    candidate = None
    confidence = "low"

    if brief.get("event_post_standard_version") == 1:
        candidate, confidence = "one-off", "high"
        signals.append("event_post_standard")
    elif category == "concert" and content_type == "dated":
        candidate, confidence = "one-off", "high"
        signals.append("dated_concert")
    elif "energy-voucher" in brief_id or re.search(r"독감|예방접종|시즌|계절", combined):
        candidate, confidence = "seasonal", "high"
        signals.append("seasonal_program_signal")
    elif ("earned-income-tax-credit" in brief_id or "car-tax-annual" in brief_id
          or re.search(r"매년|연도별|정기\s*개정", combined)):
        candidate, confidence = "annual-policy", "high"
        signals.append("annual_recurrence_signal")
    elif category == "life-admin" and content_type == "evergreen":
        candidate, confidence = "timeless-procedure", "high"
        signals.append("evergreen_administrative_procedure")
    elif category in {"health", "welfare", "tax", "transport", "finance"}:
        candidate, confidence = "policy-current", "medium"
        signals.append("mutable_policy_domain")
    elif content_type == "dated":
        candidate, confidence = "one-off", "low"
        signals.append("legacy_dated_fallback")
    elif content_type == "evergreen":
        candidate, confidence = "policy-current", "low"
        signals.append("legacy_evergreen_fallback")

    requires_live = bool(_LIVE_TEXT.search(combined))
    if requires_live:
        signals.append("current_state_language")
    if candidate == "timeless-procedure" and requires_live:
        conflicts.append("timeless_procedure_contains_live_state_language")
    if candidate in {"annual-policy", "seasonal", "one-off"} and content_type != "dated":
        conflicts.append("bounded_candidate_conflicts_with_content_type")
    if candidate == "timeless-procedure" and content_type != "evergreen":
        conflicts.append("timeless_candidate_conflicts_with_content_type")
    if candidate == "policy-current" and content_type == "dated":
        conflicts.append("policy_current_keeps_legacy_dated_contract")

    try:
        review_window_current = bool(
            brief.get("approved")
            and date.fromisoformat(brief["reviewed_at"]) <= today <= date.fromisoformat(brief["review_until"])
        )
    except (KeyError, TypeError, ValueError):
        review_window_current = False

    result = {
        "id": brief.get("id"),
        "existing_content_type": content_type,
        "category_key": category,
        "current_volatility": brief.get("volatility") if "volatility" in brief else None,
        "current_requires_live_state": (
            brief.get("requires_live_state") if "requires_live_state" in brief else None
        ),
        "explicit_metadata_present": (
            "volatility" in brief or "requires_live_state" in brief
        ),
        "suggested_volatility": candidate,
        "suggested_requires_live_state": requires_live,
        "confidence": confidence,
        "signals": signals,
        "conflicts": conflicts,
        "requires_review": confidence != "high" or bool(conflicts),
        "reviewed_at": brief.get("reviewed_at"),
        "review_until": brief.get("review_until"),
        "approved": brief.get("approved"),
        "review_window_current": review_window_current,
    }
    result["suggestion_matches_current"] = (
        result["current_volatility"] == candidate
        and result["current_requires_live_state"] == requires_live
        if result["explicit_metadata_present"] else None
    )
    if brief != original:
        raise AssertionError("volatility_migration_must_not_mutate_input")
    return result


def migration_report(briefs: Iterable[dict], *, today: date | None = None) -> list[dict]:
    """Return migration candidates without writing any source data."""
    return [migration_candidate(brief, today=today) for brief in briefs]
