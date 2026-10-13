"""Synthetic WordPress/MariaDB real-DB smoke runner for a local R4 PC.

This script deliberately does not invoke the Bloguito publisher/writer. Its
tests of fixture-only PHP CAS and SHA readback cannot certify R1-R3 or R4 GO.
One smoke execution is allowed per new, empty fixture; no blind media reimport.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time

import image_r4_pc_fixture as fixture

HEX = re.compile(r"[0-9a-f]{64}\Z")
POSITIVE = re.compile(r"[1-9][0-9]*\Z")
BODY = "<p>R4 isolated fixture: stable synthetic body.</p>"
TITLE = "R4 Isolated Synthetic Draft"
ALT = "R4 synthetic alt"


def _id(raw: str) -> int:
    value = raw.strip()
    if not POSITIVE.fullmatch(value):
        raise ValueError("expected_positive_wp_cli_id")
    return int(value)


def _wp(folder: Path, *cmd: str, allow_failure: bool = False,
        stdin: str | None = None) -> subprocess.CompletedProcess:
    return fixture._cli(folder, *cmd, timeout=180, stdin=stdin,
                        allow_failure=allow_failure)


def _safe_error(exc: BaseException) -> str:
    # Do not serialize external process errors: TimeoutExpired may include the
    # command (and WP-CLI prompt stdin) even when the caller suppresses stdout.
    candidate = str(exc)
    if (isinstance(exc, (ValueError, RuntimeError))
            and re.fullmatch(r"[a-z][a-z0-9_:.]{2,100}", candidate)
            and candidate.startswith(("synthetic_", "fixture_", "nonempty_", "stale_",
                                       "invalid_", "expected_", "repeated_", "post_",
                                       "confirm_", "wordpress_", "import_", "unrelated_"))):
        return candidate
    return "synthetic_smoke_exception:" + type(exc).__name__


def _probe(folder: Path, command: str, *args: object) -> dict | list:
    output = _wp(folder, "eval-file", "/r4-fixtures/fixture-cas.php", command,
                 *(str(x) for x in args)).stdout.strip()
    result = json.loads(output)
    if not isinstance(result, (dict, list)):
        raise ValueError("synthetic_wp_probe_invalid")
    return result


def _synthetic_admin_password(folder: Path) -> str:
    # Never include credentials in log/output/evidence file.
    for line in (folder / ".env").read_text(encoding="ascii").splitlines():
        if line.startswith("R4_ADMIN_PASSWORD="):
            return line.split("=", 1)[1]
    raise ValueError("synthetic_admin_password_missing")


def _attempt(folder: Path, post: int, attachment: int, sha: str, previous: int) -> str:
    """Return a proven WP result; transport failures are never CAS denials.

    The known, SHA-verified fixture PHP emits WP_CLI::error with exactly one
    of two CAS markers. Docker/network/CLI failures must abort the smoke.
    """
    completed = _wp(folder, "eval-file", "/r4-fixtures/fixture-cas.php",
                    "cas-set", str(post), str(attachment), sha, str(previous),
                    allow_failure=True)
    if completed.returncode == 0:
        try:
            snapshot = json.loads(completed.stdout.strip())
        except (TypeError, ValueError, AttributeError) as exc:
            raise ValueError("synthetic_wp_cas_success_unverified") from None
        if (not isinstance(snapshot, dict) or snapshot.get("post_id") != post
                or snapshot.get("thumbnail_id") != attachment
                or snapshot.get("content_sha256") != sha
                or snapshot.get("post_status") != "draft"
                or snapshot.get("alt") != ALT):
            raise ValueError("synthetic_wp_cas_success_unverified")
        return "applied"
    # WP-CLI emits `Error: stale_post_cas` or `Error: stale_thumbnail_cas`
    # from our fixed fixture PHP. Require exactly that stderr and no stdout:
    # arbitrary nonzero exit codes never count as valid CAS rejections.
    if (type(completed.returncode) is int and completed.returncode == 1
            and isinstance(completed.stderr, str)
            and not (completed.stdout or "").strip()):
        marker = completed.stderr.strip()
        if marker in ("Error: stale_post_cas", "Error: stale_thumbnail_cas"):
            return marker.removeprefix("Error: ")
    raise ValueError("synthetic_wp_cas_failure_unclassified")


def smoke(folder: Path) -> dict:
    folder = Path(folder).resolve()
    state = fixture.verified_fixture(folder)
    fixture._check_local_docker()
    # Explicitly refuse any second smoke in the same project or a partially
    # completed previous run: a lost import response must never cause reimport.
    evidence_path = folder / "r4-smoke-evidence.json"
    if evidence_path.exists():
        raise ValueError("fixture_smoke_already_attempted_no_media_reimport")
    evidence = {"status": "NO-GO", "scope": "synthetic_wp_mariadb_only",
                "project": state["project"], "production_writer_tested": False,
                "r1_r2_trusted_issuance_tested": False, "ssh_loss_tested": False,
                "r4_acceptance": False, "checks": {}, "notes": []}
    # Fence even on a failed run; do not automatically retry non-idempotent
    # imports when the result or the process termination is unknown.
    fixture._write_exclusive(evidence_path, (json.dumps(evidence, indent=2) + "\n").encode())
    try:
        installed = _wp(folder, "core", "is-installed", allow_failure=True)
        if installed.returncode == 0:
            raise ValueError("nonempty_fixture_refuses_smoke")
        for index in range(18):
            probe = _wp(folder, "core", "version", allow_failure=True)
            if probe.returncode == 0:
                break
            if index == 17:
                raise RuntimeError("wordpress_fixture_not_ready")
            time.sleep(2)
        _wp(folder, "core", "install", "--url=http://web/",
            "--title=R4 Synthetic Isolated", "--admin_user=r4_fixture_admin",
            "--admin_email=r4-fixture@example.invalid",
            "--skip-email", "--prompt=admin_password",
            stdin=_synthetic_admin_password(folder) + "\n")
        evidence["checks"]["synthetic_site_installed"] = True
        post = _id(_wp(folder, "post", "create", "--post_type=post",
                       "--post_status=draft", "--post_title=" + TITLE,
                       "--post_content=" + BODY, "--post_excerpt=R4 synthetic excerpt",
                       "--porcelain").stdout)
        before = _probe(folder, "snapshot", post)
        if not isinstance(before, dict) or before.get("post_status") != "draft":
            raise ValueError("synthetic_post_not_draft")
        if before.get("thumbnail_id") != 0 or before.get("attachment_count") != 0:
            raise ValueError("synthetic_post_not_empty")
        baseline_sha = before["content_sha256"]
        if not isinstance(baseline_sha, str) or not HEX.fullmatch(baseline_sha):
            raise ValueError("synthetic_content_sha_invalid")
        evidence["checks"]["initial_draft_baseline"] = True
        attachments: list[int] = []
        for index in (1, 2, 3):
            attachment = _id(_wp(folder, "media", "import",
                                 f"/r4-fixtures/synthetic-{index}.png",
                                 f"--post_id={post}", "--porcelain").stdout)
            if attachment in attachments:
                raise ValueError("repeated_attachment_id")
            attachments.append(attachment)
            observed = _probe(folder, "find-sha", post,
                              state["files"][f"synthetic-{index}.png"])
            if observed != [attachment]:
                raise ValueError("import_image_sha_or_parent_mismatch")
        evidence["checks"]["three_distinct_synthetic_media_imports"] = True
        # Real WP DB rejects stale content SHA before any thumbnail mutation.
        if _attempt(folder, post, attachments[0], "0" * 64, 0) != "stale_post_cas":
            raise ValueError("stale_content_cas_denial_unverified")
        if _probe(folder, "snapshot", post)["thumbnail_id"] != 0:
            raise ValueError("stale_cas_modified_thumbnail")
        evidence["checks"]["stale_content_rejected"] = True
        if _attempt(folder, post, attachments[0], baseline_sha, 0) != "applied":
            raise ValueError("valid_synthetic_cas_rejected")
        first = _probe(folder, "snapshot", post)
        if (first["thumbnail_id"] != attachments[0] or first["alt"] != ALT
                or first["attachment_sha256"] != state["files"]["synthetic-1.png"]
                or first["post_status"] != "draft"
                or first["content_sha256"] != baseline_sha
                or first["post_title"] != before["post_title"]
                or first["post_name"] != before["post_name"]
                or first["post_excerpt"] != before["post_excerpt"]
                or not first["attachment_url"].startswith("http://web/")):
            raise ValueError("post_thumbnail_alt_content_readback_mismatch")
        evidence["checks"]["single_valid_cas_and_actual_wp_readback"] = True
        if _attempt(folder, post, attachments[1], baseline_sha, 0) != "stale_thumbnail_cas":
            raise ValueError("stale_thumbnail_cas_denial_unverified")
        if _probe(folder, "snapshot", post)["thumbnail_id"] != attachments[0]:
            raise ValueError("stale_thumbnail_cas_mutated_post")
        evidence["checks"]["stale_thumbnail_rejected"] = True
        with ThreadPoolExecutor(max_workers=2) as threads:
            pending = [threads.submit(_attempt, folder, post, candidate,
                                      baseline_sha, attachments[0])
                       for candidate in attachments[1:]]
            outcomes = [future.result() for future in pending]
        if (len(outcomes) != 2 or outcomes.count("applied") != 1
                or outcomes.count("stale_thumbnail_cas") != 1):
            raise ValueError("synthetic_concurrent_cas_not_serialized")
        winner = attachments[1] if outcomes[0] == "applied" else attachments[2]
        final = _probe(folder, "snapshot", post)
        if (final["thumbnail_id"] != winner or final["content_sha256"] != baseline_sha
                or final["post_status"] != "draft" or final["alt"] != ALT
                or final["attachment_count"] != 3):
            raise ValueError("synthetic_concurrency_readback_mismatch")
        expected_sha = state["files"]["synthetic-2.png" if outcomes[0] == "applied" else "synthetic-3.png"]
        if final["attachment_sha256"] != expected_sha:
            raise ValueError("synthetic_winning_attachment_sha_changed")
        evidence["checks"]["real_wp_row_lock_serialized_race"] = True
        # A SHA lookup can recover an attachment ID without another import.
        recovered = _probe(folder, "find-sha", post, state["files"]["synthetic-3.png"])
        if recovered != [attachments[2]] or _probe(folder, "snapshot", post)["attachment_count"] != 3:
            raise ValueError("synthetic_sha_recovery_failed")
        evidence["checks"]["read_only_sha_reconcile_without_reimport"] = True
        evidence["status"] = "SYNTHETIC_E2E_PASS_R4_ACCEPTANCE_NO_GO"
        evidence["post_id"] = post
        evidence["attachment_ids"] = attachments
        evidence["baseline_content_sha256"] = baseline_sha
        evidence["final"] = final
        evidence["notes"] = [
            "Actual local MariaDB and WordPress used; fixture-only PHP CAS, not production writer.",
            "No R1/R2 signature issuer or real SSH response loss exercised.",
            "This cannot be promoted to production R4 or R5 GO.",
        ]
    except Exception as exc:
        # Preserve original failure evidence, never blind-retry the run.
        evidence["error_type"] = type(exc).__name__
        evidence["error"] = _safe_error(exc)
    evidence_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8")
    return evidence


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--confirm-local-isolated", action="store_true")
    args = parser.parse_args(argv)
    if not args.confirm_local_isolated:
        print(json.dumps({"status": "NO-GO", "reason": "confirm_local_isolated_required"}))
        return 2
    try:
        result = smoke(args.fixture)
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError, KeyError) as exc:
        result = {"status": "NO-GO", "error": _safe_error(exc)}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") == "SYNTHETIC_E2E_PASS_R4_ACCEPTANCE_NO_GO" else 2


if __name__ == "__main__":
    raise SystemExit(main())
