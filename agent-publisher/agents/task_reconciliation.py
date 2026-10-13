"""Q3 read-only, side-effect-free handoff classification and WordPress comparison.

This module must never create drafts, import images, rewrite task state, or
infer a successful mutation from a missing response. Verification is evidence,
not an authorization to resume a non-idempotent operation.
"""
from __future__ import annotations

import hashlib
import re


def summarize_state(post_id: int, state: dict | None) -> dict:
    if state is None:
        return {'post_id': post_id, 'record_status': 'missing',
                'operational_status': 'unverified',
                'next_action': 'locate_original_receipt_before_any_write'}
    completed = state.get('completed') or {}
    checkpoints = state.get('checkpoints') or {}
    result = state.get('result') or {}
    status = state.get('status')
    image_attempt = checkpoints.get('image_import_attempt') or {}
    image_outcome = checkpoints.get('image_outcome') or {}
    if image_attempt.get('started') and not image_outcome.get('attachment_id'):
        phase, action = ('image_import_outcome_ambiguous',
                         'reconcile_attachment_by_original_import_receipt_never_blind_retry')
    elif (result.get('draft_status') == 'draft_saved_pending_metadata'
          or result.get('completion') == 'draft_saved_pending_metadata'):
        phase, action = ('draft_saved_pending_metadata',
                         'verify_exact_post_id_and_metadata_with_live_cas_before_resume')
    elif status == 'saved_pending_qa':
        phase, action = ('saved_pending_qa',
                         'collect_real_browser_evidence_bound_to_saved_content_sha')
    elif status == 'complete' and completed.get('wordpress_saved'):
        verified = result.get('readback_verified') is True or (
            (result.get('image_phase') or {}).get('readback_verified') is True)
        phase = 'completed_verified' if verified else 'complete_recorded_readback_unverified'
        action = 'none' if verified else 'independent_live_readback_before_claiming_verified'
    elif status in {'failed', 'blocked'}:
        phase, action = ('write_outcome_requires_readback',
                         'inspect_post_and_receipts_before_resume_or_retry')
    else:
        phase, action = ('in_progress_unverified',
                         'resume_only_after_content_source_review_and_live_cas_check')
    return {'post_id': post_id, 'record_status': status,
            'operational_status': phase, 'next_action': action,
            'wordpress_saved_recorded': completed.get('wordpress_saved') is True,
            'pending_phases': list(state.get('pending') or []),
            'post_content_sha256': (result.get('desired_content_sha256')
                                    or (state.get('baseline') or {}).get('expected_content_sha256')),
            'task_id': state.get('task_id')}


def compare_live_snapshot(post_id: int, state: dict | None,
                          post: dict, thumbnail_id: str | None) -> dict:
    """Compare one fresh WP post/thumbnail snapshot without declaring metadata QA.

    A match is limited to fields actually bound by the saved task; it never
    proves Rank Math metadata, attachment bytes, image origin, or review freshness.
    """
    if not isinstance(state, dict) or state.get('post_id') != post_id:
        return {'status': 'unverified', 'reason': 'task_state_missing_or_mismatched',
                'write_authorized': False}
    result = state.get('result') or {}
    baseline = state.get('baseline') or {}
    expected_sha = result.get('desired_content_sha256') or baseline.get('expected_content_sha256')
    if not isinstance(expected_sha, str) or not re.fullmatch(r'[0-9a-f]{64}', expected_sha):
        return {'status': 'unverified', 'reason': 'expected_content_sha_missing',
                'write_authorized': False}
    content = post.get('post_content')
    if not isinstance(content, str):
        return {'status': 'unverified', 'reason': 'invalid_live_post_snapshot',
                'write_authorized': False}
    live_sha = hashlib.sha256(content.encode('utf-8')).hexdigest()
    comparisons = {'content_sha256': live_sha == expected_sha}
    expected_status = result.get('target_status') or baseline.get('post_status')
    if expected_status in {'draft', 'publish', 'pending', 'private'}:
        comparisons['post_status'] = post.get('post_status') == expected_status
    image_outcome = ((state.get('checkpoints') or {}).get('image_outcome') or {})
    expected_thumb = (result.get('attachment_id')
                      or (result.get('image_phase') or {}).get('attachment_id')
                      or image_outcome.get('attachment_id'))
    if type(expected_thumb) is int and expected_thumb > 0:
        comparisons['thumbnail_id'] = thumbnail_id == str(expected_thumb)
    status = 'matched_post_snapshot' if all(comparisons.values()) else 'live_state_drift'
    return {'status': status, 'comparisons': comparisons,
            'live_content_sha256': live_sha, 'expected_content_sha256': expected_sha,
            'post_status': post.get('post_status'),
            'verified_scope': 'post_and_record_bound_fields_only',
            'metadata_verified': False, 'attachment_bytes_verified': False,
            'write_authorized': False,
            'next_action': ('review_pending_phases_and_fresh_source_policy_before_resume'
                            if status == 'matched_post_snapshot'
                            else 'stop_and_reconcile_external_wordpress_change')}


def read_live_task_reconciliation(post_id: int, state: dict | None) -> dict:
    """One fresh read-only WordPress process, no media import or state write."""
    if type(post_id) is not int or post_id <= 0:
        raise ValueError('valid_post_id_required')
    if state is None:
        return compare_live_snapshot(post_id, state, {}, None)
    from agents.wordpress_mutation import read_post_thumbnail_snapshot
    post, thumb = read_post_thumbnail_snapshot(
        ['sudo', 'docker', 'exec', 'wordpress_app', 'wp'], post_id)
    return compare_live_snapshot(post_id, state, post, thumb)


def inspect_uncertain_image_import(post_id: int, state: dict | None,
                                   staged_image_sha256: str) -> dict:
    """Read-only candidate search; even one SHA match is NOT proof of import ownership.

    No call here may import media or assign featured image, and media SHA is
    never treated as an image_gen host-attestation signature.
    """
    if type(post_id) is not int or post_id <= 0:
        raise ValueError('valid_post_id_required')
    if not isinstance(staged_image_sha256, str) or not re.fullmatch(
            r'[0-9a-f]{64}', staged_image_sha256):
        raise ValueError('valid_staged_image_sha256_required')
    if not isinstance(state, dict) or state.get('post_id') != post_id:
        return {'status': 'unverified', 'reason': 'matching_task_state_required',
                'automatic_retry': False, 'write_authorized': False}
    checkpoints = state.get('checkpoints') or {}
    attempt = checkpoints.get('image_import_attempt') or {}
    outcome = checkpoints.get('image_outcome') or {}
    if not attempt.get('started') or outcome.get('attachment_id'):
        return {'status': 'not_an_uncertain_image_import',
                'automatic_retry': False, 'write_authorized': False}
    if attempt.get('image_sha256') != staged_image_sha256:
        return {'status': 'unverified', 'reason': 'original_attempt_sha_mismatch',
                'automatic_retry': False, 'write_authorized': False,
                'next_action': 'locate_original_staged_image_receipt_no_sha_adoption'}
    from agents.wordpress_mutation import find_attachment_ids_by_sha
    ids = find_attachment_ids_by_sha(
        ['sudo', 'docker', 'exec', 'wordpress_app', 'wp'],
        post_id, staged_image_sha256)
    from agents.media_recovery_contract import classify_sha_candidates
    evidence = classify_sha_candidates(
        ids, preexisting_ids=attempt.get('preexisting_attachment_ids'))
    return {'status': evidence['status'], 'post_id': post_id,
            'observed_attachment_ids': ids, 'staged_image_sha256': staged_image_sha256,
            'candidate_attachment_ids': evidence['candidate_attachment_ids'],
            'ownership_verified': False, 'import_termination_verified': False,
            'automatic_retry': False, 'write_authorized': False,
            'next_action': ('verify_original_staging_receipt_attachment_readback_and_live_cas_'
                            'then_use_existing_regular_resume_path')}
