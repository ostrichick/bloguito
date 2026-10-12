"""R1/R2 independent, signed image-origin and review/selection preflight.

An image manifest and a reviewer checklist are caller-written records. Only
separately issued Ed25519 evidence, verified against protected server trust
anchors, may authorize a new featured-image import. This module NEVER issues
keys or signatures and NEVER interprets a claim as a host observation.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path


TRUST_ROOT = Path('/etc/bloguito/image-trust')
PROOF_TTL = timedelta(hours=24)
_SHA = re.compile(r'[0-9a-f]{64}\Z')


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _time(value: str) -> datetime:
    from agents.featured_image_quality_review import _aware_timestamp
    return _aware_timestamp(value)


def _load_json(path: Path, error: str) -> dict:
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, ValueError) as exc:
        raise ValueError(error) from exc
    if not isinstance(payload, dict):
        raise ValueError(error)
    return payload


def _canonical(kind: str, payload: dict) -> bytes:
    return (b'bloguito-featured-image-trust-v1\n' + kind.encode('ascii') + b'\n'
            + json.dumps(payload, sort_keys=True, separators=(',', ':'),
                         ensure_ascii=False).encode('utf-8'))


def _verify_signed_event(path: Path, *, kind: str, public_key_path: Path,
                         task_created_at: str, now: datetime) -> dict:
    evidence = _load_json(path, 'image_trust_proof_missing_or_invalid')
    if (set(evidence) != {'version', 'kind', 'payload', 'signature'}
            or evidence['version'] != 1 or evidence['kind'] != kind
            or not isinstance(evidence['payload'], dict)
            or not isinstance(evidence['signature'], str)):
        raise ValueError('image_trust_proof_schema_invalid')
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        from cryptography.exceptions import InvalidSignature
    except ImportError as exc:
        raise ValueError('held_provenance_unverifiable:crypto_verifier_unavailable') from exc
    try:
        key_bytes = public_key_path.read_bytes()
        public_key = serialization.load_pem_public_key(key_bytes)
        if not isinstance(public_key, Ed25519PublicKey):
            raise ValueError('image_trust_wrong_public_key_type')
        signature = base64.b64decode(evidence['signature'], validate=True)
        public_key.verify(signature, _canonical(kind, evidence['payload']))
    except (OSError, ValueError, binascii.Error, InvalidSignature) as exc:
        raise ValueError('image_trust_signature_or_issuer_unverifiable') from exc
    payload = evidence['payload']
    try:
        issued = _time(payload.get('issued_at'))
        expires = _time(payload.get('expires_at'))
        created = _time(task_created_at)
    except ValueError as exc:
        raise ValueError('image_trust_time_invalid') from exc
    if (issued < created or issued > now or expires <= issued
            or expires - issued > PROOF_TTL or expires <= now
            or now - issued > PROOF_TTL):
        raise ValueError('image_trust_proof_expired_or_wrong_task_time')
    return payload


def verify_image_upload_trust(*, task: dict, manifest_path: Path | str,
                              review_path: Path | str, source_sha256: str,
                              staged_sha256: str, selected_candidate: int,
                              selection_mode: str, task_created_at: str,
                              trust_root: Path | None = None,
                              now: datetime | None = None) -> dict:
    """Require two *independently signed* events bound to actual sealed bytes.

    Production always uses the server-owned trust-root path. `trust_root` is
    for offline verifier tests; no CLI or SSH parameter exposes an override.
    A genuine issuer/approval service must be provisioned separately and must
    never place signing keys under the AI worker's account or source tree.
    """
    manifest_path, review_path = Path(manifest_path), Path(review_path)
    root = Path(trust_root) if trust_root is not None else TRUST_ROOT
    if trust_root is None and os.name != 'posix':
        # The production trust anchors belong to a protected Linux writer.
        # Windows cannot establish the root ownership/mode security boundary;
        # never treat C:\\etc\\... or a local copy as trusted authority.
        raise ValueError('held_provenance_unverifiable:protected_server_verifier_required')
    # Production keys are distributed out of band; source code, CLI flags and
    # environment variables cannot appoint a new trusted signing authority.
    # On Unix, refuse writable or non-root-controlled anchors outright.
    if trust_root is None and os.name == 'posix':
        for anchor in (root, root / 'host.pub.pem', root / 'review.pub.pem'):
            try:
                st = anchor.stat()
            except OSError as exc:
                raise ValueError('held_provenance_unverifiable:trust_anchor_missing') from exc
            if st.st_uid != 0 or st.st_mode & 0o022 or anchor.is_symlink():
                raise ValueError('held_provenance_unverifiable:trust_anchor_unprotected')
    host_public = root / 'host.pub.pem'
    review_public = root / 'review.pub.pem'
    if (not host_public.is_file() or not review_public.is_file()
            or host_public.read_bytes() == review_public.read_bytes()):
        raise ValueError('held_provenance_unverifiable:independent_trust_issuers_unavailable')
    manifest = _load_json(manifest_path, 'image_trust_manifest_invalid')
    review = _load_json(review_path, 'image_trust_review_invalid')
    rows = manifest.get('candidates')
    if not isinstance(rows, list) or len(rows) != task.get('candidate_count'):
        raise ValueError('image_trust_candidate_count_mismatch')
    candidates = []
    for index, row in enumerate(rows, 1):
        if (not isinstance(row, dict) or row.get('candidate_number') != index
                or not isinstance(row.get('sha256'), str)
                or not _SHA.fullmatch(row['sha256'])):
            raise ValueError('image_trust_candidate_inventory_invalid')
        candidates.append({'candidate_number': index, 'sha256': row['sha256']})
    if (type(selected_candidate) is not int or not 1 <= selected_candidate <= len(candidates)
            or candidates[selected_candidate - 1]['sha256'] != source_sha256
            or not isinstance(staged_sha256, str) or not _SHA.fullmatch(staged_sha256)):
        raise ValueError('image_trust_selected_source_mismatch')
    if task.get('task_id') != review.get('task_id'):
        raise ValueError('image_trust_task_mismatch')
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('image_trust_clock_timezone_invalid')
    now = now.astimezone(timezone.utc)
    common = {'task_id': task.get('task_id'), 'target': task.get('target'),
              'generator_policy_sha256': task.get('generator_policy_sha256')}
    host = _verify_signed_event(
        manifest_path.with_name(manifest_path.name + '.host-proof.json'),
        kind='host_generation', public_key_path=host_public,
        task_created_at=task_created_at, now=now)
    if set(host) != set(common) | {'candidates', 'issuer', 'issued_at', 'expires_at'}:
        raise ValueError('image_trust_host_proof_shape_invalid')
    if (any(host[key] != value for key, value in common.items())
            or host['candidates'] != candidates
            or host['issuer'] != 'verified_chatgpt_host_event'):
        raise ValueError('image_trust_host_generation_not_bound')
    approval = _verify_signed_event(
        review_path.with_name(review_path.name + '.review-proof.json'),
        kind='review_selection', public_key_path=review_public,
        task_created_at=task_created_at, now=now)
    expected = {
        **common, 'manifest_sha256': _sha(manifest_path),
        'review_receipt_sha256': _sha(review_path),
        'source_sha256': source_sha256, 'staged_sha256': staged_sha256,
        'selected_candidate': selected_candidate, 'selection_mode': selection_mode,
        'review_actor': review.get('review_actor'),
    }
    if set(approval) != set(expected) | {'issuer', 'issued_at', 'expires_at'}:
        raise ValueError('image_trust_review_proof_shape_invalid')
    if (any(approval[key] != value for key, value in expected.items())
            or approval['issuer'] != 'independent_reviewer_authority'
            or _time(approval['issued_at']) < _time(host['issued_at'])):
        raise ValueError('image_trust_review_or_selection_not_authenticated')
    return {'status': 'host_verified_and_review_authorized',
            'task_id': common['task_id'], 'manifest_sha256': expected['manifest_sha256'],
            'review_sha256': expected['review_receipt_sha256'],
            'host_proof_sha256': _sha(manifest_path.with_name(manifest_path.name + '.host-proof.json')),
            'review_proof_sha256': _sha(review_path.with_name(review_path.name + '.review-proof.json'))}
