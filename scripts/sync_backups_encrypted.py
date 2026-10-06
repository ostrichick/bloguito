#!/usr/bin/env python3
"""Sync verified Bloguito backups off-host and keep only authenticated ciphertext."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import tempfile

from backup_encryption import (
    BackupEncryptionError,
    create_key,
    encrypt_file,
    load_key,
    verify_or_decrypt,
)
from sync_backups import BackupError, DirectTransport, FILE_PATTERN, verify_archive


def sync_encrypted(*, host: str, remote_dir: str, destination: Path, key_path: Path,
                   latest_only: bool = False) -> tuple[int, int]:
    transport = DirectTransport(host)
    names = sorted(set(transport.list_filenames(remote_dir)))
    if any(not FILE_PATTERN.fullmatch(name) for name in names):
        raise BackupError("unexpected filename in remote backup listing")
    if latest_only and names:
        names = [names[-1]]
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    key = load_key(key_path)
    downloaded = skipped = 0
    for filename in names:
        remote_path = remote_dir.rstrip("/") + "/" + filename
        expected = transport.remote_hash(remote_path)
        encrypted = destination / (filename + ".blgenc")
        if encrypted.is_file():
            metadata = verify_or_decrypt(encrypted, key)
            if metadata["filename"] == filename and metadata["plaintext_sha256"] == expected:
                skipped += 1
                print("VERIFIED_ENCRYPTED_EXISTING", encrypted.name)
                continue
        with tempfile.TemporaryDirectory(prefix=".bloguito-sync-", dir=destination) as temp_name:
            temp_dir = Path(temp_name)
            temporary = temp_dir / filename
            staged_encrypted = temp_dir / (filename + ".blgenc")
            transport.download(remote_path, temporary)
            if transport.remote_hash(remote_path) != expected:
                raise BackupError("remote snapshot changed during encrypted transfer")
            from sync_backups import sha256
            if sha256(temporary) != expected:
                raise BackupError("remote/local checksum mismatch")
            verify_archive(temporary)
            encrypt_file(temporary, staged_encrypted, key)
            metadata = verify_or_decrypt(staged_encrypted, key)
            if metadata["plaintext_sha256"] != expected or metadata["filename"] != filename:
                raise BackupEncryptionError("encrypted_backup_verification_mismatch")
            os.replace(staged_encrypted, encrypted)
            downloaded += 1
            print("VERIFIED_ENCRYPTED_DOWNLOADED", encrypted.name)
    return downloaded, skipped


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=os.environ.get("BLOGUITO_BACKUP_SSH_HOST", "bloguito"))
    parser.add_argument("--remote-dir", default="/home/ubuntu/backups")
    parser.add_argument("--destination", type=Path,
                        default=Path.home() / "BloguitoBackupsEncrypted")
    parser.add_argument("--key", type=Path,
                        default=Path.home() / "Documents" / "Secure" / "Bloguito-Backup-Recovery.key")
    parser.add_argument("--init-key", action="store_true")
    parser.add_argument("--latest-only", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.init_key and not args.key.exists():
            create_key(args.key)
            print("RECOVERY_KEY_CREATED", args.key)
        downloaded, skipped = sync_encrypted(
            host=args.host, remote_dir=args.remote_dir, destination=args.destination,
            key_path=args.key, latest_only=args.latest_only)
        print("Encrypted backup sync complete:", downloaded, "downloaded,", skipped, "verified existing")
        return 0
    except (BackupError, BackupEncryptionError, OSError, ValueError) as exc:
        print("Encrypted backup sync failed:", str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
