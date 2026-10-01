"""Safely import a reviewed article-section image without changing post state."""

from __future__ import annotations

import hashlib
import json
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
SECTION_IMAGE_REVIEW_SCHEMA = "section-image-review/v1"
SECTION_IMAGE_CACHE_SCHEMA = "section-image-review-cache/v1"


def validate_section_image_file(image_path: Path | str) -> dict:
    """Require a normal decoded image large enough for article display."""
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
    return {
        "path": str(path), "width": width, "height": height, "format": image_format,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def _valid_http_url(value: object) -> bool:
    return isinstance(value, str) and value.startswith(("https://", "http://"))


def _validate_title_and_alt(media_title: str, alt_text: str) -> tuple[str, str]:
    media_title = (media_title or "").strip()
    alt_text = (alt_text or "").strip()
    if (not media_title or len(media_title) > 180 or "\x00" in media_title
            or not alt_text or len(alt_text) > 180 or "\x00" in alt_text):
        raise ValueError("section_image_title_and_alt_required")
    return media_title, alt_text


def validate_section_image_review(review: dict, *, image_info: dict | None = None) -> dict:
    """Validate the image-only provenance/rights/metadata reuse contract."""
    if not isinstance(review, dict) or review.get("schema") != SECTION_IMAGE_REVIEW_SCHEMA:
        raise ValueError("section_image_review_invalid")
    source_url = review.get("source_url")
    content_sha = review.get("content_sha256")
    if not _valid_http_url(source_url) or not re.fullmatch(r"[0-9a-f]{64}", content_sha or ""):
        raise ValueError("section_image_review_provenance_invalid")
    media_title, alt_text = _validate_title_and_alt(
        review.get("media_title"), review.get("alt_text"))
    rights = review.get("rights")
    if not isinstance(rights, dict) or rights.get("commercial_reuse_allowed") is not True:
        raise ValueError("section_image_review_rights_not_commercial")
    rights_basis = str(rights.get("basis") or "").strip()
    rights_reference = str(rights.get("reference") or "").strip()
    if (not rights_basis or not rights_reference or "\x00" in rights_basis
            or "\x00" in rights_reference):
        raise ValueError("section_image_review_rights_evidence_required")
    image = review.get("image")
    if (not isinstance(image, dict) or not isinstance(image.get("width"), int)
            or not isinstance(image.get("height"), int) or image["width"] < 1000
            or image["height"] < 560 or not str(image.get("format") or "").strip()):
        raise ValueError("section_image_review_metadata_invalid")
    if image_info and (
        content_sha != image_info.get("sha256")
        or image.get("width") != image_info.get("width")
        or image.get("height") != image_info.get("height")
        or str(image.get("format")).upper() != str(image_info.get("format")).upper()
    ):
        raise ValueError("section_image_review_hash_or_metadata_mismatch")
    attachment = review.get("attachment")
    normalized_attachment = None
    if attachment is not None:
        normalized_attachment = _validate_reviewed_attachment(attachment)
    return {
        "schema": SECTION_IMAGE_REVIEW_SCHEMA,
        "source_url": source_url,
        "content_sha256": content_sha,
        "media_title": media_title,
        "alt_text": alt_text,
        "rights": {
            "commercial_reuse_allowed": True,
            "basis": rights_basis,
            "reference": rights_reference,
        },
        "image": {
            "width": image["width"],
            "height": image["height"],
            "format": str(image["format"]),
        },
        **({"attachment": normalized_attachment} if normalized_attachment else {}),
    }


def create_section_image_review(
    image_path: Path | str,
    *,
    source_url: str,
    media_title: str,
    alt_text: str,
    rights_basis: str,
    rights_reference: str,
    attachment: dict | None = None,
) -> dict:
    """Create a reusable reviewed-image manifest entry from a validated local file."""
    image_info = validate_section_image_file(image_path)
    review = {
        "schema": SECTION_IMAGE_REVIEW_SCHEMA,
        "source_url": source_url,
        "content_sha256": image_info["sha256"],
        "media_title": media_title,
        "alt_text": alt_text,
        "rights": {
            "commercial_reuse_allowed": True,
            "basis": rights_basis,
            "reference": rights_reference,
        },
        "image": {
            "width": image_info["width"],
            "height": image_info["height"],
            "format": image_info["format"],
        },
    }
    if attachment:
        review["attachment"] = attachment
    return validate_section_image_review(review, image_info=image_info)


def _section_image_cache_path(cache_path: Path | str | None = None) -> Path:
    return Path(cache_path) if cache_path is not None else ROOT / "data" / "section-image-reviews.json"


def _review_cache_key(source_url: str, content_sha256_value: str) -> str:
    return hashlib.sha256(f"{source_url}\x00{content_sha256_value}".encode("utf-8")).hexdigest()


def cache_section_image_review(review: dict, *, cache_path: Path | str | None = None) -> dict:
    """Store one image review, replacing only an identical source+hash cache key."""
    normalized = validate_section_image_review(review)
    path = _section_image_cache_path(cache_path)
    if path.is_file():
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("section_image_review_cache_invalid") from exc
        if not isinstance(manifest, dict) or manifest.get("schema") != SECTION_IMAGE_CACHE_SCHEMA:
            raise ValueError("section_image_review_cache_invalid")
        entries = manifest.get("entries")
        if not isinstance(entries, list):
            raise ValueError("section_image_review_cache_invalid")
    else:
        entries = []
    key = _review_cache_key(normalized["source_url"], normalized["content_sha256"])
    kept = []
    for entry in entries:
        checked = validate_section_image_review(entry)
        entry_key = _review_cache_key(checked["source_url"], checked["content_sha256"])
        if entry_key != key:
            kept.append(checked)
    kept.append(normalized)
    kept.sort(key=lambda item: _review_cache_key(item["source_url"], item["content_sha256"]))
    payload = {"schema": SECTION_IMAGE_CACHE_SCHEMA, "entries": kept}
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(path)
    return normalized


def find_cached_section_image_review(
    source_url: str,
    content_sha256_value: str,
    *,
    cache_path: Path | str | None = None,
) -> dict | None:
    """Return a review only for the exact same source and content hash."""
    if not _valid_http_url(source_url) or not re.fullmatch(r"[0-9a-f]{64}", content_sha256_value or ""):
        return None
    path = _section_image_cache_path(cache_path)
    if not path.is_file():
        return None
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("section_image_review_cache_invalid") from exc
    if not isinstance(manifest, dict) or manifest.get("schema") != SECTION_IMAGE_CACHE_SCHEMA:
        raise ValueError("section_image_review_cache_invalid")
    entries = manifest.get("entries")
    if not isinstance(entries, list):
        raise ValueError("section_image_review_cache_invalid")
    wanted = _review_cache_key(source_url, content_sha256_value)
    for entry in entries:
        checked = validate_section_image_review(entry)
        if _review_cache_key(checked["source_url"], checked["content_sha256"]) == wanted:
            return checked
    return None


def decide_section_image_candidate(candidates: list[dict] | None, *, image_required: bool = True) -> dict:
    """Choose the first commercially safe candidate so discovery can stop deterministically."""
    if not image_required:
        return {"decision": "no_image", "stop_search": True, "candidate": None}
    for candidate in candidates or []:
        if not isinstance(candidate, dict) or not _valid_http_url(candidate.get("source_url")):
            continue
        rights = candidate.get("rights")
        if not isinstance(rights, dict) or rights.get("commercial_reuse_allowed") is not True:
            continue
        if not str(rights.get("basis") or "").strip() or not str(rights.get("reference") or "").strip():
            continue
        return {"decision": "adopt", "stop_search": True, "candidate": candidate}
    return {"decision": "continue", "stop_search": False, "candidate": None}


def _validate_reviewed_attachment(attachment: dict) -> dict:
    if (not isinstance(attachment, dict) or attachment.get("reviewed") is not True
            or not isinstance(attachment.get("attachment_id"), int)
            or attachment["attachment_id"] <= 0
            or not _valid_http_url(attachment.get("attachment_url"))):
        raise ValueError("reviewed_section_attachment_required")
    return {
        "reviewed": True,
        "attachment_id": attachment["attachment_id"],
        "attachment_url": attachment["attachment_url"],
    }


def _prepare_section_image(
    image_path: Path | str | None,
    media_title: str,
    alt_text: str,
    *,
    review: dict | None = None,
    reviewed_attachment: dict | None = None,
) -> dict:
    media_title, alt_text = _validate_title_and_alt(media_title, alt_text)
    image_info = validate_section_image_file(image_path) if image_path is not None else None
    normalized_review = None
    if review is not None:
        normalized_review = validate_section_image_review(review, image_info=image_info)
        if (normalized_review["media_title"] != media_title
                or normalized_review["alt_text"] != alt_text):
            raise ValueError("section_image_review_metadata_mismatch")
        if image_info is None:
            image_info = {
                "path": None,
                "width": normalized_review["image"]["width"],
                "height": normalized_review["image"]["height"],
                "format": normalized_review["image"]["format"],
                "sha256": normalized_review["content_sha256"],
            }
    if image_info is None:
        raise ValueError("reviewed_section_image_required")
    attachment = reviewed_attachment
    if attachment is None and normalized_review:
        attachment = normalized_review.get("attachment")
    if attachment is not None:
        attachment = _validate_reviewed_attachment(attachment)
    return {
        "image": image_info,
        "media_title": media_title,
        "alt_text": alt_text,
        "review": normalized_review,
        "reviewed_attachment": attachment,
    }


def _verified_attachment_result(
    base: list[str],
    attachment_id: int,
    prepared: dict,
    backup: Path,
    *,
    expected_url: str | None = None,
    reused_existing: bool = False,
) -> dict:
    attachment = get_post(
        base, attachment_id, fields=["ID", "guid", "post_title", "post_mime_type"])
    observed_alt = _read_post_meta(base, attachment_id, "_wp_attachment_image_alt")
    media_title = prepared["media_title"]
    alt_text = prepared["alt_text"]
    if observed_alt != alt_text or attachment.get("post_title") != media_title:
        raise ValueError(f"section_image_attachment_metadata_failed: recover from {backup}")
    if not str(attachment.get("post_mime_type", "")).startswith("image/"):
        raise ValueError(f"section_image_attachment_verification_failed: recover from {backup}")
    guid = str(attachment.get("guid", ""))
    if not _valid_http_url(guid) or (expected_url is not None and guid != expected_url):
        raise ValueError(f"section_image_url_verification_failed: recover from {backup}")
    return {
        "attachment_id": attachment_id,
        "attachment_url": guid,
        "media_title": media_title,
        "alt_text": alt_text,
        "image": prepared["image"],
        "reused_existing": reused_existing,
    }


def _import_section_image_attachment(base: list[str], post_id: int, prepared: dict, backup: Path) -> dict:
    image_info = prepared["image"]
    if not image_info.get("path"):
        raise ValueError("reviewed_section_image_required")
    image_path = Path(image_info["path"])
    media_title = prepared["media_title"]
    alt_text = prepared["alt_text"]
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
    return _verified_attachment_result(base, int(attachment_id), prepared, backup)


def _reuse_section_image_attachment(base: list[str], prepared: dict, backup: Path) -> dict:
    attachment = prepared["reviewed_attachment"]
    return _verified_attachment_result(
        base,
        attachment["attachment_id"],
        prepared,
        backup,
        expected_url=attachment["attachment_url"],
        reused_existing=True,
    )


def import_section_images(
    post_id: int,
    images: list[dict],
    expected_content_sha256: str,
    *,
    confirmed: bool = False,
) -> dict:
    """Import multiple attachments with one target-post baseline and one readback."""
    if not confirmed or not isinstance(post_id, int) or post_id <= 0:
        raise ValueError("specific_section_image_import_confirmation_required")
    if not re.fullmatch(r"[0-9a-f]{64}", expected_content_sha256 or ""):
        raise ValueError("original_content_sha256_required")
    if not isinstance(images, list) or not images:
        raise ValueError("section_image_batch_required")
    prepared_images = []
    for item in images:
        if not isinstance(item, dict):
            raise ValueError("section_image_batch_item_invalid")
        prepared_images.append(_prepare_section_image(
            item.get("image_path"), item.get("media_title"), item.get("alt_text"),
            review=item.get("review"), reviewed_attachment=item.get("reviewed_attachment")))

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
            ROOT, "section-image-batch-import", post_id,
            {"post": live, "thumbnail_id": before_thumb,
             "rank_math_meta": before_rank, "images": prepared_images},
        )

        attachments = []
        for prepared in prepared_images:
            if prepared.get("reviewed_attachment"):
                attachments.append(_reuse_section_image_attachment(base, prepared, backup))
            else:
                attachments.append(_import_section_image_attachment(base, post_id, prepared, backup))

        saved = get_post(base, post_id, fields=fields)
        after_thumb = _read_post_meta(base, post_id, "_thumbnail_id")
        after_rank = _rank_math_meta(base, post_id)
        if any(saved.get(key) != live.get(key) for key in fields):
            raise ValueError(f"section_image_post_preservation_failed: recover from {backup}")
        if after_thumb != before_thumb or after_rank != before_rank:
            raise ValueError(f"section_image_metadata_preservation_failed: recover from {backup}")
        return {
            "post_id": post_id,
            "status": saved.get("post_status"),
            "attachments": attachments,
            "imported_count": sum(not item["reused_existing"] for item in attachments),
            "reused_count": sum(item["reused_existing"] for item in attachments),
            "content_sha256": content_sha256(saved.get("post_content", "")),
            "backup": str(backup),
        }
    finally:
        lock.rmdir()


def import_section_image(
    post_id: int,
    image_path: Path | str,
    expected_content_sha256: str,
    *,
    media_title: str,
    alt_text: str,
    confirmed: bool = False,
) -> dict:
    """Import one attachment while preserving the legacy single-import result shape."""
    batch = import_section_images(
        post_id,
        [{"image_path": image_path, "media_title": media_title, "alt_text": alt_text}],
        expected_content_sha256,
        confirmed=confirmed,
    )
    attachment = batch["attachments"][0]
    return {
        "post_id": batch["post_id"],
        "status": batch["status"],
        **attachment,
        "content_sha256": batch["content_sha256"],
        "backup": batch["backup"],
    }
