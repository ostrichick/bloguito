"""Image-only featured-image replacement with WordPress preservation checks."""

from __future__ import annotations

import json
import hashlib
import re
import subprocess
from agents.wordpress_transport import run_wordpress
from pathlib import Path

from PIL import Image

from agents.editorial import ROOT
from agents.editorial_updater import RANK_MATH_META_KEYS
from agents.post_manifest_store import acquire_editorial_lock, release_editorial_lock
from agents.publish_gate import record_publish_attestation, reviewed_binding_for_post
from agents.task_state import (
    complete_task_state,
    completion_requirements_for_task,
    fail_task_state,
    load_after_image_checkpoint,
    load_task_state,
    start_task_state,
    update_after_image_checkpoint,
    update_task_state,
)
from agents.wordpress_mutation import (
    backup_json,
    content_sha256,
    get_post,
    guarded_set_post_thumbnail,
    guarded_update_featured_image_alt,
    verify_cas,
)
from agents.designer import FEATURED_IMAGE_POLICY
from agents.workflow_metrics import increment, timed


ALLOWED_POST_STATUSES = {"publish", "draft", "pending", "future", "private"}
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
SIMPLE_TASK_MAX_ATTEMPTS = 2


def validate_featured_image_file(image_path: Path | str) -> dict:
    path = Path(image_path).resolve()
    if not path.is_file() or path.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise ValueError("reviewed_featured_image_required")
    if path.stat().st_size <= 0:
        raise ValueError("featured_image_empty")
    expected = FEATURED_IMAGE_POLICY.get("canvas", {})
    expected_size = (int(expected.get("width", 1200)), int(expected.get("height", 675)))
    try:
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            observed_size = image.size
            image_format = image.format
    except Exception as exc:
        raise ValueError("featured_image_decode_failed") from exc
    if observed_size != expected_size:
        raise ValueError(
            f"featured_image_canvas_mismatch: expected {expected_size[0]}x{expected_size[1]}, "
            f"got {observed_size[0]}x{observed_size[1]}"
        )
    return {
        "path": str(path),
        "width": observed_size[0],
        "height": observed_size[1],
        "format": image_format,
        "policy_version": FEATURED_IMAGE_POLICY.get("version", 2),
        "safe_margin_percent": FEATURED_IMAGE_POLICY.get("composition", {}).get("safe_margin_percent", 8),
    }


def _read_post_meta(base, post_id: int, key: str) -> str | None:
    with timed("wp_meta_read"):
        increment("wp_roundtrips")
        result = run_wordpress(
            list(base) + ["post", "meta", "get", str(int(post_id)), key, "--allow-root"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="strict",
            check=False,
        )
    if result.returncode == 0:
        return (result.stdout or "").lstrip("\ufeff").rstrip("\r\n")
    stderr = (result.stderr or "").lower()
    stdout = result.stdout or ""
    if result.returncode == 1 and (
            "could not find the specified post meta field" in stderr
            or (not stdout.strip() and not stderr.strip())):
        return None
    raise subprocess.CalledProcessError(
        result.returncode, result.args, output=result.stdout, stderr=result.stderr
    )


def _rank_math_meta(base, post_id: int) -> dict[str, str | None]:
    """Legacy diagnostic helper; image-only mutations no longer call it.

    Retained for compatibility with older diagnostics/tests. Featured-image import
    cannot edit these keys through the restricted transport, so per-key readback is
    redundant for the normal image-only path.
    """
    return {key: _read_post_meta(base, post_id, key) for key in RANK_MATH_META_KEYS}


def reconcile_featured_image_outcome(post_id: int, checkpoint: dict, alt_text: str) -> dict | None:
    """Verify a previously imported attachment without importing a second copy."""
    if not isinstance(checkpoint, dict) or not checkpoint.get("attachment_id"):
        return None
    attachment_id = int(checkpoint["attachment_id"])
    base = ["sudo", "docker", "exec", "wordpress_app", "wp"]
    observed_thumb = _read_post_meta(base, post_id, "_thumbnail_id")
    expected_thumbnail_id = checkpoint.get("expected_thumbnail_id")
    if expected_thumbnail_id is not None and (
            type(expected_thumbnail_id) is not int or expected_thumbnail_id <= 0):
        raise ValueError("featured_image_resume_thumbnail_conflict")
    expected_thumb_text = None if expected_thumbnail_id is None else str(expected_thumbnail_id)
    attachment_thumb_text = str(attachment_id)
    if observed_thumb not in {attachment_thumb_text, expected_thumb_text}:
        raise ValueError("featured_image_resume_thumbnail_conflict")
    fields = ["post_status", "post_title", "post_name", "post_content", "post_excerpt"]
    saved = get_post(base, post_id, fields=fields)
    expected_post = checkpoint.get("preserved_post") or {}
    if (saved.get("post_status") != expected_post.get("post_status")
            or saved.get("post_title") != expected_post.get("post_title")
            or saved.get("post_name") != expected_post.get("post_name")
            or saved.get("post_excerpt", "") != expected_post.get("post_excerpt", "")
            or content_sha256(saved.get("post_content", "")) != checkpoint.get("content_sha256")):
        raise ValueError("featured_image_resume_post_conflict")
    mutation = guarded_set_post_thumbnail(
        base,
        post_id,
        expected={
            "post_status": expected_post.get("post_status", ""),
            "post_title": expected_post.get("post_title", ""),
            "post_name": expected_post.get("post_name", ""),
            "post_excerpt": expected_post.get("post_excerpt", ""),
            "content_sha256": checkpoint.get("content_sha256", ""),
        },
        expected_thumbnail_id=expected_thumbnail_id,
        attachment_id=attachment_id,
    )
    saved = mutation["post"]
    if mutation.get("thumbnail_id") != attachment_thumb_text:
        raise ValueError("featured_image_resume_thumbnail_conflict")
    attachment = get_post(
        base, attachment_id, fields=["ID", "guid", "post_title", "post_mime_type"])
    observed_alt = _read_post_meta(base, attachment_id, "_wp_attachment_image_alt")
    if observed_alt != alt_text:
        raise ValueError("featured_image_resume_alt_conflict")
    if not str(attachment.get("post_mime_type", "")).startswith("image/"):
        raise ValueError("featured_image_resume_attachment_conflict")
    guid = str(attachment.get("guid", ""))
    if not guid.startswith(("https://", "http://")):
        raise ValueError("featured_image_resume_url_conflict")
    return {
        "post_id": post_id,
        "status": saved.get("post_status"),
        "attachment_id": attachment_id,
        "attachment_url": guid,
        "alt_text": alt_text,
        "backup": checkpoint.get("backup"),
        "reconciled": True,
    }


def update_featured_image_alt_from_live_baseline(
    post_id: int,
    *,
    alt_text: str,
    confirmed: bool = False,
) -> dict:
    """Update only the current featured attachment ALT with exact live CAS/readback."""
    if not confirmed or not isinstance(post_id, int) or post_id <= 0:
        raise ValueError("specific_featured_image_confirmation_required")
    alt_text = (alt_text or "").strip()
    if not alt_text or len(alt_text) > 180 or "\x00" in alt_text:
        raise ValueError("featured_image_alt_text_required")

    lock = acquire_editorial_lock(ROOT)
    base = ["sudo", "docker", "exec", "wordpress_app", "wp"]
    state_started = False
    try:
        fields = ["post_status", "post_title", "post_name", "post_content", "post_excerpt"]
        live = get_post(base, post_id, fields=fields)
        if live.get("post_status") not in ALLOWED_POST_STATUSES:
            raise ValueError("target_missing_or_modified")
        live_sha = content_sha256(live.get("post_content", ""))
        before_thumb = _read_post_meta(base, post_id, "_thumbnail_id")
        if before_thumb is None or not before_thumb.isdigit() or int(before_thumb) <= 0:
            raise ValueError("featured_image_attachment_required")
        attachment_id = int(before_thumb)
        attachment = get_post(
            base, attachment_id, fields=["ID", "guid", "post_title", "post_mime_type"])
        if not str(attachment.get("post_mime_type", "")).startswith("image/"):
            raise ValueError("featured_image_attachment_verification_failed")
        before_alt = _read_post_meta(base, attachment_id, "_wp_attachment_image_alt")

        validation_plan = {
            "profile": "image-metadata-only",
            "full_regression_required": False,
            "selected_files": [],
        }
        start_task_state(
            post_id,
            action="replace-featured-image",
            edit_intent="현재 대표이미지는 유지하고 접근성 ALT 텍스트만 보완",
            baseline={
                "expected_content_sha256": live_sha,
                "status": live.get("post_status"),
                "title": live.get("post_title"),
                "post_name": live.get("post_name"),
                "thumbnail_id": attachment_id,
                "attachment_alt": before_alt,
            },
            reuse={
                "content_unchanged": True,
                "image_binary_unchanged": True,
                "source_validation_skipped": True,
                "semantic_review_skipped": True,
                "reason": "featured_image_alt_metadata_only",
            },
            validation_plan=validation_plan,
            completion_requirements=completion_requirements_for_task(
                image_changed=False, qa_requirements=[]),
        )
        state_started = True
        update_task_state(
            post_id,
            completed=[
                "baseline_read", "route_selected", "source_validation", "content_review",
                "content_saved", "image_saved",
            ],
            route="image-metadata-only",
        )

        backup = backup_json(
            ROOT,
            "featured-image-alt-edit",
            post_id,
            {
                "post": live,
                "thumbnail_id": attachment_id,
                "attachment": attachment,
                "attachment_alt": before_alt,
            },
        )
        mutation = guarded_update_featured_image_alt(
            base,
            post_id,
            expected={
                "post_status": live["post_status"],
                "post_title": live["post_title"],
                "post_name": live["post_name"],
                "post_excerpt": live.get("post_excerpt", ""),
                "content_sha256": live_sha,
            },
            attachment_id=attachment_id,
            expected_alt=before_alt,
            alt_text=alt_text,
        )
        saved = mutation["post"]
        preserved = ("post_status", "post_title", "post_name", "post_content", "post_excerpt")
        if any(saved.get(key) != live.get(key) for key in preserved):
            raise ValueError(f"featured_image_alt_post_preservation_failed: recover from {backup}")
        if mutation.get("thumbnail_id") != str(attachment_id):
            raise ValueError(f"featured_image_alt_thumbnail_changed: recover from {backup}")
        observed_alt = _read_post_meta(base, attachment_id, "_wp_attachment_image_alt")
        if observed_alt != alt_text:
            raise ValueError(f"featured_image_alt_verification_failed: recover from {backup}")
        observed_thumb = _read_post_meta(base, post_id, "_thumbnail_id")
        if observed_thumb != str(attachment_id):
            raise ValueError(f"featured_image_alt_thumbnail_changed: recover from {backup}")

        result = {
            "post_id": post_id,
            "status": saved.get("post_status"),
            "attachment_id": attachment_id,
            "attachment_url": str(attachment.get("guid", "")),
            "previous_alt_text": before_alt,
            "alt_text": alt_text,
            "content_sha256": live_sha,
            "backup": str(backup),
        }
        update_task_state(
            post_id,
            completed=["wordpress_saved"],
            result=result,
            status="in_progress",
        )
        complete_task_state(post_id)
        return result
    except Exception as exc:
        if state_started:
            fail_task_state(post_id, exc)
        raise
    finally:
        release_editorial_lock(lock)


def replace_featured_image(
    post_id: int,
    image_path: Path | str,
    expected_content_sha256: str,
    *,
    expected_thumbnail_id: int | None,
    alt_text: str,
    confirmed: bool = False,
    manage_task_state: bool = True,
    outcome_callback=None,
    validation_plan: dict | None = None,
    task_action: str = "replace-featured-image",
    task_baseline_extra: dict | None = None,
    approval_kind: str | None = None,
    approval_evidence_sha256: str | None = None,
) -> dict:
    """Replace only ``_thumbnail_id`` while preserving post body/SEO/URL/status."""
    if not confirmed or not isinstance(post_id, int) or post_id <= 0:
        raise ValueError("specific_featured_image_confirmation_required")
    if not re.fullmatch(r"[0-9a-f]{64}", expected_content_sha256 or ""):
        raise ValueError("original_content_sha256_required")
    if expected_thumbnail_id is not None and (
            not isinstance(expected_thumbnail_id, int) or expected_thumbnail_id <= 0):
        raise ValueError("expected_thumbnail_id_required")
    alt_text = (alt_text or "").strip()
    if not alt_text or len(alt_text) > 180 or "\x00" in alt_text:
        raise ValueError("featured_image_alt_text_required")
    image_info = validate_featured_image_file(image_path)
    image_path = Path(image_info["path"])

    lock = acquire_editorial_lock(ROOT)

    base = ["sudo", "docker", "exec", "wordpress_app", "wp"]
    state_started = False
    try:
        fields = ["post_status", "post_title", "post_name", "post_content", "post_excerpt"]
        live = get_post(base, post_id, fields=fields)
        if live.get("post_status") not in ALLOWED_POST_STATUSES or not verify_cas(
            live, content_sha=expected_content_sha256
        ):
            raise ValueError("target_missing_or_modified")
        publish_binding = None
        if approval_kind is not None:
            if not re.fullmatch(r"[0-9a-f]{64}", approval_evidence_sha256 or ""):
                raise ValueError("image_approval_evidence_required")
            publish_binding = reviewed_binding_for_post(
                post_id, expected_content_sha256, live.get("post_title", ""))
        before_thumb = _read_post_meta(base, post_id, "_thumbnail_id")
        expected_thumb_text = None if expected_thumbnail_id is None else str(expected_thumbnail_id)
        if before_thumb != expected_thumb_text:
            raise ValueError("featured_image_changed_before_replacement")
        qa_requirements = []
        if manage_task_state:
            if validation_plan is None:
                from agents.validation_router import build_validation_plan
                validation_plan = build_validation_plan(
                    None, None, image_changed=True,
                    target_status=live.get("post_status", "draft"), route="image-only",
                    post_id=post_id, expected_content_sha256=expected_content_sha256)
            task_baseline = {
                "expected_content_sha256": expected_content_sha256,
                "status": live.get("post_status"),
                "title": live.get("post_title"),
                "post_name": live.get("post_name"),
                "thumbnail_id": before_thumb,
            }
            if task_baseline_extra:
                task_baseline.update(task_baseline_extra)
            start_task_state(
                post_id,
                action=task_action,
                edit_intent="대표이미지만 교체하고 본문, URL, 상태, SEO 메타데이터는 보존",
                baseline=task_baseline,
                reuse={
                    "content_unchanged": True,
                    "source_validation_skipped": True,
                    "semantic_review_skipped": True,
                    "reason": "image_only_post_content_unchanged",
                },
                artifacts={"image_path": str(image_path)},
                qa_requirements=qa_requirements,
                validation_plan=validation_plan,
                completion_requirements=completion_requirements_for_task(
                    image_changed=True, qa_requirements=qa_requirements),
            )
            state_started = True
            update_task_state(
                post_id,
                completed=[
                    "baseline_read", "route_selected", "source_validation", "content_review",
                    "image_validated", "content_saved",
                ],
                route="image-only",
            )
        increment("edit_route_image_only")
        increment("validation_skipped_image_only")

        backup = backup_json(
            ROOT,
            "featured-image-edit",
            post_id,
            {
                "post": live,
                "thumbnail_id": before_thumb,
                "replacement_image": image_info,
            },
        )

        def record_outcome(payload):
            if manage_task_state:
                update_task_state(post_id, checkpoints={"image_outcome": payload})
            if outcome_callback is not None:
                outcome_callback(payload)

        if _read_post_meta(base, post_id, "_thumbnail_id") != expected_thumb_text:
            raise ValueError(f"featured_image_changed_before_import: backup {backup}")

        remote_image = f"/tmp/editorial_cover_{post_id}{image_path.suffix.lower()}"
        run_wordpress(
            ["sudo", "docker", "cp", str(image_path), f"wordpress_app:{remote_image}"],
            capture_output=True,
            check=True,
        )
        try:
            if manage_task_state:
                update_task_state(
                    post_id,
                    checkpoints={"image_import_attempt": {
                        "image_sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
                        "expected_thumbnail_id": expected_thumbnail_id,
                        "started": True,
                    }},
                )
            with timed("image_upload"):
                imported = run_wordpress(
                    base + [
                        "media",
                        "import",
                        remote_image,
                        f"--post_id={post_id}",
                        f"--title={live['post_title']}",
                        f"--alt={alt_text}",
                        "--porcelain",
                        "--allow-root",
                    ],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="strict",
                    check=True,
                )
            attachment_id = (imported.stdout or "").lstrip("\ufeff").strip()
        finally:
            run_wordpress(
                ["sudo", "docker", "exec", "wordpress_app", "rm", "-f", remote_image],
                capture_output=True,
                check=False,
            )
        if not attachment_id.isdigit():
            raise ValueError("featured_image_attachment_id_missing")

        outcome = {
            "attachment_id": int(attachment_id),
            "expected_thumbnail_id": expected_thumbnail_id,
            "image_sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
            "alt_text_sha256": hashlib.sha256(alt_text.encode("utf-8")).hexdigest(),
            "content_sha256": expected_content_sha256,
            "preserved_post": {
                key: live.get(key, "")
                for key in ("post_status", "post_title", "post_name", "post_excerpt")
            },
            "backup": str(backup),
            "verified": False,
        }
        record_outcome(outcome)

        thumbnail = guarded_set_post_thumbnail(
            base,
            post_id,
            expected={
                "post_status": live["post_status"],
                "post_title": live["post_title"],
                "post_name": live["post_name"],
                "post_excerpt": live.get("post_excerpt", ""),
                "content_sha256": expected_content_sha256,
            },
            expected_thumbnail_id=expected_thumbnail_id,
            attachment_id=int(attachment_id),
        )
        saved = thumbnail["post"]
        observed_thumb = thumbnail["thumbnail_id"]
        attachment = get_post(
            base,
            int(attachment_id),
            fields=["ID", "guid", "post_title", "post_mime_type"],
        )
        observed_alt = _read_post_meta(base, int(attachment_id), "_wp_attachment_image_alt")

        preserved = ("post_status", "post_title", "post_name", "post_content", "post_excerpt")
        if any(saved.get(key) != live.get(key) for key in preserved):
            raise ValueError(f"featured_image_post_preservation_failed: recover from {backup}")
        if observed_thumb != attachment_id:
            raise ValueError(f"featured_image_save_verification_failed: recover from {backup}")
        if observed_alt != alt_text:
            raise ValueError(f"featured_image_alt_verification_failed: recover from {backup}")
        if not str(attachment.get("post_mime_type", "")).startswith("image/"):
            raise ValueError(f"featured_image_attachment_verification_failed: recover from {backup}")
        guid = str(attachment.get("guid", ""))
        if not guid.startswith(("https://", "http://")):
            raise ValueError(f"featured_image_url_verification_failed: recover from {backup}")
        outcome = {**outcome, "verified": True, "attachment_url": guid}
        record_outcome(outcome)

        publish_attestation = None
        if publish_binding is not None:
            publish_attestation = record_publish_attestation(
                base,
                post_id,
                content_sha256=expected_content_sha256,
                review_digest=publish_binding["review_digest"],
                title_sha256=publish_binding["title_sha256"],
                thumbnail_id=int(attachment_id),
                image_path=image_path,
                alt_text=alt_text,
                approval_kind=approval_kind,
                approval_evidence_sha256=approval_evidence_sha256,
                expires_at_gmt=publish_binding["expires_at_gmt"],
            )

        if manage_task_state:
            state = update_task_state(
                post_id,
                completed=["image_saved", "wordpress_saved"],
                status="saved_pending_qa" if qa_requirements else "in_progress",
                result={
                    "post_id": post_id,
                    "attachment_id": int(attachment_id),
                    "attachment_url": guid,
                    "alt_text": alt_text,
                    "image": image_info,
                    "backup": str(backup),
                    "publish_attestation": publish_attestation,
                },
            )
            if not qa_requirements and load_task_state(post_id) is not None:
                complete_task_state(post_id)
        return {
            "post_id": post_id,
            "status": saved.get("post_status"),
            "attachment_id": int(attachment_id),
            "attachment_url": guid,
            "alt_text": alt_text,
            "image": image_info,
            "backup": str(backup),
            "publish_attestation": publish_attestation,
        }
    except Exception as exc:
        if state_started:
            fail_task_state(post_id, exc)
        raise
    finally:
        release_editorial_lock(lock)


def _quick_attempt_key(
    post_id: int,
    image_path: Path,
    alt_text: str,
    expected_content_sha256: str,
) -> str:
    digest = hashlib.sha256()
    digest.update(str(int(post_id)).encode("ascii"))
    digest.update(b"\0")
    digest.update(hashlib.sha256(image_path.read_bytes()).digest())
    digest.update(b"\0")
    digest.update(alt_text.encode("utf-8"))
    digest.update(b"\0")
    digest.update(expected_content_sha256.encode("ascii"))
    return digest.hexdigest()


def _advance_matching_after_image_checkpoint(
    post_id: int,
    *,
    expected_content_sha256: str,
    expected_thumbnail_id: int,
    image_path: Path,
    result: dict,
) -> None:
    checkpoint = load_after_image_checkpoint(post_id)
    if not checkpoint:
        return
    if (checkpoint.get("expected_content_sha256") != expected_content_sha256
            or checkpoint.get("expected_thumbnail_id") != expected_thumbnail_id):
        return
    update_after_image_checkpoint(
        post_id,
        completed_steps=[
            "image_generated",
            "image_saved_or_handed_off",
            "uploaded",
            "featured_image_set",
            "readback_verified",
            "content_sha_preserved",
        ],
        target_image_handle=str(image_path),
        result={
            "attachment_id": result.get("attachment_id"),
            "attachment_url": result.get("attachment_url"),
        },
    )


def replace_featured_image_from_live_baseline(
    post_id: int,
    image_path: Path | str,
    *,
    alt_text: str,
    confirmed: bool = False,
    approval_kind: str | None = None,
    approval_evidence_sha256: str | None = None,
) -> dict:
    """Canonical image-only path: read live CAS baseline and enforce retry budget."""
    if not confirmed or not isinstance(post_id, int) or post_id <= 0:
        raise ValueError("specific_featured_image_confirmation_required")
    alt_text = (alt_text or "").strip()
    if not alt_text or len(alt_text) > 180 or "\x00" in alt_text:
        raise ValueError("featured_image_alt_text_required")
    image_info = validate_featured_image_file(image_path)
    image_path = Path(image_info["path"])

    base = ["sudo", "docker", "exec", "wordpress_app", "wp"]
    fields = ["post_status", "post_title", "post_name", "post_content", "post_excerpt"]
    live = get_post(base, post_id, fields=fields)
    if live.get("post_status") not in ALLOWED_POST_STATUSES:
        raise ValueError("target_missing_or_modified")
    expected_content_sha256 = content_sha256(live.get("post_content", ""))
    before_thumb = _read_post_meta(base, post_id, "_thumbnail_id")
    if before_thumb is None:
        expected_thumbnail_id = None
    elif before_thumb.isdigit() and int(before_thumb) > 0:
        expected_thumbnail_id = int(before_thumb)
    else:
        raise ValueError("expected_thumbnail_id_required")
    attempt_key = _quick_attempt_key(
        post_id, image_path, alt_text, expected_content_sha256)

    def attest_existing(result: dict) -> dict:
        if approval_kind is None:
            return result
        if not re.fullmatch(r"[0-9a-f]{64}", approval_evidence_sha256 or ""):
            raise ValueError("image_approval_evidence_required")
        attachment_id = result.get("attachment_id")
        if type(attachment_id) is not int or attachment_id <= 0 or attachment_id != expected_thumbnail_id:
            raise ValueError("quick_image_saved_thumbnail_conflict")
        binding = reviewed_binding_for_post(
            post_id, expected_content_sha256, live.get("post_title", ""))
        attestation = record_publish_attestation(
            base,
            post_id,
            content_sha256=expected_content_sha256,
            review_digest=binding["review_digest"],
            title_sha256=binding["title_sha256"],
            thumbnail_id=attachment_id,
            image_path=image_path,
            alt_text=alt_text,
            approval_kind=approval_kind,
            approval_evidence_sha256=approval_evidence_sha256,
            expires_at_gmt=binding["expires_at_gmt"],
        )
        return {**result, "publish_attestation": attestation}

    previous = load_task_state(post_id)
    attempt_number = 1
    if previous and previous.get("action") in {"replace-featured-image", "quick-image-replace"}:
        previous_baseline = previous.get("baseline") or {}
        same_attempt = previous_baseline.get("attempt_key") == attempt_key
        if same_attempt and previous.get("status") == "saved_pending_qa":
            result = dict(previous.get("result") or {})
            expected_saved_thumb = result.get("attachment_id")
            if type(expected_saved_thumb) is not int or expected_thumbnail_id != expected_saved_thumb:
                raise ValueError("quick_image_saved_thumbnail_conflict")
            result.update({
                "post_id": post_id,
                "status": live.get("post_status"),
                "already_saved_pending_qa": True,
                "attempt_number": previous_baseline.get("attempt_number", 1),
            })
            return attest_existing(result)
        if same_attempt and previous.get("status") == "complete":
            result = dict(previous.get("result") or {})
            expected_saved_thumb = result.get("attachment_id")
            if type(expected_saved_thumb) is not int or expected_thumbnail_id != expected_saved_thumb:
                raise ValueError("quick_image_saved_thumbnail_conflict")
            result.update({
                "post_id": post_id,
                "status": live.get("post_status"),
                "already_complete": True,
                "attempt_number": previous_baseline.get("attempt_number", 1),
            })
            return attest_existing(result)
        if same_attempt and previous.get("status") in {"failed", "blocked"}:
            previous_thumbnail_id = previous_baseline.get("thumbnail_id")
            checkpoint = (previous.get("checkpoints") or {}).get("image_outcome") or {}
            if checkpoint.get("attachment_id"):
                reconciled = reconcile_featured_image_outcome(post_id, checkpoint, alt_text)
                if reconciled:
                    update_task_state(
                        post_id,
                        completed=["image_saved", "wordpress_saved"],
                        status="saved_pending_qa",
                        result={**reconciled, "attempt_number": previous_baseline.get("attempt_number", 1)},
                    )
                    _advance_matching_after_image_checkpoint(
                        post_id,
                        expected_content_sha256=expected_content_sha256,
                        expected_thumbnail_id=int(previous_thumbnail_id),
                        image_path=image_path,
                        result=reconciled,
                    )
                    return {**reconciled, "attempt_number": previous_baseline.get("attempt_number", 1)}
            import_attempt = (previous.get("checkpoints") or {}).get("image_import_attempt") or {}
            if import_attempt.get("started"):
                raise ValueError("featured_image_import_outcome_ambiguous")
            if previous_thumbnail_id is None:
                previous_expected_thumbnail_id = None
            elif type(previous_thumbnail_id) is str and previous_thumbnail_id.isdigit():
                previous_expected_thumbnail_id = int(previous_thumbnail_id)
            else:
                raise ValueError("quick_image_retry_baseline_missing")
            if expected_thumbnail_id != previous_expected_thumbnail_id:
                raise ValueError("featured_image_changed_since_failed_attempt")
            attempt_number = int(previous_baseline.get("attempt_number") or 1) + 1
            if attempt_number > SIMPLE_TASK_MAX_ATTEMPTS:
                raise ValueError("simple_task_retry_budget_exhausted")

    result = replace_featured_image(
        post_id,
        image_path,
        expected_content_sha256,
        expected_thumbnail_id=expected_thumbnail_id,
        alt_text=alt_text,
        confirmed=True,
        approval_kind=approval_kind,
        approval_evidence_sha256=approval_evidence_sha256,
        task_action="replace-featured-image",
        task_baseline_extra={
            "attempt_key": attempt_key,
            "attempt_number": attempt_number,
        },
    )
    result = {
        **result,
        "attempt_number": attempt_number,
        "baseline_content_sha256": expected_content_sha256,
        "replaced_thumbnail_id": expected_thumbnail_id,
    }
    _advance_matching_after_image_checkpoint(
        post_id,
        expected_content_sha256=expected_content_sha256,
        expected_thumbnail_id=expected_thumbnail_id,
        image_path=image_path,
        result=result,
    )
    return result


def quick_replace_featured_image(
    post_id: int,
    image_path: Path | str,
    *,
    alt_text: str,
    confirmed: bool = False,
    approval_kind: str | None = None,
    approval_evidence_sha256: str | None = None,
) -> dict:
    """Legacy alias for :func:`replace_featured_image_from_live_baseline`."""
    return replace_featured_image_from_live_baseline(
        post_id,
        image_path,
        alt_text=alt_text,
        confirmed=confirmed,
        approval_kind=approval_kind,
        approval_evidence_sha256=approval_evidence_sha256,
    )
