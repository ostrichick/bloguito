"""Compatibility wrapper for browser-QA scopes from the canonical classifier."""

from __future__ import annotations


QA_SCOPES = {
    "content-mobile-desktop",
    "cta-destination",
    "layout-accessibility",
    "featured-image",
    "public-page",
}


def qa_requirements_for_edit(
    old_bundle: dict | None,
    new_bundle: dict | None,
    *,
    image_changed: bool = False,
    target_status: str = "draft",
) -> list[str]:
    """Return the minimum QA scopes from the one canonical change classifier.

    Text-only, image-only and metadata-only edits are verified by deterministic
    readback. Browser QA is reserved for layout/accessibility or CTA behavior.
    """
    from agents.change_classifier import classify_change

    return classify_change(
        old_bundle,
        new_bundle,
        image_changed=image_changed,
        target_status=target_status,
    )["qa_scopes"]


def validate_qa_scopes(values) -> list[str]:
    scopes = sorted(set(values or []))
    unknown = set(scopes) - QA_SCOPES
    if unknown:
        raise ValueError("unknown_qa_scope:" + ",".join(sorted(unknown)))
    return scopes
