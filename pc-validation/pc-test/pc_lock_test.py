#!/usr/bin/env python3
"""PC-only disposable Docker smoke for the exact Bloguito WP lock PHP script.

NOT the entire release gate: media import crash/CAS tests require further work.
Requires explicit --execute. NEVER points at the operating WP host.
"""
from __future__ import annotations

import argparse
import ast
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import urllib.request

BASE = Path(__file__).resolve().parent
PACKAGE = BASE.parent
REV = "077539a25c49e67bc6f75bc36aa9ecb70557125f"
MANIFEST_SHA = "a99a68cd14757f5575c6445c228da58d27c151494f8a92ea2f355538b1c58b84"
WPCLI_URL = "https://github.com/wp-cli/wp-cli/releases/download/v2.12.0/wp-cli-2.12.0.phar"
WPCLI_SHA = "ce34ddd838f7351d6759068d09793f26755463b4a4610a5a5c0a97b68220d85c"
HOSTNAME = "https://bloguito-pc-lock-test.invalid"


class Blocked(RuntimeError):
    pass


def shell(args: list[str], *, cwd: Path | None = None, input_text: str | None = None,
          timeout: int = 180, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(args, cwd=cwd, input=input_text, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=timeout)
    if check and result.returncode:
        # Synthetic-only commands. Do not print any passwords or environment.
        raise Blocked(f"Command failed: {args[0:3]!r}; exit={result.returncode}; "
                      f"stderr tail={result.stderr[-900:]}")
    return result


def verify_repo(repo: Path) -> str:
    if not repo.is_dir():
        raise Blocked(f"Missing source checkout: {repo}")
    head = shell(["git", "rev-parse", "HEAD"], cwd=repo).stdout.strip()
    if shell(["git", "merge-base", "--is-ancestor", REV, "HEAD"],
             cwd=repo, check=False).returncode != 0:
        raise Blocked(f"Expected verified release {REV} to be a commit ancestor of HEAD {head}")
    if shell(["git", "status", "--porcelain", "--untracked-files=no"], cwd=repo).stdout.strip():
        raise Blocked("Dirty tracked source checkout; test immutable revision")
    # No ZIP or binary handoff required. The exact 80-file release manifest is
    # tracked, and each file must match the original reviewed release bytes.
    manifest_file = PACKAGE / "release-manifest.json"
    if not manifest_file.is_file() or hashlib.sha256(manifest_file.read_bytes()).hexdigest() != MANIFEST_SHA:
        raise Blocked("Reviewed release manifest SHA mismatch")
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    if manifest.get("revision") != REV or len(manifest.get("files", {})) != 80:
        raise Blocked("Unexpected release revision/inventory")
    for relative, sha in manifest["files"].items():
        source = repo / relative
        if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != sha:
            raise Blocked("Release code file does not match reviewed manifest: " + relative)
    return head


def lock_source(repo: Path) -> str:
    source = repo / "agent-publisher" / "agents" / "wordpress_mutation.py"
    parsed = ast.parse(source.read_text(encoding="utf-8"))
    for node in parsed.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "FEATURED_IMAGE_LOCK_SCRIPT" for t in node.targets):
            script = ast.literal_eval(node.value)
            if not all(key in script for key in ("START TRANSACTION", "FOR UPDATE", "import_pending", "owner_mismatch")):
                raise Blocked("Unexpected lock source contract")
            return script
    raise Blocked("FEATURED_IMAGE_LOCK_SCRIPT missing")


def check_docker():
    raw = shell(["docker", "context", "inspect"]).stdout
    contexts = json.loads(raw)
    endpoint = contexts[0].get("Endpoints", {}).get("docker", {}).get("Host", "")
    if not endpoint.startswith(("npipe:", "unix:")):
        raise Blocked("Not a local Docker context; refuse remote SSH/TCP engine")
    if shell(["docker", "info", "--format", "{{.OSType}}"]).stdout.strip() != "linux":
        raise Blocked("Docker must use Linux containers")
    shell(["docker", "compose", "version"])


def install_wpcli():
    phar = BASE / "wp-cli.phar"
    if phar.is_file() and hashlib.sha256(phar.read_bytes()).hexdigest() == WPCLI_SHA:
        return
    if phar.exists():
        raise Blocked("Existing wp-cli.phar has unexpected SHA; do not overwrite")
    staging = BASE / "wp-cli.download-part"
    if staging.exists():
        raise Blocked("Previous incomplete WP-CLI download exists")
    try:
        urllib.request.urlretrieve(WPCLI_URL, staging)
        if hashlib.sha256(staging.read_bytes()).hexdigest() != WPCLI_SHA:
            raise Blocked("Downloaded WP-CLI SHA mismatch")
        staging.replace(phar)
    finally:
        staging.unlink(missing_ok=True)


class Isolated:
    def __init__(self, project: str, env_file: Path):
        self.project = project
        self.env_file = env_file
        self.prefix = ["docker", "compose", "-p", project, "-f", str(BASE / "compose.locktest.yml"),
                       "--env-file", str(env_file)]

    def compose(self, *args: str, timeout: int = 180, check: bool = True, input_text: str | None = None):
        return shell(self.prefix + list(args), cwd=BASE, timeout=timeout, check=check, input_text=input_text)

    def wp(self, *args: str, input_text: str | None = None, timeout: int = 90):
        return self.compose("exec", "-T", "wordpress", "php", "/usr/local/bin/wp", *args,
                            "--allow-root", timeout=timeout, input_text=input_text)

    def action(self, script: str, post_id: int, token: str, action: str, *, ttl: int = 300):
        payload = {"protocol": 1, "post_id": post_id, "action": action, "token": token,
                   "ttl_seconds": ttl if action == "acquire" else 0}
        result = self.wp("eval", script, input_text=json.dumps(payload))
        try:
            return json.loads(result.stdout.strip().splitlines()[-1])
        except (json.JSONDecodeError, IndexError) as exc:
            raise Blocked(f"Non-JSON WP-CLI lock response: {result.stdout[-200:]!r}") from exc


def expect(value: dict, status: str, note: str, evidence: list[str]):
    if value.get("status") != status:
        raise Blocked(f"{note}: expected {status}, got {value.get('status')!r}")
    evidence.append(note + ": " + status)


def expire_lock(test: Isolated, post_id: int):
    # Synthetic isolated DB only. Preserve import_pending state and token exactly.
    php = ('$name="_bloguito_featured_image_lock_' + str(post_id) + '";'
           '$s=get_option($name);$v=json_decode($s,true);'
           'if(!is_array($v)){throw new Exception("missing synthetic lock");}'
           '$v["expires_at"]=time()-10;update_option($name,wp_json_encode($v),false);'
           'wp_cache_delete($name,"options");echo "EXPIRED";')
    result = test.wp("eval", php)
    if "EXPIRED" not in result.stdout:
        raise Blocked("Could not expire disposable test lock")


def exercise(test: Isolated, script: str, evidence: list[str], run_dir: Path):
    test.compose("up", "-d", "--wait", "--wait-timeout", "180", timeout=320)
    # No host port is published; no actual domain is reachable from this private network.
    result = test.compose("exec", "-T", "wordpress", "php", "/usr/local/bin/wp",
                          "core", "is-installed", "--allow-root", timeout=45, check=False)
    if result.returncode == 0:
        raise Blocked("Expected empty disposable WordPress database")


def run_cases(test: Isolated, script: str, evidence: list[str], run_dir: Path):
    admin_password = secrets.token_urlsafe(24)
    test.wp("core", "install", f"--url={HOSTNAME}", "--title=Bloguito-disposable-validation",
            "--admin_user=synthetic_admin", f"--admin_password={admin_password}",
            "--admin_email=synthetic@example.invalid", "--skip-email", timeout=120)
    home = test.wp("option", "get", "siteurl").stdout.strip()
    if home != HOSTNAME:
        raise Blocked("Synthetic site URL mismatch; stop before making posts")
    evidence.append("siteurl matched .invalid-only synthetic host")
    engine = test.wp("eval", 'global $wpdb;foreach([$wpdb->options,$wpdb->postmeta] as $t){'
                     '$v=$wpdb->get_var($wpdb->prepare("SELECT ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s",$t));echo $v." ";}').stdout
    if engine.strip() != "InnoDB InnoDB":
        raise Blocked(f"WordPress lock DB tables are not InnoDB: {engine[-100:]!r}")
    evidence.append("wp_options and wp_postmeta are InnoDB")
    row = test.wp("post", "create", "--post_type=post", "--post_status=draft",
                  "--post_title=synthetic-lock-test", "--porcelain").stdout.strip()
    post_id = int(row.splitlines()[-1])
    if post_id <= 0:
        raise Blocked("Failed to seed disposable draft")
    # Snapshot of the EMPTY-OF-REAL-CONTENT synthetic site before lock activity.
    dump = test.compose("exec", "-T", "db", "sh", "-c",
                        'exec mariadb-dump -u root -p"$MYSQL_ROOT_PASSWORD" --single-transaction bloguito_pc_test',
                        timeout=75)
    (run_dir / "synthetic-before-lock.sql").write_text(dump.stdout, encoding="utf-8")
    evidence.append("synthetic SQL snapshot saved before lock tests")

    a, b, c = (secrets.token_hex(16) for _ in range(3))
    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(test.action, script, post_id, a, "acquire")
        f2 = pool.submit(test.action, script, post_id, b, "acquire")
        first, second = f1.result(), f2.result()
    statuses = [first.get("status"), second.get("status")]
    if sorted(statuses) != ["acquired", "busy"]:
        raise Blocked(f"Parallel lock race expected one acquired and one busy, got {statuses}")
    owner = a if first["status"] == "acquired" else b
    loser = b if owner == a else a
    evidence.append("parallel independent WP-CLI: exactly one acquired")
    expect(test.action(script, post_id, loser, "acquire"), "busy", "active owner excludes second token", evidence)
    expect(test.action(script, post_id, loser, "release"), "owner_mismatch", "other owner cannot release", evidence)
    expect(test.action(script, post_id, loser, "mark_import"), "owner_mismatch", "other owner cannot mark import", evidence)
    expect(test.action(script, post_id, owner, "mark_import"), "import_marked", "owner marks import fence", evidence)
    expect(test.action(script, post_id, owner, "mark_import"), "import_already_marked", "double import mark denied", evidence)
    expire_lock(test, post_id)
    pending = test.action(script, post_id, loser, "acquire")
    if pending.get("status") != "busy" or pending.get("import_pending") is not True:
        raise Blocked("Expired pending import must never allow new owner")
    evidence.append("expired pending lock continues fencing new owners")
    expect(test.action(script, post_id, owner, "release"), "import_pending", "pending fence prevents release", evidence)
    expect(test.action(script, post_id, owner, "complete_import"), "import_completed", "original owner completes fence", evidence)
    expect(test.action(script, post_id, owner, "release"), "released", "original owner releases", evidence)
    expect(test.action(script, post_id, c, "acquire"), "acquired", "fresh acquisition after release", evidence)
    expire_lock(test, post_id)
    stale_owner = secrets.token_hex(16)
    taken = test.action(script, post_id, stale_owner, "acquire")
    if taken.get("status") != "acquired" or taken.get("stale_replaced") is not True:
        raise Blocked("Expired nonpending lock takeover must succeed")
    evidence.append("expired nonpending lock taken over with owner isolation")
    expect(test.action(script, post_id, c, "release"), "owner_mismatch", "expired former owner cannot release", evidence)
    expect(test.action(script, post_id, stale_owner, "release"), "released", "new owner releases", evidence)
    status = test.wp("post", "get", str(post_id), "--field=post_status").stdout.strip()
    if status != "draft":
        raise Blocked("Synthetic test post unexpectedly changed publication status")
    evidence.append("synthetic post remains draft; no media import attempted")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True, help="Exact 077539a source checkout")
    parser.add_argument("--execute", action="store_true", help="Allow creation of disposable Docker resources")
    args = parser.parse_args()
    repo = args.repo.resolve()
    verify_repo(repo)
    script = lock_source(repo)
    check_docker()
    if not args.execute:
        print("PREFLIGHT_PASS. No resources created. Add --execute for disposable test.")
        return 0
    install_wpcli()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(3)
    project = "bloguito-pc-lock-" + secrets.token_hex(5)
    run_dir = BASE / "evidence" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    env_file = run_dir / "test-only.env"
    env_file.write_text("PC_TEST_ROOT_PASSWORD=" + secrets.token_urlsafe(28) + "\n"
                        "PC_TEST_DB_PASSWORD=" + secrets.token_urlsafe(28) + "\n", encoding="utf-8")
    test = Isolated(project, env_file)
    evidence = []
    completed = False
    cleanup_allowed = False
    result = {"commit": REV, "project": project, "host": HOSTNAME, "scenarios": evidence,
              "safe_cleanup": False, "core_lock_tests_passed": False,
              "not_covered": ["actual SSH 255", "real media import and SHA lookup", "post/thumbnail CAS", "full v3 restore"]}
    try:
        existing = shell(["docker", "ps", "-a", "-q", "--filter",
                          "label=com.docker.compose.project=" + project]).stdout.strip()
        volumes = shell(["docker", "volume", "ls", "-q", "--filter",
                         "label=com.docker.compose.project=" + project]).stdout.strip()
        networks = shell(["docker", "network", "ls", "-q", "--filter",
                          "label=com.docker.compose.project=" + project]).stdout.strip()
        if existing or volumes or networks:
            raise Blocked("Unexpected preexisting Docker Compose project; no cleanup")
        cleanup_allowed = True
        print("Starting private disposable DB/WordPress for " + REV[:7])
        test.compose("up", "-d", "--wait", "--wait-timeout", "180", timeout=320)
        run_cases(test, script, evidence, run_dir)
        completed = True
        print("PASS: real WordPress/MariaDB independent lock processes")
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {str(exc)[:500]}"
        print("FAILED: " + result["error"], file=sys.stderr)
    finally:
        # Project is cryptographically unique and pre-checked. NEVER prune global volumes.
        if cleanup_allowed:
            cleanup = test.compose("down", "-v", "--remove-orphans", timeout=180, check=False)
            result["safe_cleanup"] = cleanup.returncode == 0
        else:
            result["safe_cleanup"] = False
        result["core_lock_tests_passed"] = completed
        result["scenarios"] = evidence
        (run_dir / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        env_file.unlink(missing_ok=True)
        print("Evidence: " + str(run_dir / "result.json"))
        print("Disposable Docker project cleanup: " + ("PASS" if result["safe_cleanup"] else "CHECK MANUALLY"))
    return 0 if completed and result["safe_cleanup"] else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (Blocked, OSError, subprocess.TimeoutExpired, ValueError) as exc:
        print(f"BLOCKED: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(2)
