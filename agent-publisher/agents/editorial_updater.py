"""Source-reviewed, compare-and-swap edits to an explicitly targeted public post."""

import hashlib
import json
import re
import subprocess
from datetime import datetime
from bs4 import BeautifulSoup

from agents.editorial import ROOT, render, save_report, validate_bundle, excerpt_from_lead
from agents.related_links import missing_internal_post_ids
from agents.editorial_writer import fetch_sources, load_inventory
from sync_wordpress_inventory import hydrate_duplicate_candidates, inventory_content_sha, invalidate_inventory, sync_inventory
from agents.wordpress_mutation import (
    backup_json,
    content_sha256,
    get_post,
    update_post,
    verify_cas,
    verify_saved_fields,
)


def _sha(content):
    return content_sha256(content)


def _existing_lead_excerpt(content):
    """Extract only the published summary paragraph, excluding badges and CTAs."""
    lead = BeautifulSoup(content, 'html.parser').select_one('.bloguito-summary > p')
    if lead is None:
        return None
    text = lead.get_text(' ', strip=True)
    return excerpt_from_lead({'text': text}) if len(text) >= 20 else None


def update_existing_public_post(post_id, bundle, expected_content_sha256, *, confirmed=False,
                                confirm_title_change=False):
    """Change reviewed content after a fresh review and unchanged-content check.

    The slug, status, categories, media and publication date are kept. Title
    changes require their own explicit confirmation; otherwise the existing
    title is preserved. The caller must explicitly authorize this specific ID.
    """
    if not confirmed or not isinstance(post_id, int) or post_id <= 0:
        raise ValueError('specific_public_post_update_confirmation_required')
    if bundle.get('brief', {}).get('existing_post_id') != post_id:
        raise ValueError('reviewed_bundle_target_id_mismatch')
    if not re.fullmatch(r'[0-9a-f]{64}', expected_content_sha256 or ''):
        raise ValueError('original_content_sha256_required')
    lock = ROOT / 'data' / '.editorial-publish.lock'
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        lock.mkdir()
    except FileExistsError:
        raise ValueError('editorial_publication_busy: verify any running process before retrying')
    try:
        sync_inventory()
        inventory = load_inventory()
        original = next((row for row in inventory['posts'] if int(row['ID']) == post_id), None)
        if (not original or original['post_status'] != 'publish'
                or inventory_content_sha(original) != expected_content_sha256):
            raise ValueError('target_missing_changed_or_not_public')
        reviewed_title = bundle.get('plan', {}).get('title') or original['post_title']
        title_changed = reviewed_title != original['post_title']
        if title_changed and not confirm_title_change:
            raise ValueError('public_title_change_confirmation_required')
        remaining = dict(inventory, posts=[row for row in inventory['posts'] if int(row['ID']) != post_id])
        remaining = hydrate_duplicate_candidates(
            bundle['brief'], remaining,
            related_post_ids={item.get('post_id') for item in bundle.get('plan', {}).get('related_posts', [])
                              if isinstance(item, dict) and type(item.get('post_id')) is int},
        )
        report = validate_bundle(bundle, remaining)
        if report['status'] != 'ready':
            raise ValueError(f'editorial_review_not_current: {report["reasons"]}')
        fresh_sources = fetch_sources(bundle['brief'])
        before = {source['url']: source['sha256'] for source in bundle['sources']}
        after = {source['url']: source['sha256'] for source in fresh_sources}
        if before != after:
            raise ValueError('official_source_changed_since_review')
        reviewed_content = render(bundle['plan'], bundle['sources'])
        base = ['sudo', 'docker', 'exec', 'wordpress_app', 'wp']
        current = get_post(base, post_id)
        if not verify_cas(current, status='publish', title=original['post_title'],
                          content_sha=expected_content_sha256):
            raise ValueError('public_post_changed_during_review')
        if missing_internal_post_ids(current['post_content'], reviewed_content):
            raise ValueError('original_internal_post_navigation_missing')
        # Preserve manually written excerpts; repair blanks or our own old previews.
        old_excerpt = current.get('post_excerpt', '')
        new_excerpt = (excerpt_from_lead(bundle['plan']['lead'])
                       if bundle['plan'].get('lead') else None)
        update_excerpt = bool(new_excerpt and (not old_excerpt.strip()
                              or old_excerpt == _existing_lead_excerpt(current['post_content'])))
        if current['post_content'] == reviewed_content and not update_excerpt and not title_changed:
            return post_id
        backup_path = backup_json(ROOT, 'public-edit', post_id, current, include_microseconds=False)
        save_report(bundle, report)
        # The reviewed, escaped renderer is the only content submitted.
        fields = {'post_content': reviewed_content}
        if title_changed:
            fields['post_title'] = reviewed_title
        if update_excerpt:
            fields['post_excerpt'] = new_excerpt
        update_post(base, post_id, fields)
        saved = get_post(base, post_id)
        expected = {
            'post_status': 'publish',
            'post_title': reviewed_title,
            'post_content': reviewed_content,
        }
        if update_excerpt:
            expected['post_excerpt'] = new_excerpt
        if not verify_saved_fields(saved, expected=expected,
                                   preserved={'post_name': current['post_name']}):
            raise ValueError('public_edit_verification_failed: inspect WordPress before retrying')
        invalidate_inventory()
        return post_id
    finally:
        lock.rmdir()


def repair_missing_excerpt(post_id, expected_content_sha256, *, confirmed=False):
    """Repair only an empty archive excerpt using the post's existing lead text."""
    if not confirmed or not isinstance(post_id, int) or post_id <= 0:
        raise ValueError('specific_public_post_update_confirmation_required')
    if not re.fullmatch(r'[0-9a-f]{64}', expected_content_sha256 or ''):
        raise ValueError('original_content_sha256_required')
    lock = ROOT / 'data' / '.editorial-publish.lock'
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        lock.mkdir()
    except FileExistsError:
        raise ValueError('editorial_publication_busy: verify any running process before retrying')
    try:
        base = ['sudo', 'docker', 'exec', 'wordpress_app', 'wp']
        current = get_post(base, post_id)
        if current['post_status'] != 'publish' or _sha(current['post_content']) != expected_content_sha256:
            raise ValueError('target_missing_changed_or_not_public')
        if current.get('post_excerpt', '').strip():
            return post_id  # A human-authored preview must not be overwritten.
        excerpt = _existing_lead_excerpt(current['post_content'])
        if not excerpt:
            raise ValueError('published_lead_missing_or_invalid')
        backup = backup_json(ROOT, 'excerpt-edit', post_id, current, include_microseconds=False)
        # One metadata field changes; facts, content and URL are untouched.
        update_post(base, post_id, {'post_excerpt': excerpt})
        saved = get_post(base, post_id)
        if (saved['post_excerpt'] != excerpt or saved['post_content'] != current['post_content']
                or saved['post_name'] != current['post_name'] or saved['post_status'] != 'publish'
                or saved['post_title'] != current['post_title']):
            raise ValueError('excerpt_verification_failed: inspect WordPress before retrying')
        return post_id
    finally:
        lock.rmdir()
