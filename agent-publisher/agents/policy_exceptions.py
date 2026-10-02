"""Strict loader for narrowly scoped editorial policy exceptions.

Post-specific exceptions live outside the global editorial policy so unrelated
posts do not inherit or fingerprint them. Registry records retain their exact
legacy rule fields plus lifecycle metadata used to fail closed.
"""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_DIR = ROOT / "data" / "policy_exceptions"
REGISTRY_FILES = {
    "dated_post": "dated-posts.json",
    "legacy_procedure": "legacy-procedures.json",
}
REGISTRY_SCHEMA_VERSION = 1


def _iso_date(value, field):
    if not isinstance(value, str):
        raise ValueError(f"invalid_policy_exception_{field}")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"invalid_policy_exception_{field}") from exc


def _validate_record(kind, key, record):
    if not isinstance(record, dict):
        raise ValueError("invalid_policy_exception_record")
    if record.get("id") != key:
        raise ValueError("policy_exception_id_mismatch")
    if record.get("status") not in {"active", "expired"}:
        raise ValueError("invalid_policy_exception_status")
    if type(record.get("existing_post_id")) is not int or record["existing_post_id"] <= 0:
        raise ValueError("invalid_policy_exception_post_id")
    if not isinstance(record.get("reason"), str) or not record["reason"].strip():
        raise ValueError("invalid_policy_exception_reason")
    _iso_date(record.get("approved_on"), "approved_on")
    expires_on = record.get("expires_on")
    termination = record.get("termination_condition")
    if kind == "dated_post":
        if expires_on is None:
            raise ValueError("dated_policy_exception_expiry_required")
        _iso_date(expires_on, "expires_on")
    elif not ((isinstance(expires_on, str) and expires_on)
              or (isinstance(termination, str) and termination.strip())):
        raise ValueError("policy_exception_termination_required")


def load_policy_exceptions(kind, *, root=None):
    """Load and validate one exception registry, failing closed on bad data."""
    if kind not in REGISTRY_FILES:
        raise ValueError("unknown_policy_exception_kind")
    base = Path(root) if root is not None else REGISTRY_DIR
    path = base / REGISTRY_FILES[kind]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as exc:
        raise ValueError("policy_exception_registry_unavailable") from exc
    if (not isinstance(payload, dict)
            or payload.get("schema_version") != REGISTRY_SCHEMA_VERSION
            or payload.get("kind") != kind
            or not isinstance(payload.get("exceptions"), dict)):
        raise ValueError("invalid_policy_exception_registry")
    records = payload["exceptions"]
    for key, record in records.items():
        if not isinstance(key, str) or not key:
            raise ValueError("invalid_policy_exception_id")
        _validate_record(kind, key, record)
    return deepcopy(records)


def get_policy_exception(kind, exception_id, *, on_date=None, root=None):
    """Return one currently applicable record, or None when it is out of scope.

    Dated records retain a static lifecycle status for audit history, while the
    supplied evaluation date determines whether the old exception was effective.
    This preserves historical regression fixtures without allowing an expired
    exception to apply during current validation.
    """
    if not isinstance(exception_id, str) or not exception_id:
        return None
    record = load_policy_exceptions(kind, root=root).get(exception_id)
    if record is None:
        return None
    if kind == "dated_post":
        effective_date = on_date or date.today()
        if not isinstance(effective_date, date):
            raise ValueError("invalid_policy_exception_evaluation_date")
        if effective_date > _iso_date(record["expires_on"], "expires_on"):
            return None
        return record
    return record if record.get("status") == "active" else None
