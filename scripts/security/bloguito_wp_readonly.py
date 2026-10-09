#!/usr/bin/python3 -I
"""Proposed root-owned sudo target with a fixed, read-only WP-CLI surface.

No arbitrary Docker arguments, WP eval, shell, file paths or publish actions.
The SSH gate is convenience validation: this privileged target enforces the
same policy if the non-privileged account invokes sudo directly.
"""

import json
import os
import re
import subprocess
import sys


DOCKER = "/usr/bin/docker"
CONTAINER = "wordpress_app"
WP = "wp"
MAX_REQUEST_BYTES = 512
POST_ID = re.compile(r"[1-9][0-9]{0,8}\Z", re.ASCII)
INVENTORY = (
    "post", "list", "--post_type=post",
    "--post_status=publish,draft,pending,future,private",
    "--posts_per_page=-1", "--fields=ID,post_title,post_status,post_content",
    "--format=json", "--allow-root",
)


def parse_request(raw):
    if not isinstance(raw, bytes) or len(raw) > MAX_REQUEST_BYTES:
        raise ValueError("invalid_request_size")
    try:
        parts = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid_request_json") from exc
    if not isinstance(parts, list) or any(not isinstance(x, str) for x in parts):
        raise ValueError("invalid_request_shape")
    if parts == ["health"]:
        return ["core", "version", "--allow-root"]
    if parts == ["inventory"]:
        return list(INVENTORY)
    if len(parts) == 2 and parts[0] in ("post-get", "post-status") and POST_ID.fullmatch(parts[1]):
        return (["post", "get", parts[1], "--format=json", "--allow-root"]
                if parts[0] == "post-get" else
                ["post", "get", parts[1], "--field=post_status", "--allow-root"])
    raise ValueError("unsupported_wp_read_operation")


def dispatch(raw, *, runner=subprocess.run):
    args = parse_request(raw)
    # Fixed container and fixed wp command; no host shell or caller-controlled
    # flags reach docker. stdin is closed to keep WP-CLI non-interactive.
    return runner(
        [DOCKER, "exec", CONTAINER, WP, *args],
        stdin=subprocess.DEVNULL,
        check=False,
        timeout=35,
        env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
    ).returncode


def main():
    if os.geteuid() != 0 or len(sys.argv) != 1:
        print("wp_readonly_privilege_or_arguments_invalid", file=sys.stderr)
        return 126
    try:
        return dispatch(sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1))
    except (ValueError, OSError, subprocess.TimeoutExpired):
        print("wp_readonly_request_denied", file=sys.stderr)
        return 126


if __name__ == "__main__":
    sys.exit(main())
