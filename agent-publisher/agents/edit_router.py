"""Automatic Fast/Standard routing for edits to reviewed WordPress drafts."""

from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path

from agents.editorial import render
from agents.editorial_draft_reviser import revise_reviewed_draft
from agents.edit_orchestration import (
    image_fingerprints,
    record_route_profile_metrics,
    run_combined_image_phase,
    validate_resume_fingerprint,
)
from agents.featured_image import reconcile_featured_image_outcome, replace_featured_image
from agents.fast_edit import (
    FULL_REVIEW_REQUIRED,
    build_fast_stored_bundle,
    fast_revise_reviewed_draft,
    prepare_fast_delta_review,
    validate_fast_edit,
    validate_prepared_delta_review,
)
from agents.change_classifier import classify_change
from agents.post_manifest_store import load_record, replace_record
from agents.task_state import (
    complete_task_state,
    completion_requirements_for_task,
    fail_task_state,
    load_task_state,
    start_task_state,
    update_task_state,
)
from agents.validation_reuse import assess_validation_reuse
from agents.validation_router import build_validation_plan
from agents.workflow_metrics import increment
from agents.wordpress_mutation import content_sha256, get_post
from config import DRAFTS_INDEX_FILE


def _load_tracked_bundle(post_id: int) -> dict:
    if not DRAFTS_INDEX_FILE.is_file():
        raise ValueError("reviewed_draft_index_missing")
    snapshot = load_record(DRAFTS_INDEX_FILE, post_id)
    if snapshot is None:
        raise ValueError("reviewed_draft_manifest_required")
    bundle = snapshot.record.get("fact_manifest", {}).get("editorial_bundle")
    if not isinstance(bundle, dict):
        raise ValueError("reviewed_draft_manifest_required")
    return bundle


def _reconcile_saved_draft_manifest(
    post_id: int,
    bundle: dict,
    expected_old_sha: str,
    desired_sha: str,
    *,
    route: str,
    fast_edit_review: dict | None,
    edit_intent: str,
) -> None:
    """Repair only the narrow WP-saved/local-index-not-yet-written crash window."""
    snapshot = load_record(DRAFTS_INDEX_FILE, post_id)
    if snapshot is None:
        raise ValueError("resume_manifest_not_updated")
    item = snapshot.record
    tracked = item.get("fact_manifest", {}).get("editorial_bundle")
    if not isinstance(tracked, dict):
        raise ValueError("resume_manifest_not_updated")
    tracked_sha = content_sha256(render(tracked["plan"], tracked["sources"]))
    if tracked_sha == desired_sha:
        return
    if tracked_sha != expected_old_sha:
        raise ValueError("resume_manifest_conflict")
    stored = bundle
    if route == "fast":
        report = validate_fast_edit(tracked, bundle)
        if not validate_prepared_delta_review(
                tracked, report, fast_edit_review, edit_intent):
            raise ValueError("resume_manifest_fast_review_mismatch")
        stored = build_fast_stored_bundle(tracked, bundle, fast_edit_review)
    updated = dict(item)
    updated.setdefault("fact_manifest", dict(item.get("fact_manifest", {})))["editorial_bundle"] = stored
    try:
        replace_record(snapshot, updated)
    except ValueError as exc:
        raise ValueError("resume_manifest_conflict") from exc


def classify_edit_route(
    post_id: int,
    bundle: dict,
    *,
    confirm_title_change: bool = False,
    image_path: Path | str | None = None,
    resume: bool = False,
    expected_content_sha256: str | None = None,
) -> dict:
    old_bundle = _load_tracked_bundle(post_id)
    reuse = assess_validation_reuse(old_bundle, bundle)
    fast_report = validate_fast_edit(old_bundle, bundle)
    classification = classify_change(
        old_bundle,
        bundle,
        image_changed=image_path is not None,
        target_status="draft",
        resume=resume,
        fast_report=fast_report,
        force_standard=confirm_title_change,
    )
    reasons = list(classification["reasons"])
    if confirm_title_change:
        reasons = [
            reason for reason in reasons if reason != "forced_standard"
        ] + ["explicit_title_change_requires_standard_revision"]
    route = classification["route"]
    classification["reasons"] = reasons
    validation_plan = build_validation_plan(
        old_bundle, bundle, image_changed=image_path is not None,
        target_status="draft", resume=resume, route=route, post_id=post_id,
        expected_content_sha256=expected_content_sha256,
        classification=classification)
    return {
        "route": route,
        "reasons": reasons,
        "fast_report": fast_report,
        "classification": classification,
        "reuse": reuse,
        "qa_requirements": list(classification["qa_scopes"]),
        "validation_plan": validation_plan,
    }


def edit_reviewed_draft(
    post_id: int,
    bundle: dict,
    expected_content_sha256: str,
    *,
    confirmed: bool = False,
    edit_intent: str,
    confirm_title_change: bool = False,
    image_path: Path | str | None = None,
    expected_thumbnail_id: int | None = None,
    alt_text: str | None = None,
    resume: bool = False,
    prepared_decision: dict | None = None,
) -> dict:
    """Choose Fast first and fall back to the existing full reviser when needed.

    This function does not broaden either path's safety rules. Fast edits still use
    the strict classifier/delta review/CAS flow; Standard edits still require a
    current full review and fresh official sources in ``revise_reviewed_draft``.
    """
    if not confirmed:
        raise ValueError("specific_draft_revision_confirmation_required")
    if not isinstance(post_id, int) or post_id <= 0:
        raise ValueError("valid_post_id_required")
    if not re.fullmatch(r"[0-9a-f]{64}", expected_content_sha256 or ""):
        raise ValueError("original_content_sha256_required")
    if not isinstance(edit_intent, str) or not edit_intent.strip():
        raise ValueError("edit_intent_required")

    image_path = Path(image_path).resolve() if image_path else None
    if image_path is not None:
        if not isinstance(expected_thumbnail_id, int) or expected_thumbnail_id <= 0:
            raise ValueError("combined_edit_expected_thumbnail_id_required")
        alt_text = (alt_text or "").strip()
        if not alt_text or len(alt_text) > 180 or "\x00" in alt_text:
            raise ValueError("combined_edit_alt_text_required")
    decision = prepared_decision or classify_edit_route(
        post_id,
        bundle,
        confirm_title_change=confirm_title_change,
        image_path=image_path,
        resume=resume,
        expected_content_sha256=expected_content_sha256,
    )
    qa_requirements = decision.get("qa_requirements", [])
    desired = render(bundle["plan"], bundle["sources"])
    desired_sha = hashlib.sha256(desired.encode("utf-8")).hexdigest()
    image_sha, alt_text_sha = image_fingerprints(image_path, alt_text)
    content_already_saved = False
    state = None
    simple_one_shot = (
        decision["route"] == "fast"
        and image_path is None
        and not qa_requirements
        and not resume
    )
    if simple_one_shot:
        increment("edit_route_fast")
        increment("simple_one_shot")
        if decision["reuse"].get("reuse_sources"):
            increment("validation_reuse_sources")
        old_bundle = _load_tracked_bundle(post_id)
        prepared_delta_review = prepare_fast_delta_review(
            old_bundle,
            bundle,
            decision["fast_report"],
            edit_intent,
        )
        updated = fast_revise_reviewed_draft(
            post_id,
            bundle,
            expected_content_sha256,
            confirmed=True,
            edit_intent=edit_intent,
            prepared_delta_review=prepared_delta_review,
        )
        return {
            "post_id": updated,
            "route": "fast",
            "reasons": decision["reasons"],
            "validation_reuse": decision["reuse"],
            "qa_requirements": [],
            "validation_plan": decision.get("validation_plan", {}),
            "simple_one_shot": True,
            "wordpress_saved": True,
        }
    if resume:
        state = load_task_state(post_id)
        if not state or state.get("action") not in {"edit-post", "edit-draft"}:
            raise ValueError("resumable_edit_task_state_required")
        if state.get("status") not in {"in_progress", "saved_pending_qa", "failed"}:
            raise ValueError("task_state_not_resumable")
        current_policy = decision["reuse"]["fingerprint_after"]["policy_digest"]
        validate_resume_fingerprint(
            state,
            expected_content_sha256=expected_content_sha256,
            desired_content_sha256=desired_sha,
            edit_intent=edit_intent,
            current_policy_digest=current_policy,
            expected_thumbnail_id=expected_thumbnail_id,
            alt_text_sha256=alt_text_sha,
            image_sha256=image_sha,
            candidate_content_digest=decision["reuse"]["fingerprint_after"]["content_digest"],
        )
        live = get_post(
            ["sudo", "docker", "exec", "wordpress_app", "wp"],
            post_id,
            fields=["post_status", "post_title", "post_name", "post_content", "post_excerpt"],
        )
        live_sha = content_sha256(live.get("post_content", ""))
        if live_sha == desired_sha:
            tracked = _load_tracked_bundle(post_id)
            tracked_sha = hashlib.sha256(
                render(tracked["plan"], tracked["sources"]).encode("utf-8")
            ).hexdigest()
            if tracked_sha != desired_sha:
                try:
                    _reconcile_saved_draft_manifest(
                        post_id,
                        bundle,
                        expected_content_sha256,
                        desired_sha,
                        route=state.get("route") or decision["route"],
                        fast_edit_review=(state.get("result") or {}).get("fast_edit_review"),
                        edit_intent=edit_intent,
                    )
                except Exception as exc:
                    fail_task_state(post_id, exc, blocked=True)
                    raise
            increment("resume_runs")
            content_already_saved = True
            update_task_state(post_id, completed=["baseline_read", "content_saved"])
            image_pending = image_path is not None and not state.get("completed", {}).get("image_saved")
            if not image_pending:
                update_task_state(
                    post_id,
                    completed=["image_saved", "wordpress_saved"],
                    status="saved_pending_qa",
                    result={"post_id": post_id, "route": state.get("route"),
                            "desired_content_sha256": desired_sha},
                )
                return {
                    "post_id": post_id,
                    "route": state.get("route") or decision["route"],
                    "reasons": state.get("route_reasons", []),
                    "validation_reuse": state.get("reuse", {}),
                    "qa_requirements": state.get("qa_requirements", qa_requirements),
                    "validation_plan": state.get("validation_plan", decision.get("validation_plan", {})),
                    "resumed": True,
                    "wordpress_saved": True,
                }
        elif live_sha != expected_content_sha256:
            fail_task_state(post_id, "resume_state_conflict", blocked=True)
            increment("resume_conflict")
            raise ValueError("resume_state_conflict")
        increment("resume_runs")
    else:
        start_task_state(
            post_id,
            action="edit-post",
            edit_intent=edit_intent,
            baseline={
                "expected_content_sha256": expected_content_sha256,
                "desired_content_sha256": desired_sha,
                "candidate_content_digest": decision["reuse"]["fingerprint_after"]["content_digest"],
                "expected_thumbnail_id": expected_thumbnail_id,
                "alt_text_sha256": alt_text_sha,
            },
            reuse=decision["reuse"],
            artifacts={"image_path": str(image_path)} if image_path else None,
            qa_requirements=qa_requirements,
            validation_plan=decision.get("validation_plan"),
            completion_requirements=completion_requirements_for_task(
                image_changed=image_path is not None,
                qa_requirements=qa_requirements,
            ),
        )
        update_task_state(
            post_id,
            completed=["route_selected"],
            route=decision["route"],
            route_reasons=decision["reasons"],
            validation_plan=decision.get("validation_plan"),
        )
    record_route_profile_metrics(decision, increment)
    if decision["reuse"].get("reuse_sources"):
        increment("validation_reuse_sources")
    if decision["reuse"].get("reuse_full_semantic_review"):
        increment("validation_reuse_full_review")
    elif decision["reuse"].get("delta_review_only"):
        increment("validation_reuse_delta_review")

    try:
        if content_already_saved:
            updated = post_id
            completed = ["baseline_read", "content_saved"]
        elif decision["route"] == "fast":
            old_bundle = _load_tracked_bundle(post_id)
            prepared_delta_review = None
            if resume:
                cached = (state.get("result") or {}).get("fast_edit_review")
                if validate_prepared_delta_review(
                        old_bundle, decision["fast_report"], cached, edit_intent):
                    prepared_delta_review = cached
                    increment("validation_reuse_delta_semantic_review")
            if prepared_delta_review is None:
                prepared_delta_review = prepare_fast_delta_review(
                    old_bundle,
                    bundle,
                    decision["fast_report"],
                    edit_intent,
                )
            update_task_state(
                post_id,
                completed=["source_validation", "content_review"],
                result={"fast_edit_review": prepared_delta_review},
            )
            updated = fast_revise_reviewed_draft(
                post_id,
                bundle,
                expected_content_sha256,
                confirmed=True,
                edit_intent=edit_intent,
                prepared_delta_review=prepared_delta_review,
            )
            completed = [
                "baseline_read",
                "content_saved",
            ]
        else:
            def checkpoint_standard(preflight):
                update_task_state(
                    post_id,
                    completed=["source_validation", "content_review"],
                    checkpoints={"standard_preflight": preflight},
                )

            updated = revise_reviewed_draft(
                post_id,
                bundle,
                expected_content_sha256,
                confirmed=True,
                confirm_title_change=confirm_title_change,
                image_path=None,
                checkpoint_callback=checkpoint_standard,
            )
            completed = [
                "baseline_read",
                "source_validation",
                "content_review",
                "content_saved",
            ]
        update_task_state(post_id, completed=completed)
        image_result = run_combined_image_phase(
            post_id,
            image_path=image_path,
            desired_content_sha256=desired_sha,
            expected_thumbnail_id=expected_thumbnail_id,
            alt_text=alt_text,
            resume=resume,
            state=state,
            update_state=update_task_state,
            reconcile_image=reconcile_featured_image_outcome,
            replace_image=replace_featured_image,
        )
        update_task_state(
            post_id,
            completed=["wordpress_saved"],
            status="saved_pending_qa" if qa_requirements else "in_progress",
            result={
                "post_id": updated,
                "route": decision["route"],
                "desired_content_sha256": desired_sha,
            },
        )
        if not qa_requirements and load_task_state(post_id) is not None:
            complete_task_state(post_id)
        return {
            "post_id": updated,
            "route": decision["route"],
            "reasons": decision["reasons"],
            "validation_reuse": decision["reuse"],
            "qa_requirements": qa_requirements,
            "validation_plan": decision.get("validation_plan"),
            "image": image_result,
        }
    except Exception as exc:
        message = str(exc).lower()
        transient = (
            isinstance(exc, (TimeoutError, subprocess.TimeoutExpired, ConnectionError))
            or (isinstance(exc, subprocess.CalledProcessError) and exc.returncode == 255)
            or any(marker in message for marker in (
                "official_source_http_500",
                "official_source_http_502",
                "official_source_http_503",
                "official_source_http_504",
                "timed out",
                "timeout",
                "transport_unavailable",
            ))
        )
        blocked = not transient and isinstance(exc, ValueError) and (
            FULL_REVIEW_REQUIRED in str(exc)
            or "review" in str(exc).lower()
            or "source" in str(exc).lower()
        )
        fail_task_state(post_id, exc, blocked=blocked)
        raise
