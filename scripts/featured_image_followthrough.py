"""Resumable CoS/ChatGPT generated featured-image handoff.

ChatGPT image_gen and CoS save_image remain HOST tool calls. This script cannot
turn those tools on or invoke them from Python. It provides a persisted preflight
before generation and a single guarded continuation after save_image succeeds.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / "agent-publisher"))

from agents.task_state import (  # noqa: E402
    assert_after_image_complete,
    load_after_image_checkpoint,
    update_after_image_checkpoint,
    write_after_image_checkpoint,
)
from agents.featured_image import verify_manual_image_upload_lineage  # noqa: E402

REQUIRED = (
    "image_generated", "image_saved_or_handed_off", "uploaded",
    "featured_image_set", "readback_verified", "content_sha_preserved",
)


def _run(argv: list[str], *, timeout: int = 120) -> str:
    try:
        completed = subprocess.run(
            argv, cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=timeout, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"command_failed_before_verified_result:{type(exc).__name__}:{exc}") from exc
    if completed.returncode != 0:
        details = (completed.stderr or completed.stdout).strip()[-1400:]
        raise RuntimeError(f"command_exit_{completed.returncode}:{details}")
    return completed.stdout.strip()


def _wp(host: str, args: list[str]) -> str:
    # Each argument is fixed or validated; no shell interpolation of untrusted text.
    remote = "sudo docker exec wordpress_app wp " + " ".join(
        shlex.quote(str(arg)) for arg in [*args, "--allow-root"]
    )
    return _run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", host, remote],
        timeout=35,
    )


def read_wordpress(post_id: int, host: str = "bloguito") -> dict:
    raw = _wp(host, [
        "post", "get", str(post_id),
        "--fields=ID,post_content,post_title,post_status,post_name,post_excerpt",
        "--format=json",
    ])
    try:
        post = json.loads(raw)
        assert int(post["ID"]) == post_id
        assert isinstance(post["post_content"], str)
        try:
            thumb_text = _wp(host, ["post", "meta", "get", str(post_id), "_thumbnail_id"]).strip()
        except RuntimeError as exc:
            # wp post meta get exits 1 for a newly created draft without a
            # thumbnail. Treat *only* this documented absence as missing.
            description = str(exc).lower()
            if not (description.startswith("command_exit_1:")
                    and "could not find the specified post meta field" in description):
                raise
            thumb_text = ""
        thumbnail_id = int(thumb_text) if thumb_text.isdecimal() else None
    except (ValueError, KeyError, TypeError, AssertionError) as exc:
        raise RuntimeError("wordpress_readback_invalid") from exc
    return {
        "post_id": post_id,
        "content_sha256": hashlib.sha256(post["post_content"].encode("utf-8")).hexdigest(),
        "thumbnail_id": thumbnail_id,
        "title": post.get("post_title"),
        "status": post.get("post_status"),
        "slug": post.get("post_name"),
        "excerpt": post.get("post_excerpt"),
    }


def begin(post_id: int, host: str = "bloguito") -> dict:
    existing = load_after_image_checkpoint(post_id)
    if existing and existing.get("status") == "in_progress":
        raise ValueError("active_after_image_checkpoint_exists:use_status_or_continue")
    baseline = read_wordpress(post_id, host)
    write_after_image_checkpoint(
        post_id,
        remaining_steps=[
            "ChatGPT image_gen 이미지 생성", "CoS save_image 원본 저장",
            "SHA 봉인 및 WebP staging", "정규 WordPress 업로드/대표이미지 지정",
            "WordPress readback",
        ],
        expected_content_sha256=baseline["content_sha256"],
        expected_thumbnail_id=baseline["thumbnail_id"],
        target_image_handle="chatgpt-native:pending",
        completion_requirements=REQUIRED,
    )
    update_after_image_checkpoint(
        post_id,
        result={"initial_status": baseline["status"], "initial_title": baseline["title"],
                "initial_slug": baseline["slug"], "initial_excerpt": baseline["excerpt"]},
    )
    return {
        "status": "awaiting_image_gen",
        "post_id": post_id,
        "wordpress_baseline": baseline,
        "next": "Call native image_gen, then CoS Core save_image, then continue.",
        "host_tool_note": "image_gen/CoS availability must be checked by actual host tool calls.",
    }


def inspect(post_id: int, host: str = "bloguito") -> dict:
    state = load_after_image_checkpoint(post_id)
    if not state:
        raise ValueError("after_image_checkpoint_missing:run_begin_before_image_gen")
    missing = [v for v in state["completion_requirements"] if not state["completed"].get(v)]
    outcome = {
        "post_id": post_id,
        "checkpoint_status": state["status"],
        "missing_requirements": missing,
        "attachment_id": (state.get("result") or {}).get("attachment_id"),
        "attachment_url": (state.get("result") or {}).get("attachment_url"),
        "upload_attempt_started": bool((state.get("result") or {}).get("upload_attempt_started")),
    }
    if missing:
        if outcome["upload_attempt_started"]:
            # Read-only diagnosis after a lost SSH response. Never infer import
            # failure from a timeout and never invoke a second media import.
            live = read_wordpress(post_id, host)
            outcome["current_thumbnail_id"] = live["thumbnail_id"]
            outcome["thumbnail_changed"] = live["thumbnail_id"] != state["expected_thumbnail_id"]
            outcome["content_sha_preserved"] = live["content_sha256"] == state["expected_content_sha256"]
        return outcome
    live = read_wordpress(post_id, host)
    expected = state["result"]
    required_initial = ("initial_status", "initial_title", "initial_slug", "initial_excerpt")
    unchanged = (
        all(key in expected for key in required_initial)
        and live["content_sha256"] == state["expected_content_sha256"]
        and all(live[key] == expected["initial_" + key] for key in
                ("status", "title", "slug", "excerpt"))
    )
    outcome["wordpress_verified"] = bool(
        unchanged and isinstance(expected.get("attachment_id"), int)
        and live["thumbnail_id"] == expected["attachment_id"]
    )
    outcome["current_thumbnail_id"] = live["thumbnail_id"]
    return outcome


def _parse_upload_receipt(output: str, post_id: int) -> dict:
    """Find the canonical CLI result despite transport timing/progress lines."""
    decoder = json.JSONDecoder()
    matches = []
    for index, char in enumerate(output):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(output[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and value.get("post_id") == post_id and type(value.get("attachment_id")) is int:
            matches.append(value)
    if len(matches) != 1 or matches[0]["attachment_id"] <= 0:
        raise RuntimeError("upload_receipt_missing_or_ambiguous:do_not_retry_import")
    return matches[0]


def continue_upload(
    post_id: int, source: Path, alt_text: str, host: str = "bloguito", *,
    candidate_manifest: Path | None = None, selected_candidate: int | None = None,
    selection_mode: str | None = None, resume: bool = False,
) -> dict:
    state = load_after_image_checkpoint(post_id)
    if not state or state.get("status") != "in_progress":
        raise ValueError("active_after_image_checkpoint_required")
    if state["completed"].get("uploaded"):
        raise ValueError("upload_already_recorded:inspect_wordpress_before_retry")
    if (state.get("result") or {}).get("upload_attempt_started"):
        raise ValueError("ambiguous_previous_upload_attempt:status_and_manual_reconciliation_required")
    if type(selected_candidate) is not int or selected_candidate < 1:
        raise ValueError("explicit_selected_candidate_required")
    if selection_mode not in {"user", "agent-delegated"}:
        raise ValueError("explicit_user_or_delegated_selection_required")
    if not alt_text or not alt_text.strip() or len(alt_text.strip()) > 180 or "\x00" in alt_text:
        raise ValueError("valid_alt_text_required")
    source = source.resolve()
    if not source.is_file() or source.stat().st_size <= 0:
        raise ValueError("cos_save_image_original_missing")
    source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    result = state.get("result") or {}
    if result.get("staged_source_sha256") and result["staged_source_sha256"] != source_sha:
        raise ValueError("previously_staged_original_changed")
    if result.get("selected_candidate") is not None and (
            result["selected_candidate"] != selected_candidate
            or result.get("selection_mode") != selection_mode):
        raise ValueError("checkpoint_selection_conflict")
    if result.get("staged_alt_text") is not None and result["staged_alt_text"] != alt_text.strip():
        raise ValueError("checkpoint_alt_text_conflict")
    # Check live WordPress state before any non-idempotent import.
    baseline = read_wordpress(post_id, host)
    if (baseline["content_sha256"] != state["expected_content_sha256"]
            or baseline["thumbnail_id"] != state["expected_thumbnail_id"]
            or any(baseline[key] != result.get("initial_" + key)
                   for key in ("status", "title", "slug", "excerpt"))):
        raise ValueError("wordpress_changed_since_image_generation_preflight")
    manifest = (candidate_manifest or source.with_name("candidate-manifest.json")).resolve()
    staged = source.with_name(source.stem + "-upload.webp")
    stage_receipt = staged.with_suffix(staged.suffix + ".stage.json")
    if not manifest.exists():
        if candidate_manifest is not None or selected_candidate != 1 or selection_mode != "agent-delegated":
            raise ValueError("sealed_candidate_manifest_required")
        if staged.exists() or stage_receipt.exists():
            raise ValueError("existing_handoff_artifacts:inspect_before_retry")
        _run([sys.executable, str(ROOT / "scripts/seal_featured_image_candidates.py"),
              str(source), "--output", str(manifest)])
    if staged.exists() or stage_receipt.exists():
        if not resume or not staged.exists() or not stage_receipt.exists():
            raise ValueError("existing_staging_requires_explicit_resume_and_complete_receipt")
    else:
        _run([sys.executable, str(ROOT / "scripts/stage_featured_image.py"),
              str(source), str(staged), "--candidate-manifest", str(manifest),
              "--selected-candidate", str(selected_candidate), "--selection-mode", selection_mode,
              "--selection-actor", selection_mode])
    binding = verify_manual_image_upload_lineage(
        staged, manifest, selected_candidate, selection_mode)
    if binding["source_sha256"] != source_sha:
        raise ValueError("candidate_sha_conflict")
    # Bind the exact original, selected candidate and stage before any upload.
    update_after_image_checkpoint(
        post_id,
        completed_steps=["image_generated", "image_saved_or_handed_off"],
        target_image_handle=str(staged),
        result={
            "staged_source_sha256": source_sha,
            "staged_output_sha256": binding["staged_sha256"],
            "candidate_manifest": str(manifest),
            "selected_candidate": selected_candidate,
            "selection_mode": selection_mode,
            "selection_actor": selection_mode,
            "staged_alt_text": alt_text.strip(),
        },
    )
    # Stage and selection may be resumed safely. A transport attempt cannot:
    # its result can be lost after media import and before caller acknowledgement.
    baseline = read_wordpress(post_id, host)
    if (baseline["content_sha256"] != state["expected_content_sha256"]
            or baseline["thumbnail_id"] != state["expected_thumbnail_id"]
            or any(baseline[key] != result.get("initial_" + key)
                   for key in ("status", "title", "slug", "excerpt"))):
        raise ValueError("wordpress_changed_before_media_import")
    update_after_image_checkpoint(post_id, result={"upload_attempt_started": True})
    raw = _run([
        sys.executable, str(ROOT / "scripts/editorial_cli_via_ssh.py"),
        "--ssh-host", host, "--", "replace-featured-image",
        "--post-id", str(post_id), "--image-path", str(staged),
        "--candidate-manifest", str(manifest), "--selected-candidate", str(selected_candidate),
        "--selection-mode", selection_mode, "--alt-text", alt_text.strip(),
        "--confirm-update", "--confirm-image-selection",
    ], timeout=240)
    receipt = _parse_upload_receipt(raw, post_id)
    assert_after_image_complete(post_id, expected_content_sha256=state["expected_content_sha256"])
    verified = inspect(post_id, host)
    if not verified.get("wordpress_verified"):
        raise RuntimeError("wordpress_final_readback_mismatch:do_not_retry_import")
    return {"status": "completed", "post_id": post_id, "receipt": receipt, "verification": verified}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    for action in ("probe", "begin", "status", "continue"):
        command = sub.add_parser(action)
        command.add_argument("--post-id", type=int, required=True)
        command.add_argument("--ssh-host", default="bloguito")
        if action == "continue":
            command.add_argument("--source", type=Path, required=True,
                                 help="Unmodified ChatGPT original saved by CoS save_image.")
            command.add_argument("--alt-text", required=True)
            command.add_argument("--candidate-manifest", type=Path,
                                 help="Required when selecting from multiple ChatGPT candidates.")
            command.add_argument("--selected-candidate", type=int, required=True)
            command.add_argument("--selection-mode", choices=["user", "agent-delegated"],
                                 required=True)
            command.add_argument("--resume", action="store_true",
                                 help="Reuse a verified local WebP stage only if upload has not started.")
    args = parser.parse_args()
    if args.post_id <= 0 or not re.fullmatch(r"[A-Za-z0-9_.-]+", args.ssh_host):
        parser.error("valid_post_id_and_ssh_host_required")
    try:
        if args.action == "probe":
            result = {"status": "ssh_wordpress_connected",
                      "wordpress": read_wordpress(args.post_id, args.ssh_host)}
        elif args.action == "begin":
            result = begin(args.post_id, args.ssh_host)
        elif args.action == "status":
            result = inspect(args.post_id, args.ssh_host)
        else:
            result = continue_upload(
                args.post_id, args.source, args.alt_text, args.ssh_host,
                candidate_manifest=args.candidate_manifest,
                selected_candidate=args.selected_candidate, selection_mode=args.selection_mode,
                resume=args.resume)
        # ASCII JSON avoids Windows PowerShell 5.1 output-codepage corruption.
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return 0 if (args.action != "status" or result.get("wordpress_verified")) else 2
    except (ValueError, RuntimeError) as exc:
        print(json.dumps({"status": "blocked", "post_id": args.post_id,
                          "reason": str(exc)}, ensure_ascii=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
