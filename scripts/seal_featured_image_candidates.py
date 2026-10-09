#!/usr/bin/env python3
"""Seal already-saved CoS/ChatGPT image candidates to immutable SHA receipts.

This script does not generate or download images. CoS Core ``save_image`` must
write each original candidate first; this command immediately records exactly
which local bytes belong to candidate 1..N so later selection never relies on
browser history/nth ordering.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image


ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}


def inspect_candidate(path: Path, candidate_number: int) -> dict:
    path = path.resolve()
    if not path.is_file() or path.stat().st_size <= 0:
        raise ValueError(f"candidate_file_missing:{candidate_number}")
    payload = path.read_bytes()
    sha256 = hashlib.sha256(payload).hexdigest()
    try:
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            image_format = str(image.format or "").upper()
            width, height = image.size
    except Exception as exc:
        raise ValueError(f"candidate_decode_failed:{candidate_number}") from exc
    if image_format not in ALLOWED_FORMATS:
        raise ValueError(f"candidate_format_invalid:{candidate_number}")
    if path.suffix.lower() not in {
            "JPEG": {".jpg", ".jpeg"}, "PNG": {".png"}, "WEBP": {".webp"},
    }[image_format]:
        raise ValueError(f"candidate_extension_format_mismatch:{candidate_number}")
    if width <= 0 or height <= 0:
        raise ValueError(f"candidate_dimensions_invalid:{candidate_number}")
    if hashlib.sha256(path.read_bytes()).hexdigest() != sha256:
        raise ValueError(f"candidate_changed_during_seal:{candidate_number}")
    return {
        "candidate_number": candidate_number,
        "path": str(path),
        "sha256": sha256,
        "format": image_format,
        "width": width,
        "height": height,
        "bytes": len(payload),
    }


def seal_candidates(paths: list[Path], output: Path) -> dict:
    if not paths:
        raise ValueError("candidate_files_required")
    rows = [inspect_candidate(path, index) for index, path in enumerate(paths, start=1)]
    if len({row["path"] for row in rows}) != len(rows):
        raise ValueError("duplicate_candidate_path")
    if len({row["sha256"] for row in rows}) != len(rows):
        raise ValueError("duplicate_candidate_content")
    # This metadata records the required tool-based workflow. It is NOT a
    # cryptographic proof of a tool invocation: operators must also preserve
    # the actual image_gen + CoS save_image tool results in the task record.
    receipt = {
        "version": 2,
        "origin_claim": {
            "generator_tool": "image_gen.text2im",
            "save_tool": "cos_core.save_image",
        },
        "candidates": rows,
    }
    output = output.resolve()
    if any(output == Path(row["path"]) for row in rows):
        raise ValueError("candidate_manifest_must_differ_from_original")
    output.parent.mkdir(parents=True, exist_ok=True)
    # A changed original must never be re-sealed under the same selection
    # manifest. 'x' is atomic, including when two tool sessions overlap.
    with output.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("candidates", nargs="+", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        help="Manifest path (default: candidate-manifest.json next to first candidate)",
    )
    args = parser.parse_args()
    output = args.output or args.candidates[0].resolve().parent / "candidate-manifest.json"
    receipt = seal_candidates(args.candidates, output)
    print(json.dumps(receipt, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
