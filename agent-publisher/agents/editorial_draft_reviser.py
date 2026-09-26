"""Replace a reviewed draft's prose after a fresh full review and CAS check."""

import hashlib
import json
import os
import re
import subprocess
from datetime import datetime

from agents.editorial import ROOT, excerpt_from_lead, render, save_report, validate_bundle
from agents.editorial_writer import fetch_sources, load_inventory
from config import DRAFTS_INDEX_FILE
from sync_wordpress_inventory import hydrate_duplicate_candidates, hydrate_post, inventory_content_sha, invalidate_inventory, sync_inventory
from agents.wordpress_mutation import backup_json, get_post, update_post, verify_cas, verify_saved_fields

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


def _before_generated_source_footer(content):
    """Return authored/rendered content before the renderer-owned source footer.

    This permits a renderer-only migration of the final source box while still
    rejecting any change to the reviewed article body before that box.
    """
    marker = '<h2 id="sources"'
    if marker not in content:
        return content.replace("\r\n", "\n")
    heading = content.index(marker)
    container = content.rfind("<div", 0, heading)
    if container < 0:
        return content.replace("\r\n", "\n")
    return content[:container].replace("\r\n", "\n")


def revise_reviewed_draft(post_id, bundle, expected_content_sha256, *, confirmed=False,
                           confirm_title_change=False):
    """Replace one unchanged reviewed draft with another fully reviewed version.

    This is intentionally separate from update_draft(), which only permits
    renderer/action-link changes while preserving authored prose.
    """
    if not confirmed or not isinstance(post_id, int) or post_id <= 0:
        raise ValueError("specific_draft_revision_confirmation_required")
    if not re.fullmatch(r"[0-9a-f]{64}", expected_content_sha256 or ""):
        raise ValueError("original_content_sha256_required")

    lock = ROOT / "data" / ".editorial-publish.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        lock.mkdir()
    except FileExistsError:
        raise ValueError("editorial_publication_busy: inspect the existing job")

    try:
        sync_inventory()
        inventory = load_inventory()
        current = next((p for p in inventory["posts"] if int(p["ID"]) == post_id), None)
        if (not current or current["post_status"] != "draft"
                or inventory_content_sha(current) != expected_content_sha256):
            raise ValueError("draft_missing_or_modified")
        inventory = hydrate_post(inventory, post_id)
        current = next((p for p in inventory["posts"] if int(p["ID"]) == post_id), None)

        if not DRAFTS_INDEX_FILE.is_file():
            raise ValueError("reviewed_draft_index_missing")
        index_before = DRAFTS_INDEX_FILE.read_text(encoding="utf-8")
        records = json.loads(index_before)
        item = next((p for p in records if int(p.get("id", -1)) == post_id), None)
        if not item or "editorial_bundle" not in item.get("fact_manifest", {}):
            raise ValueError("reviewed_draft_manifest_required")
        old_bundle = item["fact_manifest"]["editorial_bundle"]

        old_brief = old_bundle.get("brief", {})
        new_brief = bundle.get("brief", {})
        new_title = bundle.get("plan", {}).get("title")
        title_changed = new_title != current["post_title"]
        if (old_brief.get("id") != new_brief.get("id")
                or old_brief.get("category_key") != new_brief.get("category_key")
                or old_brief.get("entity") != new_brief.get("entity")
                or current["post_title"] != old_bundle.get("plan", {}).get("title")
                or (title_changed and not confirm_title_change)):
            raise ValueError("draft_revision_topic_or_title_mismatch")

        old_rendered = render(old_bundle["plan"], old_bundle["sources"])
        same_exact = (
            current["post_content"].replace("\r\n", "\n")
            == old_rendered.replace("\r\n", "\n")
        )
        same_before_source_footer = (
            _before_generated_source_footer(current["post_content"])
            == _before_generated_source_footer(old_rendered)
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

        fresh_sources = fetch_sources(bundle["brief"])
        expected_sources = {s["url"]: s["sha256"] for s in bundle["sources"]}
        observed_sources = {s["url"]: s["sha256"] for s in fresh_sources}
        if expected_sources != observed_sources:
            raise ValueError("official_sources_changed_since_review")

        base = ["sudo", "docker", "exec", "wordpress_app", "wp"]
        live = get_post(base, post_id)
        if (not verify_cas(live, status="draft", title=current["post_title"],
                           content_sha=expected_content_sha256)
                or DRAFTS_INDEX_FILE.read_text(encoding="utf-8") != index_before):
            raise ValueError("draft_changed_during_revision")

        old_excerpt = excerpt_from_lead(old_bundle["plan"]["lead"])
        if live.get("post_excerpt", "") != old_excerpt:
            raise ValueError("draft_excerpt_changed_since_review")

        desired = render(bundle["plan"], bundle["sources"])
        new_excerpt = excerpt_from_lead(bundle["plan"]["lead"])
        stamp = datetime.now().strftime("%Y%m%dT%H%M%S%f")
        post_backup = backup_json(ROOT, "draft-revision", post_id, live)
        archive = ROOT / "data" / "editorial_runs"
        index_backup = archive / f"draft-revision-index-{post_id}-{stamp}.json"
        index_backup.write_text(index_before, encoding="utf-8")
        os.chmod(index_backup, 0o600)
        save_report(bundle, report)

        update_fields = {
            "post_content": desired,
            "post_excerpt": new_excerpt,
        }
        if title_changed:
            update_fields["post_title"] = new_title
        update_post(base, post_id, update_fields)
        saved = get_post(base, post_id)
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

        if DRAFTS_INDEX_FILE.read_text(encoding="utf-8") != index_before:
            raise ValueError(f"draft_index_changed: recover from {index_backup}")
        item["fact_manifest"]["editorial_bundle"] = bundle
        temporary = DRAFTS_INDEX_FILE.with_suffix(".revision-tmp")
        temporary.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(DRAFTS_INDEX_FILE)
        invalidate_inventory()
        print(f"Draft revision backup: {post_backup}")
        print(f"Draft index backup: {index_backup}")
        return post_id
    finally:
        lock.rmdir()
