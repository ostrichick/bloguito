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
from agents.post_manifest_store import editorial_lock
from agents.wordpress_mutation import backup_json, content_sha256, verify_cas


ALLOWED_POST_STATUSES = {"publish", "draft", "pending", "future", "private"}
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

SECTION_IMAGE_SNAPSHOT_SCRIPT = r'''$payload=json_decode(file_get_contents("php://stdin"),true);
if(!is_array($payload)||($payload["protocol"]??null)!==1||!isset($payload["post_id"])||!array_key_exists("attachment_id",$payload)){fwrite(STDERR,"invalid_section_snapshot_payload\n");exit(2);}
$post_id=(int)$payload["post_id"];$post=get_post($post_id);if(!$post){fwrite(STDERR,"section_snapshot_post_missing\n");exit(3);}
$meta=function($id,$key){$value=get_post_meta($id,$key,true);return is_scalar($value)?(string)$value:"";};
$out=array("protocol"=>1,"post"=>array("post_status"=>(string)$post->post_status,"post_title"=>(string)$post->post_title,"post_name"=>(string)$post->post_name,"post_content"=>(string)$post->post_content,"post_excerpt"=>(string)$post->post_excerpt),"thumbnail_id"=>$meta($post_id,"_thumbnail_id"),"rank_math_meta"=>array("rank_math_focus_keyword"=>$meta($post_id,"rank_math_focus_keyword"),"rank_math_title"=>$meta($post_id,"rank_math_title"),"rank_math_description"=>$meta($post_id,"rank_math_description")),"attachment"=>null);
$attachment_id=$payload["attachment_id"];
if($attachment_id!==null){$attachment_id=(int)$attachment_id;$attachment=get_post($attachment_id);if(!$attachment){fwrite(STDERR,"section_snapshot_attachment_missing\n");exit(4);}$out["attachment"]=array("ID"=>(int)$attachment->ID,"guid"=>(string)$attachment->guid,"post_title"=>(string)$attachment->post_title,"post_mime_type"=>(string)$attachment->post_mime_type,"alt"=>$meta($attachment_id,"_wp_attachment_image_alt"));}
echo wp_json_encode($out);'''


def _read_section_image_snapshot(base, post_id: int, attachment_id: int | None = None) -> dict:
    payload = {"protocol": 1, "post_id": int(post_id), "attachment_id": attachment_id}
    result = subprocess.run(
        list(base) + ["eval", SECTION_IMAGE_SNAPSHOT_SCRIPT, "--allow-root"],
        input=json.dumps(payload, separators=(",", ":")),
        capture_output=True,
        text=True,
        check=True,
    )
    try:
        snapshot = json.loads((result.stdout or "").lstrip("\ufeff").strip())
    except (TypeError, ValueError) as exc:
        raise ValueError("section_image_snapshot_invalid") from exc
    if (
        not isinstance(snapshot, dict)
        or snapshot.get("protocol") != 1
        or not isinstance(snapshot.get("post"), dict)
        or set(snapshot.get("rank_math_meta", {})) != set(RANK_MATH_META_KEYS)
    ):
        raise ValueError("section_image_snapshot_invalid")
    return snapshot


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

    base = ["sudo", "docker", "exec", "wordpress_app", "wp"]
    with editorial_lock(ROOT):
        fields = ["post_status", "post_title", "post_name", "post_content", "post_excerpt"]
        before = _read_section_image_snapshot(base, post_id)
        live = before["post"]
        if live.get("post_status") not in ALLOWED_POST_STATUSES or not verify_cas(
                live, content_sha=expected_content_sha256):
            raise ValueError("target_missing_or_modified")
        before_thumb = before["thumbnail_id"]
        before_rank = before["rank_math_meta"]
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

        after = _read_section_image_snapshot(base, post_id, int(attachment_id))
        saved = after["post"]
        after_thumb = after["thumbnail_id"]
        after_rank = after["rank_math_meta"]
        attachment = after.get("attachment") or {}
        observed_alt = attachment.get("alt", "")
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
