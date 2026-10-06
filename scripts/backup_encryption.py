#!/usr/bin/env python3
"""Portable authenticated encryption for verified Bloguito backup archives."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePath
import secrets
import struct
import subprocess
import tempfile

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


MAGIC = b"BLGBAK01"
NONCE_BYTES = 12
TAG_BYTES = 16
MAX_HEADER_BYTES = 4096
CHUNK_BYTES = 1024 * 1024


class BackupEncryptionError(ValueError):
    """Encrypted backup or recovery-key validation failed."""


def _restrict_private_file(path: Path) -> None:
    """Restrict a recovery-key file to the current operator account."""
    path = Path(path)
    if os.name != "nt":
        try:
            os.chmod(path, 0o600)
        except OSError as exc:
            raise BackupEncryptionError("recovery_key_permission_update_failed") from exc
        return
    try:
        identity = subprocess.run(
            ["whoami"], check=True, capture_output=True, text=True,
            encoding="utf-8", errors="strict",
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise BackupEncryptionError("recovery_key_operator_unknown") from exc
    if not identity:
        raise BackupEncryptionError("recovery_key_operator_unknown")
    try:
        subprocess.run(
            ["icacls", str(path), "/inheritance:r"],
            check=True, capture_output=True, text=True,
            encoding="utf-8", errors="strict",
        )
        subprocess.run(
            ["icacls", str(path), "/grant:r", identity + ":(R)"],
            check=True, capture_output=True, text=True,
            encoding="utf-8", errors="strict",
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise BackupEncryptionError("recovery_key_permission_update_failed") from exc


def _sha256(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(CHUNK_BYTES), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def create_key(path: Path) -> Path:
    """Create a new 256-bit recovery key without replacing an existing key."""
    path = Path(path)
    if path.exists() or path.is_symlink():
        raise BackupEncryptionError("recovery_key_already_exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".bloguito-key-", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(secrets.token_bytes(32))
            handle.flush()
            os.fsync(handle.fileno())
        _restrict_private_file(temporary)
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return path


def load_key(path: Path) -> bytes:
    path = Path(path)
    if path.is_symlink():
        raise BackupEncryptionError("recovery_key_symlink_not_allowed")
    try:
        key = path.read_bytes()
    except OSError as exc:
        raise BackupEncryptionError("recovery_key_unreadable") from exc
    if len(key) != 32:
        raise BackupEncryptionError("invalid_recovery_key_length")
    _restrict_private_file(path)
    return key


def _header_bytes(source: Path, *, plaintext_sha256: str, plaintext_size: int) -> bytes:
    filename = source.name
    if PurePath(filename).name != filename or not filename:
        raise BackupEncryptionError("invalid_backup_filename")
    payload = {
        "version": 1,
        "filename": filename,
        "plaintext_sha256": plaintext_sha256,
        "plaintext_size": plaintext_size,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if len(raw) > MAX_HEADER_BYTES:
        raise BackupEncryptionError("encrypted_backup_header_too_large")
    return raw


def encrypt_file(source: Path, destination: Path, key: bytes) -> dict:
    """Encrypt one verified archive with AES-256-GCM using bounded memory."""
    source, destination = Path(source), Path(destination)
    if len(key) != 32:
        raise BackupEncryptionError("invalid_recovery_key_length")
    if destination.exists() or destination.is_symlink():
        raise BackupEncryptionError("encrypted_backup_destination_exists")
    digest, size = _sha256(source)
    header = _header_bytes(source, plaintext_sha256=digest, plaintext_size=size)
    header_len = struct.pack(">I", len(header))
    nonce = secrets.token_bytes(NONCE_BYTES)
    aad = MAGIC + header_len + header + nonce
    encryptor = Cipher(algorithms.AES(key), modes.GCM(nonce)).encryptor()
    encryptor.authenticate_additional_data(aad)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent, prefix=".bloguito-encrypted-", delete=False) as sink:
            temporary = Path(sink.name)
            sink.write(aad)
            with source.open("rb") as stream:
                for chunk in iter(lambda: stream.read(CHUNK_BYTES), b""):
                    sink.write(encryptor.update(chunk))
            sink.write(encryptor.finalize())
            sink.write(encryptor.tag)
            sink.flush()
            os.fsync(sink.fileno())
        try:
            os.chmod(temporary, 0o600)
        except OSError:
            pass
        os.replace(temporary, destination)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return {"filename": source.name, "plaintext_sha256": digest, "plaintext_size": size}


def _read_header(source) -> tuple[dict, bytes, int]:
    magic = source.read(len(MAGIC))
    if magic != MAGIC:
        raise BackupEncryptionError("invalid_encrypted_backup_magic")
    length_raw = source.read(4)
    if len(length_raw) != 4:
        raise BackupEncryptionError("truncated_encrypted_backup_header")
    header_len = struct.unpack(">I", length_raw)[0]
    if not 1 <= header_len <= MAX_HEADER_BYTES:
        raise BackupEncryptionError("invalid_encrypted_backup_header_length")
    header_raw = source.read(header_len)
    nonce = source.read(NONCE_BYTES)
    if len(header_raw) != header_len or len(nonce) != NONCE_BYTES:
        raise BackupEncryptionError("truncated_encrypted_backup_header")
    try:
        header = json.loads(header_raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, TypeError) as exc:
        raise BackupEncryptionError("invalid_encrypted_backup_header") from exc
    if (not isinstance(header, dict) or header.get("version") != 1
            or not isinstance(header.get("filename"), str)
            or PurePath(header["filename"]).name != header["filename"]
            or not isinstance(header.get("plaintext_sha256"), str)
            or len(header["plaintext_sha256"]) != 64
            or type(header.get("plaintext_size")) is not int
            or header["plaintext_size"] < 0):
        raise BackupEncryptionError("invalid_encrypted_backup_header")
    aad = magic + length_raw + header_raw + nonce
    return header, aad, len(aad)


def verify_or_decrypt(source: Path, key: bytes, destination: Path | None = None) -> dict:
    """Authenticate, hash-check and optionally restore an encrypted snapshot."""
    source = Path(source)
    if source.is_symlink() or len(key) != 32:
        raise BackupEncryptionError("invalid_encrypted_backup_input")
    total_size = source.stat().st_size
    temporary = None
    try:
        with source.open("rb") as encrypted:
            header, aad, header_size = _read_header(encrypted)
            ciphertext_size = total_size - header_size - TAG_BYTES
            if ciphertext_size < 0:
                raise BackupEncryptionError("truncated_encrypted_backup")
            encrypted.seek(total_size - TAG_BYTES)
            tag = encrypted.read(TAG_BYTES)
            encrypted.seek(header_size)
            nonce = aad[-NONCE_BYTES:]
            decryptor = Cipher(algorithms.AES(key), modes.GCM(nonce, tag)).decryptor()
            decryptor.authenticate_additional_data(aad)
            digest = hashlib.sha256()
            plaintext_size = 0
            sink = None
            if destination is not None:
                destination = Path(destination)
                if destination.exists() or destination.is_symlink():
                    raise BackupEncryptionError("decrypted_backup_destination_exists")
                destination.parent.mkdir(parents=True, exist_ok=True)
                sink = tempfile.NamedTemporaryFile(
                    dir=destination.parent, prefix=".bloguito-decrypted-", delete=False)
                temporary = Path(sink.name)
            try:
                remaining = ciphertext_size
                while remaining:
                    chunk = encrypted.read(min(CHUNK_BYTES, remaining))
                    if not chunk:
                        raise BackupEncryptionError("truncated_encrypted_backup")
                    remaining -= len(chunk)
                    clear = decryptor.update(chunk)
                    digest.update(clear)
                    plaintext_size += len(clear)
                    if sink is not None:
                        sink.write(clear)
                final = decryptor.finalize()
                digest.update(final)
                plaintext_size += len(final)
                if sink is not None:
                    sink.write(final)
                    sink.flush()
                    os.fsync(sink.fileno())
            finally:
                if sink is not None:
                    sink.close()
    except InvalidTag as exc:
        raise BackupEncryptionError("encrypted_backup_authentication_failed") from exc
    if (plaintext_size != header["plaintext_size"]
            or digest.hexdigest() != header["plaintext_sha256"]):
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise BackupEncryptionError("encrypted_backup_plaintext_mismatch")
    if destination is not None:
        try:
            os.chmod(temporary, 0o600)
        except OSError:
            pass
        os.replace(temporary, destination)
        temporary = None
    return header
