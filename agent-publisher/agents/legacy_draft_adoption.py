"""One-time full-reviewed onboarding of an existing, untracked WordPress draft.

This is reachable only through the canonical edit-post action.  Historical
reviewed provenance is never inferred from WordPress HTML: the replacement
bundle must pass the complete current source and semantic review.
"""

from __future__ import annotations

import re

from agents.editorial import ROOT, excerpt_from_lead, render, save_report, validate_bundle
from agents.editorial_updater import (
    _adoption_category_ids, _read_permalink, _read_rank_math_meta,
    rank_math_meta_from_brief,
)
from agents.editorial_writer import load_inventory
from agents.post_manifest_store import (
    acquire_editorial_lock, load_record, release_editorial_lock, upsert_record,
)
from agents.related_links import missing_internal_post_ids
from agents.source_validation_cache import verify_sources_unchanged
from agents.wordpress_mutation import (
    backup_json, content_sha256, get_post, guarded_update_post, verify_saved_fields,
)
from config import DRAFTS_INDEX_FILE, POSTS_INDEX_FILE, resolve_category
from sync_wordpress_inventory import (
    hydrate_duplicate_candidates, inventory_content_sha, invalidate_inventory, sync_inventory,
)


def adopt_reviewed_legacy_draft(
    post_id: int,
    bundle: dict,
    expected_content_sha256: str,
    *,
    confirmed: bool,
    confirm_title_change: bool,
) -> dict:
    """Replace a draft only after full fresh review and a guarded live CAS/readback."""
    if not confirmed or not isinstance(post_id, int) or post_id <= 0:
        raise ValueError("specific_draft_revision_confirmation_required")
    if not re.fullmatch(r"[a-f0-9]{64}", expected_content_sha256 or ""):
        raise ValueError("original_content_sha256_required")
    if (not isinstance(bundle, dict) or not isinstance(bundle.get("brief"), dict)
            or bundle["brief"].get("existing_post_id") != post_id):
        raise ValueError("legacy_draft_explicit_post_id_binding_required")
    if not isinstance(bundle.get("plan"), dict) or not isinstance(bundle.get("sources"), list):
        raise ValueError("full_reviewed_editorial_bundle_required")
    lock = acquire_editorial_lock(ROOT)
    try:
        if ((DRAFTS_INDEX_FILE.is_file() and load_record(DRAFTS_INDEX_FILE, post_id) is not None)
                or (POSTS_INDEX_FILE.is_file() and load_record(POSTS_INDEX_FILE, post_id) is not None)):
            raise ValueError("legacy_draft_already_has_reviewed_state")

        base = ["sudo", "docker", "exec", "wordpress_app", "wp"]
        sync_inventory()
        inventory = load_inventory()
        original = next((row for row in inventory["posts"] if int(row["ID"]) == post_id), None)
        live = get_post(base, post_id, fields=[
            "post_status", "post_title", "post_name", "post_excerpt", "post_content"])
        if (original is None or original.get("post_status") != "draft"
                or inventory_content_sha(original) != expected_content_sha256
                or live.get("post_status") != "draft"
                or live.get("post_title") != original.get("post_title")
                or content_sha256(live.get("post_content", "")) != expected_content_sha256):
            raise ValueError("legacy_draft_live_baseline_mismatch")

        desired_title = bundle["plan"].get("title")
        if not isinstance(desired_title, str) or not desired_title.strip():
            raise ValueError("legacy_draft_reviewed_title_required")
        title_changed = desired_title != live["post_title"]
        if title_changed and not confirm_title_change:
            raise ValueError("draft_title_change_confirmation_required")
        # Category and topic bindings are checked against the current, real
        # WordPress target.  An unrelated reviewed bundle cannot adopt this ID.
        category_ids = _adoption_category_ids(base, post_id, bundle)
        reviewed_content = render(bundle["plan"], bundle["sources"])
        if missing_internal_post_ids(live["post_content"], reviewed_content):
            raise ValueError("original_internal_post_navigation_missing")

        sources = bundle["sources"]
        source_ids = {source.get("id") for source in sources if isinstance(source, dict)}
        if len(source_ids) != len(sources) or None in source_ids:
            raise ValueError("legacy_draft_reviewed_sources_required")
        source_receipt = verify_sources_unchanged(
            bundle["brief"], sources, force_refresh_ids=source_ids)
        if not source_receipt.get("all_unchanged"):
            raise ValueError("legacy_draft_source_recheck_failed")
        remaining = dict(inventory, posts=[
            row for row in inventory["posts"] if int(row["ID"]) != post_id])
        remaining = hydrate_duplicate_candidates(bundle["brief"], remaining,
            related_post_ids={row["post_id"] for row in bundle["plan"].get("related_posts", [])
                              if isinstance(row, dict) and isinstance(row.get("post_id"), int)})
        report = validate_bundle(bundle, remaining)
        if report["status"] != "ready":
            raise ValueError(f"legacy_draft_full_review_required:{report['reasons']}")

        reviewed_meta = rank_math_meta_from_brief(bundle["brief"])
        permalink = _read_permalink(base, post_id)
        before_meta = _read_rank_math_meta(base, post_id) if reviewed_meta else None
        new_excerpt = excerpt_from_lead(bundle["plan"]["lead"])
        # Preserve manually authored excerpts.  The existing lead excerpt may
        # be replaced since it was generated with the old article body.
        from agents.editorial_updater import _existing_lead_excerpt
        old_excerpt = live.get("post_excerpt", "")
        update_excerpt = not old_excerpt.strip() or old_excerpt == _existing_lead_excerpt(live["post_content"])
        updates = {"post_content": reviewed_content}
        if title_changed:
            updates["post_title"] = desired_title
        if update_excerpt:
            updates["post_excerpt"] = new_excerpt
        backup_payload = dict(live)
        if before_meta is not None:
            backup_payload["rank_math_meta"] = before_meta
        post_backup = backup_json(ROOT, "draft-onboarding", post_id, backup_payload)
        save_report(bundle, report)
        saved = guarded_update_post(
            base, post_id,
            expected={
                "post_status": "draft",
                "post_title": live["post_title"],
                "post_name": live.get("post_name", ""),
                "post_excerpt": old_excerpt,
                "content_sha256": expected_content_sha256,
                "category_ids": category_ids,
            },
            updates=updates,
            expected_meta=before_meta if reviewed_meta != before_meta else None,
            updates_meta=reviewed_meta if reviewed_meta != before_meta else None,
        )
        expected = {"post_status": "draft", "post_title": desired_title,
                    "post_content": reviewed_content}
        if update_excerpt:
            expected["post_excerpt"] = new_excerpt
        if not verify_saved_fields(saved, expected=expected,
                                   preserved={"post_name": live.get("post_name", "")}):
            raise ValueError("legacy_draft_readback_mismatch:" + str(post_backup))
        if reviewed_meta is not None and _read_rank_math_meta(base, post_id) != reviewed_meta:
            raise ValueError("legacy_draft_seo_readback_mismatch:" + str(post_backup))
        if ((DRAFTS_INDEX_FILE.is_file() and load_record(DRAFTS_INDEX_FILE, post_id) is not None)
                or (POSTS_INDEX_FILE.is_file() and load_record(POSTS_INDEX_FILE, post_id) is not None)):
            raise ValueError("legacy_draft_index_changed_after_save:" + str(post_backup))
        category = resolve_category(bundle["brief"]["category_key"], allow_legacy=False)
        upsert_record(DRAFTS_INDEX_FILE, {
            "id": post_id,
            "title": desired_title,
            "url": permalink,
            "category_id": category["id"],
            "category_name": category["name"],
            "status": "draft",
            "expires_at": bundle["brief"].get("useful_until"),
            "fact_manifest": {"editorial_bundle": bundle},
            "published_at": None,
        })
        invalidate_inventory()
        return {
            "post_id": post_id,
            "route": "standard-legacy-draft",
            "target_status": "draft",
            "source_validation": source_receipt,
            "review_digest": bundle["review"]["digest"],
            "before_content_sha256": expected_content_sha256,
            "after_content_sha256": content_sha256(reviewed_content),
            "readback_verified": True,
            "backup": str(post_backup),
            "qa_requirements": ["content-mobile-desktop", "layout-accessibility"],
        }
    finally:
        release_editorial_lock(lock)
