"""Download Bloguito snapshots using a trusted SSH host alias and verified atomic files."""

import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

DEFAULT_LOCAL_DIR = Path(__file__).resolve().parent.parent / "backups"
FILE_PATTERN = re.compile(r"bloguito_backup_\d{8}_\d{6}\.tar\.gz")
COMPONENT_FILES = {
    "db": "db.sql.gz",
    "uploads": "uploads.tar.gz",
    "configs": "configs.tar.gz",
    "wp_content": "wp-content.tar.gz",
    "secrets": "secrets.tar.gz",
}
VERSIONS = {"2.0": {"db", "uploads", "configs"}, "3.0": set(COMPONENT_FILES)}


class BackupError(Exception):
    """Invalid backup or failed remote operation; never publish a partial download."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_member(name: str) -> bool:
    path = PurePosixPath(name)
    return bool(name) and not path.is_absolute() and "\\" not in name and ".." not in path.parts


def verify_archive(path: Path) -> str:
    """Validate the full snapshot and nested tar members without extracting any files."""
    try:
        with tarfile.open(path, "r:gz") as outer:
            members = outer.getmembers()
            by_name = {m.name: m for m in members}
            if len(by_name) != len(members) or "manifest.json" not in by_name:
                raise BackupError("missing or duplicate manifest/archive entries")
            meta = by_name["manifest.json"]
            if not meta.isfile() or meta.size > 1024 * 1024:
                raise BackupError("invalid manifest")
            manifest = json.load(outer.extractfile(meta))
            version = manifest.get("version")
            if version not in VERSIONS:
                raise BackupError("unsupported snapshot version")
            components = manifest.get("components")
            if not isinstance(components, dict) or set(components) != VERSIONS[version]:
                raise BackupError("missing/unexpected components")
            expected_files = {"manifest.json"} | {COMPONENT_FILES[name] for name in components}
            if set(by_name) != expected_files or any(not m.isfile() for m in members):
                raise BackupError("missing/unexpected outer files")
            for name, info in components.items():
                filename = COMPONENT_FILES[name]
                member = by_name[filename]
                if not isinstance(info, dict) or info.get("file") != filename:
                    raise BackupError("invalid component filename: " + name)
                if type(info.get("size_bytes")) is not int or info["size_bytes"] != member.size:
                    raise BackupError("component size mismatch: " + name)
                expected = info.get("sha256")
                if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
                    raise BackupError("invalid SHA256: " + name)
                digest = hashlib.sha256()
                with outer.extractfile(member) as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(chunk)
                if digest.hexdigest() != expected:
                    raise BackupError("checksum mismatch: " + name)
                with outer.extractfile(member) as component_stream:
                    if name == "db":
                        import gzip
                        with gzip.GzipFile(fileobj=component_stream) as database:
                            for _ in iter(lambda: database.read(1024 * 1024), b""):
                                pass
                    else:
                        with tarfile.open(fileobj=component_stream, mode="r|gz") as nested:
                            names = []
                            for entry in nested:
                                if not safe_member(entry.name) or not (entry.isfile() or entry.isdir()):
                                    raise BackupError("unsafe nested archive entry: " + name)
                                allowed = {
                                    "uploads": ("uploads",),
                                    "wp_content": ("plugins", "themes", "mu-plugins"),
                                    "configs": ("configs_staging",),
                                    "secrets": ("secrets_staging",),
                                }[name]
                                if not any(entry.name == root or entry.name.startswith(root + "/") for root in allowed):
                                    raise BackupError("component contains unexpected path: " + name)
                                names.append(entry.name)
                            if name == "wp_content" and not all(
                                any(p == directory or p.startswith(directory + "/") for p in names)
                                for directory in ("plugins", "themes")
                            ):
                                raise BackupError("WordPress plugins/themes missing")
            return version
    except (OSError, ValueError, EOFError, TypeError, KeyError, tarfile.TarError) as exc:
        raise BackupError("invalid snapshot archive") from exc


def run(command: list[str]) -> str:
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode:
        raise BackupError("SSH/SCP failed; check trusted host key, alias and network")
    return result.stdout


def ssh_args(host: str) -> list[str]:
    return ["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes", "-o", "ConnectTimeout=10", host]


def scp_args() -> list[str]:
    return ["scp", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes", "-o", "ConnectTimeout=10"]


def remote_hash(host: str, remote_path: str) -> str:
    output = run(ssh_args(host) + ["sha256sum -- " + shlex.quote(remote_path)])
    first = output.split(maxsplit=1)[0] if output.strip() else ""
    if not re.fullmatch(r"[0-9a-f]{64}", first):
        raise BackupError("invalid remote checksum")
    return first


def sync(host: str, remote_dir: str, local_dir: Path) -> tuple[int, int]:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.@-]*", host):
        raise BackupError("invalid SSH alias")
    if not re.fullmatch(r"/[A-Za-z0-9/_-]+", remote_dir):
        raise BackupError("invalid remote directory")
    local_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name != "nt":
        local_dir.chmod(0o700)
    list_command = ("find " + shlex.quote(remote_dir) +
                    " -maxdepth 1 -type f -name 'bloguito_backup_*.tar.gz' -printf '%f\\n'")
    filenames = [name for name in run(ssh_args(host) + [list_command]).splitlines() if name]
    if any(not FILE_PATTERN.fullmatch(name) for name in filenames):
        raise BackupError("unexpected filename in remote backup listing")
    downloaded = skipped = 0
    errors = []
    for filename in sorted(set(filenames)):
        remote_path = remote_dir.rstrip("/") + "/" + filename
        destination = local_dir / filename
        temporary = None
        try:
            expected = remote_hash(host, remote_path)
            if destination.is_file() and sha256(destination) == expected:
                verify_archive(destination)
                skipped += 1
                print("VERIFIED_EXISTING", filename)
                continue
            with tempfile.NamedTemporaryFile(dir=local_dir, prefix=".bloguito-", suffix=".part", delete=False) as temp:
                temporary = Path(temp.name)
            run(scp_args() + ["--", host + ":" + remote_path, str(temporary)])
            if sha256(temporary) != expected or remote_hash(host, remote_path) != expected:
                raise BackupError("remote/local checksum mismatch or snapshot changed during transfer")
            verify_archive(temporary)
            if os.name != "nt":
                temporary.chmod(0o600)
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
        raise BackupError(str(len(errors)) + " snapshot(s) failed; valid existing backups preserved")
    return downloaded, skipped


def main() -> int:
    host = os.environ.get("BLOGUITO_BACKUP_SSH_HOST", "bloguito")
    remote_dir = os.environ.get("BLOGUITO_BACKUP_REMOTE_DIR", "/home/ubuntu/backups")
    local_dir = Path(os.environ.get("BLOGUITO_BACKUP_LOCAL_DIR", str(DEFAULT_LOCAL_DIR)))
    try:
        downloaded, skipped = sync(host, remote_dir, local_dir)
        print(f"Backup sync complete: {downloaded} verified downloads, {skipped} verified existing snapshots")
        return 0
    except BackupError as exc:
        print("Backup sync failed:", str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
