"""Refresh a reviewed WordPress draft and its manifest without changing its status."""

import hashlib
import json
import re
import subprocess
from datetime import datetime

from agents.editorial import ROOT, render, save_report, validate_bundle
from agents.editorial_writer import fetch_sources, load_inventory
from config import DRAFTS_INDEX_FILE
from sync_wordpress_inventory import sync_inventory


def _hash(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _without_generated_cards(content):
    """Compare all authored prose while allowing only renderer-owned cards to change."""
    # The CTA has nested <div> nodes; its next sibling is the TOC marker.
    content = re.sub(r'<div class="bloguito-cta"[^>]*>.*?(?=<div class="bloguito-toc")',
                     '', content, flags=re.DOTALL)
    content = re.sub(r'<div class="bloguito-interlink"[^>]*>.*?</div>',
                     '', content, flags=re.DOTALL)
    return content.replace('\r\n', '\n')


def update_draft(post_id, bundle, expected_content_sha256):
    if (not isinstance(post_id, int) or post_id <= 0
            or not re.fullmatch(r'[0-9a-f]{64}', expected_content_sha256 or '')):
        raise ValueError('draft_id_and_original_content_sha256_required')
    lock = ROOT / 'data' / '.editorial-publish.lock'
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        lock.mkdir()
    except FileExistsError:
        raise ValueError('editorial_publication_busy: inspect the existing job')
    try:
        sync_inventory()
        inventory = load_inventory()
        current = next((p for p in inventory['posts'] if int(p['ID']) == post_id), None)
        if (not current or current['post_status'] != 'draft'
                or current['post_title'] != bundle['plan']['title']
                or _hash(current['post_content']) != expected_content_sha256):
            raise ValueError('draft_missing_or_modified')

        original_index = DRAFTS_INDEX_FILE.read_text(encoding='utf-8')
        records = json.loads(original_index)
        item = next((p for p in records if int(p.get('id', -1)) == post_id), None)
        if not item or 'editorial_bundle' not in item.get('fact_manifest', {}):
            raise ValueError('reviewed_draft_manifest_required')
        old_bundle = item['fact_manifest']['editorial_bundle']
        if old_bundle['brief'] != bundle['brief'] or old_bundle['plan'] != bundle['plan']:
            raise ValueError('draft_prose_or_topic_changed: independent content review required')

        def evidence_sources(sources):
            return [{k: v for k, v in source.items() if k not in {'actions', 'cta_label'}}
                    for source in sources]

        if evidence_sources(old_bundle['sources']) != evidence_sources(bundle['sources']):
            raise ValueError('draft_evidence_changed: independent content review required')
        remaining = dict(inventory, posts=[p for p in inventory['posts'] if int(p['ID']) != post_id])
        report = validate_bundle(bundle, remaining)
        if report['status'] != 'ready':
            raise ValueError(f'draft_editorial_review_failed: {report["reasons"]}')
        fresh = fetch_sources(bundle['brief'])
        if ({s['url']: s['sha256'] for s in bundle['sources']}
                != {s['url']: s['sha256'] for s in fresh}):
            raise ValueError('official_sources_changed_since_review')

        desired = render(bundle['plan'], bundle['sources'])
        if _without_generated_cards(current['post_content']) != _without_generated_cards(desired):
            raise ValueError('draft_contains_other_edits: do_not_overwrite')
        base = ['sudo', 'docker', 'exec', 'wordpress_app', 'wp']
        live = json.loads(subprocess.run(base + ['post', 'get', str(post_id), '--format=json', '--allow-root'],
                                         capture_output=True, text=True, check=True).stdout)
        if (live['post_status'] != 'draft' or live['post_title'] != current['post_title']
                or _hash(live['post_content']) != expected_content_sha256):
            raise ValueError('draft_changed_during_review')
        backups = ROOT / 'data' / 'editorial_runs'
        backups.mkdir(parents=True, exist_ok=True)
        backup = backups / f'draft-action-{post_id}-{datetime.now().strftime("%Y%m%dT%H%M%S%f")}.json'
        with backup.open('x', encoding='utf-8') as file:
            json.dump(live, file, ensure_ascii=False, indent=2)
        save_report(bundle, report)
        if live['post_content'] != desired:
            subprocess.run(base + ['post', 'update', str(post_id), '--post_content=' + desired,
                                   '--allow-root'], capture_output=True, text=True, check=True)
        saved = json.loads(subprocess.run(base + ['post', 'get', str(post_id), '--format=json', '--allow-root'],
                                          capture_output=True, text=True, check=True).stdout)
        if (saved['post_status'] != 'draft' or saved['post_title'] != live['post_title']
                or saved['post_name'] != live['post_name'] or saved['post_content'] != desired):
            raise ValueError('draft_save_verification_failed')

        item['fact_manifest']['editorial_bundle'] = bundle
        if DRAFTS_INDEX_FILE.read_text(encoding='utf-8') != original_index:
            raise ValueError('draft_index_changed_during_update')
        temporary = DRAFTS_INDEX_FILE.with_suffix('.action-tmp')
        temporary.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
        temporary.replace(DRAFTS_INDEX_FILE)
        sync_inventory()
        return post_id
    finally:
        lock.rmdir()
