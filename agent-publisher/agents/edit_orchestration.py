"""Shared bookkeeping for reviewed post edit orchestration."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Callable

from agents.task_state import intent_sha256


def image_fingerprints(
    image_path: Path | None,
    alt_text: str | None,
) -> tuple[str | None, str | None]:
    if image_path is None:
        return None, None
    return (
        hashlib.sha256(image_path.read_bytes()).hexdigest(),
        hashlib.sha256((alt_text or "").encode("utf-8")).hexdigest(),
    )


def validate_resume_fingerprint(
    state: dict,
    *,
    expected_content_sha256: str,
    desired_content_sha256: str,
    edit_intent: str,
    current_policy_digest: str,
    expected_thumbnail_id: int | None,
    alt_text_sha256: str | None,
    image_sha256: str | None,
    candidate_content_digest: str | None = None,
) -> None:
    """Validate the fields shared by draft/public resumable edit state."""
    baseline = state.get("baseline", {})
    state_policy = (
        (state.get("reuse") or {}).get("fingerprint_after", {}).get("policy_digest")
    )
    conflict = (
        baseline.get("expected_content_sha256") != expected_content_sha256
        or baseline.get("desired_content_sha256") != desired_content_sha256
        or state.get("edit_intent_sha256") != intent_sha256(edit_intent)
        or state_policy != current_policy_digest
        or baseline.get("expected_thumbnail_id") != expected_thumbnail_id
        or baseline.get("alt_text_sha256") != alt_text_sha256
    )
    if candidate_content_digest is not None:
        conflict = (
            conflict
            or baseline.get("candidate_content_digest") != candidate_content_digest
        )
    if conflict:
        raise ValueError("resume_state_fingerprint_conflict")
    if image_sha256 is not None:
        artifact = (state.get("artifacts") or {}).get("image_path") or {}
        if artifact.get("sha256") != image_sha256:
            raise ValueError("resume_image_artifact_conflict")


def record_route_profile_metrics(
    decision: dict,
    increment_metric: Callable[[str], None],
) -> None:
    increment_metric(
        "edit_route_fast" if decision["route"] == "fast" else "edit_route_standard"
    )
    profile = (decision.get("validation_plan") or {}).get("profile")
    if profile:
        increment_metric("validation_profile_" + profile.replace("-", "_"))


def run_combined_image_phase(
    post_id: int,
    *,
    image_path: Path | None,
    desired_content_sha256: str,
    expected_thumbnail_id: int | None,
    alt_text: str | None,
    resume: bool,
    state: dict | None,
    update_state: Callable[..., object],
    reconcile_image: Callable[..., dict],
    recover_imported_image: Callable[..., dict | None],
    replace_image: Callable[..., dict],
    approval_kind: str | None = None,
    approval_evidence_sha256: str | None = None,
) -> dict | None:
    """Run the identical image continuation/checkpoint phase after content save."""
    if image_path is None:
        if approval_kind is not None or approval_evidence_sha256 is not None:
            raise ValueError("image_approval_requires_image")
        update_state(post_id, completed=["image_saved"])
        return None
    if (approval_kind is None) != (approval_evidence_sha256 is None):
        raise ValueError("image_approval_pair_required")

    update_state(post_id, completed=["image_validated"])
    checkpoint = (
        ((state or {}).get("checkpoints") or {}).get("image_outcome")
        if resume else None
    )
    if checkpoint and checkpoint.get("attachment_id"):
        image_result = reconcile_image(post_id, checkpoint, alt_text)
        if approval_kind is not None and not image_result.get("publish_attestation"):
            raise ValueError("recovered_image_requires_separate_publish_attestation")
    else:
        import_attempt = (
            ((state or {}).get("checkpoints") or {}).get("image_import_attempt")
            if resume else None
        )
        if import_attempt and import_attempt.get("started"):
            # The pending remote import must belong to the exact image and
            # thumbnail baseline being resumed. Do not reconcile a stale
            # attempt against another selected file.
            if (
                import_attempt.get("image_sha256") != hashlib.sha256(image_path.read_bytes()).hexdigest()
                or import_attempt.get("expected_thumbnail_id") != expected_thumbnail_id
            ):
                raise ValueError("resume_image_import_artifact_conflict")
            image_result = recover_imported_image(
                post_id,
                image_sha256=import_attempt.get("image_sha256"),
                expected_content_sha256=desired_content_sha256,
                expected_thumbnail_id=expected_thumbnail_id,
                alt_text=alt_text,
                preexisting_attachment_ids=import_attempt.get("preexisting_attachment_ids"),
                lock_token=import_attempt.get("lock_token"),
            )
            if image_result is None:
                raise ValueError("featured_image_import_outcome_ambiguous")
            if approval_kind is not None and not image_result.get("publish_attestation"):
                raise ValueError("recovered_image_requires_separate_publish_attestation")
            update_state(post_id, checkpoints={"image_outcome": image_result})
            update_state(
                post_id,
                completed=["image_saved"],
                result={"image_phase": image_result},
            )
            return image_result

        def image_checkpoint(payload):
            update_state(post_id, checkpoints={"image_outcome": payload})

        def import_attempt_checkpoint(payload):
            update_state(post_id, checkpoints={"image_import_attempt": payload})

        image_result = replace_image(
            post_id,
            image_path,
            desired_content_sha256,
            expected_thumbnail_id=expected_thumbnail_id,
            alt_text=alt_text,
            confirmed=True,
            manage_task_state=False,
            outcome_callback=image_checkpoint,
            import_attempt_callback=import_attempt_checkpoint,
            approval_kind=approval_kind,
            approval_evidence_sha256=approval_evidence_sha256,
        )
    update_state(
        post_id,
        completed=["image_saved"],
        result={"image_phase": image_result},
    )
    return image_result
