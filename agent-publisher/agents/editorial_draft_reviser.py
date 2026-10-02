"""Replace a reviewed draft's prose after a fresh full review and CAS check."""

import hashlib
import json
import os
import re
import subprocess
from agents.wordpress_transport import run_wordpress
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from datetime import datetime
from pathlib import Path

from agents.editorial import ROOT, excerpt_from_lead, render, save_report, validate_bundle
from agents.editorial_writer import load_inventory
from agents.post_manifest_store import (
    acquire_editorial_lock,
    assert_unchanged,
    load_record,
    release_editorial_lock,
    replace_record,
    snapshot_backup_payload,
)
from agents.source_validation_cache import revision_source_recheck_plan, verify_revision_sources
from agents.temporal_validation import KST
from agents.editorial_updater import (
    _read_rank_math_meta,
    _set_rank_math_meta,
    rank_math_meta_from_brief,
)
from config import DRAFTS_INDEX_FILE
from sync_wordpress_inventory import hydrate_duplicate_candidates, inventory_content_sha, invalidate_inventory, sync_inventory
from agents.wordpress_mutation import (
    backup_json,
    get_post,
    guarded_update_post,
    verify_saved_fields,
)

try:
    from agents.related_links import missing_internal_post_ids
except ImportError:  # Compatibility with an older deployed worker during narrow rollout.
    from urllib.parse import parse_qs, urljoin, urlparse
    from bs4 import BeautifulSoup

    def _internal_post_ids(markup, site="https://lifeinfo24.org"):
        found = set()
        for anchor in BeautifulSoup(markup, "html.parser").select("a[href]"):
            parsed = urlparse(urljoin(site + "/", anchor["href"]))
            if parsed.scheme != "https" or parsed.hostname != urlparse(site).hostname:
                continue
            query = parse_qs(parsed.query, keep_blank_values=True)
            if set(query) != {"p"} or len(query["p"]) != 1:
                continue
            target = query["p"][0]
            if target.isascii() and target.isdecimal() and int(target) > 0:
                found.add(int(target))
        return found

    def missing_internal_post_ids(original, proposed):
        return sorted(_internal_post_ids(original) - _internal_post_ids(proposed))


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _revision_source_recheck_plan(old_bundle, new_bundle, now=None):
    """Compatibility wrapper for the shared draft/public Standard source planner."""
    return revision_source_recheck_plan(old_bundle, new_bundle, now=now)


def _verify_revision_sources(old_bundle, new_bundle, now=None):
    return verify_revision_sources(old_bundle, new_bundle, now=now)


def _before_generated_source_footer(content):
    """Return content with only the renderer-owned final source footer removed.

    This permits a renderer-only migration of the final source box while still
    rejecting any change to the reviewed article body.  Preserve the article's
    outer closing tag so a stored pre-footer draft compares equal to the current
    renderer with its generated source box removed.
    """
    marker = '<h2 id="sources"'
    if marker not in content:
        return content.replace("\r\n", "\n")
    heading = content.index(marker)
    container = content.rfind("<div", 0, heading)
    if container < 0:
        return content.replace("\r\n", "\n")
    footer_end = content.find("</div>", heading)
    if footer_end < 0:
        return content.replace("\r\n", "\n")
    footer_end += len("</div>")
    return (content[:container] + content[footer_end:]).replace("\r\n", "\n")


def _normalize_renderer_migrations(content):
    """Normalize only previously emitted renderer-owned markup migrations.

    Keep compatibility rules scoped to exact generated markup so authored prose
    remains part of the CAS comparison.
    """
    content = re.sub(
        r'<style id="bloguito-responsive-layout">.*?</style>',
        '',
        content,
        flags=re.DOTALL,
    )
    content = re.sub(
        r'<span class="bloguito-semantic-unit">([^<]*)</span>',
        r'\1',
        content,
    )
    # CTA responsiveness moved from an inline renderer-owned <style> + helper
    # class to the surrounding site stylesheet. Normalize only those exact
    # generated tokens so reviewed copy, hrefs and authored markup still take
    # part in the baseline comparison.
    content = content.replace(
        '<style>@media(max-width:640px){.bloguito-cta-grid{grid-template-columns:1fr!important}}</style>',
        '',
    )
    content = content.replace(
        '<div class="bloguito-cta-grid" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,210px),1fr));gap:10px">',
        '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,210px),1fr));gap:10px">',
    )
    # The event-post overview map is renderer-owned markup.  The initial
    # implementation embedded marker InfoWindow HTML directly in an inline JS
    # string; WordPress wpautop could parse those literal tags and corrupt the
    # script.  The current renderer Base64-encodes that payload.  Treat the
    # whole generated map block as one migration unit so an otherwise unchanged
    # reviewed draft can move between those renderer implementations without
    # weakening the authored-prose CAS comparison.
    content = re.sub(
        r'<section class="bloguito-kakao-map-container"[^>]*>.*?</section>',
        '<section data-bloguito-kakao-map="renderer-owned"></section>',
        content,
        flags=re.DOTALL,
    )
    content = re.sub(
        r'(<figcaption\b[^>]*>[^<]*) · '
        r'(<a href="[^"]+"[^>]*>공식 자료</a></figcaption>)',
        r'\1, \2',
        content,
    )
    content = re.sub(
        r'(<figcaption\b[^>]*>.*?<a href="[^"]+"[^>]*>)사진 출처(</a></figcaption>)',
        r'\1공식 자료\2',
        content,
        flags=re.DOTALL,
    )
    content = content.replace(
        '>📍 행사장 지도 및 길찾기</div>',
        '>📍 행사장 위치</div>',
    )
    content = re.sub(
        r'<a href="https://www\.google\.com/maps/dir/\?api=1&amp;destination=[^"]+" '
        r'target="_blank" rel="noopener noreferrer" '
        r'style="display:inline-flex;align-items:center;gap:4px;padding:7px 13px;'
        r'background:#ffffff;color:#0d7d59 !important;border:1px solid #0d7d59;'
        r'font-size:13px;font-weight:700;border-radius:6px;text-decoration:none !important">'
        r'길찾기 시작 <span aria-hidden="true">↗</span></a>',
        '',
        content,
    )

    old_location = re.compile(
        r'<div style="font-weight:700;color:#1e293b;font-size:15px;margin-bottom:8px">'
        r'📍 행사장 위치</div>'
        r'<div style="font-size:14px;color:#475569;margin-bottom:10px;line-height:1.6">'
        r'<strong>장소</strong>: (?P<venue>[^<]*)<br/>'
        r'<strong>위치</strong>: (?P<address>[^<]*)</div>'
    )
    new_location = re.compile(
        r'<div style="font-weight:700;color:#1e293b;font-size:15px;margin-bottom:(?:4px|10px)">'
        r'📍 행사장 위치: (?P<venue>[^<]*)</div>'
        r'(?:<div style="font-size:14px;color:#475569;margin-bottom:10px;line-height:1.6">'
        r'<strong>주소</strong>: (?P<address>[^<]*)</div>)?'
    )

    def canonical_location(match):
        venue = (match.group('venue') or '').strip()
        address = (match.groupdict().get('address') or '').strip()
        if address == venue:
            address = ''
        return f'<span data-bloguito-location="{venue}" data-address="{address}"></span>'

    content = old_location.sub(canonical_location, content)
    content = new_location.sub(canonical_location, content)
    return content


def revise_reviewed_draft(post_id, bundle, expected_content_sha256, *, confirmed=False,
                           confirm_title_change=False, image_path=None,
                           checkpoint_callback=None):
    """Replace one unchanged reviewed draft with another fully reviewed version.

    This is the Standard reviewed-draft mutation path. Fast wording-only edits
    use ``fast_revise_reviewed_draft`` through the canonical ``edit-post`` router.
    """
    if not confirmed or not isinstance(post_id, int) or post_id <= 0:
        raise ValueError("specific_draft_revision_confirmation_required")
    if not re.fullmatch(r"[0-9a-f]{64}", expected_content_sha256 or ""):
        raise ValueError("original_content_sha256_required")
    image_path = Path(image_path).resolve() if image_path else None
    if image_path is not None and (not image_path.is_file()
            or image_path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}):
        raise ValueError("reviewed_featured_image_required")

    lock = acquire_editorial_lock(ROOT)

    try:
        if not DRAFTS_INDEX_FILE.is_file():
            raise ValueError("reviewed_draft_index_missing")
        state_snapshot = load_record(DRAFTS_INDEX_FILE, post_id)
        item = state_snapshot.record if state_snapshot is not None else None
        if not item or "editorial_bundle" not in item.get("fact_manifest", {}):
            raise ValueError("reviewed_draft_manifest_required")
        old_bundle = item["fact_manifest"]["editorial_bundle"]

        old_brief = old_bundle.get("brief", {})
        new_brief = bundle.get("brief", {})
        reviewed_meta = rank_math_meta_from_brief(new_brief)
        new_title = bundle.get("plan", {}).get("title")
        if (old_brief.get("id") != new_brief.get("id")
                or old_brief.get("category_key") != new_brief.get("category_key")
                or old_brief.get("entity") != new_brief.get("entity")):
            raise ValueError("draft_revision_topic_or_title_mismatch")

        base = ["sudo", "docker", "exec", "wordpress_app", "wp"]
        post_fields = ["post_status", "post_title", "post_name", "post_content", "post_excerpt"]
        # Inventory, the target baseline and official-source recheck are independent
        # read-only prerequisites. Run them together, then reconcile their snapshots
        # before any validation can lead to a write.
        inventory_context = copy_context()
        target_context = copy_context()
        source_context = copy_context()
        with ThreadPoolExecutor(max_workers=3) as pool:
            inventory_future = pool.submit(inventory_context.run, sync_inventory)
            target_future = pool.submit(
                target_context.run, get_post, base, post_id, fields=post_fields)
            source_future = pool.submit(
                source_context.run,
                _verify_revision_sources,
                old_bundle,
                bundle,
            )
            inventory_future.result()
            initial_live = target_future.result()
            source_validation = source_future.result()

        inventory = load_inventory()
        current_row = next((p for p in inventory["posts"] if int(p["ID"]) == post_id), None)
        if (not current_row or current_row["post_status"] != "draft"
                or inventory_content_sha(current_row) != expected_content_sha256):
            raise ValueError("draft_missing_or_modified")
        if (initial_live.get("post_status") != current_row.get("post_status")
                or initial_live.get("post_title") != current_row.get("post_title")
                or hashlib.sha256(initial_live.get("post_content", "").encode("utf-8")).hexdigest()
                    != inventory_content_sha(current_row)):
            raise ValueError("inventory_post_detail_changed")
        current = initial_live
        title_changed = new_title != current["post_title"]
        if (current["post_title"] != old_bundle.get("plan", {}).get("title")
                or (title_changed and not confirm_title_change)):
            raise ValueError("draft_revision_topic_or_title_mismatch")

        old_rendered = render(old_bundle["plan"], old_bundle["sources"])
        current_comparable = _normalize_renderer_migrations(current["post_content"])
        old_comparable = _normalize_renderer_migrations(old_rendered)
        same_exact = (
            current_comparable.replace("\r\n", "\n")
            == old_comparable.replace("\r\n", "\n")
        )
        same_before_source_footer = (
            _before_generated_source_footer(current_comparable)
            == _before_generated_source_footer(old_comparable)
        )
        if not (same_exact or same_before_source_footer):
            raise ValueError("draft_contains_unreviewed_edits")
        if missing_internal_post_ids(old_rendered, render(bundle["plan"], bundle["sources"])):
            raise ValueError("original_internal_post_navigation_missing")

        remaining = dict(
            inventory,
            posts=[p for p in inventory["posts"] if int(p["ID"]) != post_id],
        )
        remaining = hydrate_duplicate_candidates(
            bundle['brief'], remaining,
            related_post_ids={item.get('post_id') for item in bundle.get('plan', {}).get('related_posts', [])
                              if isinstance(item, dict) and type(item.get('post_id')) is int},
        )
        report = validate_bundle(bundle, remaining)
        if report["status"] != "ready":
            raise ValueError(f'draft_editorial_review_failed: {report["reasons"]}')
        if checkpoint_callback is not None:
            checkpoint_callback({
                "inventory_checked_on": inventory.get("checked_on"),
                "source_validation": source_validation,
                "review_digest": bundle.get("review", {}).get("digest"),
                "candidate_content_sha256": hashlib.sha256(
                    render(bundle["plan"], bundle["sources"]).encode("utf-8")
                ).hexdigest(),
            })

        # The guarded mutation below performs the final target CAS and readback
        # in the same remote WP process. Keep the local manifest CAS immediately
        # before that operation so neither side can silently drift.
        live = current
        try:
            assert_unchanged(state_snapshot)
        except ValueError as exc:
            raise ValueError("draft_changed_during_revision") from exc

        old_excerpt = excerpt_from_lead(old_bundle["plan"]["lead"])
        if live.get("post_excerpt", "") != old_excerpt:
            raise ValueError("draft_excerpt_changed_since_review")

        desired = render(bundle["plan"], bundle["sources"])
        new_excerpt = excerpt_from_lead(bundle["plan"]["lead"])
        stamp = datetime.now().strftime("%Y%m%dT%H%M%S%f")
        current_meta = _read_rank_math_meta(base, post_id) if reviewed_meta else None
        update_meta = reviewed_meta is not None and current_meta != reviewed_meta
        backup_payload = dict(live)
        if current_meta is not None:
            backup_payload["rank_math_meta"] = current_meta
        post_backup = backup_json(ROOT, "draft-revision", post_id, backup_payload)
        archive = ROOT / "data" / "editorial_runs"
        index_backup = archive / f"draft-revision-index-{post_id}-{stamp}.json"
        index_backup.write_text(
            json.dumps(snapshot_backup_payload(state_snapshot), ensure_ascii=False, indent=2),
            encoding="utf-8")
        os.chmod(index_backup, 0o600)
        save_report(bundle, report)

        update_fields = {
            "post_content": desired,
            "post_excerpt": new_excerpt,
        }
        if title_changed:
            update_fields["post_title"] = new_title
        saved = guarded_update_post(
            base,
            post_id,
            expected={
                "post_status": "draft",
                "post_title": current["post_title"],
                "post_name": live.get("post_name", ""),
                "post_excerpt": live.get("post_excerpt", ""),
                "content_sha256": expected_content_sha256,
            },
            updates=update_fields,
        )
        if update_meta:
            _set_rank_math_meta(base, post_id, reviewed_meta)
        if not verify_saved_fields(
                saved,
                expected={
                    "post_status": "draft",
                    "post_title": new_title,
                    "post_content": desired,
                    "post_excerpt": new_excerpt,
                },
                preserved={"post_name": live["post_name"]}):
            raise ValueError(f"draft_revision_save_verification_failed: recover from {post_backup}")
        if reviewed_meta is not None and _read_rank_math_meta(base, post_id) != reviewed_meta:
            raise ValueError(f"draft_revision_save_verification_failed: recover from {post_backup}")

        featured_attachment_id = None
        if image_path is not None:
            remote_image = f"/tmp/editorial_cover_{post_id}{image_path.suffix.lower()}"
            run_wordpress(["sudo", "docker", "cp", str(image_path),
                            f"wordpress_app:{remote_image}"], capture_output=True, check=True)
            try:
                imported = run_wordpress(
                    base + ["media", "import", remote_image, f"--post_id={post_id}",
                            "--featured_image", "--porcelain", "--allow-root"],
                    capture_output=True, text=True, encoding="utf-8", errors="strict", check=True)
                featured_attachment_id = imported.stdout.strip()
            finally:
                run_wordpress(["sudo", "docker", "exec", "wordpress_app", "rm", "-f", remote_image],
                               capture_output=True, check=False)
            if not featured_attachment_id.isdigit():
                raise ValueError("featured_image_attachment_id_missing")
            observed_thumb = run_wordpress(
                base + ["post", "meta", "get", str(post_id), "_thumbnail_id", "--allow-root"],
                capture_output=True, text=True, encoding="utf-8", errors="strict", check=True).stdout.strip()
            if observed_thumb != featured_attachment_id:
                raise ValueError("featured_image_save_verification_failed")

        try:
            assert_unchanged(state_snapshot)
        except ValueError as exc:
            raise ValueError(f"draft_index_changed: recover from {index_backup}") from exc
        updated = dict(item)
        updated.setdefault("fact_manifest", dict(item.get("fact_manifest", {})))["editorial_bundle"] = bundle
        replace_record(state_snapshot, updated)
        invalidate_inventory()
        print(f"Draft revision backup: {post_backup}")
        print(f"Draft index backup: {index_backup}")
        if featured_attachment_id is not None:
            print(f"Featured image attachment: {featured_attachment_id}")
        return post_id
    finally:
        release_editorial_lock(lock)
