"""Content-addressed semantic-review artifacts.

The cache never turns an old review into a current one. A cached review is reused
only when the exact review body, editorial policy/instructions and reviewer
contract are unchanged, and the review timestamp is still inside the normal
``review_max_age_hours`` window.
"""

from __future__ import annotations

import json
import os
import hashlib
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from agents.editorial import ROOT, digest, fresh, policy, policy_fingerprint
from agents.temporal_validation import KST
from agents.workflow_metrics import increment


REVIEW_CACHE_SCHEMA = 1
REVIEW_CONTRACT_VERSION = "semantic-review-v1"


def review_body(bundle: dict) -> dict:
    return {
        key: deepcopy(bundle[key])
        for key in ("brief", "sources", "plan", "temporal_source")
        if key in bundle
    }


def reviewer_contract_digest() -> str:
    writer = ROOT / "agents" / "editorial_writer.py"
    code_digest = hashlib.sha256(writer.read_bytes()).hexdigest()
    return digest({
        "version": REVIEW_CONTRACT_VERSION,
        "editorial_writer_sha256": code_digest,
    })


def review_cache_key(bundle: dict) -> str:
    return digest({
        "body_digest": digest(review_body(bundle)),
        "policy_digest": policy_fingerprint(bundle),
        "review_contract_digest": reviewer_contract_digest(),
    })


def review_cache_path(bundle: dict, root: Path | None = None) -> Path:
    root = Path(root or ROOT)
    return root / "data" / "editorial_runs" / "review-cache" / f"{review_cache_key(bundle)}.json"


def _review_shape_valid(review: Any) -> bool:
    if not isinstance(review, dict):
        return False
    if not isinstance(review.get("checks"), dict) or not isinstance(review.get("issues"), list):
        return False
    return all(key in review for key in ("digest", "policy_digest", "checked_at"))


def load_cached_review(
    bundle: dict,
    *,
    root: Path | None = None,
    now: datetime | None = None,
) -> dict | None:
    """Return an exact, still-current cached review or ``None``.

    Both successful and blocking semantic reviews are cacheable. Reusing a
    blocking result is safe because the normal deterministic validator will
    continue to reject its false checks/issues; the cache cannot convert it into
    approval.
    """
    path = review_cache_path(bundle, root)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        increment("review_cache_miss")
        return None
    if not isinstance(payload, dict):
        increment("review_cache_miss")
        return None
    body = review_body(bundle)
    review = payload.get("review")
    current_policy = policy_fingerprint(bundle)
    now = now or datetime.now(KST)
    valid = (
        payload.get("schema") == REVIEW_CACHE_SCHEMA
        and payload.get("cache_key") == review_cache_key(bundle)
        and payload.get("body_digest") == digest(body)
        and payload.get("policy_digest") == current_policy
        and payload.get("review_contract_digest") == reviewer_contract_digest()
        and _review_shape_valid(review)
        and review.get("digest") == digest(body)
        and review.get("policy_digest") == current_policy
        and fresh(review.get("checked_at"), now, policy()["review_max_age_hours"])
    )
    if not valid:
        increment("review_cache_miss")
        return None
    increment("review_cache_hit")
    return deepcopy(review)


def store_cached_review(bundle: dict, review: dict, *, root: Path | None = None) -> Path:
    if not _review_shape_valid(review):
        raise ValueError("invalid_semantic_review_cache_record")
    body = review_body(bundle)
    current_policy = policy_fingerprint(bundle)
    if review.get("digest") != digest(body) or review.get("policy_digest") != current_policy:
        raise ValueError("semantic_review_cache_binding_mismatch")
    target = review_cache_path(bundle, root)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": REVIEW_CACHE_SCHEMA,
        "cache_key": review_cache_key(bundle),
        "body_digest": digest(body),
        "policy_digest": current_policy,
        "review_contract_digest": reviewer_contract_digest(),
        "review": deepcopy(review),
    }
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        os.chmod(temporary, 0o600)
    except OSError:
        pass
    temporary.replace(target)
    try:
        os.chmod(target, 0o600)
    except OSError:
        pass
    increment("review_cache_store")
    return target
