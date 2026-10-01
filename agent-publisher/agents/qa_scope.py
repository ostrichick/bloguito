"""Deterministic browser-QA requirements derived from the actual edit scope."""

from __future__ import annotations


QA_SCOPES = {
    "content-mobile-desktop",
    "cta-destination",
    "layout-accessibility",
    "featured-image",
    "public-page",
}


def qa_targets_for_events(bundle: dict | None, event_names) -> list[dict]:
    """Return stable browser-QA targets for localized event-section changes.

    Targets are intentionally keyed by ``event_name`` rather than section index so
    later orchestration can locate the rendered block without depending on nearby
    global sections. Unknown names are omitted; validation routing only emits an
    event-delta profile after proving the named event sections exist.
    """
    if not isinstance(bundle, dict):
        return []
    requested = {
        name for name in (event_names or [])
        if isinstance(name, str) and name.strip()
    }
    if not requested:
        return []
    present = {
        section.get("event_name")
        for section in bundle.get("plan", {}).get("sections", []) or []
        if isinstance(section, dict) and section.get("event_name") in requested
    }
    return [
        {"kind": "event-section", "event_name": name}
        for name in sorted(present)
    ]


def _actions(bundle: dict) -> list:
    rows = []
    for source in bundle.get("sources", []):
        if isinstance(source, dict):
            rows.extend(source.get("actions", []) or [])
    rows.extend(bundle.get("plan", {}).get("official_navigation", []) or [])
    return rows


def _layout_signature(bundle: dict) -> list:
    result = []
    for section in bundle.get("plan", {}).get("sections", []):
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


def qa_requirements_for_edit(
    old_bundle: dict | None,
    new_bundle: dict | None,
    *,
    image_changed: bool = False,
    target_status: str = "draft",
) -> list[str]:
    """Return the minimum named QA scopes required after a saved mutation."""
    required = set()
    if old_bundle is not None and new_bundle is not None:
        from agents.editorial import render
        if render(old_bundle.get("plan", {}), old_bundle.get("sources", [])) != render(
                new_bundle.get("plan", {}), new_bundle.get("sources", [])):
            required.add("content-mobile-desktop")
        if _actions(old_bundle) != _actions(new_bundle):
            required.add("cta-destination")
        if _layout_signature(old_bundle) != _layout_signature(new_bundle):
            required.add("layout-accessibility")
    if image_changed:
        required.add("featured-image")
    if target_status == "publish":
        required.add("public-page")
    return sorted(required)


def validate_qa_scopes(values) -> list[str]:
    scopes = sorted(set(values or []))
    unknown = set(scopes) - QA_SCOPES
    if unknown:
        raise ValueError("unknown_qa_scope:" + ",".join(sorted(unknown)))
    return scopes
