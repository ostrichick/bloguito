#!/usr/bin/python3 -I
"""Server-enforced, deliberately narrow WordPress featured-image write boundary.

PROPOSED / NOT DEPLOYED. A separate SSH identity can only refer to a root-owned,
preapproved request ID. Two distinct, root-controlled Ed25519 public keys must
verify origin and review events before a fixed, SHA-locked PHP routine can run.
This is an attachment-selection operation; it never imports an image or edits a
post body or publication status. Installed runtime must be a read-only mount.
"""

import base64
import binascii
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

SUDO_REQUEST_LIMIT = 256
APPROVAL_LIMIT = 8192
LOCK_LIMIT = 512
PUBKEY_LIMIT = 2048
RESPONSE_LIMIT = 4096
REQUEST_DIR = Path("/var/lib/bloguito/image-writer/approved")
CONSUMED_DIR = Path("/var/lib/bloguito/image-writer/consumed")
RELEASE_LOCK = Path("/etc/bloguito/image-writer-lock.json")
HOST_PUBLIC_KEY = Path("/etc/bloguito/image-trust/host.pub.pem")
REVIEW_PUBLIC_KEY = Path("/etc/bloguito/image-trust/review.pub.pem")
PHP_RUNTIME = Path("/usr/local/libexec/bloguito/featured_image_set.php")
CONTAINER_RUNTIME = "/usr/local/libexec/bloguito/featured_image_set.php"
DOCKER = "/usr/bin/docker"
CONTAINER = "wordpress_app"
WP_USER = "bloguito-image-writer"  # Dedicated NON-administrator WP identity.
ENV = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"}
ID = re.compile(r"[0-9a-f]{32}\Z", re.ASCII)
SHA = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
TASK_ID = re.compile(r"[A-Za-z0-9_.-]{8,128}\Z", re.ASCII)


def _object_pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("duplicate_json_key")
        result[key] = value
    return result


def _json(raw):
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_object_pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError("invalid_number")))
    except (UnicodeError, ValueError) as exc:
        raise ValueError("invalid_json") from exc


def parse_request(raw):
    if not isinstance(raw, bytes) or not 1 <= len(raw) <= SUDO_REQUEST_LIMIT:
        raise ValueError("invalid_request_length")
    message = _json(raw)
    if (not isinstance(message, list) or len(message) != 2
            or message[0] != "featured-image-set" or not isinstance(message[1], str)
            or not ID.fullmatch(message[1])):
        raise ValueError("unsupported_write_operation")
    return message[1]


def _trusted_file(path, max_size, *, private=False):
    """Read only root-owned files through fixed paths; deny symlink/ACL shortcuts.

    Directory ancestors cannot be writable by a non-root user. On a POSIX
    deployment root owns every ancestor, preventing replacement between checks.
    For lock/key/approval contents, stat the opened fd and refuse shared writes.
    """
    path = Path(path)
    for parent in reversed(path.parents):
        info = parent.lstat()
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != 0
                or info.st_mode & 0o022):
            raise ValueError("insecure_path_parent")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    fd = os.open(path, flags)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0
                or info.st_nlink != 1 or info.st_mode & 0o022
                or (private and info.st_mode & 0o077)
                or info.st_size > max_size):
            raise ValueError("insecure_server_file")
        data = os.read(fd, max_size + 1)
        if not data or len(data) > max_size:
            raise ValueError("invalid_server_file_size")
        return data
    finally:
        os.close(fd)


def _valid_id(value):
    return type(value) is int and 0 < value <= 999999999


def _valid_sha(value):
    return isinstance(value, str) and SHA.fullmatch(value) is not None


def validate_approval(request, request_id):
    """Schema validation does not grant approval; signatures are also required."""
    keys = {"protocol", "action", "request_id", "task_id", "post_id", "attachment_id",
            "candidate_number", "candidate_count", "image_sha256", "alt_text",
            "expected", "release_sha256", "origin", "review", "task_created_at",
            "target", "generator_policy_sha256", "candidates", "source_sha256",
            "staged_sha256", "manifest_sha256", "review_receipt_sha256",
            "selection_mode", "review_actor"}
    if not isinstance(request, dict) or set(request) != keys:
        raise ValueError("invalid_approval_schema")
    expected_keys = {"post_status", "content_sha256", "title_sha256", "slug_sha256",
                     "excerpt_sha256", "thumbnail_id", "alt_sha256"}
    e = request["expected"]
    if (type(request["protocol"]) is not int or request["protocol"] != 1
            or request["action"] != "featured-image-set"
            or request["request_id"] != request_id
            or not isinstance(request["task_id"], str) or not TASK_ID.fullmatch(request["task_id"])
            or not _valid_id(request["post_id"]) or not _valid_id(request["attachment_id"])
            or type(request["candidate_number"]) is not int
            or type(request["candidate_count"]) is not int
            or not 1 <= request["candidate_number"] <= request["candidate_count"] <= 20
            or not _valid_sha(request["image_sha256"])
            or not _valid_sha(request["release_sha256"])
            or not _valid_sha(request["source_sha256"])
            or not _valid_sha(request["staged_sha256"])
            or not _valid_sha(request["manifest_sha256"])
            or not _valid_sha(request["review_receipt_sha256"])
            or not _valid_sha(request["generator_policy_sha256"])
            or request["image_sha256"] != request["staged_sha256"]
            or request["target"] != {"post_id": request["post_id"]}
            or not isinstance(request["selection_mode"], str)
            or request["selection_mode"] not in {"user", "agent-delegated"}
            or not isinstance(request["review_actor"], str) or not 1 <= len(request["review_actor"]) <= 128
            or not isinstance(request["task_created_at"], str)
            or len(request["task_created_at"]) > 45
            or not isinstance(request["candidates"], list)
            or len(request["candidates"]) != request["candidate_count"]
            or any(not isinstance(row, dict)
                   or set(row) != {"candidate_number", "sha256"}
                   or type(row["candidate_number"]) is not int
                   or row["candidate_number"] != i or not _valid_sha(row["sha256"])
                   for i, row in enumerate(request["candidates"], 1))
            or len({row["sha256"] for row in request["candidates"]}) != request["candidate_count"]
            or request["candidates"][request["candidate_number"] - 1]["sha256"] != request["source_sha256"]
            or not isinstance(request["alt_text"], str)
            or not 1 <= len(request["alt_text"]) <= 400
            or any(ord(ch) < 32 or ord(ch) == 127 for ch in request["alt_text"])
            or not isinstance(e, dict) or set(e) != expected_keys
            or not isinstance(e["post_status"], str)
            or e["post_status"] not in {"draft", "publish"}
            or any(not _valid_sha(e[k]) for k in ("content_sha256", "title_sha256",
                                                    "slug_sha256", "excerpt_sha256", "alt_sha256"))
            or type(e["thumbnail_id"]) is not int or not 0 <= e["thumbnail_id"] <= 999999999):
        raise ValueError("invalid_approval_values")
    return request


def _canonical(data):
    return json.dumps(data, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _time(value):
    if not isinstance(value, str) or len(value) > 45:
        raise ValueError("invalid_signed_event_time")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid_signed_event_time") from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("invalid_signed_event_time")
    return result.astimezone(timezone.utc)


def _check_signed_event(envelope, kind, key_bytes, expected, *, created, now):
    # Signature contract shared with agents.featured_image_trust._canonical.
    if (not isinstance(envelope, dict) or set(envelope) != {"version", "kind", "payload", "signature"}
            or type(envelope["version"]) is not int or envelope["version"] != 1
            or envelope["kind"] != kind
            or not isinstance(envelope["payload"], dict)
            or not isinstance(envelope["signature"], str)):
        raise ValueError("missing_signed_event")
    event = envelope["payload"]
    if (set(event) != set(expected) | {"issued_at", "expires_at"}
            or any(event[k] != v for k, v in expected.items())):
        raise ValueError("signed_event_context_mismatch")
    instant = _time(event["issued_at"])
    expires = _time(event["expires_at"])
    if (instant < created or instant > now or expires <= instant
            or expires - instant > timedelta(hours=24)
            or expires <= now or instant < now - timedelta(hours=24)):
        raise ValueError("signed_event_stale")
    try:
        sig = base64.b64decode(envelope["signature"], validate=True)
        if len(sig) != 64:
            raise ValueError("invalid_signature_size")
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        from cryptography.hazmat.primitives.serialization import load_pem_public_key
        pub = load_pem_public_key(key_bytes)
        if not isinstance(pub, Ed25519PublicKey):
            raise ValueError("invalid_signature_key_type")
        signed = (b"bloguito-featured-image-trust-v1\n" + kind.encode("ascii")
                  + b"\n" + _canonical(event))
        pub.verify(sig, signed)
    except (binascii.Error, ImportError, ValueError, TypeError) as exc:
        raise ValueError("signature_validation_failed") from exc
    except Exception as exc:
        # cryptography.exceptions.InvalidSignature and inaccessible key files.
        raise ValueError("signature_validation_failed") from exc
    return instant


def verify_approval_signatures(request, *, now=None):
    now = now or datetime.now(timezone.utc)
    host_key = _trusted_file(HOST_PUBLIC_KEY, PUBKEY_LIMIT)
    review_key = _trusted_file(REVIEW_PUBLIC_KEY, PUBKEY_LIMIT)
    if host_key == review_key:
        raise ValueError("independent_signers_required")
    common = {"task_id": request["task_id"], "target": request["target"],
              "generator_policy_sha256": request["generator_policy_sha256"]}
    origin_time = _check_signed_event(
        request["origin"], "host_generation", host_key,
        {**common, "candidates": request["candidates"],
         "issuer": "verified_chatgpt_host_event"},
        created=_time(request["task_created_at"]), now=now)
    review_time = _check_signed_event(
        request["review"], "review_selection", review_key,
        {**common, "manifest_sha256": request["manifest_sha256"],
         "review_receipt_sha256": request["review_receipt_sha256"],
         "source_sha256": request["source_sha256"], "staged_sha256": request["staged_sha256"],
         "selected_candidate": request["candidate_number"],
         "selection_mode": request["selection_mode"], "review_actor": request["review_actor"],
         "issuer": "independent_reviewer_authority"},
        created=_time(request["task_created_at"]), now=now)
    if review_time < origin_time:
        raise ValueError("review_before_origin")


def load_approved_request(request_id):
    if not isinstance(request_id, str) or not ID.fullmatch(request_id):
        raise ValueError("invalid_request_id")
    # There is no client-provided path: the single canonical filename is derived
    # from a strictly validated identifier in a root-controlled directory.
    payload = _json(_trusted_file(REQUEST_DIR / (request_id + ".json"),
                                  APPROVAL_LIMIT, private=True))
    request = validate_approval(payload, request_id)
    manifest_bytes = _trusted_file(REQUEST_DIR / (request_id + ".manifest.json"),
                                   APPROVAL_LIMIT, private=True)
    review_bytes = _trusted_file(REQUEST_DIR / (request_id + ".review.json"),
                                 APPROVAL_LIMIT, private=True)
    if (hashlib.sha256(manifest_bytes).hexdigest() != request["manifest_sha256"]
            or hashlib.sha256(review_bytes).hexdigest() != request["review_receipt_sha256"]):
        raise ValueError("approved_evidence_hash_mismatch")
    manifest, review = _json(manifest_bytes), _json(review_bytes)
    rows = manifest.get("candidates") if isinstance(manifest, dict) else None
    if (not isinstance(rows, list) or len(rows) != request["candidate_count"]
            or any(not isinstance(row, dict)
                   or row.get("candidate_number") != i
                   or row.get("sha256") != request["candidates"][i - 1]["sha256"]
                   for i, row in enumerate(rows, 1))
            or not isinstance(review, dict) or review.get("task_id") != request["task_id"]
            or review.get("review_actor") != request["review_actor"]):
        raise ValueError("approved_evidence_content_mismatch")
    return request


def locked_runtime_hash(request):
    pin = _json(_trusted_file(RELEASE_LOCK, LOCK_LIMIT, private=True))
    if (not isinstance(pin, dict) or set(pin) != {"protocol", "runtime_sha256"}
            or type(pin["protocol"]) is not int or pin["protocol"] != 1
            or not _valid_sha(pin["runtime_sha256"])
            or request["release_sha256"] != pin["runtime_sha256"]):
        raise ValueError("release_not_approved")
    actual = hashlib.sha256(_trusted_file(PHP_RUNTIME, 65536)).hexdigest()
    if actual != pin["runtime_sha256"]:
        raise ValueError("release_hash_mismatch")
    return actual


def _claim_once(request_id):
    """Permanently fence a request before the irreversible WP call.

    On timeout or lost response, a privileged operator must reconcile WordPress
    state manually. Retrying the same ID will always be denied.
    """
    for parent in reversed(CONSUMED_DIR.parents):
        st = parent.lstat()
        if not stat.S_ISDIR(st.st_mode) or st.st_uid != 0 or st.st_mode & 0o022:
            raise ValueError("insecure_consumed_parent")
    folder = os.open(CONSUMED_DIR, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
                     | getattr(os, "O_NOFOLLOW", 0))
    try:
        st = os.fstat(folder)
        if (not stat.S_ISDIR(st.st_mode) or st.st_uid != 0
                or st.st_mode & 0o077):
            raise ValueError("insecure_consumed_directory")
        fd = os.open(request_id + ".claimed",
                     os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                     0o600, dir_fd=folder)
        try:
            os.write(fd, b"claimed-before-wordpress-write\n")
            os.fsync(fd)
        finally:
            os.close(fd)
        os.fsync(folder)
    finally:
        os.close(folder)


def dispatch(raw, *, runner=subprocess.run):
    request_id = parse_request(raw)
    request = load_approved_request(request_id)
    verify_approval_signatures(request)
    digest = locked_runtime_hash(request)
    common = [DOCKER, "exec", "--user", "www-data", CONTAINER]
    verify = runner([*common, "/usr/bin/sha256sum", CONTAINER_RUNTIME],
                    capture_output=True, check=False, timeout=20, env=ENV)
    if verify.returncode != 0 or verify.stdout != (digest + "  " + CONTAINER_RUNTIME + "\n").encode():
        raise ValueError("container_release_hash_mismatch")
    _claim_once(request_id)
    # The fixed PHP file must be mounted read-only inside wordpress_app; never
    # accept an arbitrary caller PHP expression or runtime path.
    execute = runner([*common, "wp", "eval-file", CONTAINER_RUNTIME,
                      "--user=" + WP_USER],
                     input=_canonical(request), capture_output=True,
                     check=False, timeout=45, env=ENV)
    if execute.returncode != 0 or len(execute.stdout) > RESPONSE_LIMIT:
        raise ValueError("wordpress_writer_failed")
    result = _json(execute.stdout)
    if (not isinstance(result, dict) or set(result) != {"status", "post_id", "attachment_id", "image_sha256"}
            or result["status"] != "verified"
            or result["post_id"] != request["post_id"]
            or result["attachment_id"] != request["attachment_id"]
            or result["image_sha256"] != request["image_sha256"]):
        raise ValueError("wordpress_readback_not_verified")
    return _canonical(result)


def main():
    if not hasattr(os, "geteuid") or os.geteuid() != 0 or len(sys.argv) != 1:
        print("image_writer_privilege_or_arguments_invalid", file=sys.stderr)
        return 126
    try:
        result = dispatch(sys.stdin.buffer.read(SUDO_REQUEST_LIMIT + 1))
        sys.stdout.buffer.write(result + b"\n")
        return 0
    except (ValueError, OSError, subprocess.TimeoutExpired):
        print("image_writer_request_denied", file=sys.stderr)
        return 126


if __name__ == "__main__":
    sys.exit(main())
