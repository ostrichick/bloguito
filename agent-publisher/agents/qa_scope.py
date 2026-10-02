"""Validation helpers for browser-QA completion scopes."""

from __future__ import annotations


QA_SCOPES = {
    "content-mobile-desktop",
    "cta-destination",
    "layout-accessibility",
    "featured-image",
    "public-page",
}

def validate_qa_scopes(values) -> list[str]:
    scopes = sorted(set(values or []))
    unknown = set(scopes) - QA_SCOPES
    if unknown:
        raise ValueError("unknown_qa_scope:" + ",".join(sorted(unknown)))
    return scopes
