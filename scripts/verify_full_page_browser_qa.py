#!/usr/bin/env python3
"""Independently verify supplemental real-CDP full-page/2x/blank-CTA artifacts.

This does not sign a browser trace, re-read WordPress, or update task state.
In particular CDP page-scale 2x is pinch/visual zoom, NOT browser-native 200%.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

from PIL import Image

_SHA = re.compile(r"[0-9a-f]{64}\Z")
_SIZES = {390: 844, 1280: 900}


def _check_png(root: Path, name: str, claimed: str, width: int, height: int) -> None:
    if (not isinstance(name, str) or not name.startswith("segments/")
            or "/" in name[len("segments/"):] or "\\" in name or ".." in name):
        raise ValueError("full_qa_unsafe_screenshot_path")
    if not isinstance(claimed, str) or not _SHA.fullmatch(claimed):
        raise ValueError("full_qa_missing_png_sha")
    source = root / name
    if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != claimed:
        raise ValueError("full_qa_png_sha_mismatch")
    with Image.open(source) as captured:
        if captured.format != "PNG" or captured.size != (width, height):
            raise ValueError("full_qa_png_dimensions_invalid")
        captured.verify()


def verify_full_page(receipt: dict, root: Path, *, post_id: int, content_sha: str) -> dict:
    """Validate two observed scroll series and compositor visual zoom, not native zoom."""
    if (not isinstance(receipt, dict) or receipt.get("postId") != post_id
            or receipt.get("originalContentSha256") != content_sha
            or not isinstance(content_sha, str) or not _SHA.fullmatch(content_sha)
            or receipt.get("site") != "https://lifeinfo24.org/"):
        raise ValueError("full_qa_post_or_sha_mismatch")
    screens = receipt.get("screens")
    if not isinstance(screens, list) or len(screens) != 2:
        raise ValueError("full_qa_requires_both_viewports")
    accepted = {}
    for screen, (width, height) in zip(screens, _SIZES.items()):
        if not isinstance(screen, dict) or screen.get("viewport") != {"width": width, "height": height}:
            raise ValueError("full_qa_viewport_missing")
        start, finish = screen.get("initial"), screen.get("final")
        if not isinstance(start, dict) or not isinstance(finish, dict):
            raise ValueError("full_qa_identity_missing")
        for identity in (start, finish):
            parsed = urlsplit(identity.get("url", ""))
            if (parsed.scheme, parsed.hostname) != ("https", "lifeinfo24.org") or identity.get("postId") != post_id:
                raise ValueError("full_qa_live_url_or_post_id_invalid")
            if identity.get("scrollWidth", 10**12) > identity.get("clientWidth", 0) + 2:
                raise ValueError("full_qa_horizontal_overflow")
        if start["url"] != finish["url"]:
            raise ValueError("full_qa_url_changed")
        if start.get("innerWidth") != width or finish.get("innerWidth") != width:
            raise ValueError("full_qa_actual_viewport_not_applied")
        total = screen.get("total_height")
        segments = screen.get("segments")
        if (type(total) is not int or total <= height or total != finish.get("scrollHeight")
                or not isinstance(segments, list) or len(segments) < 2):
            raise ValueError("full_qa_scroll_extent_missing")
        next_min = 0
        prev = -1
        for i, part in enumerate(segments):
            if not isinstance(part, dict) or part.get("index") != i:
                raise ValueError("full_qa_segment_index_invalid")
            y, segment_height = part.get("scrollY"), part.get("viewportHeight")
            if (type(y) is not int or type(segment_height) is not int
                    or segment_height != height or y <= prev or y > next_min
                    or part.get("viewportWidth") != width
                    or part.get("observedPostId") != post_id):
                raise ValueError("full_qa_segment_gap_or_identity")
            _check_png(root, part.get("filename"), part.get("sha256"), width, height)
            prev = y
            next_min = y + height
        if segments[0]["scrollY"] != 0 or next_min < total - 2 or screen.get("full_page_covered") is not True:
            raise ValueError("full_qa_page_not_fully_covered")
        zoom = screen.get("zoom")
        if (not isinstance(zoom, dict) or zoom.get("method") != "Emulation.setPageScaleFactor"
                or zoom.get("requested") != 2
                or zoom.get("isNativeChromeMenuZoom") is not False
                or zoom.get("isCssHalfWidthTrick") is not False
                or not isinstance(zoom.get("observedVisualScale"), (int, float))
                or abs(zoom["observedVisualScale"] - 2) > .02
                or zoom.get("observedLayoutWidth") != width
                or not isinstance(zoom.get("observedVisualWidth"), (int, float))
                or zoom["observedVisualWidth"] >= width):
            raise ValueError("full_qa_zoom_2x_unverified")
        _check_png(root, zoom.get("screenshot"), zoom.get("sha256"), width, height)
        accepted[str(width)] = {"segments": len(segments), "page_height": total,
                                "coverage": "full_page", "cdp_page_scale_2x": "verified"}
    return {"status": "supplemental_full_page_verified",
            "screens": accepted, "native_browser_menu_zoom": "not_verified",
            "wordpress_sha_currentness": "external_live_readback_required",
            "task_state_updated": False}


def verify_blank_cta(receipt: dict, *, post_id: int) -> dict:
    """Check observed, not merely asserted, CDP new target and document response."""
    if (not isinstance(receipt, dict) or receipt.get("source_post_id") != post_id
            or receipt.get("main_page_preserved") is not True
            or receipt.get("new_tab_observed") is not True):
        raise ValueError("full_qa_cta_post_or_popup_missing")
    cta = receipt.get("cta")
    if (not isinstance(cta, dict) or cta.get("tag") != "A" or cta.get("target") != "_blank"
            or cta.get("method") is not None or cta.get("centerAnchorHref") != cta.get("href")
            or not isinstance(cta.get("href"), str) or urlsplit(cta["href"]).scheme != "https"
            or receipt.get("click") != "CDP Input.dispatchMouseEvent mousePressed+mouseReleased"):
        raise ValueError("full_qa_cta_safe_click_not_recorded")
    targets = receipt.get("targets")
    responses = receipt.get("document_responses")
    if not isinstance(targets, list) or not isinstance(responses, list):
        raise ValueError("full_qa_cta_browser_proof_missing")
    found = [row for row in targets if isinstance(row, dict)
             and row.get("type") == "page" and row.get("url") == cta["href"]
             and isinstance(row.get("id"), str)]
    if not found:
        raise ValueError("full_qa_cta_new_tab_destination_unverified")
    valid_target_ids = {row["id"] for row in found}
    passing = [row for row in responses if isinstance(row, dict)
               and row.get("targetId") in valid_target_ids and row.get("url") == cta["href"]
               and row.get("status") == 200 and row.get("mimeType") == "text/html"]
    if not passing:
        raise ValueError("full_qa_cta_document_http_200_unverified")
    return {"status": "observed_new_tab_document_200",
            "destination": cta["href"], "http_status": 200, "form_submitted": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("full_page_json", type=Path)
    parser.add_argument("--cta-json", type=Path, required=True)
    parser.add_argument("--post-id", type=int, required=True)
    parser.add_argument("--content-sha", required=True)
    args = parser.parse_args()
    full = json.loads(args.full_page_json.read_text(encoding="utf-8-sig"))
    cta = json.loads(args.cta_json.read_text(encoding="utf-8-sig"))
    result = {"full_page": verify_full_page(
        full, args.full_page_json.parent, post_id=args.post_id, content_sha=args.content_sha),
        "cta": verify_blank_cta(cta, post_id=args.post_id)}
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
