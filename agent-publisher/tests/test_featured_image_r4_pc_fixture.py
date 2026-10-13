"""Offline PC fixture safety contract. No Docker / SSH / WordPress is used."""

from __future__ import annotations

import importlib.util
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch


OPS = Path(__file__).resolve().parents[2] / "scripts" / "ops"
sys.path.insert(0, str(OPS))
spec = importlib.util.spec_from_file_location("image_r4_pc_fixture", OPS / "image_r4_pc_fixture.py")
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
sys.modules.setdefault("image_r4_pc_fixture", fixture)
smoke_spec = importlib.util.spec_from_file_location("image_r4_pc_smoke", OPS / "image_r4_pc_smoke.py")
smoke = importlib.util.module_from_spec(smoke_spec)
smoke_spec.loader.exec_module(smoke)


class R4PCFixtureOfflineTests(unittest.TestCase):
    def setUp(self):
        workspace = tempfile.TemporaryDirectory()
        self.addCleanup(workspace.cleanup)
        self.root = Path(workspace.name)
        self.override = patch.object(fixture, "FIXTURES", self.root / "reserved-scratch")
        self.override.start()
        self.addCleanup(self.override.stop)
        self.folder = fixture.init_fixture()

    def test_unique_unrelated_project_and_no_production_compose_configuration(self):
        self.assertRegex(self.folder.name, r"^bloguito_r4pc_[0-9a-f]{12}$")
        other = fixture.init_fixture()
        self.assertNotEqual(self.folder.name, other.name)
        self.assertEqual("disposable-local-r4-synthetic-only",
                         fixture.verified_fixture(self.folder)["kind"])
        compose = (self.folder / "compose.yaml").read_text(encoding="utf-8")
        for forbidden in ("container_name:", "ports:", "127.0.0.1:8080", "wordpress_app",
                          "wordpress_db", "./wp-cli.phar", "sudo", "ssh", "bloguito:",
                          "/var/run/docker.sock", "external: true"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, compose)
        self.assertIn("internal: true", compose)
        self.assertIn("./fixtures:/r4-fixtures:ro", compose)
        self.assertIn("profiles: [tools]", compose)

    def test_credential_values_are_random_not_hardcoded_and_never_in_compose(self):
        first = (self.folder / ".env").read_text(encoding="ascii")
        second = (fixture.init_fixture() / ".env").read_text(encoding="ascii")
        self.assertNotEqual(first, second)
        self.assertEqual(3, len(first.splitlines()))
        self.assertTrue(all(len(line.split("=", 1)[1]) == 64 for line in first.splitlines()))
        self.assertNotIn(first.splitlines()[0].split("=", 1)[1], fixture.COMPOSE)
        self.assertEqual(0, (self.folder / ".env").stat().st_mode & 0o077 if os.name == "posix" else 0)

    def test_synthetic_png_validity_and_php_presence(self):
        state = fixture.verified_fixture(self.folder)
        self.assertEqual(3, len(state["files"]))
        self.assertEqual(3, len(set(state["files"].values())))
        for name in state["files"]:
            data = (self.folder / "fixtures" / name).read_bytes()
            self.assertTrue(data.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertIn("FOR UPDATE", fixture.FIXTURE_PHP)
        self.assertIn("ROLLBACK", fixture.FIXTURE_PHP)
        self.assertIn("attachment_sha256", fixture.FIXTURE_PHP)
        self.assertIn("metadata_write_not_verified", fixture.FIXTURE_PHP)
        self.assertLess(fixture.FIXTURE_PHP.index("metadata_write_not_verified"),
                        fixture.FIXTURE_PHP.index("$wpdb->query('COMMIT')"))

    def test_fixture_tamper_is_denied_before_any_docker_command(self):
        with (patch.object(fixture, "_check_local_docker") as docker,
              patch.object(fixture, "_docker") as command):
            (self.folder / "compose.yaml").write_text("services: {}", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "fixture_file_changed"):
                fixture.verified_fixture(self.folder)
            with self.assertRaisesRegex(ValueError, "fixture_file_changed"):
                fixture.compose_args(self.folder, "up")
            command.assert_not_called()
            docker.assert_not_called()

    def test_fixture_cannot_be_relocated_to_production_or_modified_credential_keys(self):
        with self.assertRaisesRegex(ValueError, "fixture_outside_reserved_scratch_root"):
            fixture.verified_fixture(self.root)
        (self.folder / ".env").write_text("MYSQL_ROOT_PASSWORD=x\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "fixture_credentials_missing"):
            fixture.verified_fixture(self.folder)

    def test_extra_file_in_bind_mount_is_rejected_before_docker(self):
        fixture_path = self.folder / "fixtures"
        for filename in ("private-key", ".hidden", "synthetic-extra.png"):
            with self.subTest(filename=filename):
                injection = fixture_path / filename
                injection.write_text("do not mount", encoding="utf-8")
                try:
                    with self.assertRaisesRegex(ValueError, "fixture_mount_unexpected_entries"):
                        fixture.verified_fixture(self.folder)
                finally:
                    injection.unlink()

    def test_directory_symlink_or_junction_mount_is_rejected(self):
        fixture_path = self.folder / "fixtures"
        with patch.object(fixture, "_is_link_or_junction", side_effect=lambda path:
                          Path(path) == fixture_path):
            with self.assertRaisesRegex(ValueError, "fixture_mount_directory_untrusted"):
                fixture.verified_fixture(self.folder)

    def test_env_symlink_or_junction_denied(self):
        env = self.folder / ".env"
        with patch.object(fixture, "_is_link_or_junction", side_effect=lambda path:
                          Path(path) == env):
            with self.assertRaisesRegex(ValueError, "fixture_credentials_symlink_denied"):
                fixture.verified_fixture(self.folder)

    def test_docker_context_requires_local_socket_and_no_environment_override(self):
        def remote(argv, **_kwargs):
            if argv[-1] == "show":
                return subprocess.CompletedProcess(argv, 0, stdout="default\n")
            return subprocess.CompletedProcess(argv, 0, stdout=json.dumps([
                {"Endpoints": {"docker": {"Host": "tcp://remote.example:2376"}}}]))
        with (patch.dict(os.environ, {"DOCKER_HOST": "", "DOCKER_CONTEXT": "",
                                          "DOCKER_CERT_PATH": "", "DOCKER_TLS_VERIFY": ""}),
              patch.object(fixture.subprocess, "run", side_effect=remote)):
            with self.assertRaisesRegex(RuntimeError, "nonlocal_docker_context_denied"):
                fixture._check_local_docker()
        with patch.dict(os.environ, {"DOCKER_HOST": "tcp://prod:2376"}):
            with self.assertRaisesRegex(RuntimeError, "explicit_docker_environment_override_denied"):
                fixture._check_local_docker()

    def test_valid_local_context_and_compose_invocation_scope(self):
        def local(argv, **_kwargs):
            if argv[-1] == "show":
                return subprocess.CompletedProcess(argv, 0, stdout="desktop-linux\n")
            return subprocess.CompletedProcess(argv, 0, stdout=json.dumps([
                {"Endpoints": {"docker": {"Host": "npipe:////./pipe/dockerDesktopLinuxEngine"}}}]))
        with (patch.dict(os.environ, {"DOCKER_HOST": "", "DOCKER_CONTEXT": "",
                                          "DOCKER_CERT_PATH": "", "DOCKER_TLS_VERIFY": ""}),
              patch.object(fixture.subprocess, "run", side_effect=local)):
            fixture._check_local_docker()
        argv = fixture.compose_args(self.folder, "up", "-d", "--wait", "db", "web")
        self.assertEqual("docker", argv[0])
        self.assertEqual("compose", argv[1])
        self.assertIn(self.folder.name, argv)
        self.assertIn(str(self.folder / ".env"), argv)
        self.assertIn(str(self.folder / "compose.yaml"), argv)
        self.assertNotIn("/projects/Bloguito/wordpress/docker-compose.yml", argv)

    def test_start_stop_requires_confirmation_and_scope_no_volume_wipe_by_default(self):
        self.assertEqual(2, fixture.main(["start", "--fixture", str(self.folder)]))
        self.assertEqual(2, fixture.main(["stop", "--fixture", str(self.folder),
                                          "--destroy-synthetic-data"]))
        with (patch.object(fixture, "_check_local_docker"),
              patch.object(fixture, "_docker") as command):
            fixture.start(self.folder)
            fixture.stop(self.folder)
            fixture.stop(self.folder, destroy_synthetic_data=True)
        self.assertNotIn("--volumes", command.call_args_list[1].args)
        self.assertIn("--volumes", command.call_args_list[2].args)
        self.assertEqual(("up", "-d", "--wait", "db", "web"),
                         command.call_args_list[0].args[1:])

    def test_smoke_runner_refuses_without_explicit_local_confirmation(self):
        with patch.object(smoke, "smoke") as perform:
            self.assertEqual(2, smoke.main(["--fixture", str(self.folder)]))
        perform.assert_not_called()

    def test_failed_preflight_does_not_create_smoke_receipt(self):
        with patch.object(fixture, "_check_local_docker", side_effect=RuntimeError("no_docker")):
            with self.assertRaisesRegex(RuntimeError, "no_docker"):
                smoke.smoke(self.folder)
        self.assertFalse((self.folder / "r4-smoke-evidence.json").exists())

    def test_existing_smoke_receipt_refuses_second_nonidempotent_attempt(self):
        (self.folder / "r4-smoke-evidence.json").write_text('{"status":"NO-GO"}', encoding="utf-8")
        with (patch.object(fixture, "_check_local_docker"),
              patch.object(smoke, "_wp") as command):
            with self.assertRaisesRegex(ValueError, "fixture_smoke_already_attempted"):
                smoke.smoke(self.folder)
        command.assert_not_called()

    def _mocked_smoke(self, *, failed_race_transport=False):
        """Exercise real smoke CAS parsing through a fake WP process; no Docker."""
        source = fixture.verified_fixture(self.folder)["files"]
        media_sha = [source[f"synthetic-{idx}.png"] for idx in (1, 2, 3)]
        ids = [201, 202, 203]
        body_sha = hashlib.sha256(smoke.BODY.encode()).hexdigest()
        current = {"thumb": 0, "attached": [], "imports": 0, "failed_transports": 0}
        lock = threading.Lock()

        def fake_wp(_folder, *args, allow_failure=False, stdin=None):
            if args[:2] == ("core", "is-installed"):
                return subprocess.CompletedProcess(args, 1, stdout="")
            if args[:2] == ("core", "version"):
                return subprocess.CompletedProcess(args, 0, stdout="6.9.0")
            if args[:2] == ("core", "install"):
                self.assertEqual("--prompt=admin_password", args[-1])
                self.assertFalse(any("--admin_password=" in arg for arg in args))
                self.assertEqual(65, len(stdin))  # 64 secret chars + newline
                return subprocess.CompletedProcess(args, 0, stdout="ok")
            if args[:2] == ("post", "create"):
                return subprocess.CompletedProcess(args, 0, stdout="123\n")
            if args[:2] == ("media", "import"):
                number = current["imports"]
                current["imports"] += 1
                current["attached"].append(ids[number])
                return subprocess.CompletedProcess(args, 0, stdout=str(ids[number]))
            if args[:3] == ("eval-file", "/r4-fixtures/fixture-cas.php", "cas-set"):
                post, attachment, sha, previous = args[3:7]
                self.assertEqual("123", post)
                with lock:
                    if failed_race_transport and attachment == "203" and previous == "201":
                        current["failed_transports"] += 1
                        return subprocess.CompletedProcess(args, 125, stdout="",
                                                           stderr="Cannot connect to Docker daemon\n")
                    if sha != body_sha:
                        return subprocess.CompletedProcess(args, 1, stdout="",
                                                           stderr="Error: stale_post_cas\n")
                    if current["thumb"] != int(previous):
                        return subprocess.CompletedProcess(args, 1, stdout="",
                                                           stderr="Error: stale_thumbnail_cas\n")
                    current["thumb"] = int(attachment)
                    return subprocess.CompletedProcess(
                        args, 0, stdout=json.dumps(fake_probe(_folder, "snapshot", 123)))
            raise AssertionError(args)

        def fake_probe(_folder, operation, post_id, *details):
            self.assertEqual(123, post_id)
            if operation == "find-sha":
                self.assertIn(details[0], media_sha)
                candidate = ids[media_sha.index(details[0])]
                return [candidate] if candidate in current["attached"] else []
            self.assertEqual("snapshot", operation)
            thumb = current["thumb"]
            return {
                "post_id": 123, "post_status": "draft", "post_title": smoke.TITLE,
                "post_name": "r4-isolated-synthetic-draft", "post_excerpt": "R4 synthetic excerpt",
                "content_sha256": body_sha, "thumbnail_id": thumb,
                "attachment_sha256": media_sha[ids.index(thumb)] if thumb else None,
                "alt": smoke.ALT if thumb else None,
                "attachment_url": f"http://web/uploads/{thumb}.png" if thumb else None,
                "attachment_count": len(current["attached"]),
            }

        with (patch.object(fixture, "_check_local_docker"),
              patch.object(smoke, "_wp", side_effect=fake_wp),
              patch.object(smoke, "_probe", side_effect=fake_probe)):
            result = smoke.smoke(self.folder)
        return result, current

    def test_mocked_smoke_flow_never_becomes_real_r4_acceptance(self):
        result, current = self._mocked_smoke()
        self.assertEqual("SYNTHETIC_E2E_PASS_R4_ACCEPTANCE_NO_GO", result["status"])
        self.assertFalse(result["production_writer_tested"])
        self.assertFalse(result["r4_acceptance"])
        self.assertEqual(3, current["imports"])
        self.assertTrue(all(result["checks"].values()))
        self.assertEqual(result,
                         json.loads((self.folder / "r4-smoke-evidence.json").read_text(encoding="utf-8")))

    def test_nonzero_transport_failure_in_race_cannot_count_as_cas_conflict(self):
        result, current = self._mocked_smoke(failed_race_transport=True)
        self.assertEqual(1, current["failed_transports"])
        self.assertEqual("NO-GO", result["status"])
        self.assertEqual("synthetic_wp_cas_failure_unclassified", result["error"])
        self.assertNotIn("real_wp_row_lock_serialized_race", result["checks"])

    def test_exact_cas_denial_markers_required_and_generic_failure_rejected(self):
        base = subprocess.CompletedProcess(["wp", "eval-file"], 1, stdout="",
                                           stderr="Error: stale_post_cas\n")
        with patch.object(smoke, "_wp", return_value=base):
            self.assertEqual("stale_post_cas", smoke._attempt(self.folder, 123, 201,
                                                               "0" * 64, 0))
        base.stderr = "Error: stale_thumbnail_cas\n"
        with patch.object(smoke, "_wp", return_value=base):
            self.assertEqual("stale_thumbnail_cas", smoke._attempt(
                self.folder, 123, 201, "0" * 64, 0))
        for rc, stderr in ((1, "Error: database connection lost\n"),
                           (125, "Error: stale_thumbnail_cas\n"),
                           (1, "Error: stale_thumbnail_cas\nDocker error"),
                           (137, "")):
            with self.subTest(rc=rc, stderr=stderr):
                base = subprocess.CompletedProcess(["wp", "eval-file"], rc, stdout="",
                                                   stderr=stderr)
                with patch.object(smoke, "_wp", return_value=base):
                    with self.assertRaisesRegex(ValueError, "synthetic_wp_cas_failure_unclassified"):
                        smoke._attempt(self.folder, 123, 201, "0" * 64, 0)

    def test_timeout_with_sensitive_subprocess_args_never_leaks_credentials(self):
        secret = "DO_NOT_LOG_SYNTHETIC_PASSWORD_" + "z" * 50
        args = ["docker", "compose", "run", "--admin_password=" + secret]
        with patch.object(fixture.subprocess, "run", side_effect=subprocess.TimeoutExpired(
                cmd=args, timeout=1, output=secret.encode(), stderr=secret.encode())):
            with self.assertRaises(RuntimeError) as raised:
                fixture._docker(self.folder, "run", "--rm", "-T", "cli", "core", "install",
                                stdin=secret + "\n")
        self.assertNotIn(secret, str(raised.exception))
        self.assertIn("synthetic_docker_execution_failed:TimeoutExpired", str(raised.exception))

        with (patch.object(fixture, "_check_local_docker"),
              patch.object(smoke, "_wp", side_effect=subprocess.TimeoutExpired(
                  cmd=args, timeout=1, output=secret.encode(), stderr=secret.encode()))):
            result = smoke.smoke(self.folder)
        serialized = (self.folder / "r4-smoke-evidence.json").read_text(encoding="utf-8")
        self.assertEqual("NO-GO", result["status"])
        self.assertNotIn(secret, serialized)
        self.assertNotIn(secret, json.dumps(result))


if __name__ == "__main__":
    unittest.main()
