"""Unified orchestration for reviewed draft/public edits and image-only swaps."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from agents.edit_router import edit_reviewed_draft
from agents.change_classifier import classify_change
from agents.editorial import policy_fingerprint, render
from agents.editorial_updater import update_existing_public_post
from agents.fast_edit import (
    build_fast_stored_bundle,
    prepare_fast_delta_review,
    validate_fast_edit,
    validate_prepared_delta_review,
)
from agents.featured_image import reconcile_featured_image_outcome, replace_featured_image
from agents.public_fast_edit import (
    classify_public_fast_edit,
    fast_update_public_post,
    load_tracked_public_bundle,
)
from agents.task_state import (
    complete_task_state,
    completion_requirements_for_task,
    fail_task_state,
    intent_sha256,
    load_task_state,
    start_task_state,
    update_task_state,
)
from agents.validation_reuse import assess_validation_reuse
from agents.validation_router import build_validation_plan
from agents.workflow_metrics import increment
from agents.wordpress_mutation import content_sha256, get_post
from config import DRAFTS_INDEX_FILE, POSTS_INDEX_FILE


def _index_contains_reviewed(path: Path, post_id: int) -> bool:
    if not path.is_file():
        return False
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError):
        return False
    return sum(
        1 for row in rows
        if int(row.get("id", -1)) == int(post_id)
        and isinstance(row.get("fact_manifest", {}).get("editorial_bundle"), dict)
    ) == 1


def reviewed_target_kind(post_id: int) -> str:
    draft = _index_contains_reviewed(DRAFTS_INDEX_FILE, post_id)
    public = _index_contains_reviewed(POSTS_INDEX_FILE, post_id)
    if draft and public:
        raise ValueError("reviewed_post_present_in_both_indexes")
    if draft:
        return "draft"
    if public:
        return "publish"
    raise ValueError("reviewed_post_manifest_required")


def classify_reviewed_post_route(
    post_id: int,
    bundle: dict,
    *,
    expected_content_sha256: str | None = None,
    confirm_title_change: bool = False,
    image_path: Path | str | None = None,
    resume: bool = False,
) -> dict:
    kind = reviewed_target_kind(post_id)
    if kind == "draft":
        from agents.edit_router import classify_edit_route
        result = classify_edit_route(
            post_id, bundle, confirm_title_change=confirm_title_change, image_path=image_path,
            resume=resume, expected_content_sha256=expected_content_sha256)
        return {**result, "target_status": "draft"}
    decision = classify_public_fast_edit(post_id, bundle)
    candidate = decision["candidate"] if decision["route"] == "fast" else bundle
    classification = classify_change(
        decision["tracked_bundle"],
        candidate,
        image_changed=image_path is not None,
        target_status="publish",
        resume=resume,
        fast_report=decision["fast_report"],
        force_standard=confirm_title_change,
    )
    reasons = list(classification["reasons"])
    if (expected_content_sha256 is not None
            and decision["tracked_content_sha256"] != expected_content_sha256):
        reasons.append("public_manifest_not_bound_to_expected_content")
    if confirm_title_change:
        reasons = [reason for reason in reasons if reason != "forced_standard"]
        reasons.append("explicit_title_change_requires_standard_revision")
    route = "standard" if reasons else classification["route"]
    candidate = decision["candidate"] if route == "fast" else bundle
    classification["route"] = route
    classification["reasons"] = reasons
    validation_plan = build_validation_plan(
        decision["tracked_bundle"], candidate, image_changed=image_path is not None,
        target_status="publish", resume=resume, route=route, post_id=post_id,
        expected_content_sha256=expected_content_sha256,
        classification=classification)
    return {
        **decision,
        "route": route,
        "reasons": reasons,
        "target_status": "publish",
        "classification": classification,
        "qa_requirements": list(classification["qa_scopes"]),
        "validation_plan": validation_plan,
    }


def _replace_public_manifest_if_expected(post_id: int, expected_old_sha: str, new_bundle: dict) -> None:
    raw = POSTS_INDEX_FILE.read_text(encoding="utf-8")
    rows = json.loads(raw)
    matches = [row for row in rows if int(row.get("id", -1)) == int(post_id)]
    if len(matches) != 1:
        raise ValueError("resume_public_manifest_conflict")
    current = matches[0].get("fact_manifest", {}).get("editorial_bundle")
    if not isinstance(current, dict):
        raise ValueError("resume_public_manifest_conflict")
    current_sha = content_sha256(render(current["plan"], current["sources"]))
    desired_sha = content_sha256(render(new_bundle["plan"], new_bundle["sources"]))
    if current_sha == desired_sha:
        return
    if current_sha != expected_old_sha:
        raise ValueError("resume_public_manifest_conflict")
    matches[0].setdefault("fact_manifest", {})["editorial_bundle"] = new_bundle
    if POSTS_INDEX_FILE.read_text(encoding="utf-8") != raw:
        raise ValueError("resume_public_manifest_conflict")
    temporary = POSTS_INDEX_FILE.with_suffix(".resume-public-tmp")
    temporary.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(POSTS_INDEX_FILE)


def _validated_prepared_decision(
    prepared_decision: dict | None,
    *,
    post_id: int,
    bundle: dict,
    expected_content_sha256: str,
    image_path: Path | str | None,
    resume: bool,
    target_status: str,
) -> dict | None:
    if prepared_decision is None:
        return None
    if not isinstance(prepared_decision, dict):
        raise ValueError("invalid_prepared_edit_decision")
    plan = prepared_decision.get("validation_plan") or {}
    binding = plan.get("binding") or {}
    desired_sha = content_sha256(render(bundle["plan"], bundle["sources"]))
    scope = plan.get("scope") or prepared_decision.get("classification") or {}
    if (
        binding.get("post_id") != post_id
        or binding.get("target_status") != target_status
        or binding.get("before_content_sha256") != expected_content_sha256
        or binding.get("after_content_sha256") != desired_sha
        or bool(scope.get("image_changed")) != bool(image_path)
        or bool(scope.get("resume")) != bool(resume)
    ):
        raise ValueError("prepared_edit_decision_binding_mismatch")
    return prepared_decision


def _edit_reviewed_public_post(
    post_id: int,
    bundle: dict,
    expected_content_sha256: str,
    *,
    confirmed: bool,
    edit_intent: str,
    confirm_title_change: bool = False,
    image_path: Path | str | None = None,
    expected_thumbnail_id: int | None = None,
    alt_text: str | None = None,
    resume: bool = False,
    prepared_decision: dict | None = None,
) -> dict:
    if not confirmed:
        raise ValueError("specific_public_post_update_confirmation_required")
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

    decision = _validated_prepared_decision(
        prepared_decision,
        post_id=post_id,
        bundle=bundle,
        expected_content_sha256=expected_content_sha256,
        image_path=image_path,
        resume=resume,
        target_status="publish",
    ) or classify_reviewed_post_route(
        post_id, bundle, expected_content_sha256=expected_content_sha256,
        confirm_title_change=confirm_title_change, image_path=image_path, resume=resume)
    increment("edit_target_public")
    increment("edit_route_fast" if decision["route"] == "fast" else "edit_route_standard")
    profile = (decision.get("validation_plan") or {}).get("profile")
    if profile:
        increment("validation_profile_" + profile.replace("-", "_"))
        increment("validation_test_groups_planned", len(decision["validation_plan"].get("test_groups", [])))
    candidate = decision["candidate"] if decision["route"] == "fast" else bundle
    desired = render(candidate["plan"], candidate["sources"])
    desired_sha = content_sha256(desired)
    old_bundle = decision["tracked_bundle"]
    reuse = assess_validation_reuse(old_bundle, candidate)
    image_sha = hashlib.sha256(image_path.read_bytes()).hexdigest() if image_path else None
    alt_sha = hashlib.sha256(alt_text.encode("utf-8")).hexdigest() if image_path else None
    content_already_saved = False
    state = None

    simple_one_shot = (
        decision["route"] == "fast"
        and image_path is None
        and not decision["qa_requirements"]
        and not resume
    )
    if simple_one_shot:
        increment("simple_one_shot")
        prepared = prepare_fast_delta_review(
            old_bundle,
            candidate,
            decision["fast_report"],
            edit_intent,
        )
        updated = fast_update_public_post(
            post_id,
            candidate,
            expected_content_sha256,
            confirmed=True,
            edit_intent=edit_intent,
            prepared_delta_review=prepared,
        )
        return {
            "post_id": updated,
            "target_status": "publish",
            "route": "public-fast",
            "reasons": decision["reasons"],
            "qa_requirements": [],
            "validation_plan": decision.get("validation_plan", {}),
            "simple_one_shot": True,
        }

    if resume:
        state = load_task_state(post_id)
        if not state or state.get("action") != "edit-post" or state.get("status") not in {
                "in_progress", "failed", "saved_pending_qa"}:
            raise ValueError("resumable_edit_task_state_required")
        baseline = state.get("baseline", {})
        state_policy = (state.get("reuse") or {}).get("fingerprint_after", {}).get("policy_digest")
        if (baseline.get("expected_content_sha256") != expected_content_sha256
                or baseline.get("desired_content_sha256") != desired_sha
                or state.get("edit_intent_sha256") != intent_sha256(edit_intent)
                or state_policy != policy_fingerprint()
                or baseline.get("expected_thumbnail_id") != expected_thumbnail_id
                or baseline.get("alt_text_sha256") != alt_sha):
            raise ValueError("resume_state_fingerprint_conflict")
        if image_path is not None:
            artifact = (state.get("artifacts") or {}).get("image_path") or {}
            if artifact.get("sha256") != image_sha:
                raise ValueError("resume_image_artifact_conflict")
        live = get_post(
            ["sudo", "docker", "exec", "wordpress_app", "wp"], post_id,
            fields=["post_status", "post_title", "post_name", "post_content", "post_excerpt"])
        live_sha = content_sha256(live.get("post_content", ""))
        if live_sha == desired_sha:
            tracked_now = load_tracked_public_bundle(post_id)
            tracked_sha = content_sha256(render(tracked_now["plan"], tracked_now["sources"]))
            if tracked_sha != desired_sha:
                stored = candidate
                if state.get("route") == "public-fast":
                    report = validate_fast_edit(tracked_now, candidate)
                    cached = (state.get("result") or {}).get("fast_edit_review")
                    if not validate_prepared_delta_review(tracked_now, report, cached, edit_intent):
                        raise ValueError("resume_public_manifest_fast_review_mismatch")
                    stored = build_fast_stored_bundle(tracked_now, candidate, cached)
                _replace_public_manifest_if_expected(post_id, expected_content_sha256, stored)
            content_already_saved = True
            update_task_state(post_id, completed=["baseline_read", "content_saved"])
            if image_path is None or state.get("completed", {}).get("image_saved"):
                update_task_state(
                    post_id, completed=["image_saved", "wordpress_saved"],
                    status="saved_pending_qa",
                    result={"post_id": post_id, "desired_content_sha256": desired_sha})
                return {
                    "post_id": post_id,
                    "target_status": "publish",
                    "route": state.get("route") or "public-" + decision["route"],
                    "qa_requirements": state.get("qa_requirements", decision["qa_requirements"]),
                    "validation_plan": state.get("validation_plan", decision.get("validation_plan", {})),
                    "resumed": True,
                }
        elif live_sha != expected_content_sha256:
            fail_task_state(post_id, "resume_state_conflict", blocked=True)
            raise ValueError("resume_state_conflict")
        increment("resume_runs")
    else:
        start_task_state(
            post_id,
            action="edit-post",
            edit_intent=edit_intent,
            baseline={
                "target_status": "publish",
                "expected_content_sha256": expected_content_sha256,
                "desired_content_sha256": desired_sha,
                "expected_thumbnail_id": expected_thumbnail_id,
                "alt_text_sha256": alt_sha,
            },
            reuse=reuse,
            artifacts={"image_path": str(image_path)} if image_path else None,
            qa_requirements=decision["qa_requirements"],
            validation_plan=decision.get("validation_plan"),
            completion_requirements=completion_requirements_for_task(
                image_changed=image_path is not None,
                qa_requirements=decision["qa_requirements"],
            ),
        )
        update_task_state(
            post_id, completed=["route_selected"], route="public-" + decision["route"],
            route_reasons=decision["reasons"])

    try:
        if content_already_saved:
            updated = post_id
        elif decision["route"] == "fast":
            prepared = None
            if resume:
                prepared = (state.get("result") or {}).get("fast_edit_review")
                if not validate_prepared_delta_review(
                        old_bundle, decision["fast_report"], prepared, edit_intent):
                    prepared = None
            if prepared is None:
                prepared = prepare_fast_delta_review(
                    old_bundle, candidate, decision["fast_report"], edit_intent)
            update_task_state(
                post_id, completed=["source_validation", "content_review"],
                result={"fast_edit_review": prepared})
            updated = fast_update_public_post(
                post_id, candidate, expected_content_sha256, confirmed=True,
                edit_intent=edit_intent, prepared_delta_review=prepared)
        else:
            def checkpoint(preflight):
                update_task_state(
                    post_id, completed=["source_validation", "content_review"],
                    checkpoints={"standard_preflight": preflight})

            updated = update_existing_public_post(
                post_id, bundle, expected_content_sha256, confirmed=True,
                confirm_title_change=confirm_title_change, checkpoint_callback=checkpoint,
                tracked_baseline_bundle=old_bundle)
        update_task_state(post_id, completed=["baseline_read", "content_saved"])

        image_result = None
        if image_path is not None:
            update_task_state(post_id, completed=["image_validated"])
            checkpoint_image = ((state or {}).get("checkpoints") or {}).get("image_outcome") if resume else None
            if checkpoint_image and checkpoint_image.get("attachment_id"):
                image_result = reconcile_featured_image_outcome(post_id, checkpoint_image, alt_text)
            else:
                def image_checkpoint(payload):
                    update_task_state(post_id, checkpoints={"image_outcome": payload})

                image_result = replace_featured_image(
                    post_id, image_path, desired_sha,
                    expected_thumbnail_id=expected_thumbnail_id, alt_text=alt_text,
                    confirmed=True, manage_task_state=False,
                    outcome_callback=image_checkpoint)
            update_task_state(post_id, completed=["image_saved"], result={"image_phase": image_result})
        else:
            update_task_state(post_id, completed=["image_saved"])
        update_task_state(
            post_id, completed=["wordpress_saved"], status="saved_pending_qa",
            result={"post_id": updated, "desired_content_sha256": desired_sha})
        if not decision["qa_requirements"] and load_task_state(post_id) is not None:
            update_task_state(post_id, status="in_progress")
            complete_task_state(post_id)
        return {
            "post_id": updated,
            "target_status": "publish",
            "route": "public-" + decision["route"],
            "reasons": decision["reasons"],
            "qa_requirements": decision["qa_requirements"],
            "validation_plan": decision.get("validation_plan"),
            "image": image_result,
        }
    except Exception as exc:
        fail_task_state(post_id, exc, blocked=isinstance(exc, ValueError) and "conflict" in str(exc).lower())
        raise


def edit_reviewed_post(
    post_id: int,
    bundle: dict | None,
    expected_content_sha256: str,
    *,
    confirmed: bool,
    edit_intent: str | None = None,
    confirm_title_change: bool = False,
    image_path: Path | str | None = None,
    expected_thumbnail_id: int | None = None,
    alt_text: str | None = None,
    resume: bool = False,
    prepared_decision: dict | None = None,
) -> dict:
    """One user-facing edit entry point with narrow status-specific internals."""
    if bundle is None:
        if not image_path:
            raise ValueError("edit_post_bundle_or_image_required")
        kind = reviewed_target_kind(post_id)
        validation_plan = build_validation_plan(
            None, None, image_changed=True, target_status=kind, resume=resume,
            route="image-only", post_id=post_id,
            expected_content_sha256=expected_content_sha256)
        result = replace_featured_image(
            post_id, image_path, expected_content_sha256,
            expected_thumbnail_id=expected_thumbnail_id,
            alt_text=alt_text, confirmed=confirmed, validation_plan=validation_plan)
        return {**result, "route": "image-only", "target_status": kind,
                "validation_plan": validation_plan}
    if not edit_intent:
        raise ValueError("edit_intent_required")
    kind = reviewed_target_kind(post_id)
    if kind == "draft":
        prepared = _validated_prepared_decision(
            prepared_decision,
            post_id=post_id,
            bundle=bundle,
            expected_content_sha256=expected_content_sha256,
            image_path=image_path,
            resume=resume,
            target_status="draft",
        )
        result = edit_reviewed_draft(
            post_id, bundle, expected_content_sha256, confirmed=confirmed,
            edit_intent=edit_intent, confirm_title_change=confirm_title_change,
            image_path=image_path, expected_thumbnail_id=expected_thumbnail_id,
            alt_text=alt_text, resume=resume, prepared_decision=prepared)
        return {**result, "target_status": "draft"}
    return _edit_reviewed_public_post(
        post_id, bundle, expected_content_sha256, confirmed=confirmed,
        edit_intent=edit_intent, confirm_title_change=confirm_title_change,
        image_path=image_path, expected_thumbnail_id=expected_thumbnail_id,
        alt_text=alt_text, resume=resume, prepared_decision=prepared_decision)
