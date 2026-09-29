"""Scope-aware validation planning for reviewed Bloguito edits.

This module does not weaken editorial validation.  It decides which *regression*
checks and reader-facing QA scopes are relevant to the observed change while the
existing Fast/Standard editorial routes keep their source, semantic-review, CAS,
backup and readback contracts.
"""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from pathlib import Path

from agents.editorial import render
from agents.fast_edit import FULL_REVIEW_REQUIRED, classify_fast_edit
from agents.qa_scope import qa_requirements_for_edit


VALIDATION_PROFILES = {
    "no-op",
    "docs-only",
    "quick-text",
    "quick-image",
    "standard-fact",
    "standard-source",
    "standard-cta",
    "standard-layout",
    "standard-event",
    "full-regression",
}

_ROUTES = {"fast", "standard", "image-only", "repository", "auto", None}

_KNOWN_BUNDLE_KEYS = {
    "brief",
    "sources",
    "plan",
    "temporal_source",
    "review",
    "fast_edit_review",
    "fast_edit_chain",
    "authoring",
    "used_model",
}

_FULL_REGRESSION_EXACT = {
    "agent-publisher/editorial_cli.py",
    "agent-publisher/editorial_policy.json",
    "scripts/editorial_cli_via_ssh.py",
    "scripts/run_validation.py",
    "agent-publisher/tests/test_groups.json",
    ".github/workflows/test.yml",
}


def _stable_digest(value) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _normal_path(value: str | Path) -> str:
    return str(value).replace("\\", "/").lstrip("./").lower()


def repository_change_profile(changed_files) -> dict:
    """Classify repository-file changes for regression breadth.

    Common editorial/runtime code and test-infrastructure changes require the full
    suite.  Pure documentation changes do not.  Other tracked source changes are
    conservatively full-regression rather than silently under-testing them.
    """
    paths = sorted({_normal_path(path) for path in (changed_files or []) if str(path).strip()})
    if not paths:
        return {"profile": None, "reasons": []}
    if all(path.startswith("docs/") or path in {"agents.md", "scripts/readme.md"} for path in paths):
        return {"profile": "docs-only", "reasons": ["documentation_only"]}

    reasons = []
    for path in paths:
        if (
            path in _FULL_REGRESSION_EXACT
            or path.startswith("agent-publisher/agents/")
            or path.startswith("agent-publisher/tests/")
            or path.startswith("wordpress/")
            or path.endswith(".php")
        ):
            reasons.append("shared_or_test_code_changed:" + path)
    if reasons:
        return {"profile": "full-regression", "reasons": reasons}

    # Unknown source/config changes are deliberately fail-closed.
    non_docs = [path for path in paths if not path.startswith("docs/")]
    if non_docs:
        return {
            "profile": "full-regression",
            "reasons": ["unclassified_repository_change:" + path for path in non_docs],
        }
    return {"profile": "docs-only", "reasons": ["documentation_only"]}


def _event_domain(bundle: dict | None) -> bool:
    if not isinstance(bundle, dict):
        return False
    temporal = bundle.get("temporal_source") or {}
    if temporal.get("multi_event_schedule") or temporal.get("event_entries"):
        return True
    brief = bundle.get("brief") or {}
    text = " ".join(str(brief.get(key) or "") for key in ("entity", "primary_keyword", "question"))
    return any(token in text for token in ("행사", "축제", "페어"))


def _ticket_domain(bundle: dict | None) -> bool:
    if not isinstance(bundle, dict):
        return False
    return (bundle.get("brief") or {}).get("category_key") == "concert"


def _source_evidence_signature(bundle: dict) -> list[dict]:
    """Source snapshot identity without executable action metadata."""
    result = []
    for source in bundle.get("sources", []) or []:
        if not isinstance(source, dict):
            result.append(source)
            continue
        item = deepcopy(source)
        item.pop("actions", None)
        result.append(item)
    return result


def analyze_edit_scope(
    old_bundle: dict | None,
    new_bundle: dict | None,
    *,
    image_changed: bool = False,
    target_status: str = "draft",
    resume: bool = False,
) -> dict:
    """Return deterministic change flags used by validation planning."""
    if old_bundle is None or new_bundle is None:
        return {
            "content_changed": False,
            "image_changed": bool(image_changed),
            "title_changed": False,
            "brief_changed": False,
            "category_changed": False,
            "seo_changed": False,
            "sources_changed": False,
            "actions_changed": False,
            "temporal_changed": False,
            "layout_changed": False,
            "related_changed": False,
            "review_metadata_changed": False,
            "unknown_bundle_change": False,
            "factual_risk": False,
            "event_domain": False,
            "ticket_domain": False,
            "target_status": target_status,
            "resume": bool(resume),
            "fast_candidate": False,
            "fast_reasons": [],
            "qa_scopes": qa_requirements_for_edit(
                old_bundle, new_bundle, image_changed=image_changed, target_status=target_status),
        }

    old_plan = old_bundle.get("plan") or {}
    new_plan = new_bundle.get("plan") or {}
    old_brief = old_bundle.get("brief") or {}
    new_brief = new_bundle.get("brief") or {}
    qa_scopes = qa_requirements_for_edit(
        old_bundle, new_bundle, image_changed=image_changed, target_status=target_status)
    fast = classify_fast_edit(old_bundle, new_bundle)
    fast_reasons = list(fast.get("reasons", []))

    changed_unknown = sorted(
        key for key in (set(old_bundle) | set(new_bundle)) - _KNOWN_BUNDLE_KEYS
        if old_bundle.get(key) != new_bundle.get(key)
    )
    review_metadata_changed = any(
        old_bundle.get(key) != new_bundle.get(key)
        for key in ("review", "fast_edit_review", "fast_edit_chain")
    )
    source_changed = _source_evidence_signature(old_bundle) != _source_evidence_signature(new_bundle)
    temporal_changed = old_bundle.get("temporal_source", {}) != new_bundle.get("temporal_source", {})
    brief_changed = old_brief != new_brief
    title_changed = old_plan.get("title") != new_plan.get("title")
    category_changed = old_brief.get("category_key") != new_brief.get("category_key")
    related_changed = old_plan.get("related_posts", []) != new_plan.get("related_posts", [])
    seo_changed = (
        old_brief.get("seo") != new_brief.get("seo")
        or old_brief.get("primary_keyword") != new_brief.get("primary_keyword")
    )
    risky_fast_reasons = tuple(
        reason for reason in fast_reasons
        if reason.startswith("new_fact_tokens:")
        or reason in {
            "brief_changed",
            "new_high_risk_claim",
            "title_changed",
        }
    )
    return {
        "content_changed": "content-mobile-desktop" in qa_scopes,
        "image_changed": bool(image_changed),
        "title_changed": title_changed,
        "brief_changed": brief_changed,
        "category_changed": category_changed,
        "seo_changed": seo_changed,
        "sources_changed": source_changed,
        "actions_changed": "cta-destination" in qa_scopes,
        "temporal_changed": temporal_changed,
        "layout_changed": "layout-accessibility" in qa_scopes,
        "related_changed": related_changed,
        "review_metadata_changed": review_metadata_changed,
        "unknown_bundle_change": bool(changed_unknown),
        "unknown_bundle_keys": changed_unknown,
        "factual_risk": bool(risky_fast_reasons),
        "event_domain": _event_domain(new_bundle) or _event_domain(old_bundle),
        "ticket_domain": _ticket_domain(new_bundle) or _ticket_domain(old_bundle),
        "target_status": target_status,
        "resume": bool(resume),
        "fast_candidate": fast.get("status") != FULL_REVIEW_REQUIRED,
        "fast_reasons": fast_reasons,
        "qa_scopes": qa_scopes,
    }


def _profile_for_scope(scope: dict, route: str | None) -> tuple[str, list[str]]:
    if scope.get("unknown_bundle_change"):
        reasons = ["unclassified_bundle_change_requires_full_regression"]
        reasons.extend("unknown_bundle_key:" + key for key in scope.get("unknown_bundle_keys", []))
        return "full-regression", reasons
    if route == "image-only" or (scope.get("image_changed") and not scope.get("content_changed")):
        return "quick-image", ["image_only_change"]
    if not any(scope.get(key) for key in (
            "content_changed", "image_changed", "brief_changed", "sources_changed",
            "temporal_changed", "title_changed", "related_changed", "seo_changed")):
        return "no-op", ["no_reader_or_metadata_change"]
    domain_sensitive_change = any(scope.get(key) for key in (
        "factual_risk", "sources_changed", "temporal_changed", "actions_changed",
        "brief_changed", "title_changed", "category_changed",
    ))
    if (scope.get("event_domain") or scope.get("ticket_domain")) and domain_sensitive_change:
        return "standard-event", ["event_or_ticket_domain_change"]
    if scope.get("layout_changed"):
        return "standard-layout", ["layout_topology_changed"]
    if route == "fast" and scope.get("content_changed"):
        return "quick-text", ["canonical_fast_route_existing_evidence_only"]
    # Once the canonical edit router has chosen Standard, the validation plan may
    # never downgrade itself back to a Quick profile based on an independent diff.
    if route == "standard":
        if scope.get("event_domain") or scope.get("ticket_domain"):
            return "standard-event", ["canonical_standard_event_or_ticket_change"]
        if scope.get("sources_changed"):
            return "standard-source", ["canonical_standard_source_change"]
        if scope.get("actions_changed"):
            return "standard-cta", ["canonical_standard_cta_change"]
        return "standard-fact", ["canonical_standard_fact_or_metadata_change"]
    if scope.get("event_domain") and (
            scope.get("content_changed") or scope.get("factual_risk") or scope.get("sources_changed")
            or scope.get("temporal_changed") or scope.get("actions_changed")):
        return "standard-event", ["event_domain_change"]
    if scope.get("sources_changed"):
        return "standard-source", ["source_set_or_snapshot_changed"]
    if scope.get("actions_changed"):
        return "standard-cta", ["cta_or_navigation_changed"]
    if (scope.get("factual_risk") or scope.get("brief_changed") or scope.get("temporal_changed")
            or scope.get("title_changed") or scope.get("seo_changed") or scope.get("related_changed")):
        return "standard-fact", ["factual_or_metadata_scope_changed"]
    if scope.get("layout_changed"):
        # Fast layout changes reuse the existing facts/evidence but still need the
        # layout regression group and layout/accessibility browser QA.
        return "standard-layout", ["layout_topology_changed"]
    if route in {None, "auto"} and scope.get("content_changed") and scope.get("fast_candidate"):
        return "quick-text", ["fast_candidate_existing_evidence_only"]
    if scope.get("content_changed"):
        return "standard-fact", ["content_change_not_proven_fast"]
    return "full-regression", ["unclassified_edit_scope_requires_full_regression"]


def _test_groups_for_scope(profile: str, scope: dict, route: str | None) -> list[str]:
    if profile == "full-regression":
        return ["full-regression"]
    if profile in {"no-op", "docs-only"}:
        return []

    groups = {"core-safe-edit"}
    if route == "fast":
        groups.add("fast-edit")
    if scope.get("target_status") == "publish" and scope.get("content_changed"):
        groups.add("public-edit")
    if scope.get("resume"):
        groups.add("resume")
    if profile == "quick-image" or scope.get("image_changed"):
        groups.add("image")
    if (scope.get("factual_risk") or scope.get("brief_changed") or scope.get("title_changed")
            or scope.get("seo_changed")):
        groups.add("fact")
    if scope.get("sources_changed"):
        groups.add("source")
    if scope.get("temporal_changed"):
        groups.add("temporal")
    if scope.get("actions_changed") or scope.get("related_changed"):
        groups.add("cta")
    if scope.get("layout_changed"):
        groups.add("layout")
    domain_sensitive_change = any(scope.get(key) for key in (
        "factual_risk", "sources_changed", "temporal_changed", "actions_changed",
        "brief_changed", "title_changed", "category_changed",
    ))
    if (scope.get("event_domain")
            and (domain_sensitive_change or profile == "standard-event")
            and profile != "quick-image"):
        groups.add("event")
    if scope.get("ticket_domain") and domain_sensitive_change and profile != "quick-image":
        groups.add("ticket")
    if (scope.get("title_changed") or scope.get("seo_changed") or scope.get("related_changed")
            or scope.get("category_changed")):
        groups.add("catalog")
    if route == "standard":
        groups.add("editorial-contract")
        groups.add("public-standard" if scope.get("target_status") == "publish" else "draft-standard")
    return sorted(groups)


def _content_sha(bundle: dict | None) -> str | None:
    if not isinstance(bundle, dict):
        return None
    plan = bundle.get("plan")
    sources = bundle.get("sources")
    if not isinstance(plan, dict) or not isinstance(sources, list):
        return None
    return hashlib.sha256(render(plan, sources).encode("utf-8")).hexdigest()


def build_validation_plan(
    old_bundle: dict | None = None,
    new_bundle: dict | None = None,
    *,
    image_changed: bool = False,
    target_status: str = "draft",
    changed_files=None,
    resume: bool = False,
    route: str | None = "auto",
    post_id: int | None = None,
    expected_content_sha256: str | None = None,
) -> dict:
    """Build a fail-closed validation plan without running any mutation."""
    if route not in _ROUTES:
        raise ValueError("unknown_validation_route:" + str(route))
    if target_status not in {"draft", "publish"}:
        raise ValueError("unknown_validation_target_status:" + str(target_status))
    if post_id is not None and (type(post_id) is not int or post_id <= 0):
        raise ValueError("invalid_validation_post_id")
    if expected_content_sha256 is not None and not re.fullmatch(r"[0-9a-f]{64}", expected_content_sha256):
        raise ValueError("invalid_validation_expected_content_sha256")
    repository = repository_change_profile(changed_files)
    scope = analyze_edit_scope(
        old_bundle, new_bundle, image_changed=image_changed, target_status=target_status,
        resume=resume)
    resolved_route = route
    if repository["profile"] in {"full-regression", "docs-only"}:
        resolved_route = "repository"
        profile = repository["profile"]
        reasons = list(repository["reasons"])
    else:
        if resolved_route in {None, "auto"}:
            if image_changed and not scope.get("content_changed"):
                resolved_route = "image-only"
            elif scope.get("content_changed"):
                resolved_route = "fast" if scope.get("fast_candidate") else "standard"
            else:
                resolved_route = "auto"
        profile, reasons = _profile_for_scope(scope, resolved_route)

    if profile not in VALIDATION_PROFILES:
        raise ValueError("unknown_validation_profile:" + str(profile))
    groups = _test_groups_for_scope(profile, scope, resolved_route)
    source_mode = "reuse"
    if profile in {"no-op", "docs-only", "quick-image"}:
        source_mode = "not-applicable"
    elif resolved_route == "fast":
        source_mode = "reuse"
    elif scope.get("sources_changed"):
        source_mode = "full"
    elif resolved_route == "standard" or profile in {"standard-fact", "standard-cta", "standard-event"}:
        source_mode = "affected-or-live"

    if resolved_route == "fast":
        semantic_review = "delta"
    elif profile in {"no-op", "docs-only", "quick-image"}:
        semantic_review = "none"
    else:
        semantic_review = "full"

    before_sha = expected_content_sha256 or _content_sha(old_bundle)
    after_sha = _content_sha(new_bundle) or before_sha
    plan = {
        "version": 1,
        "profile": profile,
        "reasons": reasons,
        "scope": deepcopy(scope),
        "test_groups": groups,
        "source_validation": source_mode,
        "semantic_review": semantic_review,
        "qa_scopes": list(scope.get("qa_scopes", [])),
        "full_regression_required": profile == "full-regression",
        "binding": {
            "post_id": post_id,
            "target_status": target_status,
            "route": resolved_route,
            "before_content_sha256": before_sha,
            "after_content_sha256": after_sha,
        },
        "before_digest": _stable_digest(old_bundle) if old_bundle is not None else None,
        "after_digest": _stable_digest(new_bundle) if new_bundle is not None else None,
    }
    plan["plan_digest"] = _stable_digest(plan)
    return plan


def validate_validation_plan(plan: dict) -> dict:
    """Validate a serialized plan before using it to select or run tests."""
    if not isinstance(plan, dict) or plan.get("version") != 1:
        raise ValueError("invalid_validation_plan")
    if plan.get("profile") not in VALIDATION_PROFILES:
        raise ValueError("invalid_validation_plan_profile")
    if not isinstance(plan.get("test_groups"), list):
        raise ValueError("invalid_validation_plan_groups")
    binding = plan.get("binding")
    if not isinstance(binding, dict) or binding.get("target_status") not in {"draft", "publish"}:
        raise ValueError("invalid_validation_plan_binding")
    if binding.get("route") not in {"fast", "standard", "image-only", "repository", "auto"}:
        raise ValueError("invalid_validation_plan_binding")
    for key in ("before_content_sha256", "after_content_sha256"):
        value = binding.get(key)
        if value is not None and not re.fullmatch(r"[0-9a-f]{64}", value):
            raise ValueError("invalid_validation_plan_binding")
    supplied = plan.get("plan_digest")
    body = deepcopy(plan)
    body.pop("plan_digest", None)
    if not isinstance(supplied, str) or supplied != _stable_digest(body):
        raise ValueError("validation_plan_digest_mismatch")
    return plan
