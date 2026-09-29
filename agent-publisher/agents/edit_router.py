"""Automatic Fast/Standard routing for edits to reviewed WordPress drafts."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

from agents.editorial import render
from agents.editorial_draft_reviser import revise_reviewed_draft
from agents.fast_edit import (
    FULL_REVIEW_REQUIRED,
    fast_revise_reviewed_draft,
    prepare_fast_delta_review,
    validate_fast_edit,
    validate_prepared_delta_review,
)
from agents.task_state import (
    fail_task_state,
    intent_sha256,
    load_task_state,
    start_task_state,
    update_task_state,
)
from agents.validation_reuse import assess_validation_reuse
from agents.workflow_metrics import increment
from agents.wordpress_mutation import content_sha256, get_post
from config import DRAFTS_INDEX_FILE


def _load_tracked_bundle(post_id: int) -> dict:
    if not DRAFTS_INDEX_FILE.is_file():
        raise ValueError("reviewed_draft_index_missing")
    records = json.loads(DRAFTS_INDEX_FILE.read_text(encoding="utf-8"))
    matches = [item for item in records if int(item.get("id", -1)) == int(post_id)]
    if len(matches) != 1:
        raise ValueError("reviewed_draft_manifest_required")
    bundle = matches[0].get("fact_manifest", {}).get("editorial_bundle")
    if not isinstance(bundle, dict):
        raise ValueError("reviewed_draft_manifest_required")
    return bundle


def classify_edit_route(
    post_id: int,
    bundle: dict,
    *,
    confirm_title_change: bool = False,
    image_path: Path | str | None = None,
) -> dict:
    old_bundle = _load_tracked_bundle(post_id)
    reuse = assess_validation_reuse(old_bundle, bundle)
    fast_report = validate_fast_edit(old_bundle, bundle)
    reasons = list(fast_report.get("reasons", []))
    if confirm_title_change:
        reasons.append("explicit_title_change_requires_standard_revision")
    if image_path is not None:
        reasons.append("content_plus_image_revision_requires_standard_revision")
    route = "fast" if fast_report.get("status") == "candidate" and not reasons else "standard"
    return {
        "route": route,
        "reasons": reasons,
        "fast_report": fast_report,
        "reuse": reuse,
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
    resume: bool = False,
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
    decision = classify_edit_route(
        post_id,
        bundle,
        confirm_title_change=confirm_title_change,
        image_path=image_path,
    )
    desired = render(bundle["plan"], bundle["sources"])
    desired_sha = hashlib.sha256(desired.encode("utf-8")).hexdigest()
    if resume:
        state = load_task_state(post_id)
        if not state or state.get("action") != "edit-draft":
            raise ValueError("resumable_edit_task_state_required")
        if state.get("status") not in {"in_progress", "saved_pending_qa", "failed"}:
            raise ValueError("task_state_not_resumable")
        baseline = state.get("baseline", {})
        state_policy = (
            (state.get("reuse") or {}).get("fingerprint_after", {}).get("policy_digest")
        )
        current_policy = decision["reuse"]["fingerprint_after"]["policy_digest"]
        if (baseline.get("expected_content_sha256") != expected_content_sha256
                or baseline.get("desired_content_sha256") != desired_sha
                or baseline.get("candidate_content_digest")
                    != decision["reuse"]["fingerprint_after"]["content_digest"]
                or state.get("edit_intent_sha256") != intent_sha256(edit_intent)
                or state_policy != current_policy):
            raise ValueError("resume_state_fingerprint_conflict")
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
                fail_task_state(post_id, "resume_manifest_not_updated", blocked=True)
                raise ValueError("resume_manifest_not_updated")
            update_task_state(
                post_id,
                completed=["baseline_read", "wordpress_saved"],
                status="saved_pending_qa",
                result={"post_id": post_id, "route": state.get("route"), "desired_content_sha256": desired_sha},
            )
            increment("resume_runs")
            return {
                "post_id": post_id,
                "route": state.get("route") or decision["route"],
                "reasons": state.get("route_reasons", []),
                "validation_reuse": state.get("reuse", {}),
                "resumed": True,
                "wordpress_saved": True,
            }
        if live_sha != expected_content_sha256:
            fail_task_state(post_id, "resume_state_conflict", blocked=True)
            increment("resume_conflict")
            raise ValueError("resume_state_conflict")
        increment("resume_runs")
    else:
        start_task_state(
            post_id,
            action="edit-draft",
            edit_intent=edit_intent,
            baseline={
                "expected_content_sha256": expected_content_sha256,
                "desired_content_sha256": desired_sha,
                "candidate_content_digest": decision["reuse"]["fingerprint_after"]["content_digest"],
            },
            reuse=decision["reuse"],
            artifacts={"image_path": str(image_path)} if image_path else None,
        )
        update_task_state(
            post_id,
            completed=["route_selected"],
            route=decision["route"],
            route_reasons=decision["reasons"],
        )
    increment("edit_route_fast" if decision["route"] == "fast" else "edit_route_standard")
    if decision["reuse"].get("reuse_sources"):
        increment("validation_reuse_sources")
    if decision["reuse"].get("reuse_full_semantic_review"):
        increment("validation_reuse_full_review")
    elif decision["reuse"].get("delta_review_only"):
        increment("validation_reuse_delta_review")

    try:
        if decision["route"] == "fast":
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
                "wordpress_saved",
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
                image_path=image_path,
                checkpoint_callback=checkpoint_standard,
            )
            completed = [
                "baseline_read",
                "source_validation",
                "content_review",
                "wordpress_saved",
            ]
            if image_path is not None:
                completed.append("image_validated")
        update_task_state(post_id, completed=completed)
        update_task_state(
            post_id,
            status="saved_pending_qa",
            result={
                "post_id": updated,
                "route": decision["route"],
                "desired_content_sha256": desired_sha,
            },
        )
        return {
            "post_id": updated,
            "route": decision["route"],
            "reasons": decision["reasons"],
            "validation_reuse": decision["reuse"],
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
