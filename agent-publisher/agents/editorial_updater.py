"""Source-reviewed, compare-and-swap edits to an explicitly targeted public post."""

import hashlib
import json
import re
import subprocess
from datetime import datetime
from bs4 import BeautifulSoup

from agents.editorial import ROOT, render, save_report, validate_bundle, excerpt_from_lead
from agents.editorial_writer import fetch_sources, load_inventory
from sync_wordpress_inventory import sync_inventory


def _sha(content):
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


def _existing_lead_excerpt(content):
    """Extract only the published summary paragraph, excluding badges and CTAs."""
    lead = BeautifulSoup(content, 'html.parser').select_one('.bloguito-summary > p')
    if lead is None:
        return None
    text = lead.get_text(' ', strip=True)
    return excerpt_from_lead({'text': text}) if len(text) >= 20 else None


def update_existing_public_post(post_id, bundle, expected_content_sha256, *, confirmed=False):
    """Change only content after a fresh review and an unchanged-content check.

    The existing title, slug, status, categories, media and publication date
    are kept. The caller must have explicitly authorized this specific ID.
    """
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
        sync_inventory()
        inventory = load_inventory()
        original = next((row for row in inventory['posts'] if int(row['ID']) == post_id), None)
        if not original or original['post_status'] != 'publish' or _sha(original['post_content']) != expected_content_sha256:
            raise ValueError('target_missing_changed_or_not_public')
        remaining = dict(inventory, posts=[row for row in inventory['posts'] if int(row['ID']) != post_id])
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
        current = json.loads(subprocess.run(base + ['post', 'get', str(post_id), '--format=json', '--allow-root'],
                                            capture_output=True, text=True, check=True).stdout)
        if (current['post_status'] != 'publish' or current['post_title'] != original['post_title']
                or _sha(current['post_content']) != expected_content_sha256):
            raise ValueError('public_post_changed_during_review')
        # Preserve manually written excerpts; repair blanks or our own old previews.
        old_excerpt = current.get('post_excerpt', '')
        new_excerpt = (excerpt_from_lead(bundle['plan']['lead'])
                       if bundle['plan'].get('lead') else None)
        update_excerpt = bool(new_excerpt and (not old_excerpt.strip()
                              or old_excerpt == _existing_lead_excerpt(current['post_content'])))
        if current['post_content'] == reviewed_content and not update_excerpt:
            return post_id
        archive = ROOT / 'data' / 'editorial_runs'
        archive.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime('%Y%m%dT%H%M%S')
        backup_path = archive / f'public-edit-{post_id}-{stamp}.json'
        if backup_path.exists():
            raise ValueError('public_edit_backup_collision')
        # The full original post is retained locally for a deliberate rollback.
        with backup_path.open('x', encoding='utf-8') as handle:
            json.dump(current, handle, ensure_ascii=False, indent=2)
        save_report(bundle, report)
        # The reviewed, escaped renderer is the only content submitted.
        update_args = ['post', 'update', str(post_id), '--post_content=' + reviewed_content]
        if update_excerpt:
            update_args.append('--post_excerpt=' + new_excerpt)
        subprocess.run(base + update_args + ['--allow-root'], capture_output=True, text=True, check=True)
        saved = json.loads(subprocess.run(base + ['post', 'get', str(post_id), '--format=json', '--allow-root'],
                                          capture_output=True, text=True, check=True).stdout)
        if (saved['post_status'] != 'publish' or saved['post_title'] != original['post_title']
                or saved['post_name'] != current['post_name'] or saved['post_content'] != reviewed_content
                or (update_excerpt and saved.get('post_excerpt') != new_excerpt)):
            raise ValueError('public_edit_verification_failed: inspect WordPress before retrying')
        sync_inventory()
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
        current = json.loads(subprocess.run(base + ['post', 'get', str(post_id), '--format=json', '--allow-root'],
                                            capture_output=True, text=True, check=True).stdout)
        if current['post_status'] != 'publish' or _sha(current['post_content']) != expected_content_sha256:
            raise ValueError('target_missing_changed_or_not_public')
        if current.get('post_excerpt', '').strip():
            return post_id  # A human-authored preview must not be overwritten.
        excerpt = _existing_lead_excerpt(current['post_content'])
        if not excerpt:
            raise ValueError('published_lead_missing_or_invalid')
        archive = ROOT / 'data' / 'editorial_runs'
        archive.mkdir(parents=True, exist_ok=True)
        backup = archive / f'excerpt-edit-{post_id}-{datetime.now().strftime("%Y%m%dT%H%M%S")}.json'
        with backup.open('x', encoding='utf-8') as handle:
            json.dump(current, handle, ensure_ascii=False, indent=2)
        # One metadata field changes; facts, content and URL are untouched.
        subprocess.run(base + ['post', 'update', str(post_id), '--post_excerpt=' + excerpt, '--allow-root'],
                       capture_output=True, text=True, check=True)
        saved = json.loads(subprocess.run(base + ['post', 'get', str(post_id), '--format=json', '--allow-root'],
                                          capture_output=True, text=True, check=True).stdout)
        if (saved['post_excerpt'] != excerpt or saved['post_content'] != current['post_content']
                or saved['post_name'] != current['post_name'] or saved['post_status'] != 'publish'
                or saved['post_title'] != current['post_title']):
            raise ValueError('excerpt_verification_failed: inspect WordPress before retrying')
        return post_id
    finally:
        lock.rmdir()
