#!/usr/bin/env python3
"""Safely retire an integrated disposable Git worktree after its last task.

Dry-run by default. --apply archives ALL ignored files under main/scratch before
removing the worktree and its local branch. Never touches remote branches/stashes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class RetirementBlocked(RuntimeError):
    pass


def git(*args: str, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd or ROOT, capture_output=True,
                          check=check, text=True, encoding="utf-8", errors="strict")


def registered_worktrees() -> dict[Path, dict]:
    result = {}
    for group in git("worktree", "list", "--porcelain").stdout.strip().split("\n\n"):
        props = {}
        for line in group.splitlines():
            key, _, value = line.partition(" ")
            props[key] = value
        if "worktree" in props:
            result[Path(props["worktree"]).resolve()] = props
    return result


def ignored_paths(target: Path) -> list[Path]:
    output = subprocess.run(["git", "ls-files", "--others", "--ignored",
                             "--exclude-standard", "--directory", "-z"],
                            cwd=target, capture_output=True, check=True).stdout
    names = [p.decode("utf-8", errors="strict").rstrip("/") for p in output.split(b"\0") if p]
    paths = []
    for name in names:
        path = target / name
        if not path.is_relative_to(target) or ".." in Path(name).parts:
            raise RetirementBlocked("unsafe ignored path")
        paths.append(path)
    return paths


def files_in(path: Path):
    if path.is_symlink():
        raise RetirementBlocked("ignored symlink needs manual review: " + str(path))
    if path.is_file():
        yield path
    elif path.is_dir():
        for child in path.rglob("*"):
            if child.is_symlink():
                raise RetirementBlocked("ignored symlink needs manual review: " + str(child))
            if child.is_file():
                yield child
    else:
        raise RetirementBlocked("ignored entry missing/unsupported: " + str(path))


def inspect(target: Path) -> dict:
    target = target.resolve()
    if target == ROOT or target.parent != ROOT.parent:
        raise RetirementBlocked("target must be a sibling worktree, never main")
    entry = registered_worktrees().get(target)
    if not entry or "branch" not in entry or "locked" in entry:
        raise RetirementBlocked("target is not an unlocked registered branch worktree")
    branch = entry["branch"].removeprefix("refs/heads/")
    if branch == "main":
        raise RetirementBlocked("never retire main")
    if git("status", "--porcelain", "--untracked-files=all", cwd=target).stdout:
        raise RetirementBlocked("tracked/untracked worktree changes require review")
    head = git("rev-parse", "HEAD", cwd=target).stdout.strip()
    merged = git("merge-base", "--is-ancestor", head, "main", check=False).returncode == 0
    cherry = git("cherry", "-v", "main", branch, check=False)
    if not merged and (cherry.returncode or any(line.startswith("+ ") for line in cherry.stdout.splitlines())):
        raise RetirementBlocked("branch contains commits not merged or patch-equivalent to main")
    if not merged and not cherry.stdout.strip():
        raise RetirementBlocked("unable to prove branch patch-equivalence")
    ignored = ignored_paths(target)
    files = [file for path in ignored for file in files_in(path)]
    archive = ROOT / "scratch" / "tasks" / "worktree-retirement" / target.name
    if archive.exists():
        raise RetirementBlocked("existing archive requires manual review: " + str(archive))
    return {"target": target, "branch": branch, "head": head, "merged": merged,
            "ignored": ignored, "files": files, "archive": archive,
            "bytes": sum(f.stat().st_size for f in files)}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def retire(target: Path, apply: bool) -> dict:
    state = inspect(target)
    result = {"branch": state["branch"], "worktree": str(state["target"]),
              "already_in_main": state["merged"], "patch_equivalent": not state["merged"],
              "ignored_file_count": len(state["files"]), "ignored_bytes": state["bytes"],
              "archive": str(state["archive"]), "applied": False}
    if not apply:
        return result
    archive = state["archive"]
    archive.mkdir(parents=True)
    recorded = []
    for entry in state["ignored"]:
        relative = entry.relative_to(state["target"])
        dest = archive / "ignored" / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        if entry.is_dir():
            shutil.copytree(entry, dest)
        else:
            shutil.copy2(entry, dest)
    for file in state["files"]:
        relative = file.relative_to(state["target"])
        archived = archive / "ignored" / relative
        if not archived.is_file() or sha256(file) != sha256(archived):
            raise RetirementBlocked("ignored artifact archival verification failed: " + str(relative))
        recorded.append({"path": relative.as_posix(), "sha256": sha256(file), "bytes": file.stat().st_size})
    (archive / "receipt.json").write_text(json.dumps({
        "branch": state["branch"], "head": state["head"], "source": str(state["target"]),
        "archived_at_utc": datetime.now(timezone.utc).isoformat(), "files": recorded,
        "reason": "integrated task worktree retired; ignored evidence preserved",
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    # Recheck branch and cleanliness before invoking Git's removal. The force flag
    # is limited to verified ignored material, never dirty tracked/untracked state.
    current = inspect_allow_existing_archive(state["target"])
    if (current["branch"], current["head"], current["ignored"]) != (
            state["branch"], state["head"], state["ignored"]):
        raise RetirementBlocked("worktree changed during archive; aborting removal")
    current_hashes = {p.relative_to(state["target"]).as_posix(): sha256(p)
                      for p in current["files"]}
    if current_hashes != {row["path"]: row["sha256"] for row in recorded}:
        raise RetirementBlocked("ignored file contents changed during archival; aborting removal")
    git("worktree", "remove", "--force", str(state["target"]))
    if state["target"].exists():
        raise RetirementBlocked("worktree path remains; local branch preserved")
    # git branch -d uses a branch's *upstream* as the merge target when one
    # exists. Some completed task branches track old origin/main, so -d can
    # reject an otherwise verified main ancestor after the worktree is gone.
    # inspect() proved exact ancestry or patch-equivalence to current main;
    # at this point -D is the correct narrowly scoped branch-ref cleanup.
    git("branch", "-D", state["branch"])
    result["applied"] = True
    return result


def inspect_allow_existing_archive(target: Path) -> dict:
    # Existing verified archive belongs to this one in-progress removal.
    archive = ROOT / "scratch" / "tasks" / "worktree-retirement" / target.name
    if not archive.exists():
        return inspect(target)
    renamed = archive.with_name(archive.name + ".in-progress")
    if renamed.exists():
        raise RetirementBlocked("conflicting archive validation in progress")
    archive.rename(renamed)
    try:
        state = inspect(target)
    finally:
        renamed.rename(archive)
    return state


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("worktree", type=Path)
    parser.add_argument("--apply", action="store_true", help="archive ignored artifacts and remove integrated worktree/branch")
    args = parser.parse_args()
    try:
        print(json.dumps(retire(args.worktree, args.apply), ensure_ascii=False, indent=2))
    except (RetirementBlocked, OSError, subprocess.CalledProcessError) as exc:
        print(json.dumps({"blocked": str(exc)}, ensure_ascii=False))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
