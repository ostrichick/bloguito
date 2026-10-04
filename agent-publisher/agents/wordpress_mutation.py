"""Small reusable primitives for safe WordPress post mutations."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from agents.wordpress_transport import run_wordpress
from datetime import datetime
from pathlib import Path

from agents.workflow_metrics import increment, timed


GUARDED_POST_MUTATION_PROTOCOL = 1
GUARDED_CATEGORY_MUTATION_PROTOCOL = 1
GUARDED_THUMBNAIL_MUTATION_PROTOCOL = 1
GUARDED_POST_META_KEYS = (
    "rank_math_focus_keyword",
    "rank_math_title",
    "rank_math_description",
)
POST_THUMBNAIL_SNAPSHOT_SCRIPT = (
    '$p=json_decode(file_get_contents("php://stdin"),true);'
    '$post=get_post((int)($p["post_id"]??0));'
    'if(!$post){echo wp_json_encode(["status"=>"missing"]);return;}'
    '$row=[];foreach(["post_status","post_title","post_name","post_content","post_excerpt"] as $key)'
    '{$row[$key]=(string)$post->$key;}'
    '$thumb=metadata_exists("post",$post->ID,"_thumbnail_id")'
    '?(string)get_post_meta($post->ID,"_thumbnail_id",true):null;'
    'echo wp_json_encode(["post"=>$row,"thumbnail_id"=>$thumb],JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);'
)
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
    '$id=(int)$p["post_id"];$e=$p["expected"];$u=$p["updates"];'
    '$allowed=["post_content"=>1,"post_excerpt"=>1,"post_title"=>1,"post_status"=>1];'
    'foreach($u as $k=>$v){if(!isset($allowed[$k])||!is_string($v))'
    '{$emit(["status"=>"invalid_update"]);return;}}'
    '$em=$p["expected_meta"]??null;$um=$p["updates_meta"]??null;'
    '$allowed_meta=["rank_math_focus_keyword"=>1,"rank_math_title"=>1,"rank_math_description"=>1];'
    'if(($em===null)!==($um===null)){$emit(["status"=>"invalid_payload"]);return;}'
    'if($em!==null){if(!is_array($em)||!is_array($um)||count($em)!==count($um))'
    '{$emit(["status"=>"invalid_payload"]);return;}'
    '$ek=array_keys($em);$uk=array_keys($um);sort($ek);sort($uk);if($ek!==$uk)'
    '{$emit(["status"=>"invalid_payload"]);return;}'
    'foreach($em as $k=>$v){if(!isset($allowed_meta[$k])||(!is_string($v)&&$v!==null)||!is_string($um[$k]))'
    '{$emit(["status"=>"invalid_payload"]);return;}}}'
    'global $wpdb;$wpdb->query("START TRANSACTION");'
    '$locked=$wpdb->get_var($wpdb->prepare("SELECT ID FROM {$wpdb->posts} WHERE ID=%d FOR UPDATE",$id));'
    'if(!$locked){$wpdb->query("ROLLBACK");$emit(["status"=>"missing"]);return;}'
    'clean_post_cache($id);$post=get_post($id);'
    'if(!$post){$wpdb->query("ROLLBACK");$emit(["status"=>"missing"]);return;}'
    '$cur=$snap($post);'
    'if(array_key_exists("category_ids",$e)){'
    '$wpdb->get_results($wpdb->prepare("SELECT object_id FROM {$wpdb->term_relationships} WHERE object_id=%d FOR UPDATE",$id));'
    '$cats=array_map("intval",wp_get_post_categories($id,["fields"=>"ids"]));sort($cats,SORT_NUMERIC);'
    '$expected_cats=is_array($e["category_ids"])?array_map("intval",$e["category_ids"]):null;'
    'if(!is_array($expected_cats)){$wpdb->query("ROLLBACK");$emit(["status"=>"invalid_payload"]);return;}'
    'sort($expected_cats,SORT_NUMERIC);'
    'if($cats!==$expected_cats){$wpdb->query("ROLLBACK");$emit(["status"=>"cas_mismatch","current"=>$cur,"category_ids"=>$cats]);return;}}'
    '$cur_meta=null;$desired_meta=null;'
    'if($em!==null){$meta_keys=array_keys($em);'
    '$placeholders=implode(",",array_fill(0,count($meta_keys),"%s"));'
    '$sql="SELECT meta_id FROM {$wpdb->postmeta} WHERE post_id=%d AND meta_key IN (".$placeholders.") FOR UPDATE";'
    '$wpdb->get_results($wpdb->prepare($sql,array_merge([$id],$meta_keys)));'
    '$cur_meta=[];$desired_meta=[];foreach($em as $k=>$v){'
    '$cur_meta[$k]=metadata_exists("post",$id,$k)?(string)get_post_meta($id,$k,true):null;'
    '$desired_meta[$k]=(string)$um[$k];}}'
    '$desired=["post_status"=>(string)($u["post_status"]??($e["post_status"]??$cur["post_status"])),'
    '"post_title"=>(string)($u["post_title"]??($e["post_title"]??$cur["post_title"])),'
    '"post_name"=>(string)($e["post_name"]??$cur["post_name"]),'
    '"post_content"=>(string)($u["post_content"]??$cur["post_content"]),'
    '"post_excerpt"=>(string)($u["post_excerpt"]??($e["post_excerpt"]??$cur["post_excerpt"]))];'
    '$already=true;foreach($desired as $k=>$v){$already=$already&&hash_equals($v,(string)$cur[$k]);}'
    'if($desired_meta!==null){foreach($desired_meta as $k=>$v){$already=$already&&is_string($cur_meta[$k])&&hash_equals($v,$cur_meta[$k]);}}'
    'if($already){$wpdb->query("ROLLBACK");$emit(["status"=>"already_applied","saved"=>$cur,"saved_meta"=>$cur_meta]);return;}'
    '$ok=true;'
    'if(isset($e["post_status"])){$ok=$ok&&hash_equals((string)$e["post_status"],$cur["post_status"]);}'
    'if(isset($e["post_title"])){$ok=$ok&&hash_equals((string)$e["post_title"],$cur["post_title"]);}'
    'if(isset($e["post_name"])){$ok=$ok&&hash_equals((string)$e["post_name"],$cur["post_name"]);}'
    'if(isset($e["post_excerpt"])){$ok=$ok&&hash_equals((string)$e["post_excerpt"],$cur["post_excerpt"]);}'
    'if(isset($e["content_sha256"])){$ok=$ok&&hash_equals((string)$e["content_sha256"],hash("sha256",$cur["post_content"]));}'
    'if($em!==null){foreach($em as $k=>$v){$ok=$ok&&(($v===null&&$cur_meta[$k]===null)'
    '||(is_string($v)&&is_string($cur_meta[$k])&&hash_equals($v,$cur_meta[$k])));}}'
    'if(!$ok){$wpdb->query("ROLLBACK");$emit(["status"=>"cas_mismatch","current"=>$cur,"current_meta"=>$cur_meta]);return;}'
    '$args=["ID"=>$id];foreach($u as $k=>$v){$args[$k]=$v;}'
    '$r=wp_update_post(wp_slash($args),true);'
    'if(is_wp_error($r)){$wpdb->query("ROLLBACK");$emit(["status"=>"update_failed","code"=>$r->get_error_code()]);return;}'
    'if($um!==null){foreach($um as $k=>$v){update_post_meta($id,$k,$v);}}'
    'clean_post_cache($id);$saved_post=get_post($id);'
    'if(!$saved_post){$wpdb->query("ROLLBACK");$emit(["status"=>"readback_missing"]);return;}'
    '$saved=$snap($saved_post);$saved_meta=null;$verified=true;'
    'foreach($desired as $k=>$v){$verified=$verified&&hash_equals((string)$v,(string)$saved[$k]);}'
    'if($desired_meta!==null){$saved_meta=[];foreach($desired_meta as $k=>$v){'
    '$saved_meta[$k]=metadata_exists("post",$id,$k)?(string)get_post_meta($id,$k,true):null;'
    '$verified=$verified&&is_string($saved_meta[$k])&&hash_equals($v,$saved_meta[$k]);}}'
    'if(!$verified){$wpdb->query("ROLLBACK");$emit(["status"=>"verification_failed","saved"=>$saved,"saved_meta"=>$saved_meta]);return;}'
    'if($wpdb->query("COMMIT")===false){$emit(["status"=>"update_failed","code"=>"commit_failed"]);return;}'
    'clean_post_cache($id);$emit(["status"=>"ok","saved"=>$saved,"saved_meta"=>$saved_meta]);'
)

GUARDED_CATEGORY_MUTATION_SCRIPT = (
    '$raw=file_get_contents("php://stdin");$p=json_decode($raw,true);'
    '$emit=function($v){echo wp_json_encode($v,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);};'
    'if(!is_array($p)||($p["protocol"]??null)!==1||empty($p["post_id"])'
    '||!is_array($p["expected"]??null)||!isset($p["target_category_id"]))'
    '{$emit(["status"=>"invalid_payload"]);return;}'
    '$id=(int)$p["post_id"];$target=(int)$p["target_category_id"];$e=$p["expected"];'
    'global $wpdb;$wpdb->query("START TRANSACTION");'
    '$locked=$wpdb->get_var($wpdb->prepare("SELECT ID FROM {$wpdb->posts} WHERE ID=%d FOR UPDATE",$id));'
    'if(!$locked){$wpdb->query("ROLLBACK");$emit(["status"=>"missing"]);return;}'
    '$wpdb->get_results($wpdb->prepare("SELECT object_id FROM {$wpdb->term_relationships} WHERE object_id=%d FOR UPDATE",$id));'
    'clean_post_cache($id);$post=get_post($id);'
    'if(!$post){$wpdb->query("ROLLBACK");$emit(["status"=>"missing"]);return;}'
    '$snap=function($x){return ['
    '"post_status"=>(string)$x->post_status,'
    '"post_title"=>(string)$x->post_title,'
    '"post_name"=>(string)$x->post_name,'
    '"post_content"=>(string)$x->post_content,'
    '"post_excerpt"=>(string)$x->post_excerpt];};'
    '$cats=array_map("intval",wp_get_post_categories($id,["fields"=>"ids"]));sort($cats,SORT_NUMERIC);'
    '$cur=$snap($post);'
    '$post_ok=true;'
    'if(isset($e["post_status"])){$post_ok=$post_ok&&hash_equals((string)$e["post_status"],$cur["post_status"]);}'
    'if(isset($e["post_title"])){$post_ok=$post_ok&&hash_equals((string)$e["post_title"],$cur["post_title"]);}'
    'if(isset($e["post_name"])){$post_ok=$post_ok&&hash_equals((string)$e["post_name"],$cur["post_name"]);}'
    'if(isset($e["post_excerpt"])){$post_ok=$post_ok&&hash_equals((string)$e["post_excerpt"],$cur["post_excerpt"]);}'
    'if(isset($e["content_sha256"])){$post_ok=$post_ok&&hash_equals((string)$e["content_sha256"],hash("sha256",$cur["post_content"]));}'
    '$desired_cats=[$target];'
    'if($post_ok&&$cats===$desired_cats){$wpdb->query("ROLLBACK");$emit(["status"=>"already_applied","saved"=>$cur,"category_ids"=>$cats]);return;}'
    '$expected_cats=$e["category_ids"]??null;'
    'if(!$post_ok||!is_array($expected_cats)){$wpdb->query("ROLLBACK");$emit(["status"=>"cas_mismatch","current"=>$cur,"category_ids"=>$cats]);return;}'
    '$expected_cats=array_map("intval",$expected_cats);sort($expected_cats,SORT_NUMERIC);'
    'if($cats!==$expected_cats){$wpdb->query("ROLLBACK");$emit(["status"=>"cas_mismatch","current"=>$cur,"category_ids"=>$cats]);return;}'
    '$r=wp_set_post_categories($id,$desired_cats,false);'
    'if(is_wp_error($r)){$wpdb->query("ROLLBACK");$emit(["status"=>"update_failed","code"=>$r->get_error_code()]);return;}'
    'clean_post_cache($id);$saved_post=get_post($id);'
    'if(!$saved_post){$wpdb->query("ROLLBACK");$emit(["status"=>"readback_missing"]);return;}'
    '$saved=$snap($saved_post);$saved_cats=array_map("intval",wp_get_post_categories($id,["fields"=>"ids"]));sort($saved_cats,SORT_NUMERIC);'
    '$verified=$saved_cats===$desired_cats;foreach(["post_status","post_title","post_name","post_content","post_excerpt"] as $k)'
    '{$verified=$verified&&hash_equals((string)$cur[$k],(string)$saved[$k]);}'
    'if(!$verified){$wpdb->query("ROLLBACK");$emit(["status"=>"verification_failed","saved"=>$saved,"category_ids"=>$saved_cats]);return;}'
    'if($wpdb->query("COMMIT")===false){$emit(["status"=>"update_failed","code"=>"commit_failed"]);return;}'
    'clean_post_cache($id);$emit(["status"=>"ok","saved"=>$saved,"category_ids"=>$saved_cats]);'
)

GUARDED_THUMBNAIL_MUTATION_SCRIPT = (
    '$raw=file_get_contents("php://stdin");$p=json_decode($raw,true);'
    '$emit=function($v){echo wp_json_encode($v,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);};'
    'if(!is_array($p)||($p["protocol"]??null)!==1||empty($p["post_id"])'
    '||!is_array($p["expected"]??null)||!array_key_exists("expected_thumbnail_id",$p)'
    '||empty($p["attachment_id"])){$emit(["status"=>"invalid_payload"]);return;}'
    '$id=(int)$p["post_id"];$attachment_id=(int)$p["attachment_id"];$e=$p["expected"];'
    '$expected_thumb=$p["expected_thumbnail_id"]===null?null:(string)(int)$p["expected_thumbnail_id"];'
    'global $wpdb;$wpdb->query("START TRANSACTION");'
    '$locked=$wpdb->get_var($wpdb->prepare("SELECT ID FROM {$wpdb->posts} WHERE ID=%d FOR UPDATE",$id));'
    '$attachment_locked=$wpdb->get_var($wpdb->prepare("SELECT ID FROM {$wpdb->posts} WHERE ID=%d FOR UPDATE",$attachment_id));'
    'if(!$locked||!$attachment_locked){$wpdb->query("ROLLBACK");$emit(["status"=>"missing"]);return;}'
    '$wpdb->get_results($wpdb->prepare("SELECT meta_id FROM {$wpdb->postmeta} WHERE post_id=%d AND meta_key=%s FOR UPDATE",$id,"_thumbnail_id"));'
    'clean_post_cache($id);clean_post_cache($attachment_id);$post=get_post($id);$attachment=get_post($attachment_id);'
    'if(!$post||!$attachment||$attachment->post_type!=="attachment"||!wp_attachment_is_image($attachment_id))'
    '{$wpdb->query("ROLLBACK");$emit(["status"=>"invalid_attachment"]);return;}'
    '$snap=function($x){return ['
    '"post_status"=>(string)$x->post_status,"post_title"=>(string)$x->post_title,'
    '"post_name"=>(string)$x->post_name,"post_content"=>(string)$x->post_content,'
    '"post_excerpt"=>(string)$x->post_excerpt];};$cur=$snap($post);'
    '$thumb=metadata_exists("post",$id,"_thumbnail_id")?(string)get_post_meta($id,"_thumbnail_id",true):null;'
    '$post_ok=true;foreach(["post_status","post_title","post_name","post_excerpt"] as $k)'
    '{if(isset($e[$k])){$post_ok=$post_ok&&hash_equals((string)$e[$k],$cur[$k]);}}'
    'if(isset($e["content_sha256"])){$post_ok=$post_ok&&hash_equals((string)$e["content_sha256"],hash("sha256",$cur["post_content"]));}'
    '$desired_thumb=(string)$attachment_id;'
    'if($post_ok&&is_string($thumb)&&hash_equals($desired_thumb,$thumb))'
    '{$wpdb->query("ROLLBACK");$emit(["status"=>"already_applied","saved"=>$cur,"thumbnail_id"=>$thumb]);return;}'
    '$thumb_ok=($expected_thumb===null&&$thumb===null)'
    '||(is_string($expected_thumb)&&is_string($thumb)&&hash_equals($expected_thumb,$thumb));'
    'if(!$post_ok||!$thumb_ok){$wpdb->query("ROLLBACK");$emit(["status"=>"cas_mismatch","current"=>$cur,"thumbnail_id"=>$thumb]);return;}'
    'update_post_meta($id,"_thumbnail_id",$attachment_id);clean_post_cache($id);$saved_post=get_post($id);'
    '$saved_thumb=metadata_exists("post",$id,"_thumbnail_id")?(string)get_post_meta($id,"_thumbnail_id",true):null;'
    'if(!$saved_post){$wpdb->query("ROLLBACK");$emit(["status"=>"readback_missing"]);return;}'
    '$saved=$snap($saved_post);$verified=is_string($saved_thumb)&&hash_equals($desired_thumb,$saved_thumb);'
    'foreach(["post_status","post_title","post_name","post_content","post_excerpt"] as $k)'
    '{$verified=$verified&&hash_equals((string)$cur[$k],(string)$saved[$k]);}'
    'if(!$verified){$wpdb->query("ROLLBACK");$emit(["status"=>"verification_failed","saved"=>$saved,"thumbnail_id"=>$saved_thumb]);return;}'
    'if($wpdb->query("COMMIT")===false){$emit(["status"=>"update_failed","code"=>"commit_failed"]);return;}'
    'clean_post_cache($id);$emit(["status"=>"ok","saved"=>$saved,"thumbnail_id"=>$saved_thumb]);'
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
        result = run_wordpress(
            command, capture_output=True, text=True, encoding="utf-8", errors="strict", check=True)
    return json.loads((result.stdout or "").lstrip("\ufeff"))


def _guarded_payload(
    post_id: int,
    expected: dict,
    updates: dict[str, str],
    *,
    expected_meta: dict[str, str | None] | None = None,
    updates_meta: dict[str, str] | None = None,
) -> dict:
    if not isinstance(post_id, int) or post_id <= 0:
        raise ValueError("valid_post_id_required")
    allowed_expected = {
        "post_status", "post_title", "post_name", "post_excerpt", "content_sha256",
        "category_ids",
    }
    allowed_updates = {"post_content", "post_excerpt", "post_title", "post_status"}
    string_expected = set(expected) - {"category_ids"} if isinstance(expected, dict) else set()
    if (not isinstance(expected, dict) or not expected
            or set(expected) - allowed_expected
            or any(not isinstance(expected[key], str) for key in string_expected)
            or ("category_ids" in expected and (
                not isinstance(expected["category_ids"], list)
                or any(type(value) is not int or value <= 0 for value in expected["category_ids"])
                or len(expected["category_ids"]) != len(set(expected["category_ids"]))))):
        raise ValueError("invalid_guarded_wordpress_expectation")
    if (not isinstance(updates, dict) or not updates
            or set(updates) - allowed_updates
            or any(not isinstance(value, str) for value in updates.values())):
        raise ValueError("invalid_guarded_wordpress_update")
    sha = expected.get("content_sha256")
    if sha is not None and (len(sha) != 64 or any(ch not in "0123456789abcdef" for ch in sha)):
        raise ValueError("invalid_guarded_wordpress_expectation")
    if (expected_meta is None) != (updates_meta is None):
        raise ValueError("invalid_guarded_wordpress_meta_expectation")
    if expected_meta is not None:
        if (not isinstance(expected_meta, dict) or not isinstance(updates_meta, dict)
                or set(expected_meta) != set(updates_meta)
                or not set(expected_meta).issubset(GUARDED_POST_META_KEYS)
                or not expected_meta
                or any(value is not None and not isinstance(value, str)
                       for value in expected_meta.values())
                or any(not isinstance(value, str) for value in updates_meta.values())):
            raise ValueError("invalid_guarded_wordpress_meta_expectation")
    payload = {
        "protocol": GUARDED_POST_MUTATION_PROTOCOL,
        "post_id": post_id,
        "expected": dict(expected),
        "updates": dict(updates),
    }
    if expected_meta is not None:
        payload["expected_meta"] = dict(expected_meta)
        payload["updates_meta"] = dict(updates_meta)
    return payload


def _guarded_category_payload(
    post_id: int, *, expected: dict, target_category_id: int,
) -> dict:
    required = {
        "post_status", "post_title", "post_name", "post_excerpt",
        "content_sha256", "category_ids",
    }


def _guarded_thumbnail_payload(
    post_id: int,
    *,
    expected: dict[str, str],
    expected_thumbnail_id: int | None,
    attachment_id: int,
) -> dict:
    required = {
        "post_status", "post_title", "post_name", "post_excerpt", "content_sha256",
    }
    if (not isinstance(post_id, int) or post_id <= 0
            or type(attachment_id) is not int or attachment_id <= 0
            or (expected_thumbnail_id is not None
                and (type(expected_thumbnail_id) is not int or expected_thumbnail_id <= 0))
            or not isinstance(expected, dict) or set(expected) != required
            or any(not isinstance(value, str) for value in expected.values())):
        raise ValueError("invalid_guarded_wordpress_thumbnail_expectation")
    sha = expected["content_sha256"]
    if len(sha) != 64 or any(ch not in "0123456789abcdef" for ch in sha):
        raise ValueError("invalid_guarded_wordpress_thumbnail_expectation")
    return {
        "protocol": GUARDED_THUMBNAIL_MUTATION_PROTOCOL,
        "post_id": post_id,
        "expected": dict(expected),
        "expected_thumbnail_id": expected_thumbnail_id,
        "attachment_id": attachment_id,
    }
    if (not isinstance(post_id, int) or post_id <= 0
            or type(target_category_id) is not int or target_category_id <= 0
            or not isinstance(expected, dict) or set(expected) != required
            or any(not isinstance(expected[key], str)
                   for key in required - {"category_ids"})
            or not isinstance(expected["category_ids"], list)
            or any(type(value) is not int or value <= 0 for value in expected["category_ids"])
            or len(expected["category_ids"]) != len(set(expected["category_ids"]))):
        raise ValueError("invalid_guarded_wordpress_category_expectation")
    sha = expected["content_sha256"]
    if len(sha) != 64 or any(ch not in "0123456789abcdef" for ch in sha):
        raise ValueError("invalid_guarded_wordpress_category_expectation")
    return {
        "protocol": GUARDED_CATEGORY_MUTATION_PROTOCOL,
        "post_id": post_id,
        "expected": dict(expected),
        "target_category_id": target_category_id,
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


def _matches_already_applied(
    current: dict,
    expected: dict,
    updates: dict[str, str],
    *,
    current_meta=None,
    updates_meta=None,
) -> bool:
    if not isinstance(current, dict):
        return False
    if not all(current.get(key) == value for key, value in _desired_state(expected, updates).items()):
        return False
    if updates_meta is None:
        return True
    return (isinstance(current_meta, dict)
            and all(current_meta.get(key) == value for key, value in updates_meta.items()))


def guarded_update_post(
    base,
    post_id,
    *,
    expected: dict,
    updates: dict[str, str],
    expected_meta: dict[str, str | None] | None = None,
    updates_meta: dict[str, str] | None = None,
):
    """CAS, mutate and read back one post inside a single WP-CLI process.

    Callers still perform their initial target read locally so a pre-mutation
    backup can be written before this function runs. The fixed PHP program then
    closes the long SSH gap between the final CAS, the mutation and readback.
    A retry after SSH-255 is safe: if the first write committed but its response
    was lost, the second invocation reports ``cas_mismatch`` with the already
    applied state and this helper treats that exact desired state as recovered.
    """
    payload = _guarded_payload(
        post_id, expected, updates,
        expected_meta=expected_meta, updates_meta=updates_meta)
    command = list(base) + ["eval", GUARDED_POST_MUTATION_SCRIPT, "--allow-root"]
    with timed("wp_guarded_mutation"):
        increment("wp_roundtrips")
        increment("wp_guarded_mutations")
        result = run_wordpress(
            command,
            input=json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="strict",
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
        if not _matches_already_applied(
                saved, expected, updates,
                current_meta=observed.get("saved_meta"), updates_meta=updates_meta):
            raise ValueError("wordpress_guarded_readback_failed")
        return saved
    if status == "cas_mismatch" and _matches_already_applied(
            observed.get("current"), expected, updates,
            current_meta=observed.get("current_meta"), updates_meta=updates_meta):
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


def guarded_set_post_category(
    base, post_id, *, expected: dict, target_category_id: int,
) -> dict:
    """CAS one post's category while preserving every reader-visible post field."""
    payload = _guarded_category_payload(
        post_id, expected=expected, target_category_id=target_category_id)
    command = list(base) + ["eval", GUARDED_CATEGORY_MUTATION_SCRIPT, "--allow-root"]
    with timed("wp_guarded_category_mutation"):
        increment("wp_roundtrips")
        increment("wp_guarded_mutations")
        result = run_wordpress(
            command,
            input=json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="strict",
            check=True,
        )
    observed = _guarded_result(result.stdout)
    status = observed.get("status")
    if status in {"ok", "already_applied"}:
        saved = observed.get("saved")
        categories = observed.get("category_ids")
        if not isinstance(saved, dict) or categories != [target_category_id]:
            raise ValueError("invalid_guarded_wordpress_response")
        return {"post": saved, "category_ids": categories}
    if status == "cas_mismatch":
        raise ValueError("wordpress_guarded_cas_mismatch")
    if status == "verification_failed":
        raise ValueError("wordpress_guarded_readback_failed")
    if status == "missing":
        raise ValueError("wordpress_guarded_target_missing")
    if status == "invalid_payload":
        raise ValueError("wordpress_guarded_protocol_rejected")
    if status == "update_failed":
        raise ValueError("wordpress_guarded_update_failed:" + str(observed.get("code") or "unknown"))
    raise ValueError("wordpress_guarded_mutation_failed:" + str(status or "unknown"))


def guarded_set_post_thumbnail(
    base,
    post_id: int,
    *,
    expected: dict[str, str],
    expected_thumbnail_id: int | None,
    attachment_id: int,
) -> dict:
    """CAS a featured-image attachment while preserving the exact post snapshot."""
    payload = _guarded_thumbnail_payload(
        post_id,
        expected=expected,
        expected_thumbnail_id=expected_thumbnail_id,
        attachment_id=attachment_id,
    )
    command = list(base) + ["eval", GUARDED_THUMBNAIL_MUTATION_SCRIPT, "--allow-root"]
    with timed("wp_guarded_thumbnail_mutation"):
        increment("wp_roundtrips")
        increment("wp_guarded_mutations")
        result = run_wordpress(
            command,
            input=json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="strict",
            check=True,
        )
    observed = _guarded_result(result.stdout)
    status = observed.get("status")
    expected_thumb = str(attachment_id)
    if status in {"ok", "already_applied"}:
        saved = observed.get("saved")
        if not isinstance(saved, dict) or observed.get("thumbnail_id") != expected_thumb:
            raise ValueError("invalid_guarded_wordpress_response")
        if status == "already_applied":
            increment("wp_guarded_recovered_after_retry")
        return {"post": saved, "thumbnail_id": expected_thumb}
    if (status == "cas_mismatch"
            and observed.get("thumbnail_id") == expected_thumb
            and _matches_already_applied(observed.get("current"), expected, {})):
        increment("wp_guarded_recovered_after_retry")
        return {"post": observed["current"], "thumbnail_id": expected_thumb}
    if status == "cas_mismatch":
        raise ValueError("wordpress_guarded_cas_mismatch")
    if status == "verification_failed":
        raise ValueError("wordpress_guarded_readback_failed")
    if status == "missing":
        raise ValueError("wordpress_guarded_target_missing")
    if status in {"invalid_payload", "invalid_attachment"}:
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
