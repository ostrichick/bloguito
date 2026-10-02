"""Short-lived receipts for unchanged official-source rechecks.

Receipts are deliberately short lived. They exist to avoid paying for the same
network recheck repeatedly during retries/resume of one editorial task, not to
replace the project's normal source freshness policy. Sources that contain an
explicit current-state marker bypass this cache and are fetched live.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

from agents.editorial import ROOT, fresh, policy
from agents.temporal_validation import KST
from agents.workflow_metrics import increment, timed


SOURCE_RECEIPT_SCHEMA = 1
DEFAULT_RECEIPT_TTL_MINUTES = 15
MAX_RECEIPT_TTL_MINUTES = 30
SOURCE_IDENTITY_FIELDS = ("url", "source_type", "sha256", "title")


def _receipt_ttl_minutes() -> int:
    raw = os.getenv("EDITORIAL_SOURCE_RECEIPT_TTL_MINUTES", str(DEFAULT_RECEIPT_TTL_MINUTES))
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = DEFAULT_RECEIPT_TTL_MINUTES
    return max(1, min(value, MAX_RECEIPT_TTL_MINUTES))


def _fetcher_fingerprint(root: Path | None = None) -> str:
    root = Path(root or ROOT)
    source = root / "agents" / "editorial_writer.py"
    return hashlib.sha256(source.read_bytes()).hexdigest()


def _receipt_path(url: str, root: Path | None = None) -> Path:
    root = Path(root or ROOT)
    key = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return root / "data" / "editorial_runs" / "source-validation" / f"{key}.json"


def source_requires_live_refresh(source: dict) -> bool:
    """Current-state evidence is never satisfied by a short-lived receipt."""
    text = source.get("text", "") if isinstance(source, dict) else ""
    patterns = (
        r"(?:예매|판매|신청|접수)\s*상태\s*:\s*(?:예매중|판매중|신청중|접수중|가능)",
        r"(?:현재\s*)?(?:예매|판매|신청|접수)\s*(?:중|가능)",
        r"(?:잔여\s*좌석|남은\s*좌석|재고\s*(?:있음|없음)|매진|품절)",
    )
    return any(re.search(pattern, text) for pattern in patterns)


def revision_source_recheck_plan(old_bundle: dict, new_bundle: dict, *, now: datetime | None = None) -> dict:
    """Choose new/changed/stale/live sources for a Standard edit network recheck."""
    now = now or datetime.now(KST)
    old_sources = {
        source.get("id"): source
        for source in (old_bundle or {}).get("sources", [])
        if isinstance(source, dict) and isinstance(source.get("id"), str)
    }
    refresh_sources = []
    reused_source_ids = []
    max_age = policy()["source_max_age_hours"]
    for source in (new_bundle or {}).get("sources", []):
        if not isinstance(source, dict) or not isinstance(source.get("id"), str):
            raise ValueError("reviewed_revision_source_ids_required")
        prior = old_sources.get(source["id"])
        changed = (
            prior is None
            or any(prior.get(field) != source.get(field) for field in SOURCE_IDENTITY_FIELDS)
        )
        stale = not fresh(source.get("fetched_at"), now, max_age)
        live_state = source_requires_live_refresh(source)
        if changed or stale or live_state:
            refresh_sources.append(source)
        else:
            reused_source_ids.append(source["id"])
    return {
        "refresh_sources": refresh_sources,
        "reused_source_ids": reused_source_ids,
    }


def verify_revision_sources(old_bundle: dict, new_bundle: dict, *, now: datetime | None = None) -> dict:
    """Verify only source snapshots affected by a Standard edit or freshness/live-state rules."""
    plan = revision_source_recheck_plan(old_bundle, new_bundle, now=now)
    refresh_sources = plan["refresh_sources"]
    if not refresh_sources:
        return {
            "reused_source_ids": plan["reused_source_ids"],
            "refetched_source_ids": [],
            "all_unchanged": True,
        }
    refresh_ids = {source["id"] for source in refresh_sources}
    checked = verify_sources_unchanged(
        new_bundle["brief"],
        refresh_sources,
        force_refresh_ids=refresh_ids,
        now=now,
    )
    return {
        "reused_source_ids": [
            *plan["reused_source_ids"],
            *checked.get("reused_source_ids", []),
        ],
        "refetched_source_ids": checked.get("refetched_source_ids", []),
        "all_unchanged": checked.get("all_unchanged") is True,
    }


def _load_reusable_receipt(source: dict, *, root: Path | None = None,
                           now: datetime | None = None) -> dict | None:
    if source_requires_live_refresh(source):
        return None
    path = _receipt_path(source.get("url", ""), root)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        checked = datetime.fromisoformat(payload["checked_at"])
    except (OSError, ValueError, TypeError, KeyError):
        return None
    if checked.tzinfo is None:
        return None
    now = (now or datetime.now(KST)).astimezone(KST)
    age = now - checked.astimezone(KST)
    return payload if (
        payload.get("schema") == SOURCE_RECEIPT_SCHEMA
        and payload.get("url") == source.get("url")
        and payload.get("source_id") == source.get("id")
        and payload.get("observed_sha256") == source.get("sha256")
        and payload.get("fetcher_digest") == _fetcher_fingerprint(root)
        and timedelta(0) <= age <= timedelta(minutes=_receipt_ttl_minutes())
    ) else None


def _store_receipt(source: dict, *, root: Path | None = None,
                   now: datetime | None = None) -> Path:
    target = _receipt_path(source["url"], root)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": SOURCE_RECEIPT_SCHEMA,
        "url": source["url"],
        "source_id": source.get("id"),
        "observed_sha256": source["sha256"],
        "fetcher_digest": _fetcher_fingerprint(root),
        "checked_at": (now or datetime.now(KST)).astimezone(KST).isoformat(),
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
    return target


def verify_sources_unchanged(
    brief: dict,
    expected_sources: list[dict],
    *,
    force_refresh_ids: set[str] | None = None,
    root: Path | None = None,
    now: datetime | None = None,
    fetch_subset: Callable | None = None,
) -> dict:
    """Verify source SHA values, re-fetching only sources without a usable receipt."""
    force_refresh_ids = set(force_refresh_ids or ())
    expected = {source.get("id"): source for source in expected_sources}
    if (not expected_sources or len(expected) != len(expected_sources)
            or None in expected or any(not source.get("url") or not source.get("sha256")
                                       for source in expected_sources)):
        raise ValueError("source_validation_receipt_requires_reviewed_sources")

    reusable = []
    refresh = []
    for source_id, source in expected.items():
        receipt = None if source_id in force_refresh_ids else _load_reusable_receipt(
            source, root=root, now=now)
        if receipt is not None:
            reusable.append(source_id)
        else:
            refresh.append(source_id)

    if refresh:
        if fetch_subset is None:
            from agents.editorial_writer import fetch_sources_subset
            fetch_subset = fetch_sources_subset
        with timed("source_recheck"):
            fresh_rows = fetch_subset(brief, expected_sources, refresh)
        observed = {source["id"]: source for source in fresh_rows}
        if set(observed) != set(refresh):
            raise ValueError("source_subset_recheck_incomplete")
        for source_id in refresh:
            fresh = observed[source_id]
            if fresh.get("url") != expected[source_id].get("url") or fresh.get("sha256") != expected[source_id].get("sha256"):
                raise ValueError("official_sources_changed_since_review")
            _store_receipt(fresh, root=root, now=now)
        increment("source_receipt_refetch", len(refresh))
    if reusable:
        increment("source_receipt_hit", len(reusable))
    return {
        "reused_source_ids": reusable,
        "refetched_source_ids": refresh,
        "all_unchanged": True,
    }
