"""Prepare/run a disposable, offline-only R4 WordPress/MariaDB PC fixture.

Never points at Bloguito, SSH, a public endpoint, or the production compose file.
Actual Docker commands require --confirm-local-isolated and a local Docker context.
This is an infrastructure/CAS probe, NOT the unfinished R1-R3 acceptance suite.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import struct
import subprocess
import sys
import uuid
import zlib

REPO = Path(__file__).resolve().parents[2]
FIXTURES = REPO / "scratch" / "tasks" / "featured-image-r4-pc"
NAME_PATTERN = re.compile(r"bloguito_r4pc_[0-9a-f]{12}\Z")
STATE_FIELDS = {"version", "kind", "project", "compose_sha256", "php_sha256", "files"}
COMPOSE_NAME = "compose.yaml"
STATE_NAME = "fixture-state.json"
PHP_NAME = "fixture-cas.php"

COMPOSE = """# Synthetic local R4 fixture. No ports, fixed container names or production paths.
services:
  db:
    image: mariadb:11.4
    environment:
      MARIADB_ROOT_PASSWORD: ${R4_DB_ROOT_PASSWORD:?}
      MARIADB_DATABASE: r4_synthetic
      MARIADB_USER: r4_client
      MARIADB_PASSWORD: ${R4_DB_PASSWORD:?}
    volumes:
      - r4_db_data:/var/lib/mysql
    networks: [r4_private]
    healthcheck:
      test: ["CMD", "healthcheck.sh", "--connect", "--innodb_initialized"]
      interval: 5s
      timeout: 3s
      retries: 24
  web:
    image: wordpress:php8.3-apache
    environment:
      WORDPRESS_DB_HOST: db:3306
      WORDPRESS_DB_NAME: r4_synthetic
      WORDPRESS_DB_USER: r4_client
      WORDPRESS_DB_PASSWORD: ${R4_DB_PASSWORD:?}
    volumes:
      - r4_wp_data:/var/www/html
    networks: [r4_private]
    depends_on:
      db:
        condition: service_healthy
  cli:
    image: wordpress:cli-php8.3
    profiles: [tools]
    entrypoint: ["wp"]
    working_dir: /var/www/html
    environment:
      WORDPRESS_DB_HOST: db:3306
      WORDPRESS_DB_NAME: r4_synthetic
      WORDPRESS_DB_USER: r4_client
      WORDPRESS_DB_PASSWORD: ${R4_DB_PASSWORD:?}
    volumes:
      - r4_wp_data:/var/www/html
      - ./fixtures:/r4-fixtures:ro
    networks: [r4_private]
    depends_on:
      db:
        condition: service_healthy
networks:
  r4_private:
    internal: true
volumes:
  r4_db_data:
  r4_wp_data:
"""

# Executed ONLY inside newly initialized synthetic DB. This tests PHP-level
# post row locking and readback; it is not the production root-owned writer.
FIXTURE_PHP = r'''<?php
global $wpdb, $args;
$op = $args[0] ?? '';
if (!in_array($op, ['snapshot', 'cas-set', 'find-sha'], true)) { WP_CLI::error('unsupported_probe'); }
$post_id = filter_var($args[1] ?? null, FILTER_VALIDATE_INT);
if (!$post_id || $post_id <= 0) { WP_CLI::error('invalid_synthetic_post'); }
if ($op === 'find-sha') {
    $needle = $args[2] ?? '';
    if (!preg_match('/^[0-9a-f]{64}$/D', $needle)) { WP_CLI::error('invalid_sha'); }
    $matches = [];
    foreach (get_posts(['post_type' => 'attachment', 'post_status' => 'inherit',
             'post_parent' => $post_id, 'numberposts' => -1]) as $attachment) {
        $file = get_attached_file($attachment->ID);
        if ($file && is_file($file) && hash_file('sha256', $file) === $needle) {
            $matches[] = (int) $attachment->ID;
        }
    }
    WP_CLI::line(wp_json_encode($matches));
    return;
}
if ($op === 'cas-set') {
    $attachment_id = filter_var($args[2] ?? null, FILTER_VALIDATE_INT);
    $expected_content_sha = $args[3] ?? '';
    $expected_thumbnail_id = filter_var($args[4] ?? null, FILTER_VALIDATE_INT);
    if (!$attachment_id || !preg_match('/^[0-9a-f]{64}$/D', $expected_content_sha)
        || $expected_thumbnail_id === false || $expected_thumbnail_id === null) {
        WP_CLI::error('invalid_cas_request');
    }
    $wpdb->query('START TRANSACTION');
    try {
        // Lock the post row. A second independent WP process waits for COMMIT.
        $post = $wpdb->get_row($wpdb->prepare(
            "SELECT * FROM {$wpdb->posts} WHERE ID = %d FOR UPDATE", $post_id));
        if (!$post || $post->post_status !== 'draft'
            || hash('sha256', $post->post_content) !== $expected_content_sha) {
            throw new Exception('stale_post_cas');
        }
        $current = (int) $wpdb->get_var($wpdb->prepare(
            "SELECT meta_value FROM {$wpdb->postmeta} WHERE post_id = %d AND meta_key = '_thumbnail_id' LIMIT 1", $post_id));
        if ($current !== (int) $expected_thumbnail_id) { throw new Exception('stale_thumbnail_cas'); }
        if (!wp_attachment_is_image($attachment_id)
            || (int) get_post_field('post_parent', $attachment_id) !== (int) $post_id) {
            throw new Exception('unrelated_attachment');
        }
        update_post_meta($post_id, '_thumbnail_id', $attachment_id);
        update_post_meta($attachment_id, '_wp_attachment_image_alt', 'R4 synthetic alt');
        // Check the actual database rows BEFORE commit, including both writes.
        // A failed metadata write must roll back rather than report CAS success.
        $db_thumbnail = $wpdb->get_var($wpdb->prepare(
            "SELECT meta_value FROM {$wpdb->postmeta} WHERE post_id = %d AND meta_key = '_thumbnail_id' LIMIT 1", $post_id));
        $db_alt = $wpdb->get_var($wpdb->prepare(
            "SELECT meta_value FROM {$wpdb->postmeta} WHERE post_id = %d AND meta_key = '_wp_attachment_image_alt' LIMIT 1", $attachment_id));
        if ((string) $db_thumbnail !== (string) $attachment_id
            || $db_alt !== 'R4 synthetic alt' || $wpdb->last_error !== '') {
            throw new Exception('metadata_write_not_verified');
        }
        $wpdb->query('COMMIT');
    } catch (Throwable $exc) {
        $wpdb->query('ROLLBACK');
        WP_CLI::error($exc->getMessage());
    }
}
$post = get_post($post_id);
if (!$post) { WP_CLI::error('post_not_found'); }
$attachment_id = (int) get_post_thumbnail_id($post_id);
$file = $attachment_id ? get_attached_file($attachment_id) : false;
$all = get_posts(['post_type' => 'attachment', 'post_status' => 'inherit',
    'post_parent' => $post_id, 'numberposts' => -1]);
$result = [
    'post_id' => (int) $post->ID,
    'post_status' => $post->post_status,
    'post_title' => $post->post_title,
    'post_name' => $post->post_name,
    'post_excerpt' => $post->post_excerpt,
    'content_sha256' => hash('sha256', $post->post_content),
    'thumbnail_id' => $attachment_id,
    'attachment_sha256' => ($file && is_file($file)) ? hash_file('sha256', $file) : null,
    'alt' => $attachment_id ? get_post_meta($attachment_id, '_wp_attachment_image_alt', true) : null,
    'attachment_url' => $attachment_id ? wp_get_attachment_url($attachment_id) : null,
    'attachment_count' => count($all),
];
WP_CLI::line(wp_json_encode($result));
'''


def _sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _is_link_or_junction(path: Path) -> bool:
    # Windows directory junctions are reparse points but are not necessarily
    # reported as symlinks. Python 3.12 exposes a dedicated junction predicate.
    return path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction())


def _png_bytes(rgb: tuple[int, int, int]) -> bytes:
    """Deterministic valid 256x144 test-only PNG without PIL or image services."""
    width, height = 256, 144
    payload = b"".join(b"\x00" + bytes(rgb) * width for _ in range(height))

    def chunk(label: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(label + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + label + data + struct.pack(">I", crc)

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">2I5B", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(payload, 9)) + chunk(b"IEND", b""))


def _write_exclusive(path: Path, payload: bytes, *, private: bool = False) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(path, flags, 0o600 if private else 0o644)
    with os.fdopen(fd, "wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def init_fixture() -> Path:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    project = "bloguito_r4pc_" + uuid.uuid4().hex[:12]
    folder = FIXTURES / project
    folder.mkdir(mode=0o700)
    (folder / "fixtures").mkdir()
    _write_exclusive(folder / COMPOSE_NAME, COMPOSE.encode("utf-8"))
    _write_exclusive(folder / PHP_NAME, FIXTURE_PHP.encode("utf-8"))
    # Docker mounts only ./fixtures:ro, keep source/PHP scoped there.
    _write_exclusive(folder / "fixtures" / PHP_NAME, FIXTURE_PHP.encode("utf-8"))
    files = {}
    for index, rgb in enumerate(((26, 81, 154), (171, 83, 24), (30, 145, 97)), 1):
        data = _png_bytes(rgb)
        filename = f"synthetic-{index}.png"
        _write_exclusive(folder / "fixtures" / filename, data)
        files[filename] = _sha(data)
    # These credentials belong only to disposable, internal-network fixtures.
    dotenv = (f"R4_DB_ROOT_PASSWORD={secrets.token_hex(32)}\n"
              f"R4_DB_PASSWORD={secrets.token_hex(32)}\n"
              f"R4_ADMIN_PASSWORD={secrets.token_hex(32)}\n")
    _write_exclusive(folder / ".env", dotenv.encode("ascii"), private=True)
    state = {"version": 1, "kind": "disposable-local-r4-synthetic-only",
             "project": project, "compose_sha256": _sha(COMPOSE.encode()),
             "php_sha256": _sha(FIXTURE_PHP.encode()), "files": files}
    _write_exclusive(folder / STATE_NAME, (json.dumps(state, indent=2) + "\n").encode())
    return folder


def verified_fixture(folder: Path) -> dict:
    supplied = Path(folder).absolute()
    if _is_link_or_junction(supplied):
        raise ValueError("fixture_symlink_denied")
    folder = supplied.resolve()
    root = FIXTURES.resolve()
    if folder.parent != root or not NAME_PATTERN.fullmatch(folder.name):
        raise ValueError("fixture_outside_reserved_scratch_root")
    if _is_link_or_junction(folder) or _is_link_or_junction(folder / STATE_NAME):
        raise ValueError("fixture_symlink_denied")
    state = json.loads((folder / STATE_NAME).read_text(encoding="utf-8"))
    if (not isinstance(state, dict) or set(state) != STATE_FIELDS
            or state["version"] != 1 or state["kind"] != "disposable-local-r4-synthetic-only"
            or state["project"] != folder.name or state["compose_sha256"] != _sha(COMPOSE.encode())
            or state["php_sha256"] != _sha(FIXTURE_PHP.encode())):
        raise ValueError("fixture_state_invalid_or_changed")
    observed = {COMPOSE_NAME: state["compose_sha256"], PHP_NAME: state["php_sha256"]}
    for name, sha in observed.items():
        file = folder / name
        if file.is_symlink() or _sha(file.read_bytes()) != sha:
            raise ValueError("fixture_file_changed:" + name)
    required = {f"synthetic-{index}.png" for index in (1, 2, 3)}
    if not isinstance(state["files"], dict) or set(state["files"]) != required:
        raise ValueError("fixture_source_inventory_invalid")
    fixtures_dir = folder / "fixtures"
    if (_is_link_or_junction(fixtures_dir) or not fixtures_dir.is_dir()
            or fixtures_dir.resolve() != fixtures_dir):
        raise ValueError("fixture_mount_directory_untrusted")
    # A :ro bind mount can still disclose arbitrary host files included in
    # the mounted folder. Require exactly our four audited synthetic assets.
    if {entry.name for entry in fixtures_dir.iterdir()} != required | {PHP_NAME}:
        raise ValueError("fixture_mount_unexpected_entries")
    for filename, digest in state["files"].items():
        source = fixtures_dir / filename
        if _is_link_or_junction(source) or not source.is_file() or _sha(source.read_bytes()) != digest:
            raise ValueError("fixture_source_changed:" + filename)
    copied_php = fixtures_dir / PHP_NAME
    if (_is_link_or_junction(copied_php) or not copied_php.is_file()
            or _sha(copied_php.read_bytes()) != state["php_sha256"]):
        raise ValueError("fixture_php_changed")
    secret_file = folder / ".env"
    if _is_link_or_junction(secret_file) or secret_file.resolve() != secret_file:
        raise ValueError("fixture_credentials_symlink_denied")
    creds = secret_file.read_text(encoding="ascii").splitlines()
    if len(creds) != 3 or any("=" not in line for line in creds):
        raise ValueError("fixture_credentials_missing")
    if {line.split("=", 1)[0] for line in creds} != {
            "R4_DB_ROOT_PASSWORD", "R4_DB_PASSWORD", "R4_ADMIN_PASSWORD"}:
        raise ValueError("fixture_credentials_invalid")
    if any(len(line.split("=", 1)[1]) != 64 for line in creds):
        raise ValueError("fixture_credentials_invalid")
    return state


def _check_local_docker() -> None:
    if any(os.environ.get(key) for key in (
            "DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH")):
        raise RuntimeError("explicit_docker_environment_override_denied")
    current = subprocess.run(["docker", "context", "show"],
                             capture_output=True, text=True, check=True, timeout=15).stdout.strip()
    context = subprocess.run(["docker", "context", "inspect", current],
                             capture_output=True, text=True, check=True, timeout=15)
    payload = json.loads(context.stdout)
    endpoint = payload[0]["Endpoints"]["docker"]["Host"]
    if not endpoint.startswith(("npipe://", "unix://")):
        raise RuntimeError("nonlocal_docker_context_denied")


def compose_args(folder: Path, *args: str) -> list[str]:
    state = verified_fixture(folder)
    return (["docker", "compose", "-f", str(Path(folder) / COMPOSE_NAME),
             "--project-directory", str(folder), "--env-file", str(Path(folder) / ".env"),
             "-p", state["project"], *args])


def _docker(folder: Path, *args: str, stdin: str | None = None,
            timeout: int = 180, allow_failure: bool = False) -> subprocess.CompletedProcess:
    try:
        result = subprocess.run(compose_args(folder, *args), cwd=folder,
                                input=stdin, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        # TimeoutExpired carries .cmd and sometimes .output/.stderr with data
        # including stdin/prompt text. Never propagate/serialize its contents.
        raise RuntimeError("synthetic_docker_execution_failed:" + type(exc).__name__) from None
    if result.returncode != 0 and not allow_failure:
        # Deliberately do not print stdout/stderr: they may include connection
        # strings, credentials, or other private fixture diagnostics.
        raise RuntimeError(f"synthetic_docker_command_failed:rc={result.returncode}")
    return result


def _cli(folder: Path, *wp_args: str, timeout: int = 180, stdin: str | None = None,
         allow_failure: bool = False) -> subprocess.CompletedProcess:
    return _docker(folder, "run", "--rm", "-T", "cli", *wp_args,
                   stdin=stdin, timeout=timeout, allow_failure=allow_failure)


def start(folder: Path) -> dict:
    _check_local_docker()
    state = verified_fixture(folder)
    _docker(folder, "up", "-d", "--wait", "db", "web", timeout=300)
    return {"project": state["project"], "docker_started": True,
            "status": "R4_FIXTURE_RUNNING_NOT_ACCEPTED"}


def stop(folder: Path, *, destroy_synthetic_data: bool = False) -> dict:
    _check_local_docker()
    state = verified_fixture(folder)
    # Never remove unrelated containers, even if an operator accidentally
    # assigned our unique project label to an additional local service.
    argv = ["down", "--timeout", "20"]
    if destroy_synthetic_data:
        argv.append("--volumes")
    _docker(folder, *argv, timeout=180)
    return {"project": state["project"], "stopped": True,
            "synthetic_volumes_removed": bool(destroy_synthetic_data)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("init", "check", "start", "stop"))
    parser.add_argument("--fixture", type=Path,
                        help="Absolute path returned by init inside the reserved scratch root")
    parser.add_argument("--confirm-local-isolated", action="store_true",
                        help="Required for all Docker actions; refuses remote Docker contexts")
    parser.add_argument("--destroy-synthetic-data", action="store_true",
                        help="With stop, remove only this uniquely named fixture's Docker volumes")
    options = parser.parse_args(argv)
    try:
        if options.action == "init":
            if options.fixture or options.destroy_synthetic_data:
                raise ValueError("init_accepts_no_fixture_or_destructive_flags")
            folder = init_fixture()
            result = {"status": "READY_OFFLINE_ONLY", "fixture": str(folder),
                      "project": folder.name}
        else:
            if options.fixture is None:
                raise ValueError("fixture_path_required")
            if options.destroy_synthetic_data and options.action != "stop":
                raise ValueError("destroy_synthetic_data_only_with_stop")
            state = verified_fixture(options.fixture)
            if options.action == "check":
                result = {"status": "READY_OFFLINE_ONLY", "project": state["project"],
                          "no_production_paths_or_ports": True}
            else:
                if not options.confirm_local_isolated:
                    raise ValueError("confirm_local_isolated_required")
                result = (start(options.fixture) if options.action == "start" else
                          stop(options.fixture, destroy_synthetic_data=options.destroy_synthetic_data))
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, KeyError, IndexError) as exc:
        print(json.dumps({"status": "NO-GO", "reason": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
