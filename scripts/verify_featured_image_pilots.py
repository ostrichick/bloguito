"""R5 read-only pilot readiness check; never certifies WordPress acceptance offline.

Usage: python scripts/verify_featured_image_pilots.py --manifest pilot-plan.json

The plan contains *expectations*, not WordPress observations. R1/R2 evidence is
verified using the production trust root only. Until a separate, authenticated
read-only WordPress endpoint can attest actual writes, CAS and readback, the
result is always NO-GO. No WordPress operations or signing happen here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import unicodedata
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agent-publisher"))

from agents.featured_image_trust import verify_image_upload_trust  # noqa: E402

SHA256 = re.compile(r"[0-9a-f]{64}\Z")
TOPIC_PLACEHOLDER = re.compile(
    r"(?:topic|pilot|test|sample|example|dummy|placeholder|주제|시범|테스트|예시|샘플)"
    r"(?:\s*[-#\d]+)?\Z", re.IGNORECASE)
PILOT_FIELDS = frozenset({
    "topic", "post_id", "task", "task_created_at", "manifest_path", "review_path",
    "source_path", "staged_path", "selected_candidate", "selection_mode",
    "wordpress_expectation",
})
WP_FIELDS = frozenset({
    "content_sha256", "previous_thumbnail_id", "attachment_id", "alt_text",
    "attachment_url", "post_status", "post_title", "post_slug", "post_excerpt",
})


def _is_positive_int(value: object) -> bool:
    return type(value) is int and value > 0


def _valid_sha(value: object) -> bool:
    return isinstance(value, str) and SHA256.fullmatch(value) is not None


def _path(anchor: Path, value: object) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("pilot_file_path_invalid")
    value_path = Path(value)
    return (value_path if value_path.is_absolute() else anchor / value_path).resolve()


def _file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _production_root_supported() -> bool:
    # The verifier protects /etc/bloguito/image-trust with Unix ownership/mode
    # checks. Windows cannot enforce that production Unix trust-root contract.
    return os.name == "posix"


def _topic(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("pilot_topic_missing_or_placeholder")
    topic = " ".join(unicodedata.normalize("NFKC", value).strip().split())
    if (len(topic) < 4 or len(topic) > 160 or TOPIC_PLACEHOLDER.fullmatch(topic)
            or not any(character.isalpha() for character in topic)):
        raise ValueError("pilot_topic_missing_or_placeholder")
    return topic.casefold()


def _validate_wordpress_expectation(value: object) -> None:
    """Check intended CAS/readback fields, never treat a JSON claim as proof."""
    if not isinstance(value, dict) or set(value) != WP_FIELDS:
        raise ValueError("pilot_wordpress_expectation_invalid")
    if (not _valid_sha(value["content_sha256"])
            or (value["previous_thumbnail_id"] is not None
                and not _is_positive_int(value["previous_thumbnail_id"]))
            or not _is_positive_int(value["attachment_id"])
            or value["previous_thumbnail_id"] == value["attachment_id"]
            or not isinstance(value["alt_text"], str) or not value["alt_text"].strip()
            or value["post_status"] != "draft"
            or any(not isinstance(value[field], str) or not value[field].strip()
                   for field in ("post_title", "post_slug"))
            or not isinstance(value["post_excerpt"], str)):
        raise ValueError("pilot_wordpress_expectation_invalid")
    url = value["attachment_url"]
    if not isinstance(url, str):
        raise ValueError("pilot_wordpress_expectation_invalid")
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username is not None
            or parsed.password is not None):
        raise ValueError("pilot_wordpress_expectation_invalid")


def evaluate(manifest_path: Path) -> dict:
    """Verify local readiness only. An untrusted plan cannot attest live WP state."""
    result = {
        "status": "NO-GO", "stage": "R5_offline_readiness",
        "planned_pilot_count": 0, "verified_pilot_count": 0,
        "trusted_provenance_count": 0, "wordpress_verified_count": 0,
        "pilots": [], "blockers": [], "checker_wordpress_mutations": 0,
    }
    try:
        manifest_path = Path(manifest_path).resolve()
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        result["blockers"].append("pilot_manifest_missing_or_invalid")
        return result
    if not isinstance(data, dict) or set(data) != {"version", "pilots"} or data["version"] != 1:
        result["blockers"].append("pilot_manifest_schema_invalid")
        return result
    pilots = data["pilots"]
    if not isinstance(pilots, list) or len(pilots) != 3:
        result["blockers"].append("exactly_three_pilots_required")
        return result
    result["planned_pilot_count"] = 3
    seen_topics: set[str] = set()
    seen_posts: set[int] = set()
    seen_tasks: set[str] = set()
    seen_sources: set[str] = set()
    for index, pilot in enumerate(pilots, start=1):
        detail = {"pilot": index, "status": "NO-GO", "provenance_verified": False,
                  "wordpress_verified": False, "blockers": []}
        result["pilots"].append(detail)
        try:
            if not isinstance(pilot, dict) or set(pilot) != PILOT_FIELDS:
                raise ValueError("pilot_record_schema_invalid")
            topic = _topic(pilot["topic"])
            post_id = pilot["post_id"]
            if not _is_positive_int(post_id):
                raise ValueError("pilot_post_id_invalid")
            task = pilot["task"]
            if (not isinstance(task, dict)
                    or not isinstance(task.get("task_id"), str)
                    or not task["task_id"].strip()
                    or task.get("target") != {"post_id": post_id}
                    or not _is_positive_int(task.get("candidate_count"))
                    or not _valid_sha(task.get("generator_policy_sha256"))):
                raise ValueError("pilot_task_binding_invalid")
            task_id = task["task_id"]
            if (topic in seen_topics or post_id in seen_posts or task_id in seen_tasks):
                raise ValueError("pilots_not_three_distinct_topics_posts_and_tasks")
            seen_topics.add(topic)
            seen_posts.add(post_id)
            seen_tasks.add(task_id)
            _validate_wordpress_expectation(pilot["wordpress_expectation"])
            wp = pilot["wordpress_expectation"]
            if not isinstance(pilot["task_created_at"], str):
                raise ValueError("pilot_task_created_at_invalid")
            if type(pilot["selected_candidate"]) is not int or pilot["selected_candidate"] <= 0:
                raise ValueError("pilot_selection_invalid")
            if pilot["selection_mode"] not in ("user", "agent-delegated"):
                raise ValueError("pilot_selection_invalid")
            original = _path(manifest_path.parent, pilot["source_path"])
            staged = _path(manifest_path.parent, pilot["staged_path"])
            source_sha = _file_sha(original)
            staged_sha = _file_sha(staged)
            if source_sha in seen_sources:
                raise ValueError("pilot_original_image_reused")
            seen_sources.add(source_sha)
            if not _production_root_supported():
                raise ValueError("held_provenance_unverifiable:protected_production_trust_root_unavailable")
            trust = verify_image_upload_trust(
                task=task,
                manifest_path=_path(manifest_path.parent, pilot["manifest_path"]),
                review_path=_path(manifest_path.parent, pilot["review_path"]),
                source_sha256=source_sha,
                staged_sha256=staged_sha,
                selected_candidate=pilot["selected_candidate"],
                selection_mode=pilot["selection_mode"],
                task_created_at=pilot["task_created_at"],
            )
            if (not isinstance(trust, dict)
                    or trust.get("status") != "host_verified_and_review_authorized"
                    or trust.get("task_id") != task_id):
                raise ValueError("pilot_signed_trust_verification_incomplete")
            detail["provenance_verified"] = True
            result["trusted_provenance_count"] += 1
            detail["post_id"] = post_id
            detail["topic"] = pilot["topic"]
            detail["expected_attachment_id"] = wp["attachment_id"]
        except (OSError, UnicodeError, ValueError, TypeError, KeyError) as exc:
            # Never turn a failed trust/file check into a valid pilot.
            detail["blockers"].append(str(exc) if isinstance(exc, ValueError) else
                                      "pilot_required_evidence_unavailable")
        # The only existing readback helper uses privileged SSH + WP-CLI eval;
        # it is neither an independent endpoint nor evidence of CAS at commit.
        # Do not accept user-authored WordPress JSON, dry-run receipts, or mocks.
        detail["blockers"].append("independent_wordpress_cas_alt_readback_unavailable")
    result["blockers"] = sorted({reason for item in result["pilots"]
                                  for reason in item["blockers"]})
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True,
                        help="Local three-pilot plan. Contains expectations, never WP proof.")
    args = parser.parse_args(argv)
    result = evaluate(args.manifest)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 2  # Offline R5 cannot prove actual independent WordPress acceptance.


if __name__ == "__main__":
    raise SystemExit(main())
