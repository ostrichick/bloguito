"""Unified orchestration for reviewed draft/public edits and image-only swaps."""

from __future__ import annotations

import re
from pathlib import Path

from agents.edit_router import edit_reviewed_draft
from agents.edit_orchestration import (
    image_fingerprints,
    record_route_profile_metrics,
    run_combined_image_phase,
    validate_resume_fingerprint,
)
from agents.change_classifier import classify_change
from agents.editorial import digest, policy_fingerprint, recognized_reviewed_content_hashes, render
from agents.editorial_updater import update_existing_public_post
from agents.fast_edit import (
    build_fast_stored_bundle,
    prepare_fast_delta_review,
    validate_fast_edit,
    validate_prepared_delta_review,
)
from agents.featured_image import reconcile_featured_image_outcome, replace_featured_image
from agents.post_manifest_store import load_record, replace_record
from agents.public_fast_edit import (
    classify_public_fast_edit,
    fast_update_public_post,
    load_tracked_public_bundle,
    migrate_public_renderer,
)
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
from config import DRAFTS_INDEX_FILE, POSTS_INDEX_FILE


def _index_contains_reviewed(path: Path, post_id: int) -> bool:
    if not path.is_file():
        return False
    try:
        snapshot = load_record(path, post_id)
    except (OSError, TypeError, ValueError):
        return False
    return bool(snapshot and isinstance(
        snapshot.record.get("fact_manifest", {}).get("editorial_bundle"), dict))


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


def _verified_public_edit_receipt(post_id: int, before_content_sha256: str) -> dict:
    """Bind a successful public edit result to exact live/readback reviewed provenance."""
    base = ["sudo", "docker", "exec", "wordpress_app", "wp"]
    live = get_post(
        base, post_id,
        fields=["post_status", "post_title", "post_name", "post_content", "post_excerpt"])
    bundle = load_tracked_public_bundle(post_id)
    after_sha = content_sha256(live.get("post_content", ""))
    if (live.get("post_status") != "publish"
            or live.get("post_title") != bundle.get("plan", {}).get("title")):
        raise ValueError("public_edit_receipt_identity_mismatch")
    hashes = recognized_reviewed_content_hashes(bundle, post_id=post_id)
    variant = next((name for name, value in hashes.items() if value == after_sha), None)
    if variant is None:
        raise ValueError("public_edit_receipt_provenance_unbound")
    review_digest = (bundle.get("review") or {}).get("digest")
    bundle_digest = digest(bundle)
    if (not re.fullmatch(r"[0-9a-f]{64}", review_digest or "")
            or not re.fullmatch(r"[0-9a-f]{64}", bundle_digest or "")):
        raise ValueError("public_edit_receipt_provenance_invalid")
    return {
        "action": "edit-post",
        "post_id": post_id,
        "target_status": "publish",
        "before_content_sha256": before_content_sha256,
        "after_content_sha256": after_sha,
        "review_digest": review_digest,
        "bundle_digest": bundle_digest,
        "provenance_variant": variant,
        "readback_verified": True,
    }


def _with_public_edit_receipt(result: dict, post_id: int, before_content_sha256: str) -> dict:
    return {
        **result,
        "mutation_receipt": _verified_public_edit_receipt(post_id, before_content_sha256),
    }


def _legacy_public_bundle_target(post_id: int, bundle: dict | None) -> bool:
    """Allow only an explicitly ID-bound full bundle to enter legacy public Standard."""
    return (
        isinstance(bundle, dict)
        and isinstance(bundle.get("brief"), dict)
        and bundle["brief"].get("existing_post_id") == post_id
    )


def _legacy_public_standard_decision(
    post_id: int,
    bundle: dict,
    *,
    expected_content_sha256: str | None,
    image_path: Path | str | None,
    resume: bool,
) -> dict:
    """Fail closed to full Standard when a legacy public post has no reviewed manifest.

    The actual mutator still proves that the live target is public, matches the caller's
    content SHA, passes full current source/site/semantic validation, and survives guarded
    readback before a reviewed manifest may be created.
    """
    if not _legacy_public_bundle_target(post_id, bundle):
        raise ValueError("reviewed_post_manifest_required")
    classification = {
        "route": "standard",
        "risk_level": "fact",
        "reasons": ["legacy_public_without_reviewed_manifest", "full_review_required"],
        "fast_report": None,
        "content_changed": True,
        "image_changed": image_path is not None,
        "title_changed": True,
        "brief_changed": True,
        "category_changed": True,
        "seo_changed": True,
        "sources_changed": True,
        "actions_changed": True,
        "temporal_changed": True,
        "layout_changed": True,
        "related_changed": True,
        "review_metadata_changed": True,
        "unknown_bundle_change": False,
        "unknown_bundle_keys": [],
        "factual_risk": True,
        "event_domain": bundle.get("brief", {}).get("category_key") == "events",
        "ticket_domain": bundle.get("brief", {}).get("category_key") == "concert",
        "target_status": "publish",
        "resume": bool(resume),
        "fast_candidate": False,
        "fast_reasons": ["legacy_public_without_reviewed_manifest"],
        "qa_scopes": [
            "content-mobile-desktop",
            "cta-destination",
            "layout-accessibility",
            "public-page",
        ],
    }
    validation_plan = build_validation_plan(
        None,
        bundle,
        image_changed=image_path is not None,
        target_status="publish",
        resume=resume,
        route="standard",
        post_id=post_id,
        expected_content_sha256=expected_content_sha256,
        classification=classification,
    )
    return {
        "candidate": bundle,
        "tracked_bundle": None,
        "tracked_content_sha256": None,
        "fast_report": None,
        "route": "standard",
        "reasons": list(classification["reasons"]),
        "target_status": "publish",
        "classification": classification,
        "qa_requirements": list(classification["qa_scopes"]),
        "validation_plan": validation_plan,
        "legacy_public_adoption": True,
    }


def _stale_draft_public_recovery_decision(
    post_id: int,
    bundle: dict,
    expected_content_sha256: str,
    *,
    image_path: Path | str | None,
    resume: bool,
) -> dict | None:
    """Recover only a reviewed draft index whose exact live target is now public."""
    if bundle.get("brief", {}).get("existing_post_id") != post_id:
        return None
    if not DRAFTS_INDEX_FILE.is_file():
        return None
    snapshot = load_record(DRAFTS_INDEX_FILE, post_id)
    if snapshot is None:
        return None
    tracked = snapshot.record.get("fact_manifest", {}).get("editorial_bundle")
    if not isinstance(tracked, dict):
        raise ValueError("reviewed_draft_manifest_required")
    live = get_post(
        ["sudo", "docker", "exec", "wordpress_app", "wp"],
        post_id,
        fields=["post_status", "post_title", "post_content"],
    )
    if live.get("post_status") != "publish":
        return None
    live_sha = content_sha256(live.get("post_content", ""))
    desired_sha = content_sha256(render(bundle["plan"], bundle["sources"]))
    allowed = {expected_content_sha256}
    if resume:
        allowed.add(desired_sha)
    if live_sha not in allowed:
        raise ValueError("stale_draft_public_live_sha_mismatch")
    classification = classify_change(
        tracked,
        bundle,
        image_changed=image_path is not None,
        target_status="publish",
        resume=resume,
        force_standard=True,
    )
    reasons = [
        reason for reason in classification["reasons"]
        if reason != "forced_standard"
    ]
    reasons.extend([
        "live_publish_with_stale_draft_reviewed_index",
        "full_review_required",
    ])
    classification["route"] = "standard"
    classification["reasons"] = reasons
    validation_plan = build_validation_plan(
        tracked,
        bundle,
        image_changed=image_path is not None,
        target_status="publish",
        resume=resume,
        route="standard",
        post_id=post_id,
        expected_content_sha256=expected_content_sha256,
        classification=classification,
    )
    return {
        "candidate": bundle,
        "tracked_bundle": tracked,
        "tracked_content_sha256": None,
        "tracked_content_sha256s": [],
        "fast_report": classification.get("fast_report"),
        "route": "standard",
        "reasons": reasons,
        "target_status": "publish",
        "classification": classification,
        "qa_requirements": list(classification["qa_scopes"]),
        "validation_plan": validation_plan,
        "legacy_public_adoption": True,
        "stale_draft_public_recovery": True,
        "stale_draft_snapshot": snapshot,
        "live_content_already_desired": live_sha == desired_sha,
    }


def classify_reviewed_post_route(
    post_id: int,
    bundle: dict,
    *,
    expected_content_sha256: str | None = None,
    confirm_title_change: bool = False,
    image_path: Path | str | None = None,
    resume: bool = False,
) -> dict:
    try:
        kind = reviewed_target_kind(post_id)
    except ValueError as exc:
        if str(exc) != "reviewed_post_manifest_required":
            raise
        return _legacy_public_standard_decision(
            post_id,
            bundle,
            expected_content_sha256=expected_content_sha256,
            image_path=image_path,
            resume=resume,
        )
    if kind == "draft":
        from agents.edit_router import classify_edit_route
        result = classify_edit_route(
            post_id, bundle, confirm_title_change=confirm_title_change, image_path=image_path,
            resume=resume, expected_content_sha256=expected_content_sha256)
        return {**result, "target_status": "draft"}
    decision = classify_public_fast_edit(
        post_id,
        bundle,
        expected_content_sha256=expected_content_sha256,
    )
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
            and expected_content_sha256 not in decision.get(
                "tracked_content_sha256s", [decision["tracked_content_sha256"]]
            )):
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
    snapshot = load_record(POSTS_INDEX_FILE, post_id)
    if snapshot is None:
        raise ValueError("resume_public_manifest_conflict")
    current = snapshot.record.get("fact_manifest", {}).get("editorial_bundle")
    if not isinstance(current, dict):
        raise ValueError("resume_public_manifest_conflict")
    current_sha = content_sha256(render(current["plan"], current["sources"]))
    desired_sha = content_sha256(render(new_bundle["plan"], new_bundle["sources"]))
    if current_sha == desired_sha:
        return
    if current_sha != expected_old_sha:
        raise ValueError("resume_public_manifest_conflict")
    updated = dict(snapshot.record)
    updated.setdefault("fact_manifest", dict(snapshot.record.get("fact_manifest", {})))["editorial_bundle"] = new_bundle
    try:
        replace_record(snapshot, updated)
    except ValueError as exc:
        raise ValueError("resume_public_manifest_conflict") from exc


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
    record_route_profile_metrics(decision, increment)
    candidate = decision["candidate"] if decision["route"] == "fast" else bundle
    desired = render(candidate["plan"], candidate["sources"])
    desired_sha = content_sha256(desired)
    old_bundle = decision["tracked_bundle"]
    reuse = assess_validation_reuse(old_bundle, candidate)
    image_sha, alt_sha = image_fingerprints(image_path, alt_text)
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
        if decision.get("renderer_migration"):
            updated = migrate_public_renderer(
                post_id,
                candidate,
                expected_content_sha256,
                confirmed=True,
            )
        else:
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
        return _with_public_edit_receipt({
            "post_id": updated,
            "target_status": "publish",
            "route": "public-fast",
            "reasons": decision["reasons"],
            "qa_requirements": [],
            "validation_plan": decision.get("validation_plan", {}),
            "simple_one_shot": True,
            "renderer_migration": bool(decision.get("renderer_migration")),
            "renderer_variant": decision.get("renderer_variant"),
        }, post_id, expected_content_sha256)

    if resume:
        state = load_task_state(post_id)
        if not state or state.get("action") != "edit-post" or state.get("status") not in {
                "in_progress", "failed", "saved_pending_qa"}:
            raise ValueError("resumable_edit_task_state_required")
        validate_resume_fingerprint(
            state,
            expected_content_sha256=expected_content_sha256,
            desired_content_sha256=desired_sha,
            edit_intent=edit_intent,
            current_policy_digest=policy_fingerprint(candidate),
            expected_thumbnail_id=expected_thumbnail_id,
            alt_text_sha256=alt_sha,
            image_sha256=image_sha,
        )
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
                return _with_public_edit_receipt({
                    "post_id": post_id,
                    "target_status": "publish",
                    "route": state.get("route") or "public-" + decision["route"],
                    "qa_requirements": state.get("qa_requirements", decision["qa_requirements"]),
                    "validation_plan": state.get("validation_plan", decision.get("validation_plan", {})),
                    "resumed": True,
                }, post_id, expected_content_sha256)
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
        elif decision.get("renderer_migration"):
            update_task_state(
                post_id,
                completed=["source_validation", "content_review"],
                result={
                    "renderer_migration": True,
                    "renderer_variant": decision.get("renderer_variant"),
                },
            )
            updated = migrate_public_renderer(
                post_id,
                candidate,
                expected_content_sha256,
                confirmed=True,
            )
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
                tracked_baseline_bundle=old_bundle,
                adopt_missing_manifest=decision.get("legacy_public_adoption") is True,
                stale_draft_snapshot=decision.get("stale_draft_snapshot"))
        update_task_state(post_id, completed=["baseline_read", "content_saved"])

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
            post_id, completed=["wordpress_saved"], status="saved_pending_qa",
            result={"post_id": updated, "desired_content_sha256": desired_sha})
        if not decision["qa_requirements"] and load_task_state(post_id) is not None:
            update_task_state(post_id, status="in_progress")
            complete_task_state(post_id)
        return _with_public_edit_receipt({
            "post_id": updated,
            "target_status": "publish",
            "route": "public-" + decision["route"],
            "reasons": decision["reasons"],
            "qa_requirements": decision["qa_requirements"],
            "validation_plan": decision.get("validation_plan"),
            "image": image_result,
        }, post_id, expected_content_sha256)
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
        payload = {**result, "route": "image-only", "target_status": kind,
                   "validation_plan": validation_plan}
        if kind == "publish":
            return _with_public_edit_receipt(payload, post_id, expected_content_sha256)
        return payload
    if not edit_intent:
        raise ValueError("edit_intent_required")
    try:
        kind = reviewed_target_kind(post_id)
    except ValueError as exc:
        if str(exc) != "reviewed_post_manifest_required" or not _legacy_public_bundle_target(post_id, bundle):
            raise
        kind = "publish"
    if kind == "draft":
        recovery = _stale_draft_public_recovery_decision(
            post_id,
            bundle,
            expected_content_sha256,
            image_path=image_path,
            resume=resume,
        )
        if recovery is not None:
            return _edit_reviewed_public_post(
                post_id, bundle, expected_content_sha256, confirmed=confirmed,
                edit_intent=edit_intent, confirm_title_change=confirm_title_change,
                image_path=image_path, expected_thumbnail_id=expected_thumbnail_id,
                alt_text=alt_text, resume=resume, prepared_decision=recovery)
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
