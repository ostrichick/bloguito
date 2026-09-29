"""Conservatively remove disposable browser QA profiles from legacy workspaces.

The repository's ``tmp/`` tree contains historical approval/evidence artifacts that
must not be blanket-deleted.  This tool only recognizes browser user-data
directories by Chromium/Edge marker files.  It is a dry-run unless ``--apply``
is supplied, and recent profiles are skipped by default so an active QA session
is not targeted accidentally.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / "agent-publisher"))

from agents.workspace_lifecycle import (  # noqa: E402
    DEFAULT_COMPLETED_TTL_HOURS,
    DEFAULT_FAILED_TTL_HOURS,
    load_workspace_manifest,
    workspace_expired,
)

PROFILE_MARKERS = (
    "Default",
    "Crashpad",
    "component_crx_cache",
)
PROFILE_PRESERVE_MARKERS = (".keep", ".preserve", ".in-use")
_USER_DATA_DIR_PATTERNS = (
    re.compile(r'"--user-data-dir(?:=|\s+)([^"]+)"', re.IGNORECASE),
    re.compile(r'--user-data-dir(?:=|\s+)"([^"]+)"', re.IGNORECASE),
    re.compile(r'--user-data-dir(?:=|\s+)(.+?)(?=\s+(?:--|/)|$)', re.IGNORECASE),
)


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def looks_like_browser_profile(path: Path) -> bool:
    return (
        path.is_dir()
        and (path / "Local State").is_file()
        and any((path / marker).exists() for marker in PROFILE_MARKERS)
    )


def directory_stats(path: Path) -> tuple[int, int, float]:
    size = 0
    count = 0
    latest = path.stat().st_mtime
    for current, _dirs, files in os.walk(path):
        current_path = Path(current)
        try:
            latest = max(latest, current_path.stat().st_mtime)
        except OSError:
            pass
        for name in files:
            file_path = current_path / name
            try:
                stat = file_path.stat()
            except OSError:
                continue
            size += stat.st_size
            count += 1
            latest = max(latest, stat.st_mtime)
    return size, count, latest


def _link_like(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
        junction = getattr(path, "is_junction", None)
        return bool(junction and junction())
    except OSError:
        return True


def _path_key(path: Path) -> str:
    return os.path.normcase(str(Path(path).resolve(strict=False)))


def browser_profile_path_from_command_line(command_line: str) -> Path | None:
    if not isinstance(command_line, str):
        return None
    for pattern in _USER_DATA_DIR_PATTERNS:
        match = pattern.search(command_line)
        if match:
            raw = match.group(1).strip().strip('"')
            return Path(raw).resolve(strict=False) if raw else None
    return None


def active_browser_profile_paths() -> set[Path]:
    """Return explicit --user-data-dir paths used by live Chromium-family browsers.

    Cleanup is primarily operated on Windows. If process inspection is unavailable,
    callers performing deletion must fail closed rather than assume a profile is idle.
    """
    if os.name != "nt":
        raise RuntimeError("browser_process_check_unsupported")
    script = (
        "@(Get-CimInstance Win32_Process | "
        "Where-Object { @('msedge.exe','chrome.exe','brave.exe') -contains $_.Name } | "
        "ForEach-Object { $_.CommandLine }) | ConvertTo-Json -Compress"
    )
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", script],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise RuntimeError("browser_process_check_failed") from error
    if result.returncode != 0:
        raise RuntimeError("browser_process_check_failed")
    raw = result.stdout.strip()
    if not raw:
        return set()
    try:
        command_lines = json.loads(raw)
    except json.JSONDecodeError as error:
        raise RuntimeError("browser_process_check_failed") from error
    if isinstance(command_lines, str):
        command_lines = [command_lines]
    if not isinstance(command_lines, list):
        raise RuntimeError("browser_process_check_failed")
    paths = set()
    for command_line in command_lines:
        path = browser_profile_path_from_command_line(command_line)
        if path is not None:
            paths.add(path)
    return paths


def find_browser_profiles(
    root: Path,
    *,
    min_age_hours: float = 24.0,
    active_profiles: set[Path] | None = None,
):
    tmp_root = (root / "tmp").resolve()
    if not tmp_root.exists():
        return []
    cutoff = time.time() - max(0.0, min_age_hours) * 3600
    active_keys = {_path_key(path) for path in (active_profiles or set())}
    candidates = []
    selected_paths: list[Path] = []
    dirs = sorted(
        (path for path in tmp_root.rglob("*") if path.is_dir()),
        key=lambda path: len(path.parts),
    )
    for path in dirs:
        resolved = path.resolve()
        if not _inside(resolved, tmp_root):
            continue
        if _link_like(path):
            continue
        if any((resolved / marker).exists() for marker in PROFILE_PRESERVE_MARKERS):
            continue
        if _path_key(resolved) in active_keys:
            continue
        if any(parent == selected for selected in selected_paths for parent in resolved.parents):
            continue
        if not looks_like_browser_profile(resolved):
            continue
        size, count, latest = directory_stats(resolved)
        if latest > cutoff:
            continue
        selected_paths.append(resolved)
        candidates.append({
            "path": resolved,
            "size_bytes": size,
            "file_count": count,
            "latest_mtime": latest,
        })
    return candidates


def find_expired_task_workspaces(
    root: Path,
    *,
    completed_ttl_hours: float = DEFAULT_COMPLETED_TTL_HOURS,
    failed_ttl_hours: float = DEFAULT_FAILED_TTL_HOURS,
):
    task_root = (root / "scratch" / "tasks").resolve()
    if not task_root.exists():
        return []
    candidates = []
    for path in sorted(task_root.iterdir()):
        if not path.is_dir() or _link_like(path):
            continue
        resolved = path.resolve()
        if resolved.parent != task_root:
            continue
        payload = load_workspace_manifest(resolved)
        if payload is None:
            continue
        if not workspace_expired(
            payload,
            completed_ttl_hours=completed_ttl_hours,
            failed_ttl_hours=failed_ttl_hours,
        ):
            continue
        size, count, latest = directory_stats(resolved)
        candidates.append({
            "path": resolved,
            "status": payload["status"],
            "size_bytes": size,
            "file_count": count,
            "latest_mtime": latest,
        })
    return candidates


def find_generated_covers(cover_root: Path, *, min_age_hours: float = 24.0):
    cover_root = cover_root.resolve()
    if not cover_root.exists():
        return []
    cutoff = time.time() - max(0.0, min_age_hours) * 3600
    candidates = []
    for path in sorted(cover_root.glob("thumb_*.jpg")):
        if not path.is_file() or path.parent.resolve() != cover_root:
            continue
        stat = path.stat()
        if stat.st_mtime > cutoff:
            continue
        candidates.append({
            "path": path.resolve(),
            "size_bytes": stat.st_size,
            "latest_mtime": stat.st_mtime,
        })
    return candidates


def cleanup(
    root: Path,
    *,
    apply: bool = False,
    min_age_hours: float = 24.0,
    cover_root: Path | None = None,
    completed_ttl_hours: float = DEFAULT_COMPLETED_TTL_HOURS,
    failed_ttl_hours: float = DEFAULT_FAILED_TTL_HOURS,
):
    root = root.resolve()
    tmp_root = (root / "tmp").resolve()
    cover_root = (cover_root or (Path(tempfile.gettempdir()) / "bloguito" / "covers")).resolve()
    candidates = find_browser_profiles(root, min_age_hours=min_age_hours)
    browser_process_check = "not_needed"
    if candidates:
        try:
            active_profiles = active_browser_profile_paths()
        except RuntimeError:
            browser_process_check = "unavailable"
            if apply:
                raise
        else:
            browser_process_check = "passed"
            candidates = find_browser_profiles(
                root,
                min_age_hours=min_age_hours,
                active_profiles=active_profiles,
            )
    cover_candidates = find_generated_covers(cover_root, min_age_hours=min_age_hours)
    workspace_candidates = find_expired_task_workspaces(
        root,
        completed_ttl_hours=completed_ttl_hours,
        failed_ttl_hours=failed_ttl_hours,
    )
    removed = []
    for item in candidates:
        path = item["path"]
        if not _inside(path, tmp_root):
            raise ValueError(f"cleanup_target_outside_tmp:{path}")
        if apply:
            shutil.rmtree(path)
            removed.append(path)
    removed_covers = []
    for item in cover_candidates:
        path = item["path"]
        if path.parent.resolve() != cover_root:
            raise ValueError(f"cleanup_cover_outside_root:{path}")
        if apply:
            path.unlink(missing_ok=True)
            removed_covers.append(path)
    removed_workspaces = []
    task_root = (root / "scratch" / "tasks").resolve()
    for item in workspace_candidates:
        path = item["path"]
        if path.parent != task_root or _link_like(path):
            raise ValueError(f"cleanup_workspace_outside_managed_root:{path}")
        if load_workspace_manifest(path) is None:
            raise ValueError(f"cleanup_workspace_manifest_missing:{path}")
        if apply:
            shutil.rmtree(path)
            removed_workspaces.append(path)
    return {
        "mode": "apply" if apply else "dry-run",
        "candidate_count": len(candidates),
        "candidate_bytes": sum(item["size_bytes"] for item in candidates),
        "removed_count": len(removed),
        "candidates": candidates,
        "browser_process_check": browser_process_check,
        "cover_candidate_count": len(cover_candidates),
        "cover_candidate_bytes": sum(item["size_bytes"] for item in cover_candidates),
        "cover_removed_count": len(removed_covers),
        "cover_candidates": cover_candidates,
        "workspace_candidate_count": len(workspace_candidates),
        "workspace_candidate_bytes": sum(item["size_bytes"] for item in workspace_candidates),
        "workspace_removed_count": len(removed_workspaces),
        "workspace_candidates": workspace_candidates,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--min-age-hours", type=float, default=24.0)
    parser.add_argument("--completed-ttl-hours", type=float, default=DEFAULT_COMPLETED_TTL_HOURS)
    parser.add_argument("--failed-ttl-hours", type=float, default=DEFAULT_FAILED_TTL_HOURS)
    args = parser.parse_args()
    result = cleanup(
        args.root,
        apply=args.apply,
        min_age_hours=args.min_age_hours,
        completed_ttl_hours=args.completed_ttl_hours,
        failed_ttl_hours=args.failed_ttl_hours,
    )
    print(
        f"{result['mode']}: {result['candidate_count']} browser profiles, "
        f"{result['candidate_bytes'] / 1024 / 1024:.1f} MiB "
        f"(process check: {result['browser_process_check']})"
    )
    for item in result["candidates"]:
        print(
            f"- {item['path']} ({item['file_count']} files, "
            f"{item['size_bytes'] / 1024 / 1024:.1f} MiB)"
        )
    print(
        f"{result['mode']}: {result['cover_candidate_count']} stale generated covers, "
        f"{result['cover_candidate_bytes'] / 1024 / 1024:.1f} MiB"
    )
    for item in result["cover_candidates"]:
        print(f"- {item['path']} ({item['size_bytes']} bytes)")
    print(
        f"{result['mode']}: {result['workspace_candidate_count']} expired managed task workspaces, "
        f"{result['workspace_candidate_bytes'] / 1024 / 1024:.1f} MiB"
    )
    for item in result["workspace_candidates"]:
        print(
            f"- {item['path']} ({item['status']}, {item['file_count']} files, "
            f"{item['size_bytes'] / 1024 / 1024:.1f} MiB)"
        )


if __name__ == "__main__":
    main()
