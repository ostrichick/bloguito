"""Conservatively remove disposable browser QA profiles from legacy workspaces.

The repository's ``tmp/`` tree contains historical approval/evidence artifacts that
must not be blanket-deleted.  This tool only recognizes browser user-data
directories by Chromium/Edge marker files.  It is a dry-run unless ``--apply``
is supplied, and recent profiles are skipped by default so an active QA session
is not targeted accidentally.
"""

from __future__ import annotations

import argparse
import os
import shutil
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROFILE_MARKERS = (
    "Default",
    "Crashpad",
    "component_crx_cache",
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


def find_browser_profiles(root: Path, *, min_age_hours: float = 24.0):
    tmp_root = (root / "tmp").resolve()
    if not tmp_root.exists():
        return []
    cutoff = time.time() - max(0.0, min_age_hours) * 3600
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
):
    root = root.resolve()
    tmp_root = (root / "tmp").resolve()
    cover_root = (cover_root or (Path(tempfile.gettempdir()) / "bloguito" / "covers")).resolve()
    candidates = find_browser_profiles(root, min_age_hours=min_age_hours)
    cover_candidates = find_generated_covers(cover_root, min_age_hours=min_age_hours)
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
    return {
        "mode": "apply" if apply else "dry-run",
        "candidate_count": len(candidates),
        "candidate_bytes": sum(item["size_bytes"] for item in candidates),
        "removed_count": len(removed),
        "candidates": candidates,
        "cover_candidate_count": len(cover_candidates),
        "cover_candidate_bytes": sum(item["size_bytes"] for item in cover_candidates),
        "cover_removed_count": len(removed_covers),
        "cover_candidates": cover_candidates,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--min-age-hours", type=float, default=24.0)
    args = parser.parse_args()
    result = cleanup(args.root, apply=args.apply, min_age_hours=args.min_age_hours)
    print(
        f"{result['mode']}: {result['candidate_count']} browser profiles, "
        f"{result['candidate_bytes'] / 1024 / 1024:.1f} MiB"
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


if __name__ == "__main__":
    main()
