#!/usr/bin/env python3
"""Stage one selected ChatGPT/CoS image for canonical featured-image upload."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
PUBLISHER = ROOT / "agent-publisher"
if str(PUBLISHER) not in sys.path:
    sys.path.insert(0, str(PUBLISHER))

from agents.featured_image import stage_featured_image  # noqa: E402


def require_sealed_candidate(manifest: Path | None) -> Path:
    """Never stage a manually generated CoS candidate without a SHA seal."""
    if manifest is None:
        raise ValueError("candidate_manifest_required_before_staging")
    return manifest


def verify_candidate_manifest(
    source: Path, manifest: Path, *,
    selected_candidate: int, selection_mode: str,
) -> dict:
    source = source.resolve()
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid_candidate_manifest") from exc
    rows = payload.get("candidates") if isinstance(payload, dict) else None
    if (not isinstance(payload, dict) or payload.get("version") != 2
            or payload.get("origin_claim") != {
                "generator_tool": "image_gen.text2im",
                "save_tool": "cos_core.save_image",
            }
            or not isinstance(rows, list) or not rows):
        raise ValueError("invalid_candidate_manifest")
    if type(selected_candidate) is not int or selected_candidate < 1:
        raise ValueError("invalid_selected_candidate")
    if selection_mode not in {"user", "agent-delegated"}:
        raise ValueError("invalid_candidate_selection_mode")
    if any(
        not isinstance(row, dict) or type(row.get("candidate_number")) is not int
        or row["candidate_number"] != index
        or not isinstance(row.get("path"), str)
        or not isinstance(row.get("sha256"), str)
        for index, row in enumerate(rows, 1)
    ) or len({str(Path(row["path"]).resolve()) for row in rows}) != len(rows):
        raise ValueError("invalid_candidate_manifest")
    source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    matches = [
        row for row in rows
        if isinstance(row, dict)
        and isinstance(row.get("path"), str)
        and Path(row["path"]).resolve() == source
        and row.get("candidate_number") == selected_candidate
    ]
    if len(matches) != 1:
        raise ValueError("candidate_not_sealed")
    row = matches[0]
    if row.get("sha256") != source_sha:
        raise ValueError("candidate_sha_conflict")
    try:
        with Image.open(source) as img:
            img.verify()
        with Image.open(source) as img:
            fmt = str(img.format or "").upper()
            width, height = img.size
    except Exception as exc:
        raise ValueError("candidate_decode_failed") from exc
    if (fmt not in {"JPEG", "PNG", "WEBP"}
            or row.get("format") != fmt
            or row.get("width") != width or row.get("height") != height
            or row.get("bytes") != source.stat().st_size):
        raise ValueError("candidate_format_or_size_conflict")
    if hashlib.sha256(source.read_bytes()).hexdigest() != source_sha:
        raise ValueError("candidate_changed_during_verification")
    return {
        "candidate_manifest": str(manifest.resolve()),
        "candidate_number": selected_candidate,
        "selection_mode": selection_mode,
        "origin_claim": payload["origin_claim"],
        "sealed_source_sha256": source_sha,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path, help="Original image saved by CoS Core save_image")
    parser.add_argument(
        "output", nargs="?", type=Path,
        help="Staged jpg/jpeg/png/webp path (default: <source-stem>-upload.webp)",
    )
    parser.add_argument(
        "--receipt", type=Path,
        help="JSON receipt path (default: <output>.stage.json)",
    )
    parser.add_argument(
        "--candidate-manifest", type=Path, required=True,
        help="Mandatory SHA seal from seal_featured_image_candidates.py",
    )
    parser.add_argument("--selected-candidate", type=int, required=True,
                        help="1-based candidate selected by user or explicitly delegated agent")
    parser.add_argument("--selection-mode", choices=["user", "agent-delegated"], required=True,
                        help="Agent mode requires explicit task delegation or one-cover immediate-upload instruction")
    parser.add_argument("--selection-actor", choices=["user", "agent-delegated"],
                        help="Identity of the selecting authority (must agree with selection mode)")
    args = parser.parse_args()

    output = args.output or args.source.with_name(args.source.stem + "-upload.webp")
    receipt_path = args.receipt or output.with_suffix(output.suffix + ".stage.json")
    if output.suffix.lower() != ".webp":
        parser.error("manual_candidate_stage_requires_webp_output")
    if args.selection_actor and args.selection_actor != args.selection_mode:
        parser.error("selection_actor_mode_conflict")
    if output.exists() or receipt_path.exists():
        parser.error("existing_staging_artifacts:inspect_before_retry")
    binding = {}
    try:
        binding = verify_candidate_manifest(
            args.source, require_sealed_candidate(args.candidate_manifest),
            selected_candidate=args.selected_candidate, selection_mode=args.selection_mode)
        receipt = stage_featured_image(
            args.source, output,
            expected_source_sha256=binding["sealed_source_sha256"],
        )
        receipt.update(binding)
        receipt["selection_actor"] = args.selection_actor or args.selection_mode
    except Exception as exc:
        failure = {
            "version": 1,
            "stage": "local_webp_staging",
            "error": type(exc).__name__ + ":" + str(exc),
            "original_image_path": str(args.source.resolve()),
            "original_image_sha256": binding.get("sealed_source_sha256"),
            "candidate_manifest": str(args.candidate_manifest.resolve()),
            "staged_image_path": str(output.resolve()),
            "import_attempted": False,
            "automatic_media_reimport_allowed": False,
            "next_recommended_action": "inspect_invalid_source_or_staging_policy_do_not_retry_identically",
        }
        failure_path = output.with_suffix(output.suffix + ".failed.json")
        failure_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with failure_path.open("x", encoding="utf-8") as handle:
                handle.write(json.dumps(failure, ensure_ascii=False, indent=2) + "\n")
        except FileExistsError:
            # Preserve the first failed attempt for operator diagnosis.
            pass
        print(json.dumps({
            "status": "blocked", "stage": failure["stage"],
            "failure_receipt": str(failure_path.resolve()),
        }, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(2) from exc
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    with receipt_path.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(receipt, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
