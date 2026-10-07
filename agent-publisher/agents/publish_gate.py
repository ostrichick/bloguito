"""Featured-image publication attestations shared by CLI and WordPress gates."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from agents.wordpress_transport import run_wordpress
from agents.workflow_metrics import increment, timed


PUBLISH_GATE_META_KEY = "_bloguito_publish_gate_v1"
PUBLISH_GATE_PROTOCOL = 1
ALLOWED_IMAGE_APPROVAL_KINDS = {
    "manual_user_selected",
    "automated_visual_review",
}


PUBLISH_GATE_RECORD_SCRIPT = (
    '$raw=file_get_contents("php://stdin");$p=json_decode($raw,true);'
    '$emit=function($v){echo wp_json_encode($v,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);};'
    'if(!is_array($p)||($p["protocol"]??null)!==1||empty($p["post_id"])||empty($p["thumbnail_id"])'
    '||!is_string($p["content_sha256"]??null)||!is_string($p["review_digest"]??null)'
    '||!is_string($p["title_sha256"]??null)||!is_string($p["image_sha256"]??null)'
    '||!is_string($p["alt_text_sha256"]??null)||!is_string($p["approval_evidence_sha256"]??null)'
    '||!is_string($p["expires_at_gmt"]??null)||!is_string($p["approval_kind"]??null))'
    '{$emit(["status"=>"invalid_payload"]);return;}'
    '$id=(int)$p["post_id"];$thumb=(int)$p["thumbnail_id"];$post=get_post($id);$att=get_post($thumb);'
    'if(!$post||!$att||$att->post_type!=="attachment"||!wp_attachment_is_image($thumb))'
    '{$emit(["status"=>"invalid_attachment"]);return;}'
    '$allowed=["manual_user_selected"=>1,"automated_visual_review"=>1];'
    'if(!isset($allowed[$p["approval_kind"]])){$emit(["status"=>"invalid_approval_kind"]);return;}'
    '$hex=function($v){return is_string($v)&&preg_match("/^[0-9a-f]{64}$/D",$v)===1;};'
    'foreach(["content_sha256","review_digest","title_sha256","image_sha256","alt_text_sha256","approval_evidence_sha256"] as $k)'
    '{if(!$hex($p[$k])){$emit(["status"=>"invalid_payload"]);return;}}'
    '$expires=strtotime($p["expires_at_gmt"]);if($expires===false||$expires<=time())'
    '{$emit(["status"=>"expired"]);return;}'
    '$actual_thumb=(int)get_post_thumbnail_id($id);'
    '$alt=(string)get_post_meta($thumb,"_wp_attachment_image_alt",true);'
    '$file=get_attached_file($thumb);'
    '$ok=$actual_thumb===$thumb&&hash_equals($p["content_sha256"],hash("sha256",(string)$post->post_content))'
    '&&hash_equals($p["title_sha256"],hash("sha256",(string)$post->post_title))'
    '&&$alt!==""&&hash_equals($p["alt_text_sha256"],hash("sha256",$alt))'
    '&&is_string($file)&&$file!==""&&is_file($file)&&hash_equals($p["image_sha256"],hash_file("sha256",$file));'
    'if(!$ok){$emit(["status"=>"binding_mismatch"]);return;}'
    '$gate=["version"=>1,"post_id"=>$id,"content_sha256"=>$p["content_sha256"],'
    '"review_digest"=>$p["review_digest"],"title_sha256"=>$p["title_sha256"],'
    '"thumbnail_id"=>$thumb,"image_sha256"=>$p["image_sha256"],'
    '"alt_text_sha256"=>$p["alt_text_sha256"],"approval_kind"=>$p["approval_kind"],'
    '"approval_evidence_sha256"=>$p["approval_evidence_sha256"],"expires_at_gmt"=>$p["expires_at_gmt"]];'
    '$encoded=wp_json_encode($gate,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);'
    'update_post_meta($id,"_bloguito_publish_gate_v1",$encoded);'
    '$saved=(string)get_post_meta($id,"_bloguito_publish_gate_v1",true);'
    'if(!hash_equals($encoded,$saved)){$emit(["status"=>"verification_failed"]);return;}'
    '$emit(["status"=>"ok","attestation"=>$gate]);'
)


PUBLISH_GATE_VALIDATE_SCRIPT = (
    '$raw=file_get_contents("php://stdin");$p=json_decode($raw,true);'
    '$emit=function($v){echo wp_json_encode($v,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);};'
    'if(!is_array($p)||($p["protocol"]??null)!==1||empty($p["post_id"]))'
    '{$emit(["status"=>"invalid_payload"]);return;}'
    '$id=(int)$p["post_id"];$post=get_post($id);if(!$post){$emit(["status"=>"missing"]);return;}'
    '$raw_gate=(string)get_post_meta($id,"_bloguito_publish_gate_v1",true);'
    '$g=json_decode($raw_gate,true);$required=["version","post_id","content_sha256","review_digest",'
    '"title_sha256","thumbnail_id","image_sha256","alt_text_sha256","approval_kind",'
    '"approval_evidence_sha256","expires_at_gmt"];'
    'if(!is_array($g)||array_keys($g)!==$required||($g["version"]??null)!==1||(int)($g["post_id"]??0)!==$id)'
    '{$emit(["status"=>"blocked","reason"=>"publish_attestation_missing_or_invalid"]);return;}'
    '$allowed=["manual_user_selected"=>1,"automated_visual_review"=>1];'
    'if(!isset($allowed[$g["approval_kind"]??""])){$emit(["status"=>"blocked","reason"=>"image_approval_missing"]);return;}'
    '$hex=function($v){return is_string($v)&&preg_match("/^[0-9a-f]{64}$/D",$v)===1;};'
    'foreach(["content_sha256","review_digest","title_sha256","image_sha256","alt_text_sha256","approval_evidence_sha256"] as $k)'
    '{if(!$hex($g[$k]??null)){$emit(["status"=>"blocked","reason"=>"publish_attestation_invalid"]);return;}}'
    '$expires=strtotime($g["expires_at_gmt"]??"");if($expires===false||$expires<=time())'
    '{$emit(["status"=>"blocked","reason"=>"publish_attestation_expired"]);return;}'
    '$expected_review=$p["expected_review_digest"]??null;'
    'if($expected_review!==null&&(!is_string($expected_review)||!hash_equals($expected_review,$g["review_digest"])))'
    '{$emit(["status"=>"blocked","reason"=>"review_digest_mismatch"]);return;}'
    'if(!hash_equals($g["content_sha256"],hash("sha256",(string)$post->post_content)))'
    '{$emit(["status"=>"blocked","reason"=>"content_changed_after_approval"]);return;}'
    'if(!hash_equals($g["title_sha256"],hash("sha256",(string)$post->post_title)))'
    '{$emit(["status"=>"blocked","reason"=>"title_changed_after_approval"]);return;}'
    '$thumb=(int)get_post_thumbnail_id($id);if($thumb<=0||$thumb!==(int)$g["thumbnail_id"])'
    '{$emit(["status"=>"blocked","reason"=>"featured_image_changed_after_approval"]);return;}'
    '$att=get_post($thumb);if(!$att||$att->post_type!=="attachment"||!wp_attachment_is_image($thumb))'
    '{$emit(["status"=>"blocked","reason"=>"featured_image_attachment_invalid"]);return;}'
    '$alt=(string)get_post_meta($thumb,"_wp_attachment_image_alt",true);'
    'if($alt===""||!hash_equals($g["alt_text_sha256"],hash("sha256",$alt)))'
    '{$emit(["status"=>"blocked","reason"=>"featured_image_alt_changed_after_approval"]);return;}'
    '$file=get_attached_file($thumb);if(!is_string($file)||$file===""||!is_file($file)'
    '||!hash_equals($g["image_sha256"],hash_file("sha256",$file)))'
    '{$emit(["status"=>"blocked","reason"=>"featured_image_file_changed_after_approval"]);return;}'
    '$emit(["status"=>"ready","attestation"=>$g]);'
)


def _valid_sha(value: str | None) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def approval_evidence_digest(kind: str, evidence: dict) -> str:
    if kind not in ALLOWED_IMAGE_APPROVAL_KINDS or not isinstance(evidence, dict) or not evidence:
        raise ValueError("image_approval_evidence_required")
    body = {"kind": kind, "evidence": evidence}
    return hashlib.sha256(
        json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _result(stdout: str) -> dict:
    for line in reversed((stdout or "").splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and isinstance(payload.get("status"), str):
            return payload
    raise ValueError("invalid_publish_gate_wordpress_response")


def _parse_datetime(value: str) -> datetime:
    observed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if observed.tzinfo is None:
        observed = observed.replace(tzinfo=timezone.utc)
    return observed.astimezone(timezone.utc)


def reviewed_binding_for_post(post_id: int, content_sha256: str, title: str) -> dict:
    """Return current review/title/freshness binding for an exact tracked post body."""
    if not isinstance(post_id, int) or post_id <= 0 or not _valid_sha(content_sha256):
        raise ValueError("reviewed_publish_binding_required")
    from config import DRAFTS_INDEX_FILE, POSTS_INDEX_FILE
    from agents.editorial import (
        assert_review_digest_bound,
        policy,
        recognized_reviewed_content_hashes,
    )
    from agents.post_manifest_store import load_record

    snapshot = load_record(DRAFTS_INDEX_FILE, post_id) if DRAFTS_INDEX_FILE.is_file() else None
    if snapshot is None and POSTS_INDEX_FILE.is_file():
        snapshot = load_record(POSTS_INDEX_FILE, post_id)
    record = snapshot.record if snapshot is not None else None
    bundle = (record or {}).get("fact_manifest", {}).get("editorial_bundle")
    if not isinstance(bundle, dict):
        raise ValueError("reviewed_publish_binding_required")
    if not isinstance(title, str) or bundle.get("plan", {}).get("title") != title:
        raise ValueError("reviewed_publish_title_mismatch")
    review_digest = assert_review_digest_bound(bundle)
    recognized = recognized_reviewed_content_hashes(bundle, post_id=post_id)
    if content_sha256 not in set(recognized.values()):
        raise ValueError("reviewed_publish_content_mismatch")
    rules = policy()
    deadlines = []
    review_checked_at = (bundle.get("review") or {}).get("checked_at")
    if not isinstance(review_checked_at, str):
        raise ValueError("reviewed_publish_freshness_missing")
    deadlines.append(
        _parse_datetime(review_checked_at)
        + timedelta(hours=int(rules.get("review_max_age_hours", 24)))
    )
    source_max_age = int(rules.get("source_max_age_hours", 24))
    for source in bundle.get("sources", []):
        fetched_at = source.get("fetched_at") if isinstance(source, dict) else None
        if isinstance(fetched_at, str):
            deadlines.append(_parse_datetime(fetched_at) + timedelta(hours=source_max_age))
    expiry = min(deadlines)
    if expiry <= datetime.now(timezone.utc):
        raise ValueError("reviewed_publish_binding_expired")
    return {
        "review_digest": review_digest,
        "title_sha256": hashlib.sha256(title.encode("utf-8")).hexdigest(),
        "expires_at_gmt": expiry.isoformat().replace("+00:00", "Z"),
    }


def record_publish_attestation(
    base,
    post_id: int,
    *,
    content_sha256: str,
    review_digest: str,
    title_sha256: str,
    thumbnail_id: int,
    image_path: Path | str,
    alt_text: str,
    approval_kind: str,
    approval_evidence_sha256: str,
    expires_at_gmt: str,
) -> dict:
    if (not isinstance(post_id, int) or post_id <= 0
            or type(thumbnail_id) is not int or thumbnail_id <= 0
            or not _valid_sha(content_sha256) or not _valid_sha(review_digest)
            or not _valid_sha(title_sha256) or not _valid_sha(approval_evidence_sha256)
            or approval_kind not in ALLOWED_IMAGE_APPROVAL_KINDS):
        raise ValueError("invalid_publish_attestation")
    try:
        expiry = _parse_datetime(expires_at_gmt)
    except (TypeError, ValueError):
        raise ValueError("invalid_publish_attestation_expiry") from None
    if expiry <= datetime.now(timezone.utc):
        raise ValueError("publish_attestation_expired")
    path = Path(image_path).resolve()
    if not path.is_file():
        raise ValueError("publish_attestation_image_missing")
    alt_text = (alt_text or "").strip()
    if not alt_text:
        raise ValueError("publish_attestation_alt_required")
    payload = {
        "protocol": PUBLISH_GATE_PROTOCOL,
        "post_id": post_id,
        "content_sha256": content_sha256,
        "review_digest": review_digest,
        "title_sha256": title_sha256,
        "thumbnail_id": thumbnail_id,
        "image_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "alt_text_sha256": hashlib.sha256(alt_text.encode("utf-8")).hexdigest(),
        "approval_kind": approval_kind,
        "approval_evidence_sha256": approval_evidence_sha256,
        "expires_at_gmt": expires_at_gmt,
    }
    command = list(base) + ["eval", PUBLISH_GATE_RECORD_SCRIPT, "--allow-root"]
    with timed("wp_publish_attestation_write"):
        increment("wp_roundtrips")
        result = run_wordpress(
            command,
            input=json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="strict",
            check=True,
        )
    observed = _result(result.stdout)
    if observed.get("status") != "ok" or not isinstance(observed.get("attestation"), dict):
        raise ValueError("publish_attestation_write_failed:" + str(observed.get("status") or "unknown"))
    return observed["attestation"]


def validate_publish_attestation(base, post_id: int, *, expected_review_digest: str | None = None) -> dict:
    if not isinstance(post_id, int) or post_id <= 0:
        raise ValueError("valid_post_id_required")
    if expected_review_digest is not None and not _valid_sha(expected_review_digest):
        raise ValueError("valid_review_digest_required")
    payload = {
        "protocol": PUBLISH_GATE_PROTOCOL,
        "post_id": post_id,
        "expected_review_digest": expected_review_digest,
    }
    command = list(base) + ["eval", PUBLISH_GATE_VALIDATE_SCRIPT, "--allow-root"]
    with timed("wp_publish_attestation_validate"):
        increment("wp_roundtrips")
        result = run_wordpress(
            command,
            input=json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="strict",
            check=True,
        )
    observed = _result(result.stdout)
    if observed.get("status") != "ready" or not isinstance(observed.get("attestation"), dict):
        reason = str(observed.get("reason") or observed.get("status") or "unknown")
        raise ValueError("publication_gate_blocked:" + reason)
    return observed["attestation"]
