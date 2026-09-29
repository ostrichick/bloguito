#!/usr/bin/env python3
"""Safely patch one local HTML component without creating a post-specific script.

This utility is deliberately local-only. WordPress writes must still go through
the reviewed editorial CLI (`edit-post` / related low-level compatibility
actions), which owns source/review/CAS/backup/readback safety.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
import tempfile
from pathlib import Path


VALID_ACTIONS = ("inject-after", "inject-before", "replace", "remove")


def sha256_text(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def apply_component_patch(
    content: str,
    action: str,
    target_pattern: str,
    replacement: str = "",
    *,
    flags: int = re.DOTALL,
) -> str:
    """Apply one deterministic regex patch and reject ambiguous matches."""
    if action not in VALID_ACTIONS:
        raise ValueError(f"invalid_action:{action}")
    try:
        matches = list(re.finditer(target_pattern, content, flags=flags))
    except re.error as exc:
        raise ValueError(f"invalid_target_pattern:{exc}") from exc
    if not matches:
        raise ValueError("target_pattern_not_found")
    if len(matches) != 1:
        raise ValueError(f"target_pattern_ambiguous:{len(matches)}")

    match = matches[0]
    start, end = match.span()
    if action == "inject-after":
        return content[:end] + replacement + content[end:]
    if action == "inject-before":
        return content[:start] + replacement + content[start:]
    if action == "replace":
        return content[:start] + replacement + content[end:]
    return content[:start] + content[end:]


def verify_and_patch(
    content: str,
    action: str,
    target_pattern: str,
    replacement: str = "",
    *,
    expected_sha256: str | None = None,
    flags: int = re.DOTALL,
) -> tuple[str, str]:
    """CAS-check input content, apply one patch and return content + new SHA."""
    if expected_sha256 is not None:
        if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
            raise ValueError("invalid_expected_sha256")
        if sha256_text(content) != expected_sha256:
            raise ValueError("cas_mismatch")
    patched = apply_component_patch(
        content, action, target_pattern, replacement, flags=flags)
    return patched, sha256_text(patched)


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", delete=False, dir=path.parent,
        prefix=f".{path.name}.", suffix=".tmp"
    ) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--action", required=True, choices=VALID_ACTIONS)
    parser.add_argument("--target-pattern", required=True)
    component = parser.add_mutually_exclusive_group()
    component.add_argument("--component-string")
    component.add_argument("--component-file", type=Path)
    parser.add_argument("--input-file", type=Path)
    parser.add_argument("--output-file", type=Path)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.action == "remove":
        replacement = ""
    elif args.component_file is not None:
        if not args.component_file.is_file():
            print("ERROR: component_file_not_found", file=sys.stderr)
            return 3
        replacement = args.component_file.read_text(encoding="utf-8")
    elif args.component_string is not None:
        replacement = args.component_string
    else:
        print("ERROR: component_required", file=sys.stderr)
        return 2

    if args.input_file is not None:
        if not args.input_file.is_file():
            print("ERROR: input_file_not_found", file=sys.stderr)
            return 3
        content = args.input_file.read_text(encoding="utf-8")
    else:
        content = sys.stdin.read()

    try:
        patched, digest = verify_and_patch(
            content,
            args.action,
            args.target_pattern,
            replacement,
            expected_sha256=args.expected_sha256,
        )
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.dry_run:
        print(json_summary(len(content), len(patched), digest))
        return 0
    if args.output_file is not None:
        atomic_write_text(args.output_file, patched)
        print(json_summary(len(content), len(patched), digest, output=str(args.output_file)))
        return 0
    sys.stdout.write(patched)
    return 0


def json_summary(before_length: int, after_length: int, digest: str, *, output: str | None = None) -> str:
    import json

    payload = {
        "status": "ok",
        "before_length": before_length,
        "after_length": after_length,
        "sha256": digest,
    }
    if output is not None:
        payload["output"] = output
    return json.dumps(payload, ensure_ascii=False)


if __name__ == "__main__":
    raise SystemExit(main())
