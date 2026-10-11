"""Run actual v3 backup/restore + release rollback on GitHub's disposable Docker.

This test refuses non-CI container names, never accepts external URLs or
credentials, and uses synthetic data only. This is a *detached integration*
test, not a production-disaster-recovery drill.
"""
from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
COMPOSE = ROOT / "wordpress/tests/real-db/compose.yml"
OVERLAY = ROOT / "wordpress/tests/real-db/restore.override.yml"
sys.path.insert(0, str(ROOT / "wordpress/tests/real-db"))
sys.path.insert(0, str(ROOT / "scripts"))
import run as base  # noqa: E402 (reuse only seed/CAS functions)
import build_editorial_release as builder  # noqa: E402
import install_editorial_release as installer  # noqa: E402

ROOT_PASSWORD = "ci-only-root-not-a-secret"


def verified_environment() -> tuple[str, str, str]:
    project = os.environ.get("COMPOSE_PROJECT", "")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    db = os.environ.get("CI_RESTORE_DB_CONTAINER", "")
    app = os.environ.get("CI_RESTORE_WP_CONTAINER", "")
    if not re.fullmatch(r"[0-9]{8,15}", run_id):
        raise SystemExit("Refusing to run outside GitHub-hosted CI")
    expected = (f"bloguito-fullrestore-{run_id}", f"bloguito-ci-db-{run_id}",
                f"bloguito-ci-wp-{run_id}")
    if (project, db, app) != expected or not os.environ.get("GITHUB_ACTIONS") == "true":
        raise SystemExit("Refusing non-isolated project/container identity")
    return project, db, app


def call(*args: str, input_data: bytes | None = None, expect: int = 0,
         env: dict | None = None, timeout: int = 110) -> subprocess.CompletedProcess:
    result = subprocess.run(args, input=input_data, capture_output=True, timeout=timeout,
                            env=env, check=False)
    if result.returncode != expect:
        raise AssertionError(f"Command {args[:3]} exit {result.returncode}; "
                             + (result.stdout + result.stderr).decode(errors="replace")[-1500:])
    return result


def compose(project: str, service: str, *args: str, input_data: bytes | None = None) -> str:
    completed = call("docker", "compose", "-f", str(COMPOSE), "-f", str(OVERLAY),
                     "-p", project, "exec", "-T", service, *args, input_data=input_data)
    return completed.stdout.decode().strip()


def wp(project: str, *args: str, stdin: bytes | None = None) -> str:
    return compose(project, "cli", "wp", *args, input_data=stdin)


def inside(container: str, *args: str, input_data: bytes | None = None) -> str:
    return call("docker", "exec", *("-i",) if input_data is not None else (),
                container, *args, input_data=input_data).stdout.decode().strip()


def marker(container: str, relative: str, value: str) -> None:
    root = "/var/www/html/wp-content/"
    assert relative.startswith(("uploads/", "plugins/", "themes/", "mu-plugins/"))
    command = f"mkdir -p {root}{relative.rsplit('/', 1)[0]} && printf '%s' '{value}' > {root}{relative}"
    inside(container, "sh", "-c", command)


def content(container: str, relative: str) -> str:
    return inside(container, "cat", "/var/www/html/wp-content/" + relative)


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print("PASS:", message, flush=True)


def ambiguous_commit(project: str) -> int:
    """Suppress committed response at PHP caller boundary, then recover by replay.

    We deliberately DO NOT simulate a terminated server connection; the DB
    COMMIT really succeeds, but the caller sees no machine-readable response.
    """
    # base.seed uses the identical isolated compose service labels, WP calls
    # below use overlay so the bootstrap points to `wordpress`, not `wordpress_ci`.
    post_id = int(wp(project, "post", "create", "--post_type=post", "--post_status=draft",
                     "--post_title=CI ambiguous COMMIT", "--post_content=ci-only-commit",
                     "--post_excerpt=CI", "--porcelain"))
    post = json.loads(wp(project, "post", "get", str(post_id),
                         "--fields=post_status,post_title,post_name,post_excerpt,post_content",
                         "--format=json"))
    expected = {key: post[key] for key in
                ("post_status", "post_title", "post_name", "post_excerpt")}
    expected["content_sha256"] = hashlib.sha256(post["post_content"].encode()).hexdigest()
    meta = base.proposed("lost-response")
    from agents.wordpress_mutation import GUARDED_NEW_DRAFT_META_SCRIPT
    source = base64.b64encode(GUARDED_NEW_DRAFT_META_SCRIPT.encode()).decode()
    payload = json.dumps({"protocol": 1, "post_id": post_id,
                          "expected": expected, "meta": meta}, ensure_ascii=False).encode()
    # Execute exact production PHP transaction, discard its output at transport
    # edge only; simulate client timeout/lost response without re-CREATE.
    lost = wp(project, "eval", 'ob_start();eval(base64_decode("' + source + '"));'
              'ob_end_clean();', stdin=payload)
    check(lost == "", "COMMIT succeeded but caller received no response")
    readback = json.loads(wp(project, "eval", f'$id={post_id};$out=[];'
        'foreach(["_bloguito_permalink_scheme","rank_math_focus_keyword",'
        '"rank_math_title","rank_math_description"] as $key)'
        '{$out[$key]=get_post_meta($id,$key,true);}echo wp_json_encode($out);'))
    check(readback == meta, "fresh PHP session independently confirms ambiguous COMMIT")
    replay = json.loads(wp(project, "eval", 'eval(base64_decode("' + source + '"));',
                           stdin=payload))
    check(replay.get("status") == "already_applied" and replay.get("saved_meta") == meta,
          "verified exact replay, no extra metadata write")
    metas = int(inside(os.environ["CI_RESTORE_DB_CONTAINER"], "mariadb", "-uroot",
                       "-p" + ROOT_PASSWORD, "-N", "wordpress", "-e",
                       "SELECT COUNT(*) FROM wp_postmeta WHERE post_id=" + str(post_id) +
                       " AND meta_key IN ('_bloguito_permalink_scheme','rank_math_title',"
                       "'rank_math_focus_keyword','rank_math_description')"))
    count = int(inside(os.environ["CI_RESTORE_DB_CONTAINER"], "mariadb", "-uroot",
                       "-p" + ROOT_PASSWORD, "-N", "wordpress", "-e",
                       f"SELECT COUNT(*) FROM wp_posts WHERE ID={post_id}"))
    check(count == 1 and metas == 4, "lost response recovery creates no duplicate post/meta rows")
    return post_id


def release_rollback(tmp: Path, wordpress_container: str) -> None:
    """Use actual release builder and installer; a real failing smoke executable."""
    release = tmp / "release"
    info = builder.build_release(release, root=ROOT, require_clean=False)
    manifest = installer.verify_release_manifest(release)
    check(len(manifest["files"]) >= 80 and info["files"] == len(manifest["files"]),
          "real canonical release manifest and SHA inventory")
    mu_file = installer.WP_MU_CONTAINER_PATH
    active_mu = inside(wordpress_container, "sha256sum", mu_file).split()[0]
    check(active_mu == manifest["files"][installer.WP_MU_RELATIVE],
          "release MU preflight verifies actual disposable WordPress plugin bytes")
    app = tmp / "release-target" / "agent-publisher"
    app.mkdir(parents=True)
    (app / "main.py").write_bytes(b"old app main - CI sentinel")
    (app / "config.py").write_bytes((release / "agent-publisher/config.py").read_bytes())
    (app / ".env").write_text("CI_PLACEHOLDER=retain-existing-value\n")
    shell = app / "run_daily.sh"
    shell.write_text("#!/bin/sh\necho CI-OLD\n")
    shell.chmod(0o751)
    (app / "data").mkdir()
    (app / "data/editorial-release.json").write_bytes(b"CI old release record")
    shared_docs = app.parent / "docs"
    shared_docs.mkdir()
    (shared_docs / "EDITORIAL_SYSTEM.md").write_bytes(b"CI original policy")
    # This actual subprocess, not a mocked Python call, intentionally exits
    # nonzero exactly after installer writes the temporary target modules.
    venv = app / "venv" / "bin"
    venv.mkdir(parents=True)
    executable = venv / "python"
    executable.write_text("#!/bin/sh\necho 'CI injected release smoke failure' >&2\nexit 37\n")
    executable.chmod(0o750)
    try:
        installer.install(release, app, installed_mu_digest=active_mu)
    except subprocess.CalledProcessError as exc:
        check(exc.returncode == 37, "real smoke subprocess failure triggered installer rollback")
    else:
        raise AssertionError("Release smoke unexpectedly succeeded")
    check((app / "main.py").read_bytes() == b"old app main - CI sentinel" and
          not (app / "agents/edit_post.py").exists(),
          "release rollback restores replaced module and removes new files")
    check(shell.read_text() == "#!/bin/sh\necho CI-OLD\n" and
          shell.stat().st_mode & 0o777 == 0o751,
          "release rollback restores executable shell contents and permissions")
    check((shared_docs / "EDITORIAL_SYSTEM.md").read_bytes() == b"CI original policy",
          "release rollback restores existing shared policy")
    check((app / ".env").read_text() == "CI_PLACEHOLDER=retain-existing-value\n" and
          (app / "data/editorial-release.json").read_bytes() == b"CI old release record",
          "release rollback preserves credentials and earlier receipt")
    backups = list((app / "backups").glob("editorial-*/manifest.json"))
    check(len(backups) == 1 and len(json.loads(backups[0].read_text())) > 80,
          "release failure retains auditable per-file rollback receipt")


def snapshot_cycle(project: str, db_container: str, app_container: str, tmp: Path,
                   post_id: int) -> None:
    host_wp = tmp / "synthetic-wordpress-host"
    host_wp.mkdir()
    (host_wp / ".env").write_text("MYSQL_ROOT_PASSWORD=" + ROOT_PASSWORD + "\n")
    (host_wp / "docker-compose.yml").write_text("services: {synthetic: {image: example.invalid/ci}}\n")
    (host_wp / "mysql_custom.cnf").write_text("[mariadb]\nmax_connections=17\n")
    (host_wp / "uploads.ini").write_text("upload_max_filesize=4M\n")
    agent = tmp / "synthetic-agent"
    (agent / "data").mkdir(parents=True)
    (agent / "data/ci-state.json").write_text('{"state":"before-backup"}')
    (agent / ".env").write_text("SYNTHETIC_ONLY=archive-secret\n")
    (agent / "config.py").write_text("CI_FAKE_CONFIG=True\n")
    nginx = tmp / "synthetic-nginx"
    nginx.mkdir()
    (nginx / "site.conf").write_text("server { listen 127.0.0.1:10101; }\n")
    backup_dir = tmp / "backups"
    backup_dir.mkdir()

    marker(app_container, "uploads/ci/snapshot.txt", "CI_UPLOAD_BEFORE")
    marker(app_container, "plugins/ci-rollback.txt", "CI_PLUGIN_BEFORE")
    marker(app_container, "themes/ci-rollback.txt", "CI_THEME_BEFORE")
    # Archive a real, matching MU source without touching existing users' media.
    inside(app_container, "mkdir", "-p", "/var/www/html/wp-content/mu-plugins")
    call("docker", "cp", str(ROOT / "wordpress/mu-plugins/bloguito-post-row-actions.php"),
         f"{app_container}:/var/www/html/wp-content/mu-plugins/bloguito-post-row-actions.php")
    marker(app_container, "mu-plugins/ci-rollback.txt", "CI_MU_BEFORE")

    env = {**os.environ, "BACKUP_DIR": str(backup_dir), "WORDPRESS_DIR": str(host_wp),
           "AGENT_DIR": str(agent), "CONTAINER_DB": db_container,
           "CONTAINER_APP": app_container, "MYSQL_ROOT_PASSWORD": ROOT_PASSWORD,
           "NGINX_CONFIG_DIR": str(nginx)}
    backup = call("bash", str(ROOT / "agent-publisher/backup_daily.sh"), env=env,
                  timeout=130).stdout.decode()
    archives = list(backup_dir.glob("bloguito_backup_*.tar.gz"))
    check(len(archives) == 1 and "Backup completed successfully" in backup,
          "production v3 backup script generated complete disposable archive")
    archive = archives[0]
    call("bash", str(ROOT / "agent-publisher/restore_backup.sh"),
         str(archive), "--verify-only", env=env)
    check(True, "production restore verified all five archive components")

    # Simulate drift in each mutable component before calling real --yes restore.
    wp(project, "post", "update", str(post_id), "--post_title=CI changed after backup")
    for part in ("uploads/ci/snapshot.txt", "plugins/ci-rollback.txt",
                 "themes/ci-rollback.txt", "mu-plugins/ci-rollback.txt"):
        marker(app_container, part, "CI_CHANGED_AFTER_BACKUP")
    (agent / "data/ci-state.json").write_text('{"state":"changed-after-backup"}')
    (agent / ".env").write_text("SYNTHETIC_ONLY=local-not-overwrite\n")

    # Production restore imports plain CREATE TABLE statements; target MUST be
    # an empty/new DB. Drop only this isolated 'wordpress' database.
    inside(db_container, "mariadb", "-uroot", "-p" + ROOT_PASSWORD,
           "-e", "DROP DATABASE wordpress; CREATE DATABASE wordpress")
    restoration = call("bash", str(ROOT / "agent-publisher/restore_backup.sh"),
                       str(archive), "--yes", env=env, timeout=160).stdout.decode()
    check("Database, uploads, extensions and runtime JSON restored" in restoration,
          "production --yes restored DB/uploads/extensions/runtime JSON to detached target")
    check(wp(project, "post", "get", str(post_id), "--field=post_status") == "draft",
          "restored WordPress database still boots, only synthetic draft exists")
    check(wp(project, "post", "get", str(post_id), "--field=post_title") ==
          "CI ambiguous COMMIT", "restored DB reverses post edit")
    for part, original in (("uploads/ci/snapshot.txt", "CI_UPLOAD_BEFORE"),
                           ("plugins/ci-rollback.txt", "CI_PLUGIN_BEFORE"),
                           ("themes/ci-rollback.txt", "CI_THEME_BEFORE"),
                           ("mu-plugins/ci-rollback.txt", "CI_MU_BEFORE")):
        check(content(app_container, part) == original, f"v3 restores {part}")
    check((agent / "data/ci-state.json").read_text() == '{"state":"before-backup"}',
          "runtime JSON recovered")
    check((agent / ".env").read_text() == "SYNTHETIC_ONLY=local-not-overwrite\n",
          "archive secrets are never silently installed")
    dirs = inside(app_container, "sh", "-c", "find /var/www/html/wp-content -maxdepth 1 -name '.bloguito-prerestore-*' -type d").splitlines()
    check(len(dirs) == 1, "pre-restore extensions retained for manual recovery")
    export = tmp / "export-reviewed"
    call("bash", str(ROOT / "agent-publisher/restore_backup.sh"), str(archive),
         "--export-configs", str(export), "--include-secrets", env=env)
    check((export / "configs_staging/wordpress/docker-compose.yml").is_file()
          and (export / "configs_staging/agent-publisher/data/ci-state.json").is_file(),
          "reviewed export includes host settings and runtime state")
    check((export / "secrets_staging/agent-publisher/.env").read_text() ==
          "SYNTHETIC_ONLY=archive-secret\n" and
          (export / "secrets_staging/nginx/site.conf").is_file() and
          (export / "secrets_staging/wordpress/wp-config.php").is_file(),
          "opt-in secret export contains only synthetic agent/nginx/WordPress settings")
    check(not (tmp / "synthetic-wordpress-host/wp-config.php").exists(),
          "host settings were exported, not silently installed")
    check(wp(project, "post", "get", str(post_id), "--field=post_status") == "draft",
          "full site WordPress CLI smoke verifies restored synthetic draft status")


def main() -> None:
    project, db, app = verified_environment()
    with tempfile.TemporaryDirectory(prefix="bloguito-isolated-full-restore-") as work:
        tmp = Path(work)
        # The real DB job has already run its CAS suite; only exercise new cases.
        wp(project, "core", "install", "--url=http://ci-restore.invalid",
           "--title=CI detached restore", "--admin_user=ci_admin",
           "--admin_password=ci-only-password", "--admin_email=ci@restore.invalid",
           "--skip-email")
        check(wp(project, "core", "is-installed") == "", "detached WordPress actually bootstrapped")
        post_id = ambiguous_commit(project)
        snapshot_cycle(project, db, app, tmp, post_id)
        release_rollback(tmp, app)
    print("PASS: DETACHED v3 BACKUP RESTORE + AMBIGUOUS COMMIT + RELEASE ROLLBACK", flush=True)


if __name__ == "__main__":
    main()
