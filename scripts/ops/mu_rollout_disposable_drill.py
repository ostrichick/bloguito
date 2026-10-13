#!/usr/bin/env python3
"""Exercise one MU-plugin byte swap and rollback in a disposable directory.

This script never connects to Docker, WordPress, SSH or a production path.
Inputs are read-only. Their expected SHA-256 values must come from independently
verified release and live-readback receipts, not this script's output.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import tempfile
from pathlib import Path


SHA = re.compile(r"[0-9a-f]{64}\Z")
TARGET = "bloguito-post-row-actions.php"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_drill(original: Path, staged: Path, *, current_sha: str,
              release_sha: str, inject_failure: bool = False) -> dict:
    """Prove local backup/atomic swap/restoration of the exact supplied bytes."""
    original, staged = Path(original).resolve(), Path(staged).resolve()
    if original == staged or not original.is_file() or not staged.is_file():
        raise ValueError("mu_drill_distinct_existing_input_files_required")
    if (not isinstance(current_sha, str) or not SHA.fullmatch(current_sha)
            or not isinstance(release_sha, str) or not SHA.fullmatch(release_sha)):
        raise ValueError("mu_drill_valid_independent_shas_required")
    if digest(original) != current_sha:
        raise ValueError("mu_drill_current_backup_sha_mismatch")
    if digest(staged) != release_sha:
        raise ValueError("mu_drill_staged_release_sha_mismatch")
    if current_sha == release_sha:
        raise ValueError("mu_drill_no_plugin_change_to_rehearse")

    with tempfile.TemporaryDirectory(prefix="bloguito-mu-disposable-") as root:
        root = Path(root)
        active = root / TARGET
        backup = root / (TARGET + ".backup")
        candidate = root / (TARGET + ".staged")
        restore = root / (TARGET + ".restore")
        shutil.copyfile(original, active)
        if digest(active) != current_sha:
            raise ValueError("mu_drill_original_copy_changed")
        shutil.copyfile(active, backup)
        if digest(backup) != current_sha:
            raise ValueError("mu_drill_backup_sha_mismatch")
        shutil.copyfile(staged, candidate)
        if digest(candidate) != release_sha:
            raise ValueError("mu_drill_stage_sha_mismatch")

        swapped = False
        injected = False
        try:
            os.replace(candidate, active)  # same disposable directory/filesystem
            swapped = True
            if inject_failure:
                injected = True
                raise RuntimeError("injected_failure_after_swap")
            if digest(active) != release_sha:
                raise ValueError("mu_drill_swapped_sha_mismatch")
        except RuntimeError:
            if not injected:
                raise
        finally:
            if swapped:
                shutil.copyfile(backup, restore)
                if digest(restore) != current_sha:
                    raise ValueError("mu_drill_restore_staging_sha_mismatch")
                os.replace(restore, active)
                if digest(active) != current_sha:
                    raise ValueError("mu_drill_rollback_sha_mismatch")

    if digest(original) != current_sha or digest(staged) != release_sha:
        raise ValueError("mu_drill_input_changed")
    return {
        "scope": "disposable_local_file_only",
        "current_sha256": current_sha,
        "release_sha256": release_sha,
        "backup_verified": True,
        "staged_verified": True,
        "swap_verified": not inject_failure,
        "failure_injected": inject_failure,
        "rollback_verified": True,
        "wordpress_runtime_verified": False,
        "production_modified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original", type=Path, required=True,
                        help="An independently saved byte-for-byte copy of the live MU file")
    parser.add_argument("--staged", type=Path, required=True,
                        help="Exact staged MU plugin from the reviewed release")
    parser.add_argument("--expected-original-sha", required=True)
    parser.add_argument("--expected-staged-sha", required=True)
    parser.add_argument("--inject-failure", action="store_true")
    args = parser.parse_args()
    result = run_drill(
        args.original, args.staged, current_sha=args.expected_original_sha,
        release_sha=args.expected_staged_sha, inject_failure=args.inject_failure)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
