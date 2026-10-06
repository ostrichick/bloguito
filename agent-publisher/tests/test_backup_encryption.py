import importlib.util
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("backup_encryption", ROOT / "scripts" / "backup_encryption.py")
crypto = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(crypto)


class BackupEncryptionTests(unittest.TestCase):
    def test_round_trip_and_verify_without_plaintext_output(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            key_path = crypto.create_key(root / "key.bin")
            key = crypto.load_key(key_path)
            source = root / "bloguito_backup_20261006_040001.tar.gz"
            payload = (b"backup-data-" * 10000) + b"end"
            source.write_bytes(payload)
            encrypted = root / (source.name + ".blgenc")
            crypto.encrypt_file(source, encrypted, key)
            metadata = crypto.verify_or_decrypt(encrypted, key)
            self.assertEqual(source.name, metadata["filename"])
            restored = root / "restored.tar.gz"
            crypto.verify_or_decrypt(encrypted, key, restored)
            self.assertEqual(payload, restored.read_bytes())

    def test_wrong_key_and_tamper_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "bloguito_backup_20261006_040001.tar.gz"
            source.write_bytes(b"sensitive-backup")
            key = b"a" * 32
            encrypted = root / "backup.blgenc"
            crypto.encrypt_file(source, encrypted, key)
            with self.assertRaises(crypto.BackupEncryptionError):
                crypto.verify_or_decrypt(encrypted, b"b" * 32)
            raw = bytearray(encrypted.read_bytes())
            raw[-20] ^= 1
            encrypted.write_bytes(raw)
            with self.assertRaises(crypto.BackupEncryptionError):
                crypto.verify_or_decrypt(encrypted, key)


if __name__ == "__main__":
    unittest.main()
