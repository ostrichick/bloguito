"""Single deterministic change classifier for reviewed post edits.

The classifier owns route, reader-facing QA scope and coarse risk.  Callers may
perform deeper route-specific checks, but they should not independently infer the
same edit scope again.
"""

from __future__ import annotations

from copy import deepcopy

from agents.editorial import render
from agents.fast_edit import FULL_REVIEW_REQUIRED, classify_fast_edit


def _actions(bundle: dict) -> list:
    rows = []
    for source in bundle.get("sources", []) or []:
        if isinstance(source, dict):
            rows.extend(source.get("actions", []) or [])
    rows.extend(bundle.get("plan", {}).get("official_navigation", []) or [])
    return rows


def _layout_signature(bundle: dict) -> list:
    result = []
    for section in bundle.get("plan", {}).get("sections", []) or []:
        table = section.get("table") or {}
        result.append({
            "section_kind": section.get("kind"),
            "has_table": bool(table),
            "headers": list(table.get("headers", [])) if table else [],
            "caption": table.get("caption", "") if table else "",
            "row_widths": [len(row.get("cells", [])) for row in table.get("rows", [])] if table else [],
            "paragraph_count": len(section.get("paragraphs", [])),
        })
    return result


def _source_evidence_signature(bundle: dict) -> list[dict]:
    result = []
    for source in bundle.get("sources", []) or []:
        if not isinstance(source, dict):
            result.append(source)
            continue
        item = deepcopy(source)
        item.pop("actions", None)
        result.append(item)
    return result


def _event_domain(bundle: dict | None) -> bool:
    if not isinstance(bundle, dict):
        return False
    brief = bundle.get("brief") or {}
    if brief.get("category_key") == "events":
        return True
    temporal = bundle.get("temporal_source") or {}
    if temporal.get("multi_event_schedule") or temporal.get("event_entries"):
        return True
    text = " ".join(str(brief.get(key) or "") for key in ("entity", "primary_keyword", "question"))
    return any(token in text for token in ("행사", "축제", "페어"))


def _ticket_domain(bundle: dict | None) -> bool:
    return isinstance(bundle, dict) and (bundle.get("brief") or {}).get("category_key") == "concert"


def _qa_scopes(*, layout_changed: bool, actions_changed: bool) -> list[str]:
    """Browser QA is reserved for behavior/layout changes.

    Text-only, image-only and metadata-only edits are verified by deterministic
    readback and do not require a browser session by default.
    """
    required = set()
    if layout_changed:
        required.update({"content-mobile-desktop", "layout-accessibility"})
    if actions_changed:
        required.add("cta-destination")
    return sorted(required)


def classify_change(
    old_bundle: dict | None,
    new_bundle: dict | None,
    *,
    image_changed: bool = False,
    target_status: str = "draft",
    resume: bool = False,
    fast_report: dict | None = None,
    force_standard: bool = False,
) -> dict:
    """Return the one canonical route/scope decision for an edit."""
    if old_bundle is None or new_bundle is None:
        route = "image-only" if image_changed else "auto"
        return {
            "route": route,
            "risk_level": "image" if image_changed else "none",
            "reasons": ["image_only_change"] if image_changed else ["no_bundle_change"],
            "fast_report": fast_report,
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
            "unknown_bundle_keys": [],
            "factual_risk": False,
            "event_domain": False,
            "ticket_domain": False,
            "target_status": target_status,
            "resume": bool(resume),
            "fast_candidate": False,
            "fast_reasons": [],
            "qa_scopes": [],
        }

    old_plan = old_bundle.get("plan") or {}
    new_plan = new_bundle.get("plan") or {}
    old_brief = old_bundle.get("brief") or {}
    new_brief = new_bundle.get("brief") or {}
    fast = fast_report or classify_fast_edit(old_bundle, new_bundle)
    fast_reasons = list(fast.get("reasons", []))

    known_keys = {
        "brief", "sources", "plan", "temporal_source", "review",
        "fast_edit_review", "fast_edit_chain", "authoring", "used_model",
    }
    changed_unknown = sorted(
        key for key in (set(old_bundle) | set(new_bundle)) - known_keys
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
    actions_changed = _actions(old_bundle) != _actions(new_bundle)
    layout_changed = _layout_signature(old_bundle) != _layout_signature(new_bundle)
    content_changed = render(old_plan, old_bundle.get("sources", [])) != render(
        new_plan, new_bundle.get("sources", []))
    risky_fast_reasons = tuple(
        reason for reason in fast_reasons
        if reason.startswith("new_fact_tokens:")
        or reason in {"brief_changed", "new_high_risk_claim", "title_changed"}
    )
    factual_risk = bool(
        risky_fast_reasons or source_changed or temporal_changed or actions_changed
        or brief_changed or title_changed or category_changed or seo_changed
    )
    reasons = list(fast_reasons)
    if force_standard and "forced_standard" not in reasons:
        reasons.append("forced_standard")
    if changed_unknown:
        route = "standard"
        risk_level = "system"
        reasons.extend("unknown_bundle_key:" + key for key in changed_unknown)
    elif force_standard or fast.get("status") == FULL_REVIEW_REQUIRED:
        route = "standard"
        risk_level = "fact"
    else:
        route = "fast"
        risk_level = "simple"

    return {
        "route": route,
        "risk_level": risk_level,
        "reasons": reasons,
        "fast_report": fast,
        "content_changed": content_changed,
        "image_changed": bool(image_changed),
        "title_changed": title_changed,
        "brief_changed": brief_changed,
        "category_changed": category_changed,
        "seo_changed": seo_changed,
        "sources_changed": source_changed,
        "actions_changed": actions_changed,
        "temporal_changed": temporal_changed,
        "layout_changed": layout_changed,
        "related_changed": related_changed,
        "review_metadata_changed": review_metadata_changed,
        "unknown_bundle_change": bool(changed_unknown),
        "unknown_bundle_keys": changed_unknown,
        "factual_risk": factual_risk,
        "event_domain": _event_domain(new_bundle) or _event_domain(old_bundle),
        "ticket_domain": _ticket_domain(new_bundle) or _ticket_domain(old_bundle),
        "target_status": target_status,
        "resume": bool(resume),
        "fast_candidate": fast.get("status") != FULL_REVIEW_REQUIRED,
        "fast_reasons": fast_reasons,
        "qa_scopes": _qa_scopes(layout_changed=layout_changed, actions_changed=actions_changed),
    }
