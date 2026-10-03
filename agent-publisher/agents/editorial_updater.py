"""Source-reviewed, compare-and-swap edits to an explicitly targeted public post."""

import hashlib
import json
import re
import subprocess
from agents.wordpress_transport import run_wordpress
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from datetime import datetime
from bs4 import BeautifulSoup

from agents.editorial import ROOT, render, save_report, validate_bundle, excerpt_from_lead
from agents.post_manifest_store import (
    acquire_editorial_lock,
    load_record,
    release_editorial_lock,
    replace_record,
    upsert_record,
)
from agents.related_links import missing_internal_post_ids
from agents.editorial_writer import load_inventory
from agents.source_validation_cache import verify_revision_sources
from config import POSTS_INDEX_FILE, SITE_URL, resolve_category
from sync_wordpress_inventory import hydrate_duplicate_candidates, inventory_content_sha, invalidate_inventory, sync_inventory
from agents.wordpress_mutation import (
    backup_json,
    content_sha256,
    get_post,
    guarded_update_post,
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


RANK_MATH_META_KEYS = (
    'rank_math_focus_keyword',
    'rank_math_title',
    'rank_math_description',
)


def rank_math_meta_from_brief(brief):
    """Return exact reviewed Rank Math values, or None when SEO was not reviewed."""
    if 'seo' not in brief:
        return None
    seo = brief.get('seo')
    focus = brief.get('primary_keyword')
    if (not isinstance(seo, dict) or not isinstance(focus, str) or not focus.strip()
            or not isinstance(seo.get('title'), str) or not seo['title'].strip()
            or not isinstance(seo.get('description'), str) or not seo['description'].strip()
            or any('\x00' in value for value in (focus, seo['title'], seo['description']))):
        raise ValueError('invalid_reviewed_seo_metadata')
    return {
        'rank_math_focus_keyword': focus.strip(),
        'rank_math_title': seo['title'],
        'rank_math_description': seo['description'],
    }


def _read_post_meta(base, post_id, key):
    result = run_wordpress(
        list(base) + ['post', 'meta', 'get', str(post_id), key, '--allow-root'],
        capture_output=True, text=True, encoding='utf-8', errors='strict', check=False)
    if result.returncode == 0:
        return (result.stdout or '').rstrip('\r\n')
    stderr = (result.stderr or '').lower()
    stdout = result.stdout or ''
    if result.returncode == 1 and (
            'could not find the specified post meta field' in stderr
            or (not stdout.strip() and not stderr.strip())):
        return None
    raise subprocess.CalledProcessError(
        result.returncode, result.args, output=result.stdout, stderr=result.stderr)


def _read_rank_math_meta(base, post_id):
    return {key: _read_post_meta(base, post_id, key) for key in RANK_MATH_META_KEYS}


def _set_rank_math_meta(base, post_id, values):
    for key in RANK_MATH_META_KEYS:
        run_wordpress(
            list(base) + ['post', 'meta', 'set', str(post_id), key, values[key], '--allow-root'],
            capture_output=True, text=True, encoding='utf-8', errors='strict', check=True)


def _public_manifest_record(post_id, bundle, live_post):
    """Build reviewed-state metadata only after a live public readback succeeded."""
    category = resolve_category(bundle.get('brief', {}).get('category_key', ''))
    slug = (live_post.get('post_name') or '').strip('/')
    url = f"{SITE_URL.rstrip('/')}/{slug}/" if slug else f"{SITE_URL.rstrip('/')}/?p={post_id}"
    return {
        'id': post_id,
        'title': live_post.get('post_title') or bundle.get('plan', {}).get('title') or '',
        'url': url,
        'category_id': category['id'],
        'category_name': category['name'],
        'status': 'publish',
        'expires_at': bundle.get('brief', {}).get('useful_until'),
        'fact_manifest': {'editorial_bundle': bundle},
        # This is the reviewed-state adoption timestamp for a legacy public post.
        # It deliberately does not claim to reconstruct the original WP publish time.
        'published_at': datetime.now().strftime('%Y-%m-%d %H:%M'),
    }


def _update_reviewed_public_manifest(post_id, bundle, *, allow_create=False, live_post=None):
    """Advance a reviewed manifest; optionally adopt a fully reviewed legacy public post."""
    index_file = POSTS_INDEX_FILE
    snapshot = load_record(index_file, post_id) if index_file.is_file() else None
    if snapshot is None or not snapshot.record.get('fact_manifest', {}).get('editorial_bundle'):
        if allow_create:
            if not isinstance(live_post, dict) or live_post.get('post_status') != 'publish':
                raise ValueError('legacy_public_manifest_live_readback_required')
            upsert_record(index_file, _public_manifest_record(post_id, bundle, live_post))
            return True
        return False
    updated = dict(snapshot.record)
    updated.setdefault('fact_manifest', dict(snapshot.record.get('fact_manifest', {})))['editorial_bundle'] = bundle
    try:
        replace_record(snapshot, updated)
    except ValueError as exc:
        raise ValueError('published_index_changed_during_update') from exc
    return True


def update_existing_public_post(post_id, bundle, expected_content_sha256, *, confirmed=False,
                                confirm_title_change=False, checkpoint_callback=None,
                                tracked_baseline_bundle=None, adopt_missing_manifest=False):
    """Change reviewed content after a fresh review and unchanged-content check.

    The slug, status, categories, media and publication date are kept. Title
    changes require their own explicit confirmation; otherwise the existing
    title is preserved. The caller must explicitly authorize this specific ID.
    """
    if not confirmed or not isinstance(post_id, int) or post_id <= 0:
        raise ValueError('specific_public_post_update_confirmation_required')
    if not re.fullmatch(r'[0-9a-f]{64}', expected_content_sha256 or ''):
        raise ValueError('original_content_sha256_required')
    declared_id = bundle.get('brief', {}).get('existing_post_id')
    if declared_id != post_id:
        tracked_ok = False
        if declared_id is None and isinstance(tracked_baseline_bundle, dict):
            tracked_brief = tracked_baseline_bundle.get('brief', {})
            candidate_brief = bundle.get('brief', {})
            same_identity = all(
                tracked_brief.get(key) == candidate_brief.get(key)
                for key in ('id', 'category_key', 'entity')
            )
            try:
                tracked_sha = content_sha256(render(
                    tracked_baseline_bundle['plan'], tracked_baseline_bundle['sources']))
            except (KeyError, TypeError, ValueError):
                tracked_sha = None
            tracked_ok = bool(same_identity and tracked_sha == expected_content_sha256)
        if not tracked_ok:
            raise ValueError('reviewed_bundle_target_id_mismatch')
    reviewed_meta = rank_math_meta_from_brief(bundle.get('brief', {}))
    lock = acquire_editorial_lock(ROOT)
    try:
        base = ['sudo', 'docker', 'exec', 'wordpress_app', 'wp']
        fields = ['post_status', 'post_title', 'post_name', 'post_content', 'post_excerpt']
        inventory_context = copy_context()
        target_context = copy_context()
        source_context = copy_context()
        with ThreadPoolExecutor(max_workers=3) as pool:
            inventory_future = pool.submit(inventory_context.run, sync_inventory)
            target_future = pool.submit(target_context.run, get_post, base, post_id, fields=fields)
            source_future = pool.submit(
                source_context.run,
                verify_revision_sources,
                tracked_baseline_bundle or {},
                bundle,
            )
            inventory_future.result()
            current = target_future.result()
            source_validation = source_future.result()
        inventory = load_inventory()
        original = next((row for row in inventory['posts'] if int(row['ID']) == post_id), None)
        if (not original or original['post_status'] != 'publish'
                or inventory_content_sha(original) != expected_content_sha256):
            raise ValueError('target_missing_changed_or_not_public')
        if (current.get('post_status') != original.get('post_status')
                or current.get('post_title') != original.get('post_title')
                or content_sha256(current.get('post_content', '')) != inventory_content_sha(original)):
            raise ValueError('inventory_post_detail_changed')
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
        if checkpoint_callback is not None:
            checkpoint_callback({
                'inventory_checked_on': inventory.get('checked_on'),
                'source_validation': source_validation,
                'review_digest': bundle.get('review', {}).get('digest'),
            })
        reviewed_content = render(bundle['plan'], bundle['sources'])
        if not verify_cas(current, status='publish', title=original['post_title'],
                          content_sha=expected_content_sha256):
            raise ValueError('public_post_changed_during_review')
        if missing_internal_post_ids(current['post_content'], reviewed_content):
            raise ValueError('original_internal_post_navigation_missing')
        current_meta = _read_rank_math_meta(base, post_id) if reviewed_meta else None
        update_meta = reviewed_meta is not None and current_meta != reviewed_meta
        # Preserve manually written excerpts; repair blanks or our own old previews.
        old_excerpt = current.get('post_excerpt', '')
        new_excerpt = (excerpt_from_lead(bundle['plan']['lead'])
                       if bundle['plan'].get('lead') else None)
        update_excerpt = bool(new_excerpt and (not old_excerpt.strip()
                              or old_excerpt == _existing_lead_excerpt(current['post_content'])))
        if (current['post_content'] == reviewed_content and not update_excerpt
                and not title_changed and not update_meta):
            _update_reviewed_public_manifest(
                post_id, bundle, allow_create=adopt_missing_manifest, live_post=current)
            return post_id
        backup_payload = dict(current)
        if current_meta is not None:
            backup_payload['rank_math_meta'] = current_meta
        backup_path = backup_json(
            ROOT, 'public-edit', post_id, backup_payload, include_microseconds=False)
        save_report(bundle, report)
        # The reviewed, escaped renderer is the only content submitted.
        fields = {'post_content': reviewed_content}
        if title_changed:
            fields['post_title'] = reviewed_title
        if update_excerpt:
            fields['post_excerpt'] = new_excerpt
        saved = guarded_update_post(
            base,
            post_id,
            expected={
                'post_status': 'publish',
                'post_title': current['post_title'],
                'post_name': current['post_name'],
                'post_excerpt': current.get('post_excerpt', ''),
                'content_sha256': expected_content_sha256,
            },
            updates=fields,
        )
        if update_meta:
            _set_rank_math_meta(base, post_id, reviewed_meta)
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
        if reviewed_meta is not None and _read_rank_math_meta(base, post_id) != reviewed_meta:
            raise ValueError('public_edit_verification_failed: inspect WordPress before retrying')
        _update_reviewed_public_manifest(
            post_id, bundle, allow_create=adopt_missing_manifest, live_post=saved)
        invalidate_inventory()
        return post_id
    finally:
        release_editorial_lock(lock)


def repair_missing_excerpt(post_id, expected_content_sha256, *, confirmed=False):
    """Repair only an empty archive excerpt using the post's existing lead text."""
    if not confirmed or not isinstance(post_id, int) or post_id <= 0:
        raise ValueError('specific_public_post_update_confirmation_required')
    if not re.fullmatch(r'[0-9a-f]{64}', expected_content_sha256 or ''):
        raise ValueError('original_content_sha256_required')
    lock = acquire_editorial_lock(ROOT)
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
        release_editorial_lock(lock)
