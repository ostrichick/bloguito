"""R1 provider-signal probe for a separately trusted origin evidence issuer.

This is a *read-only provider verification* helper. It cannot attest a task,
user identity or actual ChatGPT invocation, and deliberately never signs an
event. Run inside the independent, credential-controlled issuer boundary.
Required SDK: openai>=2.52.0. Never upload candidate originals without
authorization to send those files to OpenAI's Content Provenance API.
"""

from __future__ import annotations

import hashlib
from pathlib import Path


MAX_IMAGE_BYTES = 20 * 1024 * 1024
MIMES = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
         '.webp': 'image/webp'}


def classify_provenance_results(result: dict) -> dict:
    """Require a trusted OpenAI-issued C2PA generation credential.

    SynthID is useful contextual signal but doesn't bind prompt/user/task; a
    generated-image attestation must still be issued independently.
    """
    if (not isinstance(result, dict)
            or result.get('object') != 'content_provenance_check'
            or type(result.get('created_at')) is not int
            or result['created_at'] <= 0
            or not isinstance(result.get('results'), list)):
        raise ValueError('provider_provenance_response_invalid')
    matched = [entry for entry in result['results']
               if isinstance(entry, dict) and entry.get('type') == 'c2pa'
               and entry.get('outcome') == 'detected'
               and entry.get('validation_state') in {'trusted', 'valid'}
               and entry.get('issuer') == 'OpenAI OpCo, LLC'
               and isinstance(entry.get('model'), str)
               and entry.get('model')]
    return {'status': 'provider_signal_detected' if matched else 'held_provenance_unverifiable',
            'trusted_openai_c2pa': bool(matched),
            'provider_check_created_at': result['created_at']}


def probe_original(image: Path, *, client=None) -> dict:
    """Perform official verification and bind its result to *these bytes*.

    The result remains an unsigned local observation. A privileged issuer must
    independently bind this original SHA to a registered task and sign evidence.
    """
    image = Path(image).resolve(strict=True)
    mime = MIMES.get(image.suffix.lower())
    if mime is None or not image.is_file() or not 0 < image.stat().st_size <= MAX_IMAGE_BYTES:
        raise ValueError('provider_provenance_original_unsupported')
    original_sha = hashlib.sha256(image.read_bytes()).hexdigest()
    if client is None:
        try:
            from openai import OpenAI
            client = OpenAI()
        except (ImportError, ValueError) as exc:
            raise ValueError('held_provenance_unverifiable:provider_client_unavailable') from exc
    try:
        with image.open('rb') as handle:
            result = client.content_provenance_checks.create(file=(image.name, handle, mime))
        payload = result.model_dump() if hasattr(result, 'model_dump') else result
    except Exception as exc:
        raise ValueError('held_provenance_unverifiable:provider_check_failed') from exc
    if hashlib.sha256(image.read_bytes()).hexdigest() != original_sha:
        raise ValueError('provider_provenance_original_changed_during_check')
    return {'source_sha256': original_sha, **classify_provenance_results(payload)}
