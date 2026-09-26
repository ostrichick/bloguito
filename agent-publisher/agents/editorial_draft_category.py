"""Repair the WordPress category of one unchanged, fully reviewed draft."""

import hashlib
import json
import os
import re
import subprocess
from datetime import datetime

from agents.editorial import ROOT, save_report, validate_bundle
from agents.editorial_writer import fetch_sources, load_inventory
from agents.publisher import PublisherAgent
from config import DRAFTS_INDEX_FILE, resolve_category
from sync_wordpress_inventory import hydrate_duplicate_candidates, inventory_content_sha, sync_inventory


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def repair_reviewed_draft_category(post_id, expected_content_sha256, *, confirmed=False):
    if (not confirmed or not isinstance(post_id, int) or post_id <= 0
            or not re.fullmatch(r"[0-9a-f]{64}", expected_content_sha256 or "")):
        raise ValueError("specific_draft_category_repair_confirmation_required")

    lock = ROOT / "data" / ".editorial-publish.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        lock.mkdir()
    except FileExistsError:
        raise ValueError("editorial_publication_busy: inspect the existing job")

    try:
        sync_inventory()
        inventory = load_inventory()
        current = next((row for row in inventory["posts"] if int(row["ID"]) == post_id), None)
        if (not current or current["post_status"] != "draft"
                or inventory_content_sha(current) != expected_content_sha256):
            raise ValueError("draft_missing_or_modified")

        if not DRAFTS_INDEX_FILE.is_file():
            raise ValueError("reviewed_draft_index_missing")
        index_before = DRAFTS_INDEX_FILE.read_text(encoding="utf-8")
        records = json.loads(index_before)
        item = next((row for row in records if int(row.get("id", -1)) == post_id), None)
        bundle = (item or {}).get("fact_manifest", {}).get("editorial_bundle")
        if not bundle or bundle.get("plan", {}).get("title") != current["post_title"]:
            raise ValueError("reviewed_draft_manifest_required")

        remaining = dict(
            inventory,
            posts=[row for row in inventory["posts"] if int(row["ID"]) != post_id],
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
        expected_sources = {source["url"]: source["sha256"] for source in bundle["sources"]}
        observed_sources = {source["url"]: source["sha256"] for source in fresh_sources}
        if expected_sources != observed_sources:
            raise ValueError("official_sources_changed_since_review")

        category = resolve_category(bundle["brief"].get("category_key", ""))
        base = ["sudo", "docker", "exec", "wordpress_app", "wp"]
        live = json.loads(subprocess.run(
            base + ["post", "get", str(post_id), "--format=json", "--allow-root"],
            capture_output=True, text=True, check=True,
        ).stdout)
        terms = json.loads(subprocess.run(
            base + ["post", "term", "list", str(post_id), "category",
                    "--fields=term_id,name,slug", "--format=json", "--allow-root"],
            capture_output=True, text=True, check=True,
        ).stdout)
        if (live["post_status"] != "draft"
                or live["post_title"] != current["post_title"]
                or _sha(live["post_content"]) != expected_content_sha256
                or DRAFTS_INDEX_FILE.read_text(encoding="utf-8") != index_before):
            raise ValueError("draft_changed_during_category_repair")

        target_id = int(category["id"])
        if [int(term["term_id"]) for term in terms] == [target_id]:
            return post_id

        archive = ROOT / "data" / "editorial_runs"
        archive.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%dT%H%M%S%f")
        backup = archive / f"draft-category-{post_id}-{stamp}.json"
        with backup.open("x", encoding="utf-8") as handle:
            json.dump({"post": live, "categories": terms}, handle, ensure_ascii=False, indent=2)
        os.chmod(backup, 0o600)
        save_report(bundle, report)

        subprocess.run(
            base + ["post", "update", str(post_id), f"--post_category={target_id}", "--allow-root"],
            capture_output=True, text=True, check=True,
        )
        saved = json.loads(subprocess.run(
            base + ["post", "get", str(post_id), "--format=json", "--allow-root"],
            capture_output=True, text=True, check=True,
        ).stdout)
        saved_terms = json.loads(subprocess.run(
            base + ["post", "term", "list", str(post_id), "category",
                    "--fields=term_id,name,slug", "--format=json", "--allow-root"],
            capture_output=True, text=True, check=True,
        ).stdout)
        if (saved["post_status"] != "draft"
                or saved["post_title"] != live["post_title"]
                or saved["post_name"] != live["post_name"]
                or _sha(saved["post_content"]) != expected_content_sha256
                or [int(term["term_id"]) for term in saved_terms] != [target_id]):
            raise ValueError(f"draft_category_repair_verification_failed: recover from {backup}")

        PublisherAgent()._record_post(
            post_id,
            bundle["plan"]["title"],
            target_id,
            category["name"],
            status="draft",
            expires_at=bundle["brief"].get("useful_until"),
            fact_manifest={"editorial_bundle": bundle},
        )
        sync_inventory()
        print(f"Draft category backup: {backup}")
        return post_id
    finally:
        lock.rmdir()
