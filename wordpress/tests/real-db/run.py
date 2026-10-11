"""Run production PHP CAS inside disposable WordPress + MariaDB containers.

Never accepts a database URL or host override. The docker compose project and
service names are fixed to the checked-in CI-only fixture.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parents[3]
COMPOSE = ROOT / "wordpress/tests/real-db/compose.yml"
sys.path.insert(0, str(ROOT / "agent-publisher"))
from agents.wordpress_mutation import GUARDED_NEW_DRAFT_META_SCRIPT  # noqa: E402

META_KEYS = (
    "_bloguito_permalink_scheme", "rank_math_focus_keyword", "rank_math_title",
    "rank_math_description",
)


def docker(project: str, service: str, args: list[str], *, input_data: bytes | None = None,
           allow_failure: bool = False) -> subprocess.CompletedProcess:
    command = ["docker", "compose", "-f", str(COMPOSE), "-p", project,
               "exec", "-T", service, *args]
    result = subprocess.run(command, input=input_data, capture_output=True,
                            timeout=80, check=False)
    if result.returncode and not allow_failure:
        raise AssertionError(
            f"{service} command failed ({result.returncode}): "
            + result.stderr.decode("utf-8", "replace")[-1500:])
    return result


def wp(project: str, *args: str, stdin: bytes | None = None) -> str:
    result = docker(project, "cli", ["wp", *args], input_data=stdin)
    return result.stdout.decode("utf-8", "strict").strip()


def ensure(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print("PASS:", message, flush=True)


def seed(project: str, *, name: str) -> tuple[int, dict]:
    post_id = int(wp(project, "post", "create", "--post_type=post",
                     "--post_status=draft", f"--post_title=CI draft {name}",
                     '--post_content=<p>Test "quotes" \\ slash and 한국어</p>',
                     "--post_excerpt=CI excerpt", "--porcelain"))
    row = json.loads(wp(project, "post", "get", str(post_id),
                        "--fields=post_status,post_title,post_name,post_excerpt,post_content",
                        "--format=json"))
    expected = {key: row[key] for key in
                ("post_status", "post_title", "post_name", "post_excerpt")}
    expected["content_sha256"] = hashlib.sha256(row["post_content"].encode()).hexdigest()
    ensure(expected["post_status"] == "draft", f"fixture {name} is draft")
    return post_id, expected


def proposed(name: str) -> dict:
    return {
        "_bloguito_permalink_scheme": "post-id-v1",
        "rank_math_focus_keyword": f"keyword {name} \\",
        "rank_math_title": f'CI "quoted" \\ {name}',
        "rank_math_description": '{"backslash":"\\\\path","utf8":"한국어"}',
    }


def guarded(project: str, post_id: int, expected: dict, meta: dict, *,
            reject_second_write: bool = False) -> dict:
    encoded = base64.b64encode(GUARDED_NEW_DRAFT_META_SCRIPT.encode()).decode()
    before = (
        'add_filter("update_post_metadata",function($check,$id,$key){'
        'return $key==="rank_math_focus_keyword"?false:$check;},10,3);'
        if reject_second_write else ""
    )
    code = before + 'eval(base64_decode("' + encoded + '"));'
    payload = json.dumps({"protocol": 1, "post_id": post_id, "expected": expected,
                          "meta": meta}, ensure_ascii=False).encode()
    return json.loads(wp(project, "eval", code, stdin=payload))


def read_meta(project: str, post_id: int) -> dict:
    keys = json.dumps(META_KEYS)
    code = (f'$id={post_id};$out=[];foreach(json_decode({json.dumps(keys)},true) as $key)'
            '{$out[$key]=metadata_exists("post",$id,$key)?get_post_meta($id,$key,true):null;}'
            'echo wp_json_encode($out,JSON_UNESCAPED_UNICODE);')
    return json.loads(wp(project, "eval", code))


def expect_status(actual: dict, status: str, name: str) -> None:
    ensure(actual.get("status") == status, f"{name}: {status}, observed {actual}")


def init_wordpress(project: str) -> None:
    for attempt in range(45):
        check = docker(project, "cli", ["wp", "core", "version"], allow_failure=True)
        if check.returncode == 0:
            break
        time.sleep(2)
    else:
        raise AssertionError("WordPress core failed to initialize: " +
                             check.stderr.decode("utf-8", "replace")[-900:])
    wp(project, "core", "install", "--url=http://wordpress-ci.invalid",
       "--title=CI disposable WordPress", "--admin_user=ci_admin",
       "--admin_password=ci-only-admin-not-a-secret",
       "--admin_email=ci@wordpress-ci.invalid", "--skip-email")
    ensure(wp(project, "core", "is-installed") == "", "actual WordPress bootstrap installed")


def restore_db_copy(project: str, expected_post_id: int) -> None:
    root_args = ["mariadb", "-uroot", "-pci-only-root-not-a-secret"]
    dump = docker(project, "db", ["mariadb-dump", "-uroot",
                                    "-pci-only-root-not-a-secret", "--single-transaction",
                                    "wordpress_ci"]).stdout
    ensure(len(dump) > 5000 and b"CREATE TABLE" in dump, "actual MariaDB SQL dump")
    docker(project, "db", [*root_args, "-e", "CREATE DATABASE wordpress_ci_restore"])
    docker(project, "db", [*root_args, "wordpress_ci_restore"], input_data=dump)
    count_sql = ("SELECT COUNT(*) FROM wp_posts WHERE ID=" + str(expected_post_id) +
                 " AND post_status='draft'")
    count = docker(project, "db", [*root_args, "-N", "wordpress_ci_restore",
                                   "-e", count_sql]).stdout.decode().strip()
    ensure(count == "1", "isolated SQL restore retains exact draft ID/status")
    meta_sql = ("SELECT COUNT(*) FROM wp_postmeta WHERE post_id=" +
                str(expected_post_id) + " AND meta_key='_bloguito_permalink_scheme'")
    meta_count = docker(project, "db", [*root_args, "-N", "wordpress_ci_restore",
                                        "-e", meta_sql]).stdout.decode().strip()
    ensure(meta_count == "1", "isolated SQL restore retains draft metadata")


def main(project: str) -> None:
    init_wordpress(project)
    post_id, expected = seed(project, name="fresh")
    meta = proposed("fresh")
    expect_status(guarded(project, post_id, expected, meta), "ok", "first write")
    ensure(read_meta(project, post_id) == meta, "actual MariaDB/wp_slash roundtrip")
    expect_status(guarded(project, post_id, expected, meta), "already_applied", "exact replay")
    expect_status(guarded(project, post_id, expected, proposed("other")),
                  "meta_conflict", "conflicting replay")
    ensure(read_meta(project, post_id) == meta, "conflict preserves stored metadata")

    failing_id, failing_expected = seed(project, name="rollback")
    failing_meta = proposed("rollback")
    expect_status(guarded(project, failing_id, failing_expected, failing_meta,
                          reject_second_write=True), "update_failed", "injected second-key failure")
    ensure(all(value is None for value in read_meta(project, failing_id).values()),
           "real InnoDB rollback removes first key after second write failure")
    expect_status(guarded(project, failing_id, failing_expected, failing_meta),
                  "ok", "rollback recovery clean retry")

    drift_id, drift_expected = seed(project, name="content drift")
    wp(project, "post", "update", str(drift_id), "--post_content=<p>changed by editor</p>")
    expect_status(guarded(project, drift_id, drift_expected, proposed("drift")),
                  "cas_mismatch", "changed body blocks metadata")
    ensure(all(value is None for value in read_meta(project, drift_id).values()),
           "content CAS mismatch writes nothing")

    partial_id, partial_expected = seed(project, name="existing partial")
    wp(project, "post", "meta", "add", str(partial_id), "rank_math_title", "external")
    expect_status(guarded(project, partial_id, partial_expected, proposed("partial")),
                  "meta_conflict", "partial metadata conflicts")
    ensure(read_meta(project, partial_id)["rank_math_title"] == "external",
           "partial conflict preserves external value")

    race_id, race_expected = seed(project, name="two writers")
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(guarded, project, race_id, race_expected, proposed(word))
                   for word in ("writer-a", "writer-b")]
        answers = [future.result() for future in futures]
    ensure(sorted(a["status"] for a in answers) == ["meta_conflict", "ok"],
           "two real InnoDB writers serialize to exactly one winner")
    ensure(read_meta(project, race_id) in (proposed("writer-a"), proposed("writer-b")),
           "only winning writer metadata persisted")

    policy_id, _ = seed(project, name="MU approval")
    gate_result = wp(project, "eval-file", "/bloguito/wordpress/tests/real-db/mu_policy.php",
                     str(policy_id))
    ensure("PASS: real WordPress MU policy checks" in gate_result,
           "delegated vs user real WordPress MU gate")
    restore_db_copy(project, post_id)
    ensure(wp(project, "post", "get", str(post_id), "--field=post_status") == "draft",
           "no test post became public")
    print("PASS: ALL ISOLATED REAL WORDPRESS/MARIADB INTEGRATION CHECKS", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    params = parser.parse_args()
    if not params.project.startswith("bloguito-realdb-") or not params.project.replace("-", "").isalnum():
        raise SystemExit("Refusing unknown docker compose project")
    main(params.project)
