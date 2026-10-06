from __future__ import annotations

import hashlib
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import sync_backups_encrypted as sync  # noqa: E402


class FakeTransport:
    def __init__(self, source: Path):
        self.source = Path(source)
        self.downloads = 0

    def list_filenames(self, _remote_dir):
        return [self.source.name]

    def remote_hash(self, _remote_path):
        return hashlib.sha256(self.source.read_bytes()).hexdigest()

    def download(self, _remote_path, destination):
        self.downloads += 1
        shutil.copyfile(self.source, destination)


class EncryptedBackupSyncTests(unittest.TestCase):
    def test_sync_binds_canonical_remote_filename_and_second_run_skips(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "bloguito_backup_20261006_040001.tar.gz"
            source.write_bytes(b"verified-backup-payload")
            destination = root / "encrypted"
            key_path = root / "key.bin"
            sync.create_key(key_path)
            fake = FakeTransport(source)

            with patch.object(sync, "DirectTransport", return_value=fake), \
                    patch.object(sync, "verify_archive", return_value=None):
                first = sync.sync_encrypted(
                    host="unused", remote_dir="/unused", destination=destination,
                    key_path=key_path, latest_only=True,
                )
                second = sync.sync_encrypted(
                    host="unused", remote_dir="/unused", destination=destination,
                    key_path=key_path, latest_only=True,
                )

            encrypted = destination / (source.name + ".blgenc")
            metadata = sync.verify_or_decrypt(encrypted, sync.load_key(key_path))
            self.assertEqual(source.name, metadata["filename"])
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),
                             metadata["plaintext_sha256"])
            self.assertEqual(source.stat().st_size, metadata["plaintext_size"])
            self.assertEqual((1, 0), first)
            self.assertEqual((0, 1), second)
            self.assertEqual(1, fake.downloads)
            self.assertFalse(any(destination.glob(".bloguito-sync-*")))
            self.assertEqual([encrypted], [path for path in destination.iterdir() if path.is_file()])


if __name__ == "__main__":
    unittest.main()
