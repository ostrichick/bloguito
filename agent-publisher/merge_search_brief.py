#!/usr/bin/env python3
"""Safely merge one reviewed search brief by ID without replacing the data file wholesale."""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from urllib.parse import urlparse

from agents.editorial import topic_reasons
from agents.growth_analysis import load_policy
from agents.search_intent import GROWTH_POLICY, SearchBriefError, validate_search_brief_rows
from agents.temporal_validation import KST
from agents.topic_scoring import brief_value_gate_reasons


APP_ROOT = Path(__file__).resolve().parent
DEFAULT_TARGET = APP_ROOT / "data" / "search_briefs.json"
DEFAULT_BACKUP_ROOT = APP_ROOT / "backups"


class SearchBriefMergeError(ValueError):
    """Fail-closed search-brief mutation error."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_json(path: Path, code: str):
    if path.is_symlink():
        raise SearchBriefMergeError(code + "_symlink_not_allowed")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise SearchBriefMergeError(code) from None


def validate_incoming_brief(brief: dict, *, today: date) -> None:
    """Validate the reviewed row independent of inventory and private score state."""
    if not isinstance(brief, dict):
        raise SearchBriefMergeError("incoming_brief_invalid")
    validate_search_brief_rows([brief])
    required = (
        "category_key", "entity", "primary_keyword", "question", "angle",
        "required_title_terms", "official_urls", "serp_urls", "queries",
        "reviewed_at", "review_until", "content_type", "reader_questions",
        "intent_type", "ai_answerability", "added_value",
    )
    if brief.get("approved") is not True or any(not brief.get(key) for key in required):
        raise SearchBriefMergeError("incoming_brief_incomplete")
    if brief["entity"] not in brief["primary_keyword"]:
        raise SearchBriefMergeError("incoming_brief_entity_keyword_mismatch")
    for key in ("required_title_terms", "official_urls", "serp_urls", "queries", "reader_questions"):
        if not isinstance(brief.get(key), list) or not brief[key]:
            raise SearchBriefMergeError("incoming_brief_incomplete")
    if any(not isinstance(value, str) or not value.strip() for value in brief["required_title_terms"]):
        raise SearchBriefMergeError("incoming_brief_required_title_terms_invalid")
    if any(not isinstance(value, str) or not value.strip() for value in brief["queries"]):
        raise SearchBriefMergeError("incoming_brief_queries_invalid")
    for key in ("official_urls", "serp_urls"):
        if any(
            not isinstance(url, str)
            or urlparse(url).scheme != "https"
            or not urlparse(url).hostname
            or urlparse(url).username
            for url in brief[key]
        ):
            raise SearchBriefMergeError("incoming_brief_url_invalid")
    reasons = topic_reasons(brief, today)
    if reasons:
        raise SearchBriefMergeError("incoming_brief_topic_reasons:" + ",".join(sorted(set(reasons))))
    policy = load_policy(GROWTH_POLICY)
    value_reasons = brief_value_gate_reasons(brief, policy)
    if value_reasons:
        raise SearchBriefMergeError(
            "incoming_brief_value_reasons:" + ",".join(sorted(set(value_reasons))))


def merge_search_brief(
    target: Path,
    brief: dict,
    *,
    today: date,
    backup_root: Path,
    expected_sha256: str | None = None,
    replace_existing: bool = False,
    confirm: bool = False,
) -> dict:
    """Append or explicitly replace one ID while preserving every non-target row byte-semantically."""
    if target.is_symlink() or backup_root.is_symlink():
        raise SearchBriefMergeError("search_brief_path_symlink_not_allowed")
    target = target.resolve()
    backup_root = backup_root.resolve()
    try:
        original = target.read_bytes()
        mode = target.stat().st_mode & 0o777
    except OSError:
        raise SearchBriefMergeError("search_briefs_unreadable") from None
    pre_sha = _sha256(original)
    if expected_sha256 is not None and expected_sha256 != pre_sha:
        raise SearchBriefMergeError("search_briefs_expected_sha_mismatch")
    try:
        rows = validate_search_brief_rows(json.loads(original.decode("utf-8")))
    except (UnicodeDecodeError, ValueError, TypeError, SearchBriefError):
        raise SearchBriefMergeError("search_briefs_invalid") from None
    validate_incoming_brief(brief, today=today)

    brief_id = brief["id"]
    matches = [index for index, row in enumerate(rows) if row["id"] == brief_id]
    if matches:
        current = rows[matches[0]]
        if current == brief:
            return {
                "status": "no_change",
                "target_id": brief_id,
                "pre_sha256": pre_sha,
                "post_sha256": pre_sha,
                "backup": None,
            }
        if not replace_existing:
            raise SearchBriefMergeError("search_brief_id_already_exists")
        updated = list(rows)
        updated[matches[0]] = brief
        action = "replace"
    else:
        updated = list(rows) + [brief]
        action = "append"
    validate_search_brief_rows(updated)
    if not confirm:
        return {
            "status": "dry_run",
            "action": action,
            "target_id": brief_id,
            "pre_sha256": pre_sha,
            "count_before": len(rows),
            "count_after": len(updated),
        }

    # CAS immediately before mutation so a concurrent operator cannot be overwritten.
    if _sha256(target.read_bytes()) != pre_sha:
        raise SearchBriefMergeError("search_briefs_changed_during_merge")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_dir = backup_root / ("search-briefs-" + stamp)
    backup_dir.mkdir(parents=True, mode=0o700)
    backup_file = backup_dir / "search_briefs.json"
    backup_file.write_bytes(original)
    if os.name == "posix":
        backup_file.chmod(0o600)
    manifest = {
        "schema_version": 1,
        "target": str(target),
        "target_id": brief_id,
        "action": action,
        "pre_sha256": pre_sha,
        "count_before": len(rows),
    }
    manifest_path = backup_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if os.name == "posix":
        manifest_path.chmod(0o600)

    encoded = (json.dumps(updated, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    temp = None
    try:
        with tempfile.NamedTemporaryFile(
            "wb", dir=target.parent, prefix=".search-brief-", suffix=".tmp", delete=False
        ) as handle:
            temp = Path(handle.name)
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        temp.chmod(mode)
        os.replace(temp, target)
        readback = validate_search_brief_rows(json.loads(target.read_text(encoding="utf-8")))
        before_map = {row["id"]: row for row in rows if row["id"] != brief_id}
        after_map = {row["id"]: row for row in readback if row["id"] != brief_id}
        target_rows = [row for row in readback if row["id"] == brief_id]
        expected_count = len(rows) if action == "replace" else len(rows) + 1
        if (
            len(readback) != expected_count
            or before_map != after_map
            or target_rows != [brief]
        ):
            raise SearchBriefMergeError("search_brief_readback_mismatch")
        post_sha = _sha256(target.read_bytes())
        manifest.update({"post_sha256": post_sha, "count_after": len(readback)})
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if os.name == "posix":
            manifest_path.chmod(0o600)
        return {
            "status": "merged",
            "action": action,
            "target_id": brief_id,
            "pre_sha256": pre_sha,
            "post_sha256": post_sha,
            "backup": str(backup_dir),
            "count_before": len(rows),
            "count_after": len(readback),
        }
    except Exception:
        shutil.copyfile(backup_file, target)
        target.chmod(mode)
        if target.read_bytes() != original:
            raise SearchBriefMergeError("search_brief_rollback_failed") from None
        raise
    finally:
        if temp is not None and temp.exists():
            temp.unlink()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("brief", type=Path, help="JSON file containing exactly one reviewed brief object")
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    parser.add_argument("--backup-root", type=Path, default=DEFAULT_BACKUP_ROOT)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--replace-existing", action="store_true")
    parser.add_argument("--confirm-merge", action="store_true")
    parser.add_argument("--today", help="YYYY-MM-DD; defaults to Korea local date")
    args = parser.parse_args(argv)
    try:
        today = date.fromisoformat(args.today) if args.today else datetime.now(KST).date()
        brief = _load_json(args.brief, "incoming_brief_unreadable")
        result = merge_search_brief(
            args.target,
            brief,
            today=today,
            backup_root=args.backup_root,
            expected_sha256=args.expected_sha256,
            replace_existing=args.replace_existing,
            confirm=args.confirm_merge,
        )
    except (ValueError, OSError) as exc:
        print("search_brief_merge_failed:" + (str(exc) or "unknown_error"))
        return 1
    print("search_brief_merge_ok " + json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
