"""Image-only featured-image replacement with WordPress preservation checks."""

from __future__ import annotations

import json
import hashlib
import io
import re
import subprocess
import time
from datetime import datetime
from agents.wordpress_transport import run_wordpress
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps

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
    acquire_featured_image_lock,
    backup_json,
    content_sha256,
    find_attachment_ids_by_sha,
    get_post,
    guarded_set_post_thumbnail,
    guarded_update_featured_image_alt,
    release_featured_image_lock,
    set_featured_image_import_pending,
    verify_cas,
)
from agents.designer import FEATURED_IMAGE_POLICY
from agents.workflow_metrics import increment, timed


ALLOWED_POST_STATUSES = {"publish", "draft", "pending", "future", "private"}
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_SOURCE_FORMATS = {"JPEG", "PNG", "WEBP"}
NEAR_TARGET_ASPECT_RELATIVE_ERROR = 0.003
SIMPLE_TASK_MAX_ATTEMPTS = 2
FEATURED_IMAGE_PIPELINE_BUDGET_SECONDS = 180
FEATURED_IMAGE_REMOTE_LOCK_TTL_SECONDS = 300
FEATURED_IMAGE_LOCK_TIMEOUT_SECONDS = 15
FEATURED_IMAGE_COPY_TIMEOUT_SECONDS = 30
FEATURED_IMAGE_READ_TIMEOUT_SECONDS = 30
FEATURED_IMAGE_IMPORT_TIMEOUT_SECONDS = 90
FEATURED_IMAGE_CLEANUP_TIMEOUT_SECONDS = 15


class _FeaturedImageBudget:
    def __init__(self, total_seconds: int = FEATURED_IMAGE_PIPELINE_BUDGET_SECONDS):
        self.started = time.monotonic()
        self.deadline = self.started + total_seconds

    def timeout(self, maximum: int, stage: str) -> float:
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(f"featured_image_pipeline_budget_exhausted:{stage}")
        return min(float(maximum), remaining)

    def elapsed_ms(self) -> int:
        return int((time.monotonic() - self.started) * 1000)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_manual_image_upload_lineage(
    image_path: Path | str,
    candidate_manifest: Path | str | None,
    selected_candidate: int | None,
    selection_mode: str | None,
) -> dict:
    """Fail closed on accidental local substitute/stale candidate upload.

    Provenance tool names in a JSON file are *claims*, not cryptographic
    attestation. The actual image_gen and CoS save_image tool calls must also
    be visible in the task record. This validator enforces byte continuity
    between those saved candidate bytes, manifest, stage receipt and upload.
    """
    if not candidate_manifest or selected_candidate is None or not selection_mode:
        raise ValueError("manual_cover_requires_candidate_manifest_selection_and_mode")
    if type(selected_candidate) is not int or selected_candidate < 1:
        raise ValueError("invalid_selected_candidate")
    if selection_mode not in {"user", "agent-delegated"}:
        raise ValueError("invalid_candidate_selection_mode")
    staged = Path(image_path).resolve()
    manifest_path = Path(candidate_manifest).resolve()
    stage_path = staged.with_suffix(staged.suffix + ".stage.json")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        stage = json.loads(stage_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise ValueError("manual_cover_missing_valid_stage_or_manifest") from exc
    expected_origin = {
        "generator_tool": "image_gen.text2im",
        "save_tool": "cos_core.save_image",
    }
    if (not isinstance(manifest, dict)
            or manifest.get("version") != 2
            or manifest.get("origin_claim") != expected_origin
            or not isinstance(manifest.get("candidates"), list)):
        raise ValueError("manual_cover_chatgpt_origin_claim_required")
    entries = [
        entry for entry in manifest["candidates"]
        if isinstance(entry, dict) and entry.get("candidate_number") == selected_candidate
    ]
    if len(entries) != 1:
        raise ValueError("selected_candidate_not_sealed")
    entry = entries[0]
    try:
        original = Path(entry["path"]).resolve()
        original_sha = _sha256_file(original)
        staged_sha = _sha256_file(staged)
    except (KeyError, OSError, TypeError) as exc:
        raise ValueError("manual_cover_lineage_file_missing") from exc
    if entry.get("sha256") != original_sha:
        raise ValueError("candidate_sha_conflict")
    expected_stage = {
        "source_path": str(original),
        "source_sha256": original_sha,
        "output_path": str(staged),
        "output_sha256": staged_sha,
        "candidate_manifest": str(manifest_path),
        "candidate_number": selected_candidate,
        "selection_mode": selection_mode,
        "sealed_source_sha256": original_sha,
        "origin_claim": expected_origin,
    }
    if not isinstance(stage, dict) or any(stage.get(k) != v for k, v in expected_stage.items()):
        raise ValueError("manual_cover_lineage_receipt_mismatch")
    with Image.open(staged) as decoded:
        if decoded.size != (1200, 675):
            raise ValueError("manual_cover_stage_size_invalid")
    return {
        "candidate_number": selected_candidate,
        "selection_mode": selection_mode,
        "source_sha256": original_sha,
        "staged_sha256": staged_sha,
        "staged_path": str(staged),
    }


def _fit_featured_image_without_subject_crop(
    image: Image.Image,
    width: int,
    height: int,
) -> Image.Image:
    source_ratio = image.width / image.height
    target_ratio = width / height
    relative_error = abs(source_ratio - target_ratio) / target_ratio
    if relative_error <= NEAR_TARGET_ASPECT_RELATIVE_ERROR:
        return image.resize((width, height), Image.Resampling.LANCZOS)
    background = ImageOps.fit(image, (width, height), method=Image.Resampling.LANCZOS)
    background = background.filter(ImageFilter.GaussianBlur(radius=20))
    foreground = ImageOps.contain(image, (width, height), method=Image.Resampling.LANCZOS)
    x = (width - foreground.width) // 2
    y = (height - foreground.height) // 2
    background.paste(foreground, (x, y))
    return background


def stage_featured_image(
    source_path: Path | str,
    output_path: Path | str,
    *,
    expected_source_sha256: str | None = None,
) -> dict:
    """Decode and normalize one selected ChatGPT/CoS image for WordPress upload."""
    source = Path(source_path).resolve()
    output = Path(output_path).resolve()
    if not source.is_file() or source.stat().st_size <= 0:
        raise ValueError("featured_image_stage_source_required")
    if output.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise ValueError("featured_image_stage_output_extension_invalid")
    if source == output:
        raise ValueError("featured_image_stage_output_must_differ")

    source_bytes = source.read_bytes()
    source_sha256 = hashlib.sha256(source_bytes).hexdigest()
    if expected_source_sha256 is not None and source_sha256 != expected_source_sha256:
        raise ValueError("candidate_sha_conflict")
    try:
        with Image.open(io.BytesIO(source_bytes)) as probe:
            probe.verify()
        with Image.open(io.BytesIO(source_bytes)) as opened:
            source_format = str(opened.format or "").upper()
            if source_format not in ALLOWED_SOURCE_FORMATS:
                raise ValueError("featured_image_stage_source_format_invalid")
            image = ImageOps.exif_transpose(opened).convert("RGB")
            source_size = image.size
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("featured_image_stage_decode_failed") from exc

    canvas = FEATURED_IMAGE_POLICY.get("canvas", {})
    width = int(canvas.get("width", 1200))
    height = int(canvas.get("height", 675))
    staged = _fit_featured_image_without_subject_crop(image, width, height)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".tmp")
    suffix = output.suffix.lower()
    if suffix == ".png":
        staged.save(temporary, format="PNG", optimize=True)
    elif suffix in {".jpg", ".jpeg"}:
        staged.save(temporary, format="JPEG", quality=95, optimize=True)
    else:
        staged.save(temporary, format="WEBP", quality=95, method=6)
    if expected_source_sha256 is not None and _sha256_file(source) != expected_source_sha256:
        temporary.unlink(missing_ok=True)
        raise ValueError("candidate_changed_during_staging")
    temporary.replace(output)

    try:
        with Image.open(output) as verified:
            verified.verify()
        with Image.open(output) as verified:
            staged_size = verified.size
            staged_format = str(verified.format or "").upper()
    except Exception as exc:
        raise ValueError("featured_image_stage_output_decode_failed") from exc
    if staged_size != (width, height):
        raise ValueError("featured_image_stage_output_size_invalid")

    return {
        "source_path": str(source),
        "source_sha256": source_sha256,
        "source_format": source_format,
        "source_width": source_size[0],
        "source_height": source_size[1],
        "output_path": str(output),
        "output_sha256": _sha256_file(output),
        "output_format": staged_format,
        "output_width": staged_size[0],
        "output_height": staged_size[1],
        "policy_version": FEATURED_IMAGE_POLICY.get("version", 1),
    }


def validate_featured_image_file(image_path: Path | str) -> dict:
    path = Path(image_path).resolve()
    if not path.is_file() or path.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise ValueError("reviewed_featured_image_required")
    if path.stat().st_size <= 0:
        raise ValueError("featured_image_empty")
    initial_sha256 = _sha256_file(path)
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
    if _sha256_file(path) != initial_sha256:
        raise ValueError("featured_image_changed_during_validation")
    expected_format = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG", ".webp": "WEBP"}[path.suffix.lower()]
    if image_format != expected_format:
        raise ValueError("featured_image_extension_format_mismatch")
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
        "sha256": initial_sha256,
        "policy_version": FEATURED_IMAGE_POLICY.get("version", 2),
        "safe_margin_percent": FEATURED_IMAGE_POLICY.get("composition", {}).get("safe_margin_percent", 8),
    }


def _read_post_meta(base, post_id: int, key: str, *, timeout=None) -> str | None:
    with timed("wp_meta_read"):
        increment("wp_roundtrips")
        kwargs = dict(
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="strict",
            check=False,
        )
        if timeout is not None:
            kwargs["timeout"] = timeout
        result = run_wordpress(
            list(base) + ["post", "meta", "get", str(int(post_id)), key, "--allow-root"],
            **kwargs,
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


def _reconcile_featured_image_outcome_under_lock(
    post_id: int,
    checkpoint: dict,
    alt_text: str,
    *,
    budget: _FeaturedImageBudget | None = None,
) -> dict | None:
    """Verify a previously imported attachment without importing a second copy."""
    if not isinstance(checkpoint, dict) or not checkpoint.get("attachment_id"):
        return None
    if checkpoint.get("import_fence_started") and not checkpoint.get("import_termination_confirmed"):
        raise ValueError("featured_image_import_process_termination_unknown")
    budget = budget or _FeaturedImageBudget(90)
    attachment_id = int(checkpoint["attachment_id"])
    base = ["sudo", "docker", "exec", "wordpress_app", "wp"]
    observed_thumb = _read_post_meta(
        base, post_id, "_thumbnail_id",
        timeout=budget.timeout(FEATURED_IMAGE_READ_TIMEOUT_SECONDS, "resume_thumbnail_read"))
    expected_thumbnail_id = checkpoint.get("expected_thumbnail_id")
    if expected_thumbnail_id is not None and (
            type(expected_thumbnail_id) is not int or expected_thumbnail_id <= 0):
        raise ValueError("featured_image_resume_thumbnail_conflict")
    expected_thumb_text = None if expected_thumbnail_id is None else str(expected_thumbnail_id)
    attachment_thumb_text = str(attachment_id)
    if observed_thumb not in {attachment_thumb_text, expected_thumb_text}:
        raise ValueError("featured_image_resume_thumbnail_conflict")
    fields = ["post_status", "post_title", "post_name", "post_content", "post_excerpt"]
    saved = get_post(
        base, post_id, fields=fields,
        timeout=budget.timeout(FEATURED_IMAGE_READ_TIMEOUT_SECONDS, "resume_post_read"))
    expected_post = checkpoint.get("preserved_post") or {}
    if (saved.get("post_status") != expected_post.get("post_status")
            or saved.get("post_title") != expected_post.get("post_title")
            or saved.get("post_name") != expected_post.get("post_name")
            or saved.get("post_excerpt", "") != expected_post.get("post_excerpt", "")
            or content_sha256(saved.get("post_content", "")) != checkpoint.get("content_sha256")):
        raise ValueError("featured_image_resume_post_conflict")
    expected_image_sha = checkpoint.get("image_sha256")
    if (not isinstance(expected_image_sha, str)
            or not re.fullmatch(r"[0-9a-f]{64}", expected_image_sha)):
        raise ValueError("featured_image_resume_sha_required")
    matching_ids = find_attachment_ids_by_sha(
        base, post_id, expected_image_sha,
        timeout=budget.timeout(FEATURED_IMAGE_READ_TIMEOUT_SECONDS, "resume_sha_verify"))
    if attachment_id not in matching_ids:
        raise ValueError("featured_image_resume_sha_conflict")
    attachment = get_post(
        base, attachment_id, fields=["ID", "guid", "post_title", "post_mime_type"],
        timeout=budget.timeout(FEATURED_IMAGE_READ_TIMEOUT_SECONDS, "resume_attachment_read"))
    observed_alt = _read_post_meta(
        base, attachment_id, "_wp_attachment_image_alt",
        timeout=budget.timeout(FEATURED_IMAGE_READ_TIMEOUT_SECONDS, "resume_alt_read"))
    if observed_alt != alt_text:
        raise ValueError("featured_image_resume_alt_conflict")
    if not str(attachment.get("post_mime_type", "")).startswith("image/"):
        raise ValueError("featured_image_resume_attachment_conflict")
    guid = str(attachment.get("guid", ""))
    if not guid.startswith(("https://", "http://")):
        raise ValueError("featured_image_resume_url_conflict")
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
        timeout=budget.timeout(FEATURED_IMAGE_READ_TIMEOUT_SECONDS, "resume_thumbnail_cas"),
    )
    saved = mutation["post"]
    if mutation.get("thumbnail_id") != attachment_thumb_text:
        raise ValueError("featured_image_resume_thumbnail_conflict")
    if checkpoint.get("import_fence_started") and checkpoint.get("lock_token"):
        set_featured_image_import_pending(
            base, post_id, checkpoint["lock_token"], pending=False,
            timeout=budget.timeout(FEATURED_IMAGE_LOCK_TIMEOUT_SECONDS, "resume_import_fence_complete"),
        )
    return {
        "post_id": post_id,
        "status": saved.get("post_status"),
        "attachment_id": attachment_id,
        "attachment_url": guid,
        "image_sha256": expected_image_sha,
        "alt_text": alt_text,
        "backup": checkpoint.get("backup"),
        "reconciled": True,
    }


def reconcile_featured_image_outcome(
    post_id: int,
    checkpoint: dict,
    alt_text: str,
    *,
    budget: _FeaturedImageBudget | None = None,
) -> dict | None:
    """Resume an import under the same cross-machine post lock as new uploads."""
    if not isinstance(checkpoint, dict) or not checkpoint.get("attachment_id"):
        return None
    if checkpoint.get("import_fence_started") and not checkpoint.get("import_termination_confirmed"):
        raise ValueError("featured_image_import_process_termination_unknown")
    budget = budget or _FeaturedImageBudget(90)
    base = ["sudo", "docker", "exec", "wordpress_app", "wp"]
    lock = acquire_featured_image_lock(
        base,
        post_id,
        ttl_seconds=FEATURED_IMAGE_REMOTE_LOCK_TTL_SECONDS,
        resume_token=checkpoint.get("lock_token") if checkpoint.get("import_fence_started") else None,
        timeout=budget.timeout(FEATURED_IMAGE_LOCK_TIMEOUT_SECONDS, "resume_remote_lock"),
    )
    try:
        return _reconcile_featured_image_outcome_under_lock(
            post_id, checkpoint, alt_text, budget=budget)
    finally:
        release_featured_image_lock(
            base,
            post_id,
            lock["token"],
            timeout=budget.timeout(FEATURED_IMAGE_LOCK_TIMEOUT_SECONDS, "resume_lock_release"),
        )


def _find_unique_imported_attachment_by_sha(
    post_id: int,
    *,
    image_sha256: str,
    timeout=None,
) -> int | None:
    base = ["sudo", "docker", "exec", "wordpress_app", "wp"]
    matches = find_attachment_ids_by_sha(base, post_id, image_sha256, timeout=timeout)
    if not matches:
        return None
    if len(matches) != 1:
        raise ValueError("featured_image_import_multiple_sha_matches")
    return matches[0]


def _find_new_imported_attachment_by_sha(
    post_id: int,
    *,
    image_sha256: str,
    preexisting_attachment_ids: list[int] | tuple[int, ...],
    timeout=None,
) -> int | None:
    """Resolve exactly one attachment created after the import attempt snapshot."""
    if (not isinstance(preexisting_attachment_ids, (list, tuple))
            or any(type(value) is not int or value <= 0 for value in preexisting_attachment_ids)
            or len(preexisting_attachment_ids) != len(set(preexisting_attachment_ids))):
        raise ValueError("invalid_featured_image_preimport_snapshot")
    base = ["sudo", "docker", "exec", "wordpress_app", "wp"]
    current = find_attachment_ids_by_sha(base, post_id, image_sha256, timeout=timeout)
    previous = set(preexisting_attachment_ids)
    created = [attachment_id for attachment_id in current if attachment_id not in previous]
    if not created:
        return None
    if len(created) != 1:
        raise ValueError("featured_image_import_multiple_new_sha_matches")
    return created[0]


def recover_imported_featured_image_outcome(
    post_id: int,
    *,
    image_sha256: str,
    expected_content_sha256: str,
    expected_thumbnail_id: int | None,
    alt_text: str,
    preexisting_attachment_ids: list[int] | tuple[int, ...] | None = None,
    lock_token: str | None = None,
) -> dict | None:
    """Recover a previously committed media import without issuing another import."""
    budget = _FeaturedImageBudget(90)
    attachment_id = (
        _find_new_imported_attachment_by_sha(
            post_id,
            image_sha256=image_sha256,
            preexisting_attachment_ids=preexisting_attachment_ids,
            timeout=budget.timeout(FEATURED_IMAGE_READ_TIMEOUT_SECONDS, "resume_import_sha_reconcile"),
        )
        if preexisting_attachment_ids is not None
        else _find_unique_imported_attachment_by_sha(
            post_id,
            image_sha256=image_sha256,
            timeout=budget.timeout(FEATURED_IMAGE_READ_TIMEOUT_SECONDS, "resume_import_sha_reconcile"),
        )
    )
    if attachment_id is None:
        return None
    base = ["sudo", "docker", "exec", "wordpress_app", "wp"]
    fields = ["post_status", "post_title", "post_name", "post_content", "post_excerpt"]
    live = get_post(
        base, post_id, fields=fields,
        timeout=budget.timeout(FEATURED_IMAGE_READ_TIMEOUT_SECONDS, "resume_import_post_read"))
    if not verify_cas(live, content_sha=expected_content_sha256):
        raise ValueError("featured_image_resume_post_conflict")
    checkpoint = {
        "attachment_id": attachment_id,
        "expected_thumbnail_id": expected_thumbnail_id,
        "content_sha256": expected_content_sha256,
        "image_sha256": image_sha256,
        "preserved_post": {
            key: live.get(key, "")
            for key in ("post_status", "post_title", "post_name", "post_excerpt")
        },
        "backup": None,
        "lock_token": lock_token,
        "import_fence_started": bool(lock_token),
        "import_termination_confirmed": False,
    }
    return reconcile_featured_image_outcome(post_id, checkpoint, alt_text, budget=budget)


def _failure_receipt_file(post_id: int) -> Path:
    folder = ROOT / "data" / "editorial_runs" / "image-failures"
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S%f")
    return folder / f"featured-image-{int(post_id)}-{stamp}.json"


def _write_featured_image_failure_receipt(
    post_id: int,
    *,
    stage: str,
    error: BaseException,
    image_info: dict,
    expected_content_sha256: str,
    expected_thumbnail_id: int | None,
    budget: _FeaturedImageBudget,
    import_attempted: bool,
    reconcile_attempted: bool,
    attachment_id: int | None,
    remote_image: str,
    preexisting_attachment_ids: list[int] | None = None,
    reconcile_observed_ids: list[int] | None = None,
    cleanup_error: str | None = None,
    lock_release_error: str | None = None,
    cleanup_attempted: bool = False,
    lock_release_attempted: bool = False,
    import_fence_started: bool = False,
    lock_token: str | None = None,
    import_termination_confirmed: bool = False,
) -> Path:
    """Persist the minimum state needed to resume without blind retries."""
    image_path = Path(str(image_info.get("path") or ""))
    stage_receipt = image_path.with_suffix(image_path.suffix + ".stage.json")
    stage_payload = None
    if stage_receipt.is_file():
        try:
            candidate = json.loads(stage_receipt.read_text(encoding="utf-8"))
            if isinstance(candidate, dict):
                staged = Path(str(candidate.get("output_path") or "")).resolve()
                if staged == image_path.resolve() and candidate.get("output_sha256") == image_info.get("sha256"):
                    stage_payload = candidate
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
            stage_payload = None
    if (import_fence_started and not import_termination_confirmed):
        next_action = "inspect_remote_import_process_then_reconcile_without_reimport"
    elif attachment_id is not None:
        next_action = "reconcile_existing_attachment_without_reimport"
    elif import_attempted or import_fence_started:
        next_action = "inspect_remote_import_process_then_reconcile_existing_attachment_do_not_reimport"
    elif stage == "remote_lock_acquire":
        next_action = "inspect_existing_post_lock_then_retry_once_do_not_poll"
    else:
        next_action = "fix_reported_blocker_then_retry_once"
    payload = {
        "version": 1,
        "post_id": int(post_id),
        "stage": stage,
        "error": {
            "type": type(error).__name__,
            "code": re.sub(r"[^A-Za-z0-9_.:-]+", "_", str(error).strip())[:200]
            or "unknown_error",
        },
        "elapsed_ms": budget.elapsed_ms(),
        "original_image_path": stage_payload.get("source_path") if stage_payload else None,
        "staged_image_path": str(image_path),
        "image_sha256": image_info.get("sha256"),
        "stage_receipt_path": str(stage_receipt) if stage_payload is not None else None,
        "image": {
            "path": str(image_path),
            "sha256": image_info.get("sha256"),
            "format": image_info.get("format"),
            "width": image_info.get("width"),
            "height": image_info.get("height"),
            "stage_receipt": str(stage_receipt) if stage_receipt.is_file() else None,
        },
        "expected_content_sha256": expected_content_sha256,
        "expected_thumbnail_id": expected_thumbnail_id,
        "remote_image": remote_image,
        "import_attempted": bool(import_attempted),
        "import_fence_started": bool(import_fence_started),
        "import_termination_confirmed": bool(import_termination_confirmed),
        "lock_token": lock_token if import_fence_started else None,
        "sha_reconcile_attempted": bool(reconcile_attempted),
        "attachment_id": attachment_id,
        "preexisting_attachment_ids": list(preexisting_attachment_ids or []),
        "reconcile_observed_ids": (
            list(reconcile_observed_ids) if reconcile_observed_ids is not None else None
        ),
        "cleanup_error": cleanup_error,
        "lock_release_error": lock_release_error,
        "cleanup_status": (
            "failed" if cleanup_error else "completed" if cleanup_attempted else "not_needed"
        ),
        "lock_release_status": (
            "failed" if lock_release_error else "completed" if lock_release_attempted else "not_acquired"
        ),
        "automatic_media_reimport_allowed": not (import_attempted or import_fence_started),
        "next_recommended_action": next_action,
        "resume": {
            "allowed": image_path.is_file(),
            "next_action": next_action,
            "automatic_media_reimport_allowed": not (import_attempted or import_fence_started),
        },
    }
    target = _failure_receipt_file(post_id)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(target)
    return target


def _annotate_pipeline_error(error: BaseException, *, receipt: Path, stage: str) -> None:
    try:
        setattr(error, "failure_receipt", str(receipt))
        setattr(error, "failure_stage", stage)
    except Exception:
        pass


def _validate_featured_image_with_receipt(
    post_id: int, image_path: Path | str, *,
    expected_content_sha256: str = "", expected_thumbnail_id: int | None = None,
) -> dict:
    try:
        return validate_featured_image_file(image_path)
    except Exception as exc:
        path = Path(image_path).resolve()
        sha = None
        if path.is_file():
            try:
                sha = _sha256_file(path)
            except OSError:
                pass
        receipt = _write_featured_image_failure_receipt(
            post_id, stage="local_validation", error=exc,
            image_info={"path": str(path), "sha256": sha},
            expected_content_sha256=expected_content_sha256,
            expected_thumbnail_id=expected_thumbnail_id,
            budget=_FeaturedImageBudget(), import_attempted=False,
            reconcile_attempted=False, attachment_id=None, remote_image="",
        )
        _annotate_pipeline_error(exc, receipt=receipt, stage="local_validation")
        raise


def hardened_attach_featured_image(
    post_id: int,
    image_path: Path | str,
    expected_content_sha256: str,
    *,
    expected_thumbnail_id: int | None,
    alt_text: str,
    image_info: dict | None = None,
    preserved_post: dict | None = None,
    backup: str | Path | None = None,
    import_attempt_callback=None,
    outcome_callback=None,
    publish_binding: dict | None = None,
    approval_kind: str | None = None,
    approval_evidence_sha256: str | None = None,
) -> dict:
    """One fail-fast upload primitive shared by create, edit and image-only flows.

    It owns the cross-machine per-post image lock, but intentionally does not own
    the local editorial lock or higher-level task state.
    """
    if not isinstance(post_id, int) or post_id <= 0:
        raise ValueError("valid_post_id_required")
    if not re.fullmatch(r"[0-9a-f]{64}", expected_content_sha256 or ""):
        raise ValueError("original_content_sha256_required")
    if expected_thumbnail_id is not None and (
            type(expected_thumbnail_id) is not int or expected_thumbnail_id <= 0):
        raise ValueError("expected_thumbnail_id_required")
    alt_text = (alt_text or "").strip()
    if not alt_text or len(alt_text) > 180 or "\x00" in alt_text:
        raise ValueError("featured_image_alt_text_required")

    image_info = dict(image_info or validate_featured_image_file(image_path))
    image_path = Path(image_info["path"])
    image_sha256 = str(image_info.get("sha256") or "")
    if not re.fullmatch(r"[0-9a-f]{64}", image_sha256):
        raise ValueError("featured_image_sha_required")

    budget = _FeaturedImageBudget()
    base = ["sudo", "docker", "exec", "wordpress_app", "wp"]
    remote_image = ""
    stage = "remote_lock_acquire"
    lock_token = None
    import_attempted = False
    import_fence_started = False
    import_termination_confirmed = False
    reconcile_attempted = False
    attachment_id: int | None = None
    attachment_sha_verified = False
    preexisting_attachment_ids: list[int] = []
    reconcile_observed_ids: list[int] | None = None
    copy_started = False
    cleanup_attempted = False
    lock_release_attempted = False
    cleanup_error = None
    lock_release_error = None

    try:
        try:
            lock_info = acquire_featured_image_lock(
                base,
                post_id,
                ttl_seconds=FEATURED_IMAGE_REMOTE_LOCK_TTL_SECONDS,
                timeout=budget.timeout(FEATURED_IMAGE_LOCK_TIMEOUT_SECONDS, stage),
            )
        except Exception as lock_exc:
            ambiguous_token = getattr(lock_exc, "featured_image_lock_token", None)
            if isinstance(ambiguous_token, str):
                lock_token = ambiguous_token
            raise
        lock_token = lock_info["token"]
        # Tokenized paths prevent a disconnected prior SSH copy/cleanup from
        # corrupting a later worker's remote file after the lease expires.
        remote_image = f"/tmp/editorial_cover_{post_id}_{lock_token}{image_path.suffix.lower()}"

        stage = "baseline_read"
        live = get_post(
            base,
            post_id,
            fields=["post_status", "post_title", "post_name", "post_content", "post_excerpt"],
            timeout=budget.timeout(FEATURED_IMAGE_READ_TIMEOUT_SECONDS, stage),
        )
        if live.get("post_status") not in ALLOWED_POST_STATUSES or not verify_cas(
                live, content_sha=expected_content_sha256):
            raise ValueError("target_missing_or_modified")
        if preserved_post is not None:
            for key in ("post_status", "post_title", "post_name", "post_excerpt"):
                if live.get(key, "") != preserved_post.get(key, ""):
                    raise ValueError("featured_image_post_changed_before_upload")
        before_thumb = _read_post_meta(
            base,
            post_id,
            "_thumbnail_id",
            timeout=budget.timeout(FEATURED_IMAGE_READ_TIMEOUT_SECONDS, stage),
        )
        expected_thumb_text = None if expected_thumbnail_id is None else str(expected_thumbnail_id)
        if before_thumb != expected_thumb_text:
            raise ValueError("featured_image_changed_before_replacement")

        stage = "local_hash_recheck"
        if _sha256_file(image_path) != image_sha256:
            raise ValueError("featured_image_changed_after_validation")

        stage = "remote_copy"
        copy_started = True
        run_wordpress(
            ["sudo", "docker", "cp", str(image_path), f"wordpress_app:{remote_image}"],
            capture_output=True,
            check=True,
            timeout=budget.timeout(FEATURED_IMAGE_COPY_TIMEOUT_SECONDS, stage),
        )

        stage = "remote_hash"
        copied_hash = run_wordpress(
            ["sudo", "docker", "exec", "wordpress_app", "sha256sum", remote_image],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="strict",
            check=True,
            timeout=budget.timeout(FEATURED_IMAGE_READ_TIMEOUT_SECONDS, stage),
        )
        remote_sha256 = (copied_hash.stdout or "").strip().split(maxsplit=1)[0].lower()
        if remote_sha256 != image_sha256:
            raise ValueError("featured_image_remote_hash_mismatch")

        stage = "pre_import_sha_snapshot"
        preexisting_attachment_ids = find_attachment_ids_by_sha(
            base,
            post_id,
            image_sha256,
            timeout=budget.timeout(FEATURED_IMAGE_READ_TIMEOUT_SECONDS, stage),
        )
        import_attempt = {
            "image_sha256": image_sha256,
            "expected_thumbnail_id": expected_thumbnail_id,
            "preexisting_attachment_ids": preexisting_attachment_ids,
            "lock_token": lock_token,
            "import_fence_started": True,
            "started": True,
        }
        if import_attempt_callback is not None:
            import_attempt_callback(import_attempt)

        stage = "remote_import_fence"
        import_fence_started = True
        set_featured_image_import_pending(
            base, post_id, lock_token, pending=True,
            timeout=budget.timeout(FEATURED_IMAGE_LOCK_TIMEOUT_SECONDS, stage),
        )

        def reconcile_ambiguous_import(exc: BaseException) -> int:
            nonlocal stage, reconcile_attempted, reconcile_observed_ids
            stage = "media_import_sha_reconcile"
            reconcile_attempted = True
            reconcile_observed_ids = find_attachment_ids_by_sha(
                base,
                post_id,
                image_sha256,
                timeout=budget.timeout(FEATURED_IMAGE_READ_TIMEOUT_SECONDS, stage),
            )
            previous = set(preexisting_attachment_ids)
            created = [value for value in reconcile_observed_ids if value not in previous]
            if len(created) != 1:
                if len(created) > 1:
                    raise ValueError("featured_image_import_multiple_new_sha_matches") from exc
                raise ValueError("featured_image_import_outcome_ambiguous") from exc
            return created[0]

        stage = "media_import"
        import_attempted = True
        try:
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
                    timeout=budget.timeout(FEATURED_IMAGE_IMPORT_TIMEOUT_SECONDS, stage),
                )
            # A transport success proves the remote CLI exited; a file SHA
            # match after SSH timeout or 255 does not prove process quiescence.
            import_termination_confirmed = True
            imported_id = (imported.stdout or "").lstrip("\ufeff").strip()
            if not imported_id.isdigit() or int(imported_id) <= 0:
                raise ValueError("featured_image_attachment_id_missing")
            attachment_id = int(imported_id)
        except (subprocess.TimeoutExpired, OSError, ConnectionError) as exc:
            attachment_id = reconcile_ambiguous_import(exc)
            attachment_sha_verified = True
        except subprocess.CalledProcessError as exc:
            if exc.returncode != 255:
                raise
            attachment_id = reconcile_ambiguous_import(exc)
            attachment_sha_verified = True
        except ValueError as exc:
            if str(exc) != "featured_image_attachment_id_missing":
                raise
            attachment_id = reconcile_ambiguous_import(exc)
            attachment_sha_verified = True

        if not attachment_sha_verified:
            stage = "attachment_sha_verify"
            matching_ids = find_attachment_ids_by_sha(
                base,
                post_id,
                image_sha256,
                timeout=budget.timeout(FEATURED_IMAGE_READ_TIMEOUT_SECONDS, stage),
            )
            if attachment_id not in matching_ids:
                raise ValueError("featured_image_imported_attachment_sha_mismatch")

        outcome = {
            "attachment_id": attachment_id,
            "expected_thumbnail_id": expected_thumbnail_id,
            "image_sha256": image_sha256,
            "alt_text_sha256": hashlib.sha256(alt_text.encode("utf-8")).hexdigest(),
            "content_sha256": expected_content_sha256,
            "preserved_post": {
                key: live.get(key, "")
                for key in ("post_status", "post_title", "post_name", "post_excerpt")
            },
            "backup": str(backup) if backup else None,
            "lock_token": lock_token,
            "import_fence_started": True,
            "import_termination_confirmed": import_termination_confirmed,
            "verified": False,
        }
        if outcome_callback is not None:
            outcome_callback(outcome)

        stage = "thumbnail_cas"
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
            attachment_id=attachment_id,
            timeout=budget.timeout(FEATURED_IMAGE_READ_TIMEOUT_SECONDS, stage),
        )
        saved = thumbnail["post"]
        observed_thumb = thumbnail["thumbnail_id"]

        stage = "attachment_readback"
        attachment = get_post(
            base,
            attachment_id,
            fields=["ID", "guid", "post_title", "post_mime_type"],
            timeout=budget.timeout(FEATURED_IMAGE_READ_TIMEOUT_SECONDS, stage),
        )
        observed_alt = _read_post_meta(
            base,
            attachment_id,
            "_wp_attachment_image_alt",
            timeout=budget.timeout(FEATURED_IMAGE_READ_TIMEOUT_SECONDS, stage),
        )
        preserved = ("post_status", "post_title", "post_name", "post_content", "post_excerpt")
        if any(saved.get(key) != live.get(key) for key in preserved):
            raise ValueError("featured_image_post_preservation_failed")
        if observed_thumb != str(attachment_id):
            raise ValueError("featured_image_save_verification_failed")
        if observed_alt != alt_text:
            raise ValueError("featured_image_alt_verification_failed")
        expected_mime = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}.get(
            str(image_info.get("format") or "").upper())
        if not expected_mime or attachment.get("post_mime_type") != expected_mime:
            raise ValueError("featured_image_attachment_verification_failed")
        guid = str(attachment.get("guid", ""))
        if not guid.startswith(("https://", "http://")):
            raise ValueError("featured_image_url_verification_failed")

        outcome = {**outcome, "verified": True, "attachment_url": guid}
        if outcome_callback is not None:
            outcome_callback(outcome)

        if not import_termination_confirmed:
            stage = "media_import_process_unknown"
            raise ValueError("featured_image_import_process_termination_unknown")

        stage = "remote_import_fence_complete"
        set_featured_image_import_pending(
            base, post_id, lock_token, pending=False,
            timeout=budget.timeout(FEATURED_IMAGE_LOCK_TIMEOUT_SECONDS, stage),
        )

        publish_attestation = None
        if publish_binding is not None:
            stage = "publish_attestation"
            publish_attestation = record_publish_attestation(
                base,
                post_id,
                content_sha256=expected_content_sha256,
                review_digest=publish_binding["review_digest"],
                title_sha256=publish_binding["title_sha256"],
                thumbnail_id=attachment_id,
                image_path=image_path,
                alt_text=alt_text,
                approval_kind=approval_kind,
                approval_evidence_sha256=approval_evidence_sha256,
                expires_at_gmt=publish_binding["expires_at_gmt"],
                requires_live_state=publish_binding["requires_live_state"],
            )

        warnings = []
        stage = "remote_cleanup"
        cleanup_attempted = True
        try:
            cleanup = run_wordpress(
                ["sudo", "docker", "exec", "wordpress_app", "rm", "-f", remote_image],
                capture_output=True,
                check=False,
                timeout=budget.timeout(FEATURED_IMAGE_CLEANUP_TIMEOUT_SECONDS, stage),
            )
            if getattr(cleanup, "returncode", 0) != 0:
                warnings.append("featured_image_remote_cleanup_failed")
        except Exception as cleanup_exc:
            warnings.append("featured_image_remote_cleanup_failed:" + type(cleanup_exc).__name__)

        stage = "remote_lock_release"
        lock_release_attempted = True
        try:
            release_featured_image_lock(
                base,
                post_id,
                lock_token,
                timeout=budget.timeout(FEATURED_IMAGE_LOCK_TIMEOUT_SECONDS, stage),
            )
            lock_token = None
        except Exception as release_exc:
            warnings.append("featured_image_remote_lock_release_failed:" + type(release_exc).__name__)

        return {
            "post_id": post_id,
            "status": saved.get("post_status"),
            "attachment_id": attachment_id,
            "attachment_url": guid,
            "alt_text": alt_text,
            "image": image_info,
            "backup": str(backup) if backup else None,
            "publish_attestation": publish_attestation,
            "pipeline": {
                "import_attempts": 1,
                "sha_reconcile_attempts": 1 if reconcile_attempted else 0,
                "remote_lock": "released" if lock_token is None else "expires_by_ttl",
                "elapsed_ms": budget.elapsed_ms(),
                "warnings": warnings,
            },
        }
    except Exception as exc:
        if copy_started and not cleanup_attempted:
            cleanup_attempted = True
            try:
                cleanup = run_wordpress(
                    ["sudo", "docker", "exec", "wordpress_app", "rm", "-f", remote_image],
                    capture_output=True,
                    check=False,
                    timeout=budget.timeout(FEATURED_IMAGE_CLEANUP_TIMEOUT_SECONDS, "failure_cleanup"),
                )
                if getattr(cleanup, "returncode", 0) != 0:
                    cleanup_error = "featured_image_remote_cleanup_failed"
            except Exception as cleanup_exc:
                cleanup_error = type(cleanup_exc).__name__
        if lock_token is not None and not lock_release_attempted:
            lock_release_attempted = True
            try:
                release_featured_image_lock(
                    base,
                    post_id,
                    lock_token,
                    timeout=budget.timeout(FEATURED_IMAGE_LOCK_TIMEOUT_SECONDS, "failure_lock_release"),
                )
                lock_token = None
            except Exception as release_exc:
                lock_release_error = type(release_exc).__name__
        receipt = _write_featured_image_failure_receipt(
            post_id,
            stage=stage,
            error=exc,
            image_info=image_info,
            expected_content_sha256=expected_content_sha256,
            expected_thumbnail_id=expected_thumbnail_id,
            budget=budget,
            import_attempted=import_attempted,
            reconcile_attempted=reconcile_attempted,
            attachment_id=attachment_id,
            remote_image=remote_image,
            preexisting_attachment_ids=preexisting_attachment_ids,
            reconcile_observed_ids=reconcile_observed_ids,
            cleanup_error=cleanup_error,
            lock_release_error=lock_release_error,
            cleanup_attempted=cleanup_attempted,
            lock_release_attempted=lock_release_attempted,
            import_fence_started=import_fence_started,
            lock_token=lock_token,
            import_termination_confirmed=import_termination_confirmed,
        )
        _annotate_pipeline_error(exc, receipt=receipt, stage=stage)
        raise


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
        live = get_post(base, post_id, fields=fields, timeout=FEATURED_IMAGE_READ_TIMEOUT_SECONDS)
        if live.get("post_status") not in ALLOWED_POST_STATUSES:
            raise ValueError("target_missing_or_modified")
        live_sha = content_sha256(live.get("post_content", ""))
        before_thumb = _read_post_meta(
            base, post_id, "_thumbnail_id", timeout=FEATURED_IMAGE_READ_TIMEOUT_SECONDS)
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
    import_attempt_callback=None,
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
    image_info = _validate_featured_image_with_receipt(
        post_id, image_path,
        expected_content_sha256=expected_content_sha256,
        expected_thumbnail_id=expected_thumbnail_id,
    )
    image_path = Path(image_info["path"])

    lock = acquire_editorial_lock(ROOT)

    base = ["sudo", "docker", "exec", "wordpress_app", "wp"]
    state_started = False
    try:
        fields = ["post_status", "post_title", "post_name", "post_content", "post_excerpt"]
        live = get_post(base, post_id, fields=fields, timeout=FEATURED_IMAGE_READ_TIMEOUT_SECONDS)
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
        elif approval_evidence_sha256 is not None:
            raise ValueError("image_approval_kind_required")
        before_thumb = _read_post_meta(
            base, post_id, "_thumbnail_id", timeout=FEATURED_IMAGE_READ_TIMEOUT_SECONDS)
        expected_thumb_text = None if expected_thumbnail_id is None else str(expected_thumbnail_id)
        if before_thumb != expected_thumb_text:
            raise ValueError("featured_image_changed_before_replacement")
        qa_requirements = []
        if manage_task_state:
            previous_state = load_task_state(post_id)
            prior_import = ((previous_state or {}).get("checkpoints") or {}).get(
                "image_import_attempt") or {}
            if (previous_state
                    and previous_state.get("status") in {"failed", "blocked"}
                    and prior_import.get("started")):
                # Do not replace a failed import checkpoint with a fresh task:
                # even another selected image must wait until the previous
                # attachment outcome is reconciled or explicitly investigated.
                raise ValueError("featured_image_prior_import_requires_reconcile")
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

        def record_import_attempt(import_attempt):
            if manage_task_state:
                update_task_state(
                    post_id,
                    checkpoints={"image_import_attempt": import_attempt},
                )
            if import_attempt_callback is not None:
                import_attempt_callback(import_attempt)

        result = hardened_attach_featured_image(
            post_id,
            image_path,
            expected_content_sha256,
            expected_thumbnail_id=expected_thumbnail_id,
            alt_text=alt_text,
            image_info=image_info,
            preserved_post=live,
            backup=backup,
            import_attempt_callback=record_import_attempt,
            outcome_callback=record_outcome,
            publish_binding=publish_binding,
            approval_kind=approval_kind,
            approval_evidence_sha256=approval_evidence_sha256,
        )

        if manage_task_state:
            state = update_task_state(
                post_id,
                completed=["image_saved", "wordpress_saved"],
                status="saved_pending_qa" if qa_requirements else "in_progress",
                result={
                    "post_id": post_id,
                    "attachment_id": result["attachment_id"],
                    "attachment_url": result["attachment_url"],
                    "alt_text": alt_text,
                    "image": image_info,
                    "backup": str(backup),
                },
            )
            if not qa_requirements and load_task_state(post_id) is not None:
                complete_task_state(post_id)
        return result
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
    expected_thumbnail_id: int | None,
    image_path: Path,
    result: dict,
) -> None:
    checkpoint = load_after_image_checkpoint(post_id)
    if not checkpoint:
        return
    if (checkpoint.get("expected_content_sha256") != expected_content_sha256
            or checkpoint.get("expected_thumbnail_id") != expected_thumbnail_id):
        return
    # An AFTER_IMAGE checkpoint names the image the user selected. Never let
    # another upload silently replace that identity or claim generation/saving.
    handle = checkpoint.get("target_image_handle")
    if not isinstance(handle, str) or not handle.strip():
        return
    try:
        if Path(handle).resolve() != image_path.resolve():
            return
    except (OSError, ValueError):
        return
    result_sha = (result.get("image") or {}).get("sha256")
    if result_sha is None:
        result_sha = result.get("image_sha256")
    sealed_sha = checkpoint.get("target_image_sha256")
    if (not isinstance(sealed_sha, str) or not re.fullmatch(r"[0-9a-f]{64}", sealed_sha)
            or result_sha != sealed_sha or _sha256_file(image_path) != sealed_sha):
        return
    update_after_image_checkpoint(
        post_id,
        completed_steps=[
            "uploaded",
            "featured_image_set",
            "readback_verified",
            "content_sha_preserved",
        ],
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
    image_info = _validate_featured_image_with_receipt(post_id, image_path)
    image_path = Path(image_info["path"])

    base = ["sudo", "docker", "exec", "wordpress_app", "wp"]
    fields = ["post_status", "post_title", "post_name", "post_content", "post_excerpt"]
    live = get_post(base, post_id, fields=fields, timeout=FEATURED_IMAGE_READ_TIMEOUT_SECONDS)
    if live.get("post_status") not in ALLOWED_POST_STATUSES:
        raise ValueError("target_missing_or_modified")
    expected_content_sha256 = content_sha256(live.get("post_content", ""))
    before_thumb = _read_post_meta(
        base, post_id, "_thumbnail_id", timeout=FEATURED_IMAGE_READ_TIMEOUT_SECONDS)
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
            if approval_evidence_sha256 is not None:
                raise ValueError("image_approval_kind_required")
            return result
        if not re.fullmatch(r"[0-9a-f]{64}", approval_evidence_sha256 or ""):
            raise ValueError("image_approval_evidence_required")
        attachment_id = result.get("attachment_id")
        if type(attachment_id) is not int or attachment_id <= 0:
            raise ValueError("quick_image_saved_thumbnail_conflict")
        # A recovered import may have changed the thumbnail after the initial
        # live baseline was read. Never attest based only on a task receipt.
        current = get_post(base, post_id, fields=fields, timeout=FEATURED_IMAGE_READ_TIMEOUT_SECONDS)
        if (any(current.get(key, "") != live.get(key, "") for key in
                ("post_status", "post_title", "post_name", "post_excerpt"))
                or content_sha256(current.get("post_content", "")) != expected_content_sha256
                or _read_post_meta(
                    base, post_id, "_thumbnail_id",
                    timeout=FEATURED_IMAGE_READ_TIMEOUT_SECONDS) != str(attachment_id)):
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
            requires_live_state=binding["requires_live_state"],
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
                        expected_thumbnail_id=(
                            int(previous_thumbnail_id)
                            if isinstance(previous_thumbnail_id, str) and previous_thumbnail_id.isdigit()
                            else None
                        ),
                        image_path=image_path,
                        result=reconciled,
                    )
                    return attest_existing({
                        **reconciled, "attempt_number": previous_baseline.get("attempt_number", 1)})
            import_attempt = (previous.get("checkpoints") or {}).get("image_import_attempt") or {}
            if import_attempt.get("started"):
                image_sha256 = import_attempt.get("image_sha256")
                if image_sha256 == _sha256_file(image_path):
                    preexisting_attachment_ids = import_attempt.get("preexisting_attachment_ids")
                    recovered_attachment_id = (
                        _find_new_imported_attachment_by_sha(
                            post_id,
                            image_sha256=image_sha256,
                            preexisting_attachment_ids=preexisting_attachment_ids,
                        )
                        if preexisting_attachment_ids is not None
                        else _find_unique_imported_attachment_by_sha(
                            post_id,
                            image_sha256=image_sha256,
                        )
                    )
                    if recovered_attachment_id is not None:
                        previous_expected_thumbnail_id = (
                            int(previous_thumbnail_id)
                            if isinstance(previous_thumbnail_id, str) and previous_thumbnail_id.isdigit()
                            else None
                        )
                        checkpoint = {
                            "attachment_id": recovered_attachment_id,
                            "expected_thumbnail_id": previous_expected_thumbnail_id,
                            "content_sha256": expected_content_sha256,
                            "image_sha256": image_sha256,
                            "preserved_post": {
                                key: live.get(key, "")
                                for key in ("post_status", "post_title", "post_name", "post_excerpt")
                            },
                            "backup": None,
                            "lock_token": import_attempt.get("lock_token"),
                            "import_fence_started": bool(import_attempt.get("lock_token")),
                        }
                        recovered = reconcile_featured_image_outcome(post_id, checkpoint, alt_text)
                        update_task_state(
                            post_id,
                            completed=["image_saved", "wordpress_saved"],
                            status="saved_pending_qa",
                            result={**recovered, "attempt_number": previous_baseline.get("attempt_number", 1)},
                        )
                        _advance_matching_after_image_checkpoint(
                            post_id,
                            expected_content_sha256=expected_content_sha256,
                            expected_thumbnail_id=previous_expected_thumbnail_id,
                            image_path=image_path,
                            result=recovered,
                        )
                        return attest_existing({
                            **recovered, "attempt_number": previous_baseline.get("attempt_number", 1)})
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
) -> dict:
    """Legacy alias for :func:`replace_featured_image_from_live_baseline`."""
    return replace_featured_image_from_live_baseline(
        post_id,
        image_path,
        alt_text=alt_text,
        confirmed=confirmed,
    )
