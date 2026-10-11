"""Pure, read-only evidence policy for ambiguous non-idempotent media imports.

SHA equality describes bytes, not which WP-CLI process created a row. A pending
attempt record is NOT a successful import/ownership receipt. Only the normal
image_outcome path, with an exact attachment ID and guarded WordPress readback,
may continue to write a thumbnail. This module never contacts WordPress.
"""

from __future__ import annotations

import re


def assess_pending_import(attempt: dict, *, image_sha256: str,
                          expected_thumbnail_id: int | None) -> dict:
    """Validate a persisted attempt; report why automation must remain fenced."""
    if not isinstance(attempt, dict) or attempt.get("started") is not True:
        raise ValueError("featured_image_import_receipt_missing")
    if (not isinstance(image_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", image_sha256)
            or attempt.get("image_sha256") != image_sha256
            or attempt.get("expected_thumbnail_id") != expected_thumbnail_id):
        raise ValueError("resume_image_import_artifact_conflict")
    # The lock token alone is not proof of ownership of any attachment, and
    # disappearance of the remote process is not established by the SHA scan.
    fenced = attempt.get("import_fence_started") is True or bool(attempt.get("lock_token"))
    return {
        "status": "import_process_unknown" if fenced else "import_ownership_unverified",
        "attachment_id_verified": False,
        "import_termination_verified": False,
        "automatic_retry": False,
        "write_authorized": False,
        "next_action": "verify_original_process_liveness_and_durable_attachment_id_receipt",
    }


def hold_pending_import(attempt: dict, *, image_sha256: str,
                        expected_thumbnail_id: int | None) -> None:
    """Fail closed before ANY SHA-result could be treated as owned media."""
    assessment = assess_pending_import(
        attempt, image_sha256=image_sha256,
        expected_thumbnail_id=expected_thumbnail_id)
    if assessment["status"] == "import_process_unknown":
        raise ValueError("featured_image_import_process_termination_unknown")
    raise ValueError("featured_image_import_ownership_unverified")


def classify_sha_candidates(observed_ids: list[int], *,
                            preexisting_ids: list[int] | None = None) -> dict:
    """Offer operator hints, never automatically adopt a candidate by SHA."""
    for name, ids in (("observed", observed_ids), ("preexisting", preexisting_ids)):
        if ids is not None and (not isinstance(ids, list)
                or any(type(i) is not int or i <= 0 for i in ids)
                or len(ids) != len(set(ids))):
            raise ValueError("invalid_featured_image_" + name + "_attachment_ids")
    candidate_ids = [i for i in observed_ids if preexisting_ids is None or i not in preexisting_ids]
    if not candidate_ids:
        status = "no_sha_matching_attachment_outcome_unknown"
    elif len(candidate_ids) == 1:
        status = "single_sha_matching_attachment_unconfirmed"
    else:
        status = "multiple_sha_matching_attachments_ambiguous"
    return {
        "status": status,
        "candidate_attachment_ids": candidate_ids,
        "ownership_verified": False,
        "import_termination_verified": False,
        "automatic_retry": False,
        "write_authorized": False,
    }
