"""Sync Bloguito backups over Tailscale SSH and verify them atomically."""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from sync_backups import BackupError, FILE_PATTERN, sha256, verify_archive


DEFAULT_LOCAL_DIR = Path.home() / "BloguitoBackups"


def run_text(host: str, remote_args: list[str]) -> str:
    result = subprocess.run(
        ["tailscale", "ssh", host, *remote_args],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise BackupError("Tailscale SSH command failed")
    return result.stdout


def remote_hash(host: str, remote_path: str) -> str:
    output = run_text(host, ["sha256sum", "--", remote_path])
    first = output.split(maxsplit=1)[0] if output.strip() else ""
    if not re.fullmatch(r"[0-9a-f]{64}", first):
        raise BackupError("invalid remote checksum")
    return first


def download(host: str, remote_path: str, destination: Path) -> None:
    with destination.open("wb") as sink:
        result = subprocess.run(
            ["tailscale", "ssh", host, "cat", "--", remote_path],
            stdout=sink,
            stderr=subprocess.PIPE,
            check=False,
        )
    if result.returncode:
        raise BackupError("Tailscale SSH download failed")


def sync(host: str, remote_dir: str, local_dir: Path) -> tuple[int, int]:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.@-]*", host):
        raise BackupError("invalid Tailscale SSH host")
    if not re.fullmatch(r"/[A-Za-z0-9/_-]+", remote_dir):
        raise BackupError("invalid remote directory")

    local_dir.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        try:
            local_dir.chmod(0o700)
        except PermissionError:
            # WSL-mounted Windows paths (for example /mnt/c/...) may not
            # support POSIX chmod semantics. Windows ACLs remain authoritative.
            pass

    remote_paths = [
        name
        for name in run_text(
            host,
            [
                "find",
                remote_dir,
                "-maxdepth",
                "1",
                "-type",
                "f",
                "-name",
                "bloguito_backup_*.tar.gz",
                "-print",
            ],
        ).splitlines()
        if name
    ]
    filenames = [Path(remote_path).name for remote_path in remote_paths]
    if any(not FILE_PATTERN.fullmatch(name) for name in filenames):
        raise BackupError("unexpected filename in remote backup listing")

    downloaded = 0
    skipped = 0
    errors: list[str] = []

    for filename in sorted(set(filenames)):
        remote_path = remote_dir.rstrip("/") + "/" + filename
        destination = local_dir / filename
        temporary: Path | None = None
        try:
            expected = remote_hash(host, remote_path)
            if destination.is_file() and sha256(destination) == expected:
                verify_archive(destination)
                skipped += 1
                print("VERIFIED_EXISTING", filename)
                continue

            with tempfile.NamedTemporaryFile(
                dir=local_dir, prefix=".bloguito-", suffix=".part", delete=False
            ) as temp:
                temporary = Path(temp.name)

            download(host, remote_path, temporary)
            if sha256(temporary) != expected or remote_hash(host, remote_path) != expected:
                raise BackupError("remote/local checksum mismatch or snapshot changed")
            verify_archive(temporary)
            try:
                temporary.chmod(0o600)
            except PermissionError:
                # Same WSL/Windows filesystem caveat as the directory above.
                pass
            os.replace(temporary, destination)
            temporary = None
            downloaded += 1
            print("VERIFIED_DOWNLOADED", filename)
        except BackupError as exc:
            errors.append(filename)
            print("FAILED", filename, str(exc), file=sys.stderr)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    if errors:
        raise BackupError(f"{len(errors)} snapshot(s) failed; valid backups preserved")
    return downloaded, skipped


def main() -> int:
    host = os.environ.get("BLOGUITO_BACKUP_TS_HOST", "ubuntu@bloguito-server")
    remote_dir = os.environ.get("BLOGUITO_BACKUP_REMOTE_DIR", "/home/ubuntu/backups")
    local_dir = Path(os.environ.get("BLOGUITO_BACKUP_LOCAL_DIR", str(DEFAULT_LOCAL_DIR)))
    try:
        downloaded, skipped = sync(host, remote_dir, local_dir)
        print(
            f"Tailscale backup sync complete: {downloaded} verified downloads, "
            f"{skipped} verified existing snapshots"
        )
        return 0
    except BackupError as exc:
        print("Tailscale backup sync failed:", str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
