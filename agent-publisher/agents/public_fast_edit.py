"""Fast, evidence-preserving edits to tracked reviewed public posts."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re

from agents.editorial import ROOT, excerpt_from_lead, render
from agents.editorial_updater import _existing_lead_excerpt
from agents.fast_edit import (
    FULL_REVIEW_REQUIRED,
    build_fast_stored_bundle,
    prepare_fast_delta_review,
    validate_fast_edit,
    validate_prepared_delta_review,
)
from agents.post_manifest_store import (
    acquire_editorial_lock,
    assert_unchanged,
    load_record,
    release_editorial_lock,
    replace_record,
    snapshot_backup_payload,
)
from agents.wordpress_mutation import (
    backup_json,
    content_sha256,
    get_post,
    guarded_update_post,
    verify_cas,
    verify_saved_fields,
)
from config import POSTS_INDEX_FILE
from sync_wordpress_inventory import invalidate_inventory


def load_tracked_public_bundle(post_id: int) -> dict:
    if not POSTS_INDEX_FILE.is_file():
        raise ValueError("reviewed_public_index_missing")
    snapshot = load_record(POSTS_INDEX_FILE, post_id)
    if snapshot is None:
        raise ValueError("reviewed_public_manifest_required")
    bundle = snapshot.record.get("fact_manifest", {}).get("editorial_bundle")
    if not isinstance(bundle, dict):
        raise ValueError("reviewed_public_manifest_required")
    return bundle


def normalize_public_fast_candidate(old_bundle: dict, new_bundle: dict, post_id: int) -> dict:
    """Ignore only a newly-added technical target ID on legacy promoted bundles."""
    candidate = copy.deepcopy(new_bundle)
    old_id = old_bundle.get("brief", {}).get("existing_post_id")
    new_id = candidate.get("brief", {}).get("existing_post_id")
    if old_id is None and new_id == post_id:
        candidate["brief"].pop("existing_post_id", None)
    return candidate


def classify_public_fast_edit(post_id: int, bundle: dict) -> dict:
    old_bundle = load_tracked_public_bundle(post_id)
    candidate = normalize_public_fast_candidate(old_bundle, bundle, post_id)
    expected_old = render(old_bundle["plan"], old_bundle["sources"])
    report = validate_fast_edit(old_bundle, candidate)
    reasons = list(report.get("reasons", []))
    return {
        "route": "fast" if report.get("status") == "candidate" and not reasons else "standard",
        "reasons": reasons,
        "fast_report": report,
        "candidate": candidate,
        "tracked_bundle": old_bundle,
        "tracked_content_sha256": content_sha256(expected_old),
    }


def fast_update_public_post(
    post_id: int,
    bundle: dict,
    expected_content_sha256: str,
    *,
    confirmed: bool = False,
    edit_intent: str,
    prepared_delta_review: dict | None = None,
) -> int:
    """Apply a wording/organization-only edit to one reviewed public post."""
    if not confirmed or not isinstance(post_id, int) or post_id <= 0:
        raise ValueError("specific_public_post_update_confirmation_required")
    if not re.fullmatch(r"[0-9a-f]{64}", expected_content_sha256 or ""):
        raise ValueError("original_content_sha256_required")
    if (not isinstance(edit_intent, str) or not 4 <= len(edit_intent.strip()) <= 1000
            or re.search(r"[<>\x00]", edit_intent)):
        raise ValueError("fast_edit_intent_required")
    edit_intent = edit_intent.strip()

    lock = acquire_editorial_lock(ROOT)

    try:
        if not POSTS_INDEX_FILE.is_file():
            raise ValueError("reviewed_public_index_missing")
        state_snapshot = load_record(POSTS_INDEX_FILE, post_id)
        if state_snapshot is None:
            raise ValueError("reviewed_public_manifest_required")
        item = state_snapshot.record
        old_bundle = item.get("fact_manifest", {}).get("editorial_bundle")
        if not isinstance(old_bundle, dict):
            raise ValueError("reviewed_public_manifest_required")
        candidate = normalize_public_fast_candidate(old_bundle, bundle, post_id)
        old_rendered = render(old_bundle["plan"], old_bundle["sources"])
        if content_sha256(old_rendered) != expected_content_sha256:
            raise ValueError(FULL_REVIEW_REQUIRED + ":public_manifest_not_bound_to_expected_content")

        report = validate_fast_edit(old_bundle, candidate)
        if report["status"] != "candidate":
            raise ValueError(FULL_REVIEW_REQUIRED + ":" + json.dumps(report["reasons"], ensure_ascii=False))
        if prepared_delta_review is not None:
            if not validate_prepared_delta_review(
                    old_bundle, report, prepared_delta_review, edit_intent):
                raise ValueError(FULL_REVIEW_REQUIRED + ":prepared_delta_review_mismatch")
            delta_review = prepared_delta_review
        else:
            delta_review = prepare_fast_delta_review(old_bundle, candidate, report, edit_intent)

        base = ["sudo", "docker", "exec", "wordpress_app", "wp"]
        fields = ["post_status", "post_title", "post_name", "post_content", "post_excerpt"]
        live = get_post(base, post_id, fields=fields)
        if (not verify_cas(
                live,
                status="publish",
                title=old_bundle["plan"]["title"],
                content_sha=expected_content_sha256)
                or live.get("post_content", "") != old_rendered):
            raise ValueError("public_post_changed_before_fast_revision")
        assert_unchanged(state_snapshot)

        desired = render(candidate["plan"], candidate["sources"])
        old_excerpt = live.get("post_excerpt", "")
        generated_old = _existing_lead_excerpt(live.get("post_content", ""))
        new_excerpt = excerpt_from_lead(candidate["plan"]["lead"])
        update_excerpt = bool(new_excerpt and (not old_excerpt.strip() or old_excerpt == generated_old))
        updates = {"post_content": desired}
        if update_excerpt:
            updates["post_excerpt"] = new_excerpt

        post_backup = backup_json(ROOT, "fast-public-edit", post_id, live)
        archive = ROOT / "data" / "editorial_runs"
        stamp = post_backup.stem.rsplit("-", 1)[-1]
        index_backup = archive / f"fast-public-edit-index-{post_id}-{stamp}.json"
        index_backup.write_text(
            json.dumps(snapshot_backup_payload(state_snapshot), ensure_ascii=False, indent=2),
            encoding="utf-8")
        os.chmod(index_backup, 0o600)

        saved = guarded_update_post(
            base,
            post_id,
            expected={
                "post_status": "publish",
                "post_title": live.get("post_title", ""),
                "post_name": live.get("post_name", ""),
                "post_excerpt": old_excerpt,
                "content_sha256": expected_content_sha256,
            },
            updates=updates,
        )
        expected_saved = {
            "post_status": "publish",
            "post_title": live.get("post_title", ""),
            "post_content": desired,
        }
        if update_excerpt:
            expected_saved["post_excerpt"] = new_excerpt
        if not verify_saved_fields(
                saved, expected=expected_saved, preserved={"post_name": live.get("post_name", "")}):
            raise ValueError(f"fast_public_save_verification_failed: recover from {post_backup}")
        try:
            assert_unchanged(state_snapshot)
        except ValueError as exc:
            raise ValueError(f"public_index_changed: recover from {index_backup}") from exc

        stored = build_fast_stored_bundle(old_bundle, candidate, delta_review)
        updated = dict(item)
        updated.setdefault("fact_manifest", dict(item.get("fact_manifest", {})))["editorial_bundle"] = stored
        replace_record(state_snapshot, updated)
        invalidate_inventory()
        return post_id
    finally:
        release_editorial_lock(lock)
