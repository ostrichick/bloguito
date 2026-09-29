"""Managed lifecycle helpers for disposable local editorial workspaces.

Only workspaces created through this module receive an ownership manifest and are
eligible for TTL cleanup. Historical/unmanaged scratch files are deliberately
left alone so cleanup cannot reinterpret user artifacts after the fact.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
import re
import tempfile
from pathlib import Path


WORKSPACE_MANIFEST = ".bloguito-workspace.json"
WORKSPACE_VERSION = 1
WORKSPACE_STATUSES = {"active", "completed", "failed", "preserved"}
DEFAULT_COMPLETED_TTL_HOURS = 72.0
DEFAULT_FAILED_TTL_HOURS = 168.0
_TASK_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}\Z")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None = None) -> str:
    return (value or _utc_now()).astimezone(timezone.utc).isoformat()


def _parse_iso(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _link_like(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
        junction = getattr(path, "is_junction", None)
        return bool(junction and junction())
    except OSError:
        return True


def validate_task_name(task_name: str) -> str:
    if not isinstance(task_name, str) or not _TASK_NAME.fullmatch(task_name):
        raise ValueError("invalid_task_workspace_name")
    return task_name


def task_workspace_root(repo_root: Path) -> Path:
    return Path(repo_root).resolve() / "scratch" / "tasks"


def task_workspace_path(repo_root: Path, task_name: str) -> Path:
    return task_workspace_root(repo_root) / validate_task_name(task_name)


def _manifest_path(workspace: Path) -> Path:
    return workspace / WORKSPACE_MANIFEST


def load_workspace_manifest(workspace: Path) -> dict | None:
    workspace = Path(workspace)
    manifest_path = _manifest_path(workspace)
    if not manifest_path.is_file():
        return None
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or payload.get("version") != WORKSPACE_VERSION:
        return None
    if payload.get("status") not in WORKSPACE_STATUSES:
        return None
    if payload.get("task_id") != workspace.name:
        return None
    if _parse_iso(payload.get("created_at")) is None or _parse_iso(payload.get("updated_at")) is None:
        return None
    return payload


def _write_manifest(workspace: Path, payload: dict) -> dict:
    workspace.mkdir(parents=True, exist_ok=True)
    target = _manifest_path(workspace)
    temporary = workspace / f"{WORKSPACE_MANIFEST}.tmp"
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        os.chmod(temporary, 0o600)
    except OSError:
        pass
    temporary.replace(target)
    return payload


def ensure_task_workspace(repo_root: Path, task_name: str, *, kind: str = "general") -> Path:
    """Create or reuse one stable managed workspace for a task."""
    path = task_workspace_path(repo_root, task_name)
    if path.exists() and (_link_like(path) or not path.is_dir()):
        raise ValueError("unsafe_task_workspace_path")
    existing = load_workspace_manifest(path) if path.exists() else None
    if path.exists() and existing is None and any(path.iterdir()):
        raise ValueError("unmanaged_nonempty_task_workspace")
    now = _iso()
    payload = existing or {
        "version": WORKSPACE_VERSION,
        "task_id": task_name,
        "kind": kind,
        "created_at": now,
    }
    payload.update({
        "status": "active",
        "updated_at": now,
        "finished_at": None,
        "preserve_reason": None,
    })
    payload.setdefault("kind", kind)
    _write_manifest(path, payload)
    return path


def mark_task_workspace(workspace: Path, status: str, *, preserve_reason: str | None = None) -> dict:
    if status not in WORKSPACE_STATUSES:
        raise ValueError("invalid_task_workspace_status")
    workspace = Path(workspace).resolve()
    if _link_like(workspace):
        raise ValueError("unsafe_task_workspace_path")
    payload = load_workspace_manifest(workspace)
    if payload is None:
        raise ValueError("managed_task_workspace_required")
    now = _iso()
    payload["status"] = status
    payload["updated_at"] = now
    payload["finished_at"] = None if status == "active" else now
    payload["preserve_reason"] = preserve_reason if status == "preserved" else None
    return _write_manifest(workspace, payload)


def workspace_expired(
    payload: dict,
    *,
    completed_ttl_hours: float = DEFAULT_COMPLETED_TTL_HOURS,
    failed_ttl_hours: float = DEFAULT_FAILED_TTL_HOURS,
    now: datetime | None = None,
) -> bool:
    status = payload.get("status")
    if status not in {"completed", "failed"}:
        return False
    finished = _parse_iso(payload.get("finished_at"))
    if finished is None:
        return False
    ttl = completed_ttl_hours if status == "completed" else failed_ttl_hours
    if ttl < 0:
        raise ValueError("workspace_ttl_must_be_nonnegative")
    current = (now or _utc_now()).astimezone(timezone.utc)
    return (current - finished).total_seconds() >= ttl * 3600


@contextmanager
def temporary_browser_profile(*, temp_root: Path | None = None):
    """Yield one OS-temp browser profile and always remove it on exit."""
    base = Path(temp_root or tempfile.gettempdir()).resolve() / "bloguito" / "browser-profiles"
    base.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix="qa-", dir=base) as folder:
            yield Path(folder)
    finally:
        for candidate in (base, base.parent):
            try:
                candidate.rmdir()
            except OSError:
                break
