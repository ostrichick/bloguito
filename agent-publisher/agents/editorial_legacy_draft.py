"""One-time, source-reviewed upgrade for an explicitly authorized legacy draft.

This uses the same editorial review, current-source and compare-and-swap guards
as existing-post edits, then registers the reviewed bundle for normal promotion.
"""

import json
import os
import re
from datetime import datetime

from agents.editorial import (ROOT, excerpt_from_lead, render, save_report,
                              validate_bundle)
from agents.editorial_updater import (
    _read_rank_math_meta,
    _set_rank_math_meta,
    rank_math_meta_from_brief,
)
from agents.editorial_writer import fetch_sources, load_inventory
from agents.publisher import PublisherAgent
from agents.temporal_validation import KST
from agents.wordpress_mutation import content_sha256, get_post, guarded_update_post, verify_saved_fields
from config import DRAFTS_INDEX_FILE, resolve_category
from sync_wordpress_inventory import hydrate_duplicate_candidates, inventory_content_sha, invalidate_inventory, sync_inventory


def upgrade_legacy_draft(post_id, bundle, expected_content_sha256, *, confirmed=False):
    brief = bundle.get('brief', {})
    evergreen_existing = (
        brief.get('content_type') == 'evergreen'
        and brief.get('useful_until') is None
        and brief.get('existing_post_id') == post_id
    )
    dated_existing = (
        brief.get('content_type') == 'dated'
        and isinstance(brief.get('useful_until'), str)
        and brief.get('existing_post_id') == post_id
    )
    if (not confirmed or not isinstance(post_id, int) or post_id <= 0
            or not re.fullmatch(r'[0-9a-f]{64}', expected_content_sha256 or '')
            or not (evergreen_existing or dated_existing)
            or brief.get('existing_post_id') != post_id):
        raise ValueError('specific_legacy_draft_upgrade_confirmation_required')

    lock = ROOT / 'data' / '.editorial-publish.lock'
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        lock.mkdir()
    except FileExistsError:
        raise ValueError('editorial_publication_busy: inspect the running process')

    try:
        sync_inventory()
        inventory = load_inventory()
        matching = [row for row in inventory['posts'] if int(row['ID']) == post_id]
        if (len(matching) != 1 or matching[0]['post_status'] != 'draft'
                or matching[0]['post_title'] != bundle['plan']['title']
                or inventory_content_sha(matching[0]) != expected_content_sha256):
            raise ValueError('legacy_draft_missing_modified_or_title_mismatch')

        if not DRAFTS_INDEX_FILE.is_file():
            raise ValueError('legacy_draft_index_missing')
        index_before = DRAFTS_INDEX_FILE.read_text(encoding='utf-8')
        index_rows = json.loads(index_before)
        old_record = next((row for row in index_rows if int(row.get('id', -1)) == post_id), None)
        if old_record and old_record.get('fact_manifest', {}).get('editorial_bundle'):
            raise ValueError('draft_already_has_reviewed_manifest')

        remainder = dict(inventory, posts=[row for row in inventory['posts'] if int(row['ID']) != post_id])
        remainder = hydrate_duplicate_candidates(
            bundle['brief'], remainder,
            related_post_ids={item.get('post_id') for item in bundle.get('plan', {}).get('related_posts', [])
                              if isinstance(item, dict) and type(item.get('post_id')) is int},
        )
        report = validate_bundle(bundle, remainder)
        if report['status'] != 'ready':
            raise ValueError(f'editorial_review_not_current: {report["reasons"]}')

        fresh_sources = fetch_sources(bundle['brief'])
        expected_sources = {s['url']: s['sha256'] for s in bundle['sources']}
        if {s['url']: s['sha256'] for s in fresh_sources} != expected_sources:
            raise ValueError('official_source_changed_since_review')

        target_html = render(bundle['plan'], bundle['sources'])
        excerpt = excerpt_from_lead(bundle['plan']['lead'])
        reviewed_meta = rank_math_meta_from_brief(brief)
        category = resolve_category(bundle['brief']['category_key'])
        base = ['sudo', 'docker', 'exec', 'wordpress_app', 'wp']
        current = get_post(base, post_id)
        if (current['post_status'] != 'draft'
                or current['post_title'] != matching[0]['post_title']
                or content_sha256(current['post_content']) != expected_content_sha256
                or DRAFTS_INDEX_FILE.read_text(encoding='utf-8') != index_before):
            raise ValueError('legacy_draft_changed_during_review')

        archive = ROOT / 'data' / 'editorial_runs'
        archive.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime('%Y%m%dT%H%M%S%f')
        current_meta = _read_rank_math_meta(base, post_id) if reviewed_meta else None
        update_meta = reviewed_meta is not None and current_meta != reviewed_meta
        backup = archive / f'legacy-draft-{post_id}-{stamp}.json'
        index_backup = archive / f'legacy-draft-index-{post_id}-{stamp}.json'
        with backup.open('x', encoding='utf-8') as file:
            backup_payload = dict(current)
            if current_meta is not None:
                backup_payload['rank_math_meta'] = current_meta
            json.dump(backup_payload, file, ensure_ascii=False, indent=2)
        index_backup.write_text(index_before, encoding='utf-8')
        os.chmod(backup, 0o600)
        os.chmod(index_backup, 0o600)
        save_report(bundle, report)

        saved = guarded_update_post(
            base,
            post_id,
            expected={
                'post_status': 'draft',
                'post_title': current['post_title'],
                'post_name': current['post_name'],
                'post_excerpt': current.get('post_excerpt', ''),
                'content_sha256': expected_content_sha256,
            },
            updates={
                'post_content': target_html,
                'post_excerpt': excerpt,
            },
        )
        observed_meta = current_meta
        if update_meta:
            observed_meta = _set_rank_math_meta(base, post_id, reviewed_meta)
        if not verify_saved_fields(
                saved,
                expected={
                    'post_status': 'draft',
                    'post_title': current['post_title'],
                    'post_content': target_html,
                    'post_excerpt': excerpt,
                },
                preserved={'post_name': current['post_name']}):
            raise ValueError(f'legacy_draft_saved_mismatch: recover from {backup}')
        if reviewed_meta is not None and observed_meta != reviewed_meta:
            raise ValueError(f'legacy_draft_saved_mismatch: recover from {backup}')

        if DRAFTS_INDEX_FILE.read_text(encoding='utf-8') != index_before:
            raise ValueError(f'legacy_index_changed: recover from {index_backup}')
        PublisherAgent()._record_post(post_id, bundle['plan']['title'], category['id'],
                                      category['name'], status='draft',
                                      expires_at=bundle['brief']['useful_until'],
                                      fact_manifest={'editorial_bundle': bundle})
        invalidate_inventory()
        print(f'Legacy draft backup: {backup}')
        print(f'Legacy draft index backup: {index_backup}')
        return post_id
    finally:
        lock.rmdir()
