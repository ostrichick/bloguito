"""Read-only, journal-bound operator diagnosis for interrupted new drafts.

Never infers ownership from matching title/content and never writes a journal,
WordPress post or metadata. The *existing* canonical prepare-draft workflow is
the only writer after reviewed evidence and live source/CAS gates are renewed.
"""
from __future__ import annotations

import hashlib
import json

from agents.draft_create_journal import DraftCreateJournal, workflow_key


def reconcile_draft_create(bundle: dict, *, candidate_post_id: int | None = None,
                           journal_directory=None, wordpress_reader=None) -> dict:
    from agents.editorial import render, excerpt_from_lead
    if not isinstance(bundle, dict) or not isinstance(bundle.get('plan'), dict) or not isinstance(bundle.get('sources'), list):
        raise ValueError('reviewed_editorial_bundle_required')
    if candidate_post_id is not None and (type(candidate_post_id) is not int or candidate_post_id <= 0):
        raise ValueError('valid_candidate_post_id_required')
    content = render(bundle['plan'], bundle['sources'])
    title = bundle['plan']['title']
    excerpt = excerpt_from_lead(bundle['plan']['lead'])
    key = workflow_key(bundle, content=content, title=title, excerpt=excerpt)
    journal = DraftCreateJournal(key, directory=journal_directory)
    entry = journal.read()
    result = {'workflow_key': key, 'journal_state': entry.get('state') if entry else 'missing',
              'recorded_post_id': entry.get('post_id') if entry else None,
              'write_authorized': False, 'automatic_create_retry': False,
              'live_post_match': None}
    if entry is None:
        result['next_action'] = 'missing_journal_requires_independent_operator_investigation'
        return result
    if entry['state'] == 'creating' and candidate_post_id is None:
        result['next_action'] = 'unknown_create_outcome_do_not_retry_or_adopt_by_title'
        return result
    if entry['state'] in {'created', 'complete'}:
        if candidate_post_id is not None and entry['post_id'] != candidate_post_id:
            result['next_action'] = 'candidate_post_id_conflicts_with_durable_journal'
            return result
        check_id = entry['post_id']
    else:
        check_id = candidate_post_id
    if wordpress_reader is None:
        from agents.wordpress_transport import run_wordpress
        def wordpress_reader(post_id):
            argv = ['sudo', 'docker', 'exec', 'wordpress_app', 'wp', 'post', 'get',
                    str(post_id), '--fields=post_status,post_title,post_name,post_content,post_excerpt',
                    '--format=json', '--allow-root']
            return json.loads(run_wordpress(argv, check=True, capture_output=True,
                            text=True, encoding='utf-8', errors='strict').stdout)
    saved = wordpress_reader(check_id)
    if not isinstance(saved, dict):
        raise ValueError('invalid_wordpress_draft_readback')
    checks = {'status': saved.get('post_status') == 'draft',
              'title': saved.get('post_title') == title,
              'excerpt': saved.get('post_excerpt') == excerpt,
              'content_sha256': isinstance(saved.get('post_content'), str)
              and hashlib.sha256(saved['post_content'].encode('utf-8')).hexdigest()
              == hashlib.sha256(content.encode('utf-8')).hexdigest()}
    result.update(live_post_match=all(checks.values()), comparisons=checks,
                  inspected_post_id=check_id,
                  content_sha256=hashlib.sha256(content.encode('utf-8')).hexdigest())
    if not all(checks.values()):
        result['next_action'] = 'stop_draft_drift_or_unowned_candidate'
    elif entry['state'] == 'creating':
        result['next_action'] = 'operator_prove_original_post_id_receipt_before_any_journal_repair'
    elif entry['state'] == 'created':
        result['next_action'] = 'rerun_canonical_prepare_draft_after_fresh_review_and_source_check'
    else:
        result['next_action'] = 'already_complete_confirm_metadata_and_index_readback'
    return result
