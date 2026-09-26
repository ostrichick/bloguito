"""Small reusable primitives for safe WordPress post mutations."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path

from agents.workflow_metrics import increment, timed


def content_sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def get_post(base, post_id, *, fields=None):
    command = list(base) + ["post", "get", str(int(post_id))]
    if fields:
        command.append("--fields=" + ",".join(fields))
    command += ["--format=json", "--allow-root"]
    with timed("wp_target_read"):
        increment("wp_roundtrips")
        result = subprocess.run(command, capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def update_post(base, post_id, fields: dict[str, str]):
    if not fields:
        raise ValueError("wordpress_update_fields_required")
    args = ["post", "update", str(int(post_id))]
    for key, value in fields.items():
        if not isinstance(key, str) or not key or not isinstance(value, str):
            raise ValueError("invalid_wordpress_update_field")
        args.append(f"--{key}={value}")
    args.append("--allow-root")
    with timed("wp_update"):
        increment("wp_roundtrips")
        return subprocess.run(list(base) + args, capture_output=True, text=True, check=True)


def verify_cas(post, *, status=None, title=None, content_sha=None):
    if status is not None and post.get("post_status") != status:
        return False
    if title is not None and post.get("post_title") != title:
        return False
    if content_sha is not None and content_sha256(post.get("post_content", "")) != content_sha:
        return False
    return True


def backup_json(root: Path, prefix: str, post_id: int, payload, *, include_microseconds=True):
    archive = root / "data" / "editorial_runs"
    archive.mkdir(parents=True, exist_ok=True)
    fmt = "%Y%m%dT%H%M%S%f" if include_microseconds else "%Y%m%dT%H%M%S"
    target = archive / f"{prefix}-{post_id}-{datetime.now().strftime(fmt)}.json"
    with target.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    os.chmod(target, 0o600)
    return target


def verify_saved_fields(saved, *, expected: dict[str, str], preserved=None):
    for key, value in expected.items():
        if saved.get(key) != value:
            return False
    if preserved:
        for key, value in preserved.items():
            if saved.get(key) != value:
                return False
    return True
