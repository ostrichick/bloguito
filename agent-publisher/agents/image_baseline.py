"""Immutable post-state fingerprints shared by image handoff and CAS.

This module intentionally has no WordPress/network/file side effects.
The fingerprint itself is a freshness fence, NOT approval evidence.
"""

from __future__ import annotations

import hashlib
import json
import re

from agents.wordpress_mutation import content_sha256


def image_baseline_sha256(*, content_sha256: str, thumbnail_id: int | None,
                          status: str, title: str, slug: str, excerpt: str) -> str:
    """Fingerprint all image-handoff CAS fields, including an explicit null cover."""
    if not re.fullmatch(r"[0-9a-f]{64}", content_sha256 or ""):
        raise ValueError("invalid_image_initial_baseline")
    if thumbnail_id is not None and (type(thumbnail_id) is not int or thumbnail_id <= 0):
        raise ValueError("invalid_image_initial_baseline")
    if any(not isinstance(value, str) for value in (status, title, slug, excerpt)):
        raise ValueError("invalid_image_initial_baseline")
    payload = {
        "content_sha256": content_sha256, "thumbnail_id": thumbnail_id,
        "status": status, "title": title, "slug": slug, "excerpt": excerpt,
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False,
                         separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def post_image_baseline_sha256(live: dict, thumbnail_id: int | None) -> str:
    return image_baseline_sha256(
        content_sha256=content_sha256(live.get("post_content", "")),
        thumbnail_id=thumbnail_id,
        status=live.get("post_status", ""), title=live.get("post_title", ""),
        slug=live.get("post_name", ""), excerpt=live.get("post_excerpt", ""),
    )
