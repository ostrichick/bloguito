"""Safely import a reviewed article-section image without changing post state."""

from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path

from PIL import Image

from agents.editorial import ROOT
from agents.editorial_updater import RANK_MATH_META_KEYS
from agents.featured_image import _read_post_meta, _rank_math_meta
from agents.wordpress_mutation import backup_json, content_sha256, get_post, verify_cas


ALLOWED_POST_STATUSES = {"publish", "draft", "pending", "future", "private"}
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def validate_section_image_file(image_path: Path | str) -> dict:
    """Require a normal decoded 16:9 image large enough for article display."""
    path = Path(image_path).resolve()
    if not path.is_file() or path.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise ValueError("reviewed_section_image_required")
    if path.stat().st_size <= 0:
        raise ValueError("section_image_empty")
    try:
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            width, height = image.size
            image_format = image.format
    except Exception as exc:
        raise ValueError("section_image_decode_failed") from exc
    if width < 1000 or height < 560:
        raise ValueError("section_image_too_small")
    ratio = width / height
    if not 1.70 <= ratio <= 1.82:
        raise ValueError("section_image_aspect_ratio_invalid")
    return {
        "path": str(path), "width": width, "height": height, "format": image_format,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def import_section_image(
    post_id: int,
    image_path: Path | str,
    expected_content_sha256: str,
    *,
    media_title: str,
    alt_text: str,
    confirmed: bool = False,
) -> dict:
    """Import one attachment while preserving the target post and featured image."""
    if not confirmed or not isinstance(post_id, int) or post_id <= 0:
        raise ValueError("specific_section_image_import_confirmation_required")
    if not re.fullmatch(r"[0-9a-f]{64}", expected_content_sha256 or ""):
        raise ValueError("original_content_sha256_required")
    media_title = (media_title or "").strip()
    alt_text = (alt_text or "").strip()
    if (not media_title or len(media_title) > 180 or "\x00" in media_title
            or not alt_text or len(alt_text) > 180 or "\x00" in alt_text):
        raise ValueError("section_image_title_and_alt_required")
    image_info = validate_section_image_file(image_path)
    image_path = Path(image_info["path"])

    lock = ROOT / "data" / ".editorial-publish.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        lock.mkdir()
    except FileExistsError:
        raise ValueError("editorial_publication_busy: inspect the existing job")

    base = ["sudo", "docker", "exec", "wordpress_app", "wp"]
    try:
        fields = ["post_status", "post_title", "post_name", "post_content", "post_excerpt"]
        live = get_post(base, post_id, fields=fields)
        if live.get("post_status") not in ALLOWED_POST_STATUSES or not verify_cas(
                live, content_sha=expected_content_sha256):
            raise ValueError("target_missing_or_modified")
        before_thumb = _read_post_meta(base, post_id, "_thumbnail_id")
        before_rank = _rank_math_meta(base, post_id)
        backup = backup_json(
            ROOT, "section-image-import", post_id,
            {"post": live, "thumbnail_id": before_thumb,
             "rank_math_meta": before_rank, "image": image_info},
        )

        token = image_info["sha256"][:12]
        remote_image = f"/tmp/editorial_section_{post_id}_{token}{image_path.suffix.lower()}"
        subprocess.run(
            ["sudo", "docker", "cp", str(image_path), f"wordpress_app:{remote_image}"],
            capture_output=True, check=True,
        )
        try:
            imported = subprocess.run(
                base + ["media", "import", remote_image, f"--post_id={post_id}",
                        f"--title={media_title}", f"--alt={alt_text}",
                        "--porcelain", "--allow-root"],
                capture_output=True, text=True, check=True,
            )
        finally:
            subprocess.run(
                ["sudo", "docker", "exec", "wordpress_app", "rm", "-f", remote_image],
                capture_output=True, check=False,
            )
        attachment_id = (imported.stdout or "").strip()
        if not attachment_id.isdigit():
            raise ValueError("section_image_attachment_id_missing")

        saved = get_post(base, post_id, fields=fields)
        after_thumb = _read_post_meta(base, post_id, "_thumbnail_id")
        after_rank = _rank_math_meta(base, post_id)
        attachment = get_post(
            base, int(attachment_id), fields=["ID", "guid", "post_title", "post_mime_type"])
        observed_alt = _read_post_meta(base, int(attachment_id), "_wp_attachment_image_alt")
        if any(saved.get(key) != live.get(key) for key in fields):
            raise ValueError(f"section_image_post_preservation_failed: recover from {backup}")
        if after_thumb != before_thumb or after_rank != before_rank:
            raise ValueError(f"section_image_metadata_preservation_failed: recover from {backup}")
        if observed_alt != alt_text or attachment.get("post_title") != media_title:
            raise ValueError(f"section_image_attachment_metadata_failed: recover from {backup}")
        if not str(attachment.get("post_mime_type", "")).startswith("image/"):
            raise ValueError(f"section_image_attachment_verification_failed: recover from {backup}")
        guid = str(attachment.get("guid", ""))
        if not guid.startswith(("https://", "http://")):
            raise ValueError(f"section_image_url_verification_failed: recover from {backup}")
        return {
            "post_id": post_id,
            "status": saved.get("post_status"),
            "attachment_id": int(attachment_id),
            "attachment_url": guid,
            "media_title": media_title,
            "alt_text": alt_text,
            "image": image_info,
            "content_sha256": content_sha256(saved.get("post_content", "")),
            "backup": str(backup),
        }
    finally:
        lock.rmdir()
