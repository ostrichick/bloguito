"""Image-only featured-image replacement with WordPress preservation checks."""

from __future__ import annotations

import json
import hashlib
import re
import subprocess
from pathlib import Path

from PIL import Image

from agents.editorial import ROOT
from agents.editorial_updater import RANK_MATH_META_KEYS
from agents.task_state import fail_task_state, start_task_state, update_task_state
from agents.wordpress_mutation import backup_json, content_sha256, get_post, verify_cas
from agents.designer import FEATURED_IMAGE_POLICY
from agents.qa_scope import qa_requirements_for_edit
from agents.workflow_metrics import increment


ALLOWED_POST_STATUSES = {"publish", "draft", "pending", "future", "private"}
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


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
    result = subprocess.run(
        list(base) + ["post", "meta", "get", str(int(post_id)), key, "--allow-root"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        return (result.stdout or "").lstrip("\ufeff").rstrip("\r\n")
    stderr = (result.stderr or "").lower()
    if result.returncode == 1 and "could not find the specified post meta field" in stderr:
        return None
    raise subprocess.CalledProcessError(
        result.returncode, result.args, output=result.stdout, stderr=result.stderr
    )


def _rank_math_meta(base, post_id: int) -> dict[str, str | None]:
    return {key: _read_post_meta(base, post_id, key) for key in RANK_MATH_META_KEYS}


def reconcile_featured_image_outcome(post_id: int, checkpoint: dict, alt_text: str) -> dict | None:
    """Verify a previously imported attachment without importing a second copy."""
    if not isinstance(checkpoint, dict) or not checkpoint.get("attachment_id"):
        return None
    attachment_id = int(checkpoint["attachment_id"])
    base = ["sudo", "docker", "exec", "wordpress_app", "wp"]
    observed_thumb = _read_post_meta(base, post_id, "_thumbnail_id")
    if observed_thumb != str(attachment_id):
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
    if _rank_math_meta(base, post_id) != checkpoint.get("before_rank_math"):
        raise ValueError("featured_image_resume_seo_conflict")
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


def replace_featured_image(
    post_id: int,
    image_path: Path | str,
    expected_content_sha256: str,
    *,
    expected_thumbnail_id: int,
    alt_text: str,
    confirmed: bool = False,
    manage_task_state: bool = True,
    outcome_callback=None,
    validation_plan: dict | None = None,
) -> dict:
    """Replace only ``_thumbnail_id`` while preserving post body/SEO/URL/status."""
    if not confirmed or not isinstance(post_id, int) or post_id <= 0:
        raise ValueError("specific_featured_image_confirmation_required")
    if not re.fullmatch(r"[0-9a-f]{64}", expected_content_sha256 or ""):
        raise ValueError("original_content_sha256_required")
    if not isinstance(expected_thumbnail_id, int) or expected_thumbnail_id <= 0:
        raise ValueError("expected_thumbnail_id_required")
    alt_text = (alt_text or "").strip()
    if not alt_text or len(alt_text) > 180 or "\x00" in alt_text:
        raise ValueError("featured_image_alt_text_required")
    image_info = validate_featured_image_file(image_path)
    image_path = Path(image_info["path"])

    lock = ROOT / "data" / ".editorial-publish.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        lock.mkdir()
    except FileExistsError:
        raise ValueError("editorial_publication_busy: inspect the existing job")

    base = ["sudo", "docker", "exec", "wordpress_app", "wp"]
    state_started = False
    try:
        fields = ["post_status", "post_title", "post_name", "post_content", "post_excerpt"]
        live = get_post(base, post_id, fields=fields)
        if live.get("post_status") not in ALLOWED_POST_STATUSES or not verify_cas(
            live, content_sha=expected_content_sha256
        ):
            raise ValueError("target_missing_or_modified")
        before_thumb = _read_post_meta(base, post_id, "_thumbnail_id")
        if before_thumb != str(expected_thumbnail_id):
            raise ValueError("featured_image_changed_before_replacement")
        before_rank_math = _rank_math_meta(base, post_id)
        if manage_task_state:
            if validation_plan is None:
                from agents.validation_router import build_validation_plan
                validation_plan = build_validation_plan(
                    None, None, image_changed=True,
                    target_status=live.get("post_status", "draft"), route="image-only",
                    post_id=post_id, expected_content_sha256=expected_content_sha256)
            start_task_state(
                post_id,
                action="replace-featured-image",
                edit_intent="대표이미지만 교체하고 본문, URL, 상태, SEO 메타데이터는 보존",
                baseline={
                    "expected_content_sha256": expected_content_sha256,
                    "status": live.get("post_status"),
                    "title": live.get("post_title"),
                    "post_name": live.get("post_name"),
                    "thumbnail_id": before_thumb,
                },
                reuse={
                    "content_unchanged": True,
                    "source_validation_skipped": True,
                    "semantic_review_skipped": True,
                    "reason": "image_only_post_content_unchanged",
                },
                artifacts={"image_path": str(image_path)},
                qa_requirements=qa_requirements_for_edit(
                    None, None, image_changed=True, target_status=live.get("post_status", "draft")),
                validation_plan=validation_plan,
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
                "rank_math_meta": before_rank_math,
                "replacement_image": image_info,
            },
        )

        def record_outcome(payload):
            if manage_task_state:
                update_task_state(post_id, checkpoints={"image_outcome": payload})
            if outcome_callback is not None:
                outcome_callback(payload)

        if _read_post_meta(base, post_id, "_thumbnail_id") != str(expected_thumbnail_id):
            raise ValueError(f"featured_image_changed_before_import: backup {backup}")

        remote_image = f"/tmp/editorial_cover_{post_id}{image_path.suffix.lower()}"
        subprocess.run(
            ["sudo", "docker", "cp", str(image_path), f"wordpress_app:{remote_image}"],
            capture_output=True,
            check=True,
        )
        try:
            imported = subprocess.run(
                base + [
                    "media",
                    "import",
                    remote_image,
                    f"--post_id={post_id}",
                    "--featured_image",
                    f"--title={live['post_title']}",
                    f"--alt={alt_text}",
                    "--porcelain",
                    "--allow-root",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            attachment_id = (imported.stdout or "").strip()
        finally:
            subprocess.run(
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
            "before_rank_math": before_rank_math,
            "backup": str(backup),
            "verified": False,
        }
        record_outcome(outcome)

        observed_thumb = _read_post_meta(base, post_id, "_thumbnail_id")
        saved = get_post(base, post_id, fields=fields)
        after_rank_math = _rank_math_meta(base, post_id)
        attachment = get_post(
            base,
            int(attachment_id),
            fields=["ID", "guid", "post_title", "post_mime_type"],
        )
        observed_alt = _read_post_meta(base, int(attachment_id), "_wp_attachment_image_alt")

        preserved = ("post_status", "post_title", "post_name", "post_content", "post_excerpt")
        if any(saved.get(key) != live.get(key) for key in preserved):
            raise ValueError(f"featured_image_post_preservation_failed: recover from {backup}")
        if after_rank_math != before_rank_math:
            raise ValueError(f"featured_image_seo_preservation_failed: recover from {backup}")
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

        if manage_task_state:
            update_task_state(
                post_id,
                completed=["image_saved", "wordpress_saved"],
                status="saved_pending_qa",
                result={
                    "post_id": post_id,
                    "attachment_id": int(attachment_id),
                    "attachment_url": guid,
                    "alt_text": alt_text,
                    "image": image_info,
                    "backup": str(backup),
                },
            )
        return {
            "post_id": post_id,
            "status": saved.get("post_status"),
            "attachment_id": int(attachment_id),
            "attachment_url": guid,
            "alt_text": alt_text,
            "image": image_info,
            "backup": str(backup),
        }
    except Exception as exc:
        if state_started:
            fail_task_state(post_id, exc)
        raise
    finally:
        lock.rmdir()
