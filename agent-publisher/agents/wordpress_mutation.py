"""Small reusable primitives for safe WordPress post mutations."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import uuid
from agents.wordpress_transport import run_wordpress
from datetime import datetime
from pathlib import Path

from agents.workflow_metrics import increment, timed


GUARDED_POST_MUTATION_PROTOCOL = 1
GUARDED_CATEGORY_MUTATION_PROTOCOL = 1
GUARDED_THUMBNAIL_MUTATION_PROTOCOL = 1
GUARDED_ATTACHMENT_ALT_MUTATION_PROTOCOL = 1
FEATURED_IMAGE_LOCK_PROTOCOL = 1
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


ATTACHMENT_SHA_LOOKUP_SCRIPT = (
    '$p=json_decode(file_get_contents("php://stdin"),true);'
    '$emit=function($v){echo wp_json_encode($v,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);};'
    'if(!is_array($p)||($p["protocol"]??null)!==1||empty($p["post_id"])||empty($p["sha256"]))'
    '{$emit(["status"=>"invalid_payload"]);return;}'
    '$id=(int)$p["post_id"];$sha=strtolower((string)$p["sha256"]);'
    'if(!preg_match("/^[0-9a-f]{64}$/",$sha)){$emit(["status"=>"invalid_payload"]);return;}'
    '$ids=get_posts(["post_type"=>"attachment","post_parent"=>$id,"post_status"=>"inherit",'
    '"posts_per_page"=>-1,"fields"=>"ids","orderby"=>"ID","order"=>"DESC"]);'
    '$matches=[];foreach($ids as $aid){$aid=(int)$aid;if(!wp_attachment_is_image($aid)){continue;}'
    '$file=get_attached_file($aid);if(!is_string($file)||!is_file($file)){continue;}'
    '$observed=hash_file("sha256",$file);'
    'if(is_string($observed)&&hash_equals($sha,strtolower($observed))){$matches[]=$aid;}}'
    '$emit(["status"=>"ok","attachment_ids"=>$matches]);'
)


FEATURED_IMAGE_LOCK_SCRIPT = (
    '$raw=file_get_contents("php://stdin");$p=json_decode($raw,true);'
    '$emit=function($v){echo wp_json_encode($v,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);};'
    'if(!is_array($p)||($p["protocol"]??null)!==1||empty($p["post_id"])'
    '||!isset($p["action"])||!isset($p["token"])||!is_string($p["token"])'
    '||!preg_match("/^[A-Za-z0-9_-]{16,128}$/",$p["token"]))'
    '{$emit(["status"=>"invalid_payload"]);return;}'
    '$id=(int)$p["post_id"];$action=(string)$p["action"];$token=(string)$p["token"];'
    '$ttl=(int)($p["ttl_seconds"]??0);'
    'if($id<=0||!in_array($action,["acquire","release","mark_import","complete_import"],true)'
    '||($action==="acquire"&&($ttl<30||$ttl>900)))'
    '{$emit(["status"=>"invalid_payload"]);return;}'
    '$name="_bloguito_featured_image_lock_".$id;$now=time();global $wpdb;'
    'if($action==="acquire"){'
    '$new=wp_json_encode(["token"=>$token,"expires_at"=>$now+$ttl,"import_pending"=>false,"import_phase"=>"reserved"]);'
    'if(add_option($name,$new,"","no")){$emit(["status"=>"acquired","expires_at"=>$now+$ttl,"stale_replaced"=>false]);return;}'
    'if($wpdb->query("START TRANSACTION")===false){$emit(["status"=>"transaction_failed"]);return;}'
    '$row=$wpdb->get_row($wpdb->prepare("SELECT option_value FROM {$wpdb->options} WHERE option_name=%s FOR UPDATE",$name),ARRAY_A);'
    'if(!$row){$wpdb->query("ROLLBACK");$emit(["status"=>"busy","code"=>"lock_race"]);return;}'
    '$observed=(string)$row["option_value"];$cur=json_decode($observed,true);'
    '$expires=is_array($cur)?(int)($cur["expires_at"]??0):0;'
    '$pending=is_array($cur)&&($cur["import_pending"]??false)===true;'
    'if(is_array($cur)&&hash_equals((string)($cur["token"]??""),$token)&&($expires>=$now||$pending))'
    '{$wpdb->query("ROLLBACK");'
    '$emit(["status"=>"acquired","expires_at"=>$expires,"reentrant"=>true,"stale_replaced"=>false]);return;}'
    'if($pending||$expires>=$now){$wpdb->query("ROLLBACK");$emit(["status"=>"busy","expires_at"=>$expires,"import_pending"=>$pending]);return;}'
    '$updated=$wpdb->query($wpdb->prepare("UPDATE {$wpdb->options} SET option_value=%s WHERE option_name=%s AND option_value=%s",$new,$name,$observed));'
    'if($updated!==1){$wpdb->query("ROLLBACK");$emit(["status"=>"busy","code"=>"stale_replace_race"]);return;}'
    'if($wpdb->query("COMMIT")===false){$emit(["status"=>"update_failed","code"=>"commit_failed"]);return;}'
    'wp_cache_delete($name,"options");$emit(["status"=>"acquired","expires_at"=>$now+$ttl,"stale_replaced"=>true]);return;}'
    'if($wpdb->query("START TRANSACTION")===false){$emit(["status"=>"transaction_failed"]);return;}'
    '$row=$wpdb->get_row($wpdb->prepare("SELECT option_value FROM {$wpdb->options} WHERE option_name=%s FOR UPDATE",$name),ARRAY_A);'
    'if(!$row){$wpdb->query("ROLLBACK");$emit(["status"=>"released","already_missing"=>true]);return;}'
    '$observed=(string)$row["option_value"];$cur=json_decode($observed,true);'
    'if(!is_array($cur)||!hash_equals((string)($cur["token"]??""),$token))'
    '{$wpdb->query("ROLLBACK");$emit(["status"=>"owner_mismatch"]);return;}'
    'if($action==="mark_import"||$action==="complete_import"){'
    '$pending=($cur["import_pending"]??false)===true;$mark=$action==="mark_import";'
    '$phase=(string)($cur["import_phase"]??"reserved");'
    'if($mark&&((int)($cur["expires_at"]??0)<=time()))'
    '{$wpdb->query("ROLLBACK");$emit(["status"=>"expired_owner"]);return;}'
    'if($mark&&($pending||$phase!=="reserved"))'
    '{$wpdb->query("ROLLBACK");$emit(["status"=>"import_already_marked"]);return;}'
    'if(!$mark&&$phase==="completed")'
    '{$wpdb->query("ROLLBACK");$emit(["status"=>"import_completed","reentrant"=>true]);return;}'
    'if(!$mark&&(!$pending||$phase!=="claimed"))'
    '{$wpdb->query("ROLLBACK");$emit(["status"=>"invalid_import_phase"]);return;}'
    '$cur["import_pending"]=$mark;$cur["import_phase"]=$mark?"claimed":"completed";'
    '$new=wp_json_encode($cur);'
    '$updated=$wpdb->query($wpdb->prepare("UPDATE {$wpdb->options} SET option_value=%s WHERE option_name=%s AND option_value=%s",$new,$name,$observed));'
    'if($updated!==1){$wpdb->query("ROLLBACK");$emit(["status"=>"update_failed"]);return;}'
    'if($wpdb->query("COMMIT")===false){$emit(["status"=>"update_failed"]);return;}'
    'wp_cache_delete($name,"options");$emit(["status"=>$mark?"import_marked":"import_completed"]);return;}'
    'if(($cur["import_pending"]??false)===true){$wpdb->query("ROLLBACK");'
    '$emit(["status"=>"import_pending"]);return;}'
    '$deleted=$wpdb->query($wpdb->prepare("DELETE FROM {$wpdb->options} WHERE option_name=%s AND option_value=%s",$name,$observed));'
    'if($deleted!==1){$wpdb->query("ROLLBACK");$emit(["status"=>"owner_mismatch","code"=>"release_race"]);return;}'
    'if($wpdb->query("COMMIT")===false){$emit(["status"=>"update_failed","code"=>"commit_failed"]);return;}'
    'wp_cache_delete($name,"options");$emit(["status"=>"released"]);'
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
    'global $wpdb;if($wpdb->query("START TRANSACTION")===false)'
    '{$emit(["status"=>"transaction_failed"]);return;}'
    '$locked=$wpdb->get_var($wpdb->prepare("SELECT ID FROM {$wpdb->posts} WHERE ID=%d FOR UPDATE",$id));'
    'if(!$locked){$wpdb->query("ROLLBACK");$emit(["status"=>"missing"]);return;}'
    'clean_post_cache($id);$post=get_post($id);'
    'if(!$post){$wpdb->query("ROLLBACK");$emit(["status"=>"missing"]);return;}'
    '$publishing=(($u["post_status"]??null)==="publish"&&($e["post_status"]??null)!=="publish");'
    'if($publishing){'
    '$wpdb->get_results($wpdb->prepare("SELECT meta_id FROM {$wpdb->postmeta} WHERE post_id=%d AND meta_key IN (%s,%s) FOR UPDATE",$id,"_thumbnail_id","_bloguito_publish_gate_v1"));'
    'wp_cache_delete($id,"post_meta");clean_post_cache($id);'
    '$thumb_id=(int)get_post_thumbnail_id($id);'
    'if($thumb_id>0){$wpdb->get_var($wpdb->prepare("SELECT ID FROM {$wpdb->posts} WHERE ID=%d FOR UPDATE",$thumb_id));'
    '$wpdb->get_results($wpdb->prepare("SELECT meta_id FROM {$wpdb->postmeta} WHERE post_id=%d AND meta_key IN (%s,%s) FOR UPDATE",$thumb_id,"_wp_attachment_image_alt","_wp_attached_file"));'
    'wp_cache_delete($thumb_id,"post_meta");clean_post_cache($thumb_id);}'
    'if(!function_exists("bloguito_validate_publishability"))'
    '{$wpdb->query("ROLLBACK");$emit(["status"=>"publish_gate_blocked","code"=>"gate_unavailable"]);return;}'
    '$gate=bloguito_validate_publishability($id,null,null,true);if(is_wp_error($gate))'
    '{$wpdb->query("ROLLBACK");$emit(["status"=>"publish_gate_blocked","code"=>$gate->get_error_code()]);return;}}'
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
    '$allow_auto_slug=(($u["post_status"]??null)==="publish"&&($e["post_status"]??null)==="draft"'
    '&&array_key_exists("post_name",$e)&&(string)$e["post_name"]==="");'
    '$already=true;foreach($desired as $k=>$v){'
    'if($k==="post_name"&&$allow_auto_slug){continue;}'
    '$already=$already&&hash_equals($v,(string)$cur[$k]);}'
    'if($desired_meta!==null){foreach($desired_meta as $k=>$v){$already=$already&&is_string($cur_meta[$k])&&hash_equals($v,$cur_meta[$k]);}}'
    'if($already){$wpdb->query("ROLLBACK");$emit(["status"=>"already_applied","saved"=>$cur,"saved_meta"=>$cur_meta,"category_ids"=>$cats??null]);return;}'
    '$ok=true;'
    'if(isset($e["post_status"])){$ok=$ok&&hash_equals((string)$e["post_status"],$cur["post_status"]);}'
    'if(isset($e["post_title"])){$ok=$ok&&hash_equals((string)$e["post_title"],$cur["post_title"]);}'
    'if(isset($e["post_name"])){$ok=$ok&&hash_equals((string)$e["post_name"],$cur["post_name"]);}'
    'if(isset($e["post_excerpt"])){$ok=$ok&&hash_equals((string)$e["post_excerpt"],$cur["post_excerpt"]);}'
    'if(isset($e["content_sha256"])){$ok=$ok&&hash_equals((string)$e["content_sha256"],hash("sha256",$cur["post_content"]));}'
    'if($em!==null){foreach($em as $k=>$v){$ok=$ok&&(($v===null&&$cur_meta[$k]===null)'
    '||(is_string($v)&&is_string($cur_meta[$k])&&hash_equals($v,$cur_meta[$k])));}}'
    'if(!$ok){$wpdb->query("ROLLBACK");$emit(["status"=>"cas_mismatch","current"=>$cur,"current_meta"=>$cur_meta,"category_ids"=>$cats??null]);return;}'
    '$args=["ID"=>$id];foreach($u as $k=>$v){$args[$k]=$v;}'
    'if($publishing){$GLOBALS["bloguito_guarded_publish_post_id"]=$id;}'
    '$r=wp_update_post(wp_slash($args),true);'
    'if($publishing){unset($GLOBALS["bloguito_guarded_publish_post_id"]);}'
    'if(is_wp_error($r)){$wpdb->query("ROLLBACK");$emit(["status"=>"update_failed","code"=>$r->get_error_code()]);return;}'
    'if($um!==null){foreach($um as $k=>$v){update_post_meta($id,$k,$v);}}'
    'clean_post_cache($id);$saved_post=get_post($id);'
    'if(!$saved_post){$wpdb->query("ROLLBACK");$emit(["status"=>"readback_missing"]);return;}'
    '$saved=$snap($saved_post);$saved_meta=null;$saved_cats=null;$verified=true;'
    'foreach($desired as $k=>$v){'
    'if($k==="post_name"&&$allow_auto_slug){continue;}'
    '$verified=$verified&&hash_equals((string)$v,(string)$saved[$k]);}'
    'if(array_key_exists("category_ids",$e)){$saved_cats=array_map("intval",wp_get_post_categories($id,["fields"=>"ids"]));sort($saved_cats,SORT_NUMERIC);$verified=$verified&&$saved_cats===$expected_cats;}'
    'if($desired_meta!==null){$saved_meta=[];foreach($desired_meta as $k=>$v){'
    '$saved_meta[$k]=metadata_exists("post",$id,$k)?(string)get_post_meta($id,$k,true):null;'
    '$verified=$verified&&is_string($saved_meta[$k])&&hash_equals($v,$saved_meta[$k]);}}'
    'if(!$verified){$wpdb->query("ROLLBACK");$emit(["status"=>"verification_failed","saved"=>$saved,"saved_meta"=>$saved_meta,"category_ids"=>$saved_cats]);return;}'
    'if($wpdb->query("COMMIT")===false){$emit(["status"=>"update_failed","code"=>"commit_failed"]);return;}'
    'clean_post_cache($id);$emit(["status"=>"ok","saved"=>$saved,"saved_meta"=>$saved_meta,"category_ids"=>$saved_cats]);'
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

GUARDED_ATTACHMENT_ALT_MUTATION_SCRIPT = (
    '$raw=file_get_contents("php://stdin");$p=json_decode($raw,true);'
    '$emit=function($v){echo wp_json_encode($v,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);};'
    'if(!is_array($p)||($p["protocol"]??null)!==1||empty($p["post_id"])'
    '||!is_array($p["expected"]??null)||empty($p["attachment_id"])'
    '||!array_key_exists("expected_alt",$p)||!isset($p["alt_text"])||!is_string($p["alt_text"]))'
    '{$emit(["status"=>"invalid_payload"]);return;}'
    '$id=(int)$p["post_id"];$attachment_id=(int)$p["attachment_id"];$e=$p["expected"];'
    '$expected_alt=$p["expected_alt"];$target_alt=(string)$p["alt_text"];'
    'if($expected_alt!==null&&!is_string($expected_alt)){$emit(["status"=>"invalid_payload"]);return;}'
    'global $wpdb;$wpdb->query("START TRANSACTION");'
    '$locked=$wpdb->get_var($wpdb->prepare("SELECT ID FROM {$wpdb->posts} WHERE ID=%d FOR UPDATE",$id));'
    '$attachment_locked=$wpdb->get_var($wpdb->prepare("SELECT ID FROM {$wpdb->posts} WHERE ID=%d FOR UPDATE",$attachment_id));'
    'if(!$locked||!$attachment_locked){$wpdb->query("ROLLBACK");$emit(["status"=>"missing"]);return;}'
    '$wpdb->get_results($wpdb->prepare("SELECT meta_id FROM {$wpdb->postmeta} WHERE post_id=%d AND meta_key=%s FOR UPDATE",$id,"_thumbnail_id"));'
    '$wpdb->get_results($wpdb->prepare("SELECT meta_id FROM {$wpdb->postmeta} WHERE post_id=%d AND meta_key=%s FOR UPDATE",$attachment_id,"_wp_attachment_image_alt"));'
    'clean_post_cache($id);clean_post_cache($attachment_id);$post=get_post($id);$attachment=get_post($attachment_id);'
    'if(!$post||!$attachment||$attachment->post_type!=="attachment"||!wp_attachment_is_image($attachment_id))'
    '{$wpdb->query("ROLLBACK");$emit(["status"=>"invalid_attachment"]);return;}'
    '$snap=function($x){return ['
    '"post_status"=>(string)$x->post_status,"post_title"=>(string)$x->post_title,'
    '"post_name"=>(string)$x->post_name,"post_content"=>(string)$x->post_content,'
    '"post_excerpt"=>(string)$x->post_excerpt];};$cur=$snap($post);'
    '$thumb=metadata_exists("post",$id,"_thumbnail_id")?(string)get_post_meta($id,"_thumbnail_id",true):null;'
    '$alt=metadata_exists("post",$attachment_id,"_wp_attachment_image_alt")?(string)get_post_meta($attachment_id,"_wp_attachment_image_alt",true):null;'
    '$post_ok=true;foreach(["post_status","post_title","post_name","post_excerpt"] as $k)'
    '{if(isset($e[$k])){$post_ok=$post_ok&&hash_equals((string)$e[$k],$cur[$k]);}}'
    'if(isset($e["content_sha256"])){$post_ok=$post_ok&&hash_equals((string)$e["content_sha256"],hash("sha256",$cur["post_content"]));}'
    '$thumb_ok=is_string($thumb)&&hash_equals((string)$attachment_id,$thumb);'
    'if($post_ok&&$thumb_ok&&is_string($alt)&&hash_equals($target_alt,$alt))'
    '{$wpdb->query("ROLLBACK");$emit(["status"=>"already_applied","saved"=>$cur,"thumbnail_id"=>$thumb,"attachment_id"=>$attachment_id,"alt_text"=>$alt]);return;}'
    '$alt_ok=($expected_alt===null&&$alt===null)'
    '||(is_string($expected_alt)&&is_string($alt)&&hash_equals($expected_alt,$alt));'
    'if(!$post_ok||!$thumb_ok||!$alt_ok){$wpdb->query("ROLLBACK");$emit(["status"=>"cas_mismatch","current"=>$cur,"thumbnail_id"=>$thumb,"attachment_id"=>$attachment_id,"alt_text"=>$alt]);return;}'
    'update_post_meta($attachment_id,"_wp_attachment_image_alt",$target_alt);'
    'clean_post_cache($id);clean_post_cache($attachment_id);$saved_post=get_post($id);'
    '$saved_thumb=metadata_exists("post",$id,"_thumbnail_id")?(string)get_post_meta($id,"_thumbnail_id",true):null;'
    '$saved_alt=metadata_exists("post",$attachment_id,"_wp_attachment_image_alt")?(string)get_post_meta($attachment_id,"_wp_attachment_image_alt",true):null;'
    'if(!$saved_post){$wpdb->query("ROLLBACK");$emit(["status"=>"readback_missing"]);return;}'
    '$saved=$snap($saved_post);$verified=is_string($saved_thumb)&&hash_equals((string)$attachment_id,$saved_thumb)'
    '&&is_string($saved_alt)&&hash_equals($target_alt,$saved_alt);'
    'foreach(["post_status","post_title","post_name","post_content","post_excerpt"] as $k)'
    '{$verified=$verified&&hash_equals((string)$cur[$k],(string)$saved[$k]);}'
    'if(!$verified){$wpdb->query("ROLLBACK");$emit(["status"=>"verification_failed","saved"=>$saved,"thumbnail_id"=>$saved_thumb,"attachment_id"=>$attachment_id,"alt_text"=>$saved_alt]);return;}'
    'if($wpdb->query("COMMIT")===false){$emit(["status"=>"update_failed","code"=>"commit_failed"]);return;}'
    'clean_post_cache($id);clean_post_cache($attachment_id);'
    '$emit(["status"=>"ok","saved"=>$saved,"thumbnail_id"=>$saved_thumb,"attachment_id"=>$attachment_id,"alt_text"=>$saved_alt]);'
)


def content_sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def get_post(base, post_id, *, fields=None, timeout=None):
    command = list(base) + ["post", "get", str(int(post_id))]
    if fields:
        command.append("--fields=" + ",".join(fields))
    command += ["--format=json", "--allow-root"]
    with timed("wp_target_read"):
        increment("wp_roundtrips")
        kwargs = dict(
            capture_output=True, text=True, encoding="utf-8", errors="strict", check=True)
        if timeout is not None:
            kwargs["timeout"] = timeout
        result = run_wordpress(command, **kwargs)
    return json.loads((result.stdout or "").lstrip("\ufeff"))


def find_attachment_ids_by_sha(base, post_id: int, image_sha256: str, *, timeout=None) -> list[int]:
    if (not isinstance(post_id, int) or post_id <= 0
            or not isinstance(image_sha256, str)
            or len(image_sha256) != 64
            or any(ch not in "0123456789abcdef" for ch in image_sha256)):
        raise ValueError("invalid_attachment_sha_lookup")
    payload = {"protocol": 1, "post_id": post_id, "sha256": image_sha256}
    command = list(base) + ["eval", ATTACHMENT_SHA_LOOKUP_SCRIPT, "--allow-root"]
    with timed("wp_target_read"):
        increment("wp_roundtrips")
        kwargs = dict(
            input=json.dumps(payload, ensure_ascii=False),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="strict",
            check=True,
        )
        if timeout is not None:
            kwargs["timeout"] = timeout
        result = run_wordpress(command, **kwargs)
    observed = json.loads((result.stdout or "").lstrip("\ufeff"))
    ids = observed.get("attachment_ids") if isinstance(observed, dict) else None
    if observed.get("status") != "ok" or not isinstance(ids, list) or any(
            type(value) is not int or value <= 0 for value in ids):
        raise ValueError("invalid_attachment_sha_lookup_response")
    return ids


def acquire_featured_image_lock(
    base,
    post_id: int,
    *,
    ttl_seconds: int = 300,
    resume_token: str | None = None,
    timeout=None,
) -> dict:
    """Acquire one cross-machine per-post featured-image lock without polling."""
    if (not isinstance(post_id, int) or post_id <= 0
            or not isinstance(ttl_seconds, int) or not 30 <= ttl_seconds <= 900
            or (resume_token is not None and not re.fullmatch(r"[A-Za-z0-9_-]{16,128}", resume_token))):
        raise ValueError("invalid_featured_image_lock_request")
    token = resume_token or uuid.uuid4().hex
    payload = {
        "protocol": FEATURED_IMAGE_LOCK_PROTOCOL,
        "post_id": post_id,
        "action": "acquire",
        "token": token,
        "ttl_seconds": ttl_seconds,
    }
    command = list(base) + ["eval", FEATURED_IMAGE_LOCK_SCRIPT, "--allow-root"]
    kwargs = dict(
        input=json.dumps(payload, ensure_ascii=False),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="strict",
        check=True,
    )
    if timeout is not None:
        kwargs["timeout"] = timeout
    try:
        result = run_wordpress(command, **kwargs)
        observed = json.loads((result.stdout or "").lstrip("\ufeff"))
        status = observed.get("status") if isinstance(observed, dict) else None
        if status == "busy":
            if observed.get("import_pending"):
                raise ValueError("featured_image_remote_import_pending")
            raise ValueError("featured_image_remote_lock_busy")
        if status != "acquired":
            raise ValueError("featured_image_remote_lock_failed")
    except Exception as exc:
        # The server may have committed the acquire before an SSH response was
        # lost. Preserve the exact token so the caller can release only its own
        # possible lock; never guess or poll for ownership.
        if not (isinstance(exc, ValueError) and str(exc) in {
                "featured_image_remote_lock_busy", "featured_image_remote_import_pending"}):
            try:
                setattr(exc, "featured_image_lock_token", token)
            except Exception:
                pass
        raise
    return {
        "token": token,
        "expires_at": observed.get("expires_at"),
        "stale_replaced": bool(observed.get("stale_replaced")),
    }


def set_featured_image_import_pending(
    base, post_id: int, token: str, *, pending: bool, timeout=None
) -> None:
    """Fence in-flight WP import; clear only after verified post/attachment readback.

    Unlike the expiring worker lease, an unfinished import fence remains set
    until its original token finishes reconciliation. This prevents another PC
    from importing while the original SSH-disconnected process may still run.
    """
    if (type(post_id) is not int or post_id <= 0
            or not isinstance(token, str)
            or not re.fullmatch(r"[A-Za-z0-9_-]{16,128}", token)):
        raise ValueError("invalid_featured_image_import_fence")
    payload = {
        "protocol": FEATURED_IMAGE_LOCK_PROTOCOL,
        "post_id": post_id,
        "action": "mark_import" if pending else "complete_import",
        "token": token,
        "ttl_seconds": 0,
    }
    kwargs = dict(
        input=json.dumps(payload, ensure_ascii=False),
        capture_output=True, text=True, encoding="utf-8", errors="strict", check=True,
    )
    if timeout is not None:
        kwargs["timeout"] = timeout
    result = run_wordpress(
        list(base) + ["eval", FEATURED_IMAGE_LOCK_SCRIPT, "--allow-root"], **kwargs)
    observed = json.loads((result.stdout or "").lstrip("\ufeff"))
    expected = "import_marked" if pending else "import_completed"
    if not isinstance(observed, dict) or observed.get("status") != expected:
        raise ValueError("featured_image_import_fence_failed")


def release_featured_image_lock(base, post_id: int, token: str, *, timeout=None) -> None:
    """Release the exact lock token. Missing is idempotent; another owner is not."""
    if (not isinstance(post_id, int) or post_id <= 0
            or not isinstance(token, str)
            or not re.fullmatch(r"[A-Za-z0-9_-]{16,128}", token)):
        raise ValueError("invalid_featured_image_lock_release")
    payload = {
        "protocol": FEATURED_IMAGE_LOCK_PROTOCOL,
        "post_id": post_id,
        "action": "release",
        "token": token,
        "ttl_seconds": 0,
    }
    command = list(base) + ["eval", FEATURED_IMAGE_LOCK_SCRIPT, "--allow-root"]
    kwargs = dict(
        input=json.dumps(payload, ensure_ascii=False),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="strict",
        check=True,
    )
    if timeout is not None:
        kwargs["timeout"] = timeout
    result = run_wordpress(command, **kwargs)
    observed = json.loads((result.stdout or "").lstrip("\ufeff"))
    if not isinstance(observed, dict) or observed.get("status") != "released":
        if isinstance(observed, dict) and observed.get("status") == "owner_mismatch":
            raise ValueError("featured_image_remote_lock_owner_mismatch")
        if isinstance(observed, dict) and observed.get("status") == "import_pending":
            raise ValueError("featured_image_remote_import_pending")
        raise ValueError("featured_image_remote_lock_release_failed")


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


def _guarded_attachment_alt_payload(
    post_id: int,
    *,
    expected: dict[str, str],
    attachment_id: int,
    expected_alt: str | None,
    alt_text: str,
) -> dict:
    required = {
        "post_status", "post_title", "post_name", "post_excerpt", "content_sha256",
    }
    if (not isinstance(post_id, int) or post_id <= 0
            or type(attachment_id) is not int or attachment_id <= 0
            or not isinstance(expected, dict) or set(expected) != required
            or any(not isinstance(value, str) for value in expected.values())
            or (expected_alt is not None and not isinstance(expected_alt, str))
            or not isinstance(alt_text, str) or not alt_text or len(alt_text) > 180
            or "\x00" in alt_text):
        raise ValueError("invalid_guarded_wordpress_attachment_alt_expectation")
    sha = expected["content_sha256"]
    if len(sha) != 64 or any(ch not in "0123456789abcdef" for ch in sha):
        raise ValueError("invalid_guarded_wordpress_attachment_alt_expectation")
    return {
        "protocol": GUARDED_ATTACHMENT_ALT_MUTATION_PROTOCOL,
        "post_id": post_id,
        "expected": dict(expected),
        "attachment_id": attachment_id,
        "expected_alt": expected_alt,
        "alt_text": alt_text,
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
    current_categories=None,
) -> bool:
    if not isinstance(current, dict):
        return False
    allow_auto_slug = (
        expected.get("post_status") == "draft"
        and expected.get("post_name") == ""
        and updates.get("post_status") == "publish"
    )
    for key, value in _desired_state(expected, updates).items():
        if key == "post_name" and allow_auto_slug:
            continue
        if current.get(key) != value:
            return False
    if "category_ids" in expected:
        if (not isinstance(current_categories, list)
                or sorted(current_categories) != sorted(expected["category_ids"])):
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
                current_meta=observed.get("saved_meta"), updates_meta=updates_meta,
                current_categories=observed.get("category_ids")):
            raise ValueError("wordpress_guarded_readback_failed")
        return saved
    if status == "cas_mismatch" and _matches_already_applied(
            observed.get("current"), expected, updates,
            current_meta=observed.get("current_meta"), updates_meta=updates_meta,
            current_categories=observed.get("category_ids")):
        increment("wp_guarded_recovered_after_retry")
        return observed["current"]
    if status == "cas_mismatch":
        raise ValueError("wordpress_guarded_cas_mismatch")
    if status == "verification_failed":
        raise ValueError("wordpress_guarded_readback_failed")
    if status == "publish_gate_blocked":
        raise ValueError("publication_gate_blocked:" + str(observed.get("code") or "unknown"))
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
    timeout=None,
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
        kwargs = dict(
            input=json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="strict",
            check=True,
        )
        if timeout is not None:
            kwargs["timeout"] = timeout
        result = run_wordpress(command, **kwargs)
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


def guarded_update_featured_image_alt(
    base,
    post_id: int,
    *,
    expected: dict[str, str],
    attachment_id: int,
    expected_alt: str | None,
    alt_text: str,
    timeout=None,
) -> dict:
    """CAS featured-image ALT while preserving the attachment relation and post snapshot."""
    payload = _guarded_attachment_alt_payload(
        post_id,
        expected=expected,
        attachment_id=attachment_id,
        expected_alt=expected_alt,
        alt_text=alt_text,
    )
    command = list(base) + ["eval", GUARDED_ATTACHMENT_ALT_MUTATION_SCRIPT, "--allow-root"]
    with timed("wp_guarded_attachment_alt_mutation"):
        increment("wp_roundtrips")
        increment("wp_guarded_mutations")
        kwargs = dict(
            input=json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="strict",
            check=True,
        )
        if timeout is not None:
            kwargs["timeout"] = timeout
        result = run_wordpress(command, **kwargs)
    observed = _guarded_result(result.stdout)
    status = observed.get("status")
    expected_thumb = str(attachment_id)
    if status in {"ok", "already_applied"}:
        saved = observed.get("saved")
        if (not isinstance(saved, dict)
                or observed.get("thumbnail_id") != expected_thumb
                or observed.get("attachment_id") != attachment_id
                or observed.get("alt_text") != alt_text):
            raise ValueError("invalid_guarded_wordpress_response")
        if status == "already_applied":
            increment("wp_guarded_recovered_after_retry")
        return {
            "post": saved,
            "thumbnail_id": expected_thumb,
            "attachment_id": attachment_id,
            "alt_text": alt_text,
        }
    if (status == "cas_mismatch"
            and observed.get("thumbnail_id") == expected_thumb
            and observed.get("attachment_id") == attachment_id
            and observed.get("alt_text") == alt_text
            and _matches_already_applied(observed.get("current"), expected, {})):
        increment("wp_guarded_recovered_after_retry")
        return {
            "post": observed["current"],
            "thumbnail_id": expected_thumb,
            "attachment_id": attachment_id,
            "alt_text": alt_text,
        }
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
