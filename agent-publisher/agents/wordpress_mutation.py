"""Small reusable primitives for safe WordPress post mutations."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path

from agents.workflow_metrics import increment, timed


GUARDED_POST_MUTATION_PROTOCOL = 1
GUARDED_POST_MUTATION_SCRIPT = (
    '$raw=file_get_contents("php://stdin");'
    '$p=json_decode($raw,true);'
    '$snap=function($x){return ['
    '"post_status"=>(string)$x->post_status,'
    '"post_title"=>(string)$x->post_title,'
    '"post_name"=>(string)$x->post_name,'
    '"post_content"=>(string)$x->post_content,'
    '"post_excerpt"=>(string)$x->post_excerpt];};'
    '$emit=function($v){echo wp_json_encode($v,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);};'
    'if(!is_array($p)||($p["protocol"]??null)!==1||empty($p["post_id"])'
    '||!is_array($p["expected"]??null)||!is_array($p["updates"]??null))'
    '{$emit(["status"=>"invalid_payload"]);return;}'
    '$id=(int)$p["post_id"];$post=get_post($id);'
    'if(!$post){$emit(["status"=>"missing"]);return;}'
    '$cur=$snap($post);$e=$p["expected"];$u=$p["updates"];'
    '$desired=["post_status"=>(string)($e["post_status"]??$cur["post_status"]),'
    '"post_title"=>(string)($u["post_title"]??($e["post_title"]??$cur["post_title"])),'
    '"post_name"=>(string)($e["post_name"]??$cur["post_name"]),'
    '"post_content"=>(string)($u["post_content"]??$cur["post_content"]),'
    '"post_excerpt"=>(string)($u["post_excerpt"]??($e["post_excerpt"]??$cur["post_excerpt"]))];'
    '$already=true;foreach($desired as $k=>$v){$already=$already&&hash_equals($v,(string)$cur[$k]);}'
    'if($already){$emit(["status"=>"already_applied","saved"=>$cur]);return;}'
    '$ok=true;'
    'if(isset($e["post_status"])){$ok=$ok&&hash_equals((string)$e["post_status"],$cur["post_status"]);}'
    'if(isset($e["post_title"])){$ok=$ok&&hash_equals((string)$e["post_title"],$cur["post_title"]);}'
    'if(isset($e["post_name"])){$ok=$ok&&hash_equals((string)$e["post_name"],$cur["post_name"]);}'
    'if(isset($e["post_excerpt"])){$ok=$ok&&hash_equals((string)$e["post_excerpt"],$cur["post_excerpt"]);}'
    'if(isset($e["content_sha256"])){$ok=$ok&&hash_equals((string)$e["content_sha256"],hash("sha256",$cur["post_content"]));}'
    'if(!$ok){$emit(["status"=>"cas_mismatch","current"=>$cur]);return;}'
    '$allowed=["post_content"=>1,"post_excerpt"=>1,"post_title"=>1];'
    '$args=["ID"=>$id];foreach($u as $k=>$v){if(!isset($allowed[$k])||!is_string($v))'
    '{$emit(["status"=>"invalid_update"]);return;}$args[$k]=$v;}'
    '$r=wp_update_post(wp_slash($args),true);'
    'if(is_wp_error($r)){$emit(["status"=>"update_failed","code"=>$r->get_error_code()]);return;}'
    'clean_post_cache($id);$saved_post=get_post($id);'
    'if(!$saved_post){$emit(["status"=>"readback_missing"]);return;}'
    '$saved=$snap($saved_post);$verified=true;'
    'foreach($desired as $k=>$v){$verified=$verified&&hash_equals((string)$v,(string)$saved[$k]);}'
    '$emit(["status"=>$verified?"ok":"verification_failed","saved"=>$saved]);'
)


def content_sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def get_post(base, post_id, *, fields=None):
    command = list(base) + ["post", "get", str(int(post_id))]
    if fields:
        command.append("--fields=" + ",".join(fields))
    command += ["--format=json", "--allow-root"]
    with timed("wp_target_read"):
        increment("wp_roundtrips")
        result = subprocess.run(command, capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def update_post(base, post_id, fields: dict[str, str]):
    if not fields:
        raise ValueError("wordpress_update_fields_required")
    args = ["post", "update", str(int(post_id))]
    for key, value in fields.items():
        if not isinstance(key, str) or not key or not isinstance(value, str):
            raise ValueError("invalid_wordpress_update_field")
        args.append(f"--{key}={value}")
    args.append("--allow-root")
    with timed("wp_update"):
        increment("wp_roundtrips")
        return subprocess.run(list(base) + args, capture_output=True, text=True, check=True)


def _guarded_payload(post_id: int, expected: dict[str, str], updates: dict[str, str]) -> dict:
    if not isinstance(post_id, int) or post_id <= 0:
        raise ValueError("valid_post_id_required")
    allowed_expected = {
        "post_status", "post_title", "post_name", "post_excerpt", "content_sha256",
    }
    allowed_updates = {"post_content", "post_excerpt", "post_title"}
    if (not isinstance(expected, dict) or not expected
            or set(expected) - allowed_expected
            or any(not isinstance(value, str) for value in expected.values())):
        raise ValueError("invalid_guarded_wordpress_expectation")
    if (not isinstance(updates, dict) or not updates
            or set(updates) - allowed_updates
            or any(not isinstance(value, str) for value in updates.values())):
        raise ValueError("invalid_guarded_wordpress_update")
    sha = expected.get("content_sha256")
    if sha is not None and (len(sha) != 64 or any(ch not in "0123456789abcdef" for ch in sha)):
        raise ValueError("invalid_guarded_wordpress_expectation")
    return {
        "protocol": GUARDED_POST_MUTATION_PROTOCOL,
        "post_id": post_id,
        "expected": dict(expected),
        "updates": dict(updates),
    }


def _guarded_result(stdout: str) -> dict:
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
    raise ValueError("invalid_guarded_wordpress_response")


def _desired_state(expected: dict[str, str], updates: dict[str, str]) -> dict[str, str]:
    desired = {
        "post_status": expected.get("post_status", ""),
        "post_title": expected.get("post_title", ""),
        "post_name": expected.get("post_name", ""),
        "post_excerpt": expected.get("post_excerpt", ""),
    }
    desired.update({key: value for key, value in updates.items() if key != "post_content"})
    if "post_content" in updates:
        desired["post_content"] = updates["post_content"]
    return desired


def _matches_already_applied(current: dict, expected: dict[str, str], updates: dict[str, str]) -> bool:
    if not isinstance(current, dict):
        return False
    return all(current.get(key) == value for key, value in _desired_state(expected, updates).items())


def guarded_update_post(base, post_id, *, expected: dict[str, str], updates: dict[str, str]):
    """CAS, mutate and read back one post inside a single WP-CLI process.

    Callers still perform their initial target read locally so a pre-mutation
    backup can be written before this function runs. The fixed PHP program then
    closes the long SSH gap between the final CAS, the mutation and readback.
    A retry after SSH-255 is safe: if the first write committed but its response
    was lost, the second invocation reports ``cas_mismatch`` with the already
    applied state and this helper treats that exact desired state as recovered.
    """
    payload = _guarded_payload(post_id, expected, updates)
    command = list(base) + ["eval", GUARDED_POST_MUTATION_SCRIPT, "--allow-root"]
    with timed("wp_guarded_mutation"):
        increment("wp_roundtrips")
        increment("wp_guarded_mutations")
        result = subprocess.run(
            command,
            input=json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            capture_output=True,
            text=True,
            check=True,
        )
    observed = _guarded_result(result.stdout)
    status = observed.get("status")
    if status in {"ok", "already_applied"}:
        saved = observed.get("saved")
        if not isinstance(saved, dict):
            raise ValueError("invalid_guarded_wordpress_response")
        if status == "already_applied":
            increment("wp_guarded_recovered_after_retry")
        if not _matches_already_applied(saved, expected, updates):
            raise ValueError("wordpress_guarded_readback_failed")
        return saved
    if status == "cas_mismatch" and _matches_already_applied(
            observed.get("current"), expected, updates):
        increment("wp_guarded_recovered_after_retry")
        return observed["current"]
    if status == "cas_mismatch":
        raise ValueError("wordpress_guarded_cas_mismatch")
    if status == "verification_failed":
        raise ValueError("wordpress_guarded_readback_failed")
    if status == "missing":
        raise ValueError("wordpress_guarded_target_missing")
    if status in {"invalid_payload", "invalid_update"}:
        raise ValueError("wordpress_guarded_protocol_rejected")
    if status == "update_failed":
        raise ValueError("wordpress_guarded_update_failed:" + str(observed.get("code") or "unknown"))
    raise ValueError("wordpress_guarded_mutation_failed:" + str(status or "unknown"))


def verify_cas(post, *, status=None, title=None, content_sha=None):
    if status is not None and post.get("post_status") != status:
        return False
    if title is not None and post.get("post_title") != title:
        return False
    if content_sha is not None and content_sha256(post.get("post_content", "")) != content_sha:
        return False
    return True


def backup_json(root: Path, prefix: str, post_id: int, payload, *, include_microseconds=True):
    archive = root / "data" / "editorial_runs"
    archive.mkdir(parents=True, exist_ok=True)
    fmt = "%Y%m%dT%H%M%S%f" if include_microseconds else "%Y%m%dT%H%M%S"
    target = archive / f"{prefix}-{post_id}-{datetime.now().strftime(fmt)}.json"
    with target.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    os.chmod(target, 0o600)
    return target


def verify_saved_fields(saved, *, expected: dict[str, str], preserved=None):
    for key, value in expected.items():
        if saved.get(key) != value:
            return False
    if preserved:
        for key, value in preserved.items():
            if saved.get(key) != value:
                return False
    return True
