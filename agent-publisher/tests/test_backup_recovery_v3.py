"""Synthetic backup/recovery checks; never open the production Docker engine."""

import gzip
import hashlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
BACKUP = ROOT / "agent-publisher" / "backup_daily.sh"
RESTORE = ROOT / "agent-publisher" / "restore_backup.sh"
SYNC = ROOT / "scripts" / "sync_backups.py"
SPEC = importlib.util.spec_from_file_location("bloguito_backup_sync_test", SYNC)
sync_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync_module)


def tar_bytes(files, *, symlink=None):
    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode="w:gz") as archive:
        for name, content in files.items():
            item = tarfile.TarInfo(name)
            item.size = len(content)
            archive.addfile(item, io.BytesIO(content))
        if symlink:
            item = tarfile.TarInfo(symlink)
            item.type = tarfile.SYMTYPE
            item.linkname = "../../external-secret"
            archive.addfile(item)
    return data.getvalue()


def snapshot(unsafe_upload=False, symlink=False, outside_component=False):
    components = {
        "db": gzip.compress(b"CREATE TABLE wp_posts (id int);"),
        "uploads": tar_bytes({"../outside.txt" if unsafe_upload else
                              "unrelated/photo.jpg" if outside_component else "uploads/photo.jpg": b"photo"},
                             symlink="uploads/escape" if symlink else None),
        "wp_content": tar_bytes({"plugins/example/main.php": b"plugin", "themes/example/style.css": b"theme",
                                 "mu-plugins/boot.php": b"mu-plugin"}),
        "configs": tar_bytes({"configs_staging/wordpress/docker-compose.yml": b"services: {}"}),
        "secrets": tar_bytes({"secrets_staging/wordpress/.env": b"TEST_PLACEHOLDER=not-a-real-secret"}),
    }
    filenames = {
        "db": "db.sql.gz", "uploads": "uploads.tar.gz", "wp_content": "wp-content.tar.gz",
        "configs": "configs.tar.gz", "secrets": "secrets.tar.gz",
    }
    manifest = {"version": "3.0", "components": {
        key: {"file": filenames[key], "size_bytes": len(value), "sha256": hashlib.sha256(value).hexdigest()}
        for key, value in components.items()
    }}
    return tar_bytes({**{filenames[key]: value for key, value in components.items()},
                      "manifest.json": json.dumps(manifest).encode()})


class SnapshotRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.archive = self.root / "bloguito_backup_20260920_100000.tar.gz"
        self.archive.write_bytes(snapshot())

    def restore(self, *args):
        if os.name == "nt":
            bash = Path("C:/Program Files/Git/bin/bash.exe")
            if not bash.is_file():
                self.skipTest("Git Bash unavailable")
        else:
            bash = shutil.which("bash")
            if not bash:
                self.skipTest("Bash unavailable")
        env = {**os.environ, "BACKUP_PYTHON": "python" if os.name == "nt" else "python3",
               "WORDPRESS_DIR": str(self.root / "no-live-wordpress"),
               "AGENT_DIR": str(self.root / "no-live-agent")}
        return subprocess.run([str(bash), str(RESTORE), str(self.archive), *args],
                              capture_output=True, text=True, env=env, timeout=30)

    @staticmethod
    def shell_path(path):
        if os.name == "nt":
            return "/" + path.drive[0].lower() + path.as_posix()[2:]
        return str(path)

    def test_snapshot_v3_integrity_and_export_with_secrets_opt_in(self):
        self.assertEqual(sync_module.verify_archive(self.archive), "3.0")
        verified = self.restore("--verify-only")
        self.assertEqual(verified.returncode, 0, verified.stderr)
        self.assertIn("VERIFY_ONLY_OK", verified.stdout)
        exported = self.root / "exported"
        result = self.restore("--export-configs", self.shell_path(exported))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((exported / "secrets_staging").exists())
        self.assertTrue((exported / "configs_staging/wordpress/docker-compose.yml").exists())
        secret_export = self.root / "with-secrets"
        result = self.restore("--export-configs", self.shell_path(secret_export), "--include-secrets")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((secret_export / "secrets_staging/wordpress/.env").exists())
        self.assertNotIn("TEST_PLACEHOLDER", result.stdout + result.stderr)

    def test_checksum_mismatch_and_traversal_refused_before_export(self):
        corrupted = bytearray(self.archive.read_bytes())
        corrupted[-80] ^= 1
        self.archive.write_bytes(corrupted)
        with self.assertRaises(sync_module.BackupError):
            sync_module.verify_archive(self.archive)
        result = self.restore("--verify-only")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / "outside.txt").exists())

        self.archive.write_bytes(snapshot(unsafe_upload=True))
        with self.assertRaises(sync_module.BackupError):
            sync_module.verify_archive(self.archive)
        exported = self.root / "should-not-exist"
        result = self.restore("--export-configs", self.shell_path(exported))
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(exported.exists())

        for content in (snapshot(symlink=True), snapshot(outside_component=True)):
            self.archive.write_bytes(content)
            with self.assertRaises(sync_module.BackupError):
                sync_module.verify_archive(self.archive)
            self.assertNotEqual(self.restore("--verify-only").returncode, 0)

    def test_no_implicit_restore_of_legacy_or_secrets_export(self):
        result = self.restore("--include-secrets")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requires", result.stdout)
        exported = self.root / "existing"
        exported.mkdir()
        (exported / "keep.txt").write_text("preserve")
        self.assertNotEqual(self.restore("--export-configs", self.shell_path(exported)).returncode, 0)
        self.assertEqual((exported / "keep.txt").read_text(), "preserve")

    def test_backup_script_builds_complete_v3_snapshot_with_fake_docker(self):
        if os.name == "nt":
            bash = Path("C:/Program Files/Git/bin/bash.exe")
            if not bash.is_file():
                self.skipTest("Git Bash unavailable")
        else:
            bash = shutil.which("bash")
            if not bash:
                self.skipTest("Bash unavailable")
        wp_content = self.root / "fake-wordpress-content"
        for directory in ("uploads", "plugins", "themes", "mu-plugins"):
            (wp_content / directory).mkdir(parents=True)
            (wp_content / directory / "fixture.txt").write_text(directory)
        agent = self.root / "fake-agent"
        (agent / "data").mkdir(parents=True)
        (agent / "data/history.json").write_text("{}")
        (agent / ".env").write_text("TEST_PLACEHOLDER=secret")
        (agent / "config.py").write_text("EXAMPLE=True")
        wordpress = self.root / "fake-wordpress"
        wordpress.mkdir()
        (wordpress / ".env").write_text("MYSQL_ROOT_PASSWORD=test_only")
        (wordpress / "docker-compose.yml").write_text("services: {}")
        nginx = self.root / "fake-nginx"
        nginx.mkdir()
        (nginx / "nginx.conf").write_text("events {}")
        destination = self.root / "generated-backups"
        destination.mkdir()
        # Daily retention must never delete explicitly isolated deployment
        # snapshots in nested folders, even when their names are identical.
        protected = destination / "isolated-postdeploy"
        protected.mkdir()
        protected_archive = protected / "bloguito_backup_20260901_040000.tar.gz"
        protected_archive.write_bytes(b"independent archive kept outside daily rotation")
        old_daily = destination / "bloguito_backup_20260901_040000.tar.gz"
        old_daily.write_bytes(b"expired daily archive")
        old_time = time.time() - 10 * 24 * 60 * 60
        os.utime(protected_archive, (old_time, old_time))
        os.utime(old_daily, (old_time, old_time))

        # BASH_ENV injects a local function, so the backup script cannot access a
        # real Docker daemon even if one is running on the developer's computer.
        mock = self.root / "fake-docker.bash"
        mock.write_text("""docker() {
  case \"$1\" in
    ps) return 0 ;;
    exec)
      shift
      container=\"$1\"
      shift
      if [ \"$container\" = wordpress_db ]; then printf 'CREATE TABLE fixture (id int);'; return 0; fi
      case \"$1\" in
        test) return 1 ;;
        sh) tar -czf - -C \"$FAKE_WP_CONTENT_DIR\" plugins themes mu-plugins ;;
        tar) tar -czf - -C \"$FAKE_WP_CONTENT_DIR\" uploads ;;
        *) return 1 ;;
      esac
      ;;
    *) return 1 ;;
  esac
}
""")
        env = {**os.environ, "BASH_ENV": self.shell_path(mock),
               "FAKE_WP_CONTENT_DIR": self.shell_path(wp_content),
               "BACKUP_DIR": self.shell_path(destination),
               "WORDPRESS_DIR": self.shell_path(wordpress),
               "AGENT_DIR": self.shell_path(agent),
               "NGINX_CONFIG_DIR": self.shell_path(nginx),
               "MYSQL_ROOT_PASSWORD": "test_only"}
        result = subprocess.run([str(bash), str(BACKUP)], capture_output=True,
                                text=True, encoding="utf-8", errors="replace", env=env, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(protected_archive.read_bytes(), b"independent archive kept outside daily rotation")
        self.assertFalse(old_daily.exists(), "expired root daily archive should be pruned")
        archives = list(destination.glob("bloguito_backup_*.tar.gz"))
        self.assertEqual(len(archives), 1)
        self.assertEqual(sync_module.verify_archive(archives[0]), "3.0")
        with tarfile.open(archives[0], "r:gz") as outer:
            with tarfile.open(fileobj=outer.extractfile("configs.tar.gz"), mode="r:gz") as configs:
                self.assertFalse(any(name.endswith("/.env") for name in configs.getnames()))
            with tarfile.open(fileobj=outer.extractfile("secrets.tar.gz"), mode="r:gz") as secrets:
                self.assertIn("secrets_staging/agent-publisher/.env", secrets.getnames())
                self.assertIn("secrets_staging/nginx/nginx.conf", secrets.getnames())


class RemoteSyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.filename = "bloguito_backup_20260920_100000.tar.gz"
        self.remote = snapshot()
        self.digest = hashlib.sha256(self.remote).hexdigest()

    def fake_run(self, command):
        if command[0] == "scp":
            Path(command[-1]).write_bytes(self.remote)
            return ""
        if "find " in command[-1]:
            return self.filename + "\n"
        if "sha256sum" in command[-1]:
            return self.digest + "  example.tar.gz\n"
        raise AssertionError("unexpected command")

    def test_atomic_sync_replaces_only_after_complete_verification(self):
        current = self.folder / self.filename
        current.write_bytes(b"old, corrupt local snapshot")
        with patch.object(sync_module, "run", side_effect=self.fake_run):
            downloaded, skipped = sync_module.sync("bloguito", "/home/ubuntu/backups", self.folder)
        self.assertEqual((downloaded, skipped), (1, 0))
        self.assertEqual(current.read_bytes(), self.remote)
        self.assertFalse(list(self.folder.glob("*.part")))
        with patch.object(sync_module, "run", side_effect=self.fake_run):
            self.assertEqual(sync_module.sync("bloguito", "/home/ubuntu/backups", self.folder), (0, 1))

    def test_failed_download_keeps_existing_backup_and_cleans_partial(self):
        current = self.folder / self.filename
        current.write_bytes(b"previous file")

        def broken_run(command):
            if command[0] == "scp":
                Path(command[-1]).write_bytes(b"incomplete")
                raise sync_module.BackupError("simulated transfer interruption")
            return self.fake_run(command)

        with patch.object(sync_module, "run", side_effect=broken_run):
            with self.assertRaises(sync_module.BackupError):
                sync_module.sync("bloguito", "/home/ubuntu/backups", self.folder)
        self.assertEqual(current.read_bytes(), b"previous file")
        self.assertFalse(list(self.folder.glob("*.part")))

    def test_host_key_checks_are_mandatory(self):
        self.assertIn("StrictHostKeyChecking=yes", sync_module.ssh_args("bloguito"))
        self.assertIn("StrictHostKeyChecking=yes", sync_module.scp_args())
        with self.assertRaises(sync_module.BackupError):
            sync_module.sync("-untrusted", "/home/ubuntu/backups", self.folder)


if __name__ == "__main__":
    unittest.main()
