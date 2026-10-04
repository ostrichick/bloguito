#!/usr/bin/env python3
"""Build a complete, reproducible Bloguito editorial runtime release.

This builder packages the full tracked runtime surface instead of copying a
previous scratch release inventory, so newly-added shared modules cannot be
silently omitted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY_DOCS = (
    "EDITORIAL_SYSTEM.md",
    "GENERAL_POST_STANDARD.md",
    "EVENT_POST_STANDARD.md",
    "FEATURED_IMAGE_STANDARD.md",
)
RUNTIME_JSON = (
    "agent-publisher/editorial_policy.json",
    "agent-publisher/growth_policy.json",
    "agent-publisher/data/content_clusters.json",
    "agent-publisher/data/renderer_provenance.json",
    "agent-publisher/data/reviewed_content_provenance.json",
)
RETIRED_FILES = (
    "agents/copywriter.py",
    "agents/editorial_draft_updater.py",
    "agents/editorial_legacy_draft.py",
)

def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def inventory_digest(names) -> str:
    encoded = json.dumps(sorted(names), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()

def release_inventory(root: Path = ROOT) -> list[str]:
    root = Path(root)
    files: set[str] = set()
    for path in (root / "agent-publisher").glob("*.py"):
        if path.is_file():
            files.add(path.relative_to(root).as_posix())
    for path in (root / "agent-publisher" / "agents").glob("*.py"):
        if path.is_file():
            files.add(path.relative_to(root).as_posix())
    for relative in RUNTIME_JSON:
        if not (root / relative).is_file():
            raise ValueError("required_release_file_missing:" + relative)
        files.add(relative)
    for folder in (
        root / "agent-publisher" / "data" / "critical_facts",
        root / "agent-publisher" / "data" / "policy_exceptions",
    ):
        if not folder.is_dir():
            raise ValueError("required_release_directory_missing:" + str(folder))
        for path in folder.glob("*.json"):
            files.add(path.relative_to(root).as_posix())
    for name in POLICY_DOCS:
        relative = "docs/" + name
        if not (root / relative).is_file():
            raise ValueError("required_release_file_missing:" + relative)
        files.add(relative)
    return sorted(files)

def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True,
        encoding="utf-8", errors="strict", check=True,
    )
    return result.stdout.strip()

def build_release(output_dir: Path, *, root: Path = ROOT, revision: str | None = None,
                  require_clean: bool = True, archive: bool = False) -> dict:
    root = Path(root).resolve()
    output_dir = Path(output_dir).resolve()
    if output_dir.exists():
        raise ValueError("release_output_must_not_exist")
    if require_clean and _git(root, "status", "--porcelain", "--untracked-files=no"):
        raise ValueError("release_requires_clean_tracked_worktree")
    head_revision = _git(root, "rev-parse", "HEAD")
    if revision is not None and revision != head_revision:
        raise ValueError("release_revision_must_match_head")
    revision = head_revision
    if len(revision) != 40 or any(ch not in "0123456789abcdef" for ch in revision):
        raise ValueError("invalid_release_revision")
    inventory = release_inventory(root)
    tracked = set(_git(root, "ls-files").splitlines())
    untracked = sorted(set(inventory) - tracked)
    if untracked:
        raise ValueError("release_inventory_contains_untracked_file:" + untracked[0])
    changed = set(_git(root, "diff", "HEAD", "--name-only").splitlines())
    changed_inventory = sorted(set(inventory) & changed)
    if changed_inventory:
        raise ValueError("release_inventory_not_at_head:" + changed_inventory[0])
    output_dir.mkdir(parents=True)
    hashes = {}
    for relative in inventory:
        source = root / relative
        target = output_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        hashes[relative] = _sha(target)
    manifest = {
        "schema_version": 2,
        "revision": revision,
        "inventory_digest": inventory_digest(hashes),
        "files": hashes,
        "retired_files": list(RETIRED_FILES),
    }
    manifest_path = output_dir / "release-manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    archive_path = None
    if archive:
        archive_path = output_dir.with_suffix(".tar.gz")
        if archive_path.exists():
            raise ValueError("release_archive_must_not_exist")
        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(output_dir, arcname=output_dir.name)
    return {"revision": revision, "files": len(hashes), "release_dir": str(output_dir),
            "manifest": str(manifest_path), "archive": str(archive_path) if archive_path else None}

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--archive", action="store_true")
    args = parser.parse_args(argv)
    print(json.dumps(build_release(args.output_dir, archive=args.archive), ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
