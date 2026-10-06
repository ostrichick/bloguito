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
    result = subprocess.run(
        command, capture_output=True, check=False)
    if result.returncode:
        raise BackupError("SSH/SCP failed; check trusted host key, alias and network")
    try:
        return result.stdout.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise BackupError("SSH/SCP returned non-UTF-8 stdout") from exc


def ssh_args(host: str) -> list[str]:
    return ["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes", "-o", "ConnectTimeout=10", host]


def scp_args() -> list[str]:
    return ["scp", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes", "-o", "ConnectTimeout=10"]


def _valid_host(host: str, label: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.@-]*", host):
        raise BackupError("invalid " + label)


def _checksum(output: str) -> str:
    first = output.split(maxsplit=1)[0] if output.strip() else ""
    if not re.fullmatch(r"[0-9a-f]{64}", first):
        raise BackupError("invalid remote checksum")
    return first


class DirectTransport:
    def __init__(self, host: str):
        _valid_host(host, "SSH alias")
        self.host = host

    def list_filenames(self, remote_dir: str) -> list[str]:
        command = ("find " + shlex.quote(remote_dir) +
                   " -maxdepth 1 -type f -name 'bloguito_backup_*.tar.gz' -printf '%f\\n'")
        return [name for name in run(ssh_args(self.host) + [command]).splitlines() if name]

    def remote_hash(self, remote_path: str) -> str:
        return _checksum(run(ssh_args(self.host) + ["sha256sum -- " + shlex.quote(remote_path)]))

    def download(self, remote_path: str, destination: Path) -> None:
        run(scp_args() + ["--", self.host + ":" + remote_path, str(destination)])


class TailscaleTransport:
    def __init__(self, host: str):
        _valid_host(host, "Tailscale SSH host")
        self.host = host

    def _run_text(self, args: list[str]) -> str:
        result = subprocess.run(
            ["tailscale", "ssh", self.host, *args], capture_output=True, check=False)
        if result.returncode:
            raise BackupError("Tailscale SSH command failed")
        try:
            return result.stdout.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise BackupError("Tailscale SSH returned non-UTF-8 stdout") from exc

    def list_filenames(self, remote_dir: str) -> list[str]:
        paths = [p for p in self._run_text(["find", remote_dir, "-maxdepth", "1", "-type", "f",
                                            "-name", "bloguito_backup_*.tar.gz", "-print"]).splitlines() if p]
        return [PurePosixPath(path).name for path in paths]

    def remote_hash(self, remote_path: str) -> str:
        return _checksum(self._run_text(["sha256sum", "--", remote_path]))

    def download(self, remote_path: str, destination: Path) -> None:
        with destination.open("wb") as sink:
            result = subprocess.run(["tailscale", "ssh", self.host, "cat", "--", remote_path],
                                    stdout=sink, stderr=subprocess.PIPE, check=False)
        if result.returncode:
            raise BackupError("Tailscale SSH download failed")


def remote_hash(host: str, remote_path: str) -> str:
    return DirectTransport(host).remote_hash(remote_path)


def sync_transport(transport, remote_dir: str, local_dir: Path) -> tuple[int, int]:
    if not re.fullmatch(r"/[A-Za-z0-9/_-]+", remote_dir):
        raise BackupError("invalid remote directory")
    local_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name != "nt":
        try:
            local_dir.chmod(0o700)
        except PermissionError:
            pass
    filenames = transport.list_filenames(remote_dir)
    if any(not FILE_PATTERN.fullmatch(name) for name in filenames):
        raise BackupError("unexpected filename in remote backup listing")
    downloaded = skipped = 0
    errors = []
    for filename in sorted(set(filenames)):
        remote_path = remote_dir.rstrip("/") + "/" + filename
        destination = local_dir / filename
        temporary = None
        try:
            expected = transport.remote_hash(remote_path)
            if destination.is_file() and sha256(destination) == expected:
                verify_archive(destination)
                skipped += 1
                print("VERIFIED_EXISTING", filename)
                continue
            with tempfile.NamedTemporaryFile(dir=local_dir, prefix=".bloguito-", suffix=".part", delete=False) as temp:
                temporary = Path(temp.name)
            transport.download(remote_path, temporary)
            if sha256(temporary) != expected or transport.remote_hash(remote_path) != expected:
                raise BackupError("remote/local checksum mismatch or snapshot changed during transfer")
            verify_archive(temporary)
            if os.name != "nt":
                try:
                    temporary.chmod(0o600)
                except PermissionError:
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
        raise BackupError(str(len(errors)) + " snapshot(s) failed; valid existing backups preserved")
    return downloaded, skipped


def sync(host: str, remote_dir: str, local_dir: Path) -> tuple[int, int]:
    return sync_transport(DirectTransport(host), remote_dir, local_dir)


def sync_tailscale(host: str, remote_dir: str, local_dir: Path) -> tuple[int, int]:
    return sync_transport(TailscaleTransport(host), remote_dir, local_dir)


def main() -> int:
    transport_name = os.environ.get("BLOGUITO_BACKUP_TRANSPORT", "direct").strip().lower()
    remote_dir = os.environ.get("BLOGUITO_BACKUP_REMOTE_DIR", "/home/ubuntu/backups")
    try:
        if transport_name == "direct":
            transport = DirectTransport(os.environ.get("BLOGUITO_BACKUP_SSH_HOST", "bloguito"))
            default_local = DEFAULT_LOCAL_DIR
        elif transport_name == "tailscale":
            transport = TailscaleTransport(os.environ.get("BLOGUITO_BACKUP_TS_HOST", "ubuntu@bloguito-server"))
            default_local = Path.home() / "BloguitoBackups"
        else:
            raise BackupError("invalid BLOGUITO_BACKUP_TRANSPORT")
        local_dir = Path(os.environ.get("BLOGUITO_BACKUP_LOCAL_DIR", str(default_local)))
        downloaded, skipped = sync_transport(transport, remote_dir, local_dir)
        print(f"Backup sync complete ({transport_name}): {downloaded} verified downloads, {skipped} verified existing snapshots")
        return 0
    except BackupError as exc:
        print("Backup sync failed:", str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
