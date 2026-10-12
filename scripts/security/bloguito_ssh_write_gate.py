#!/usr/bin/python3 -I
"""Restricted SSH entrypoint for preapproved featured-image attachment updates.

The SSH identity cannot issue arbitrary WP, PHP, Docker, sudo, or host commands.
The root-owned counterpart independently revalidates every request.
"""

import json
import os
import re
import subprocess
import sys

WRITER = "/usr/local/libexec/bloguito/bloguito_wp_image_writer.py"
SUDO = "/usr/bin/sudo"
ORIGINAL = re.compile(r"wp-write featured-image-set ([0-9a-f]{32})\Z", re.ASCII)


def parse_original(value):
    if not isinstance(value, str) or len(value) > 80:
        raise ValueError("invalid_ssh_write_command")
    match = ORIGINAL.fullmatch(value)
    if match is None:
        raise ValueError("unsupported_ssh_write_command")
    return ["featured-image-set", match.group(1)]


def dispatch(value, *, runner=subprocess.run):
    command = parse_original(value)
    return runner(
        [SUDO, "-n", WRITER],
        input=json.dumps(command, separators=(",", ":")).encode("ascii"),
        check=False,
        timeout=70,
        env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
    ).returncode


def main():
    try:
        if len(sys.argv) != 1:
            raise ValueError("unexpected_arguments")
        return dispatch(os.environ.get("SSH_ORIGINAL_COMMAND"))
    except (ValueError, OSError, subprocess.TimeoutExpired):
        print("restricted_ssh_write_denied", file=sys.stderr)
        return 126


if __name__ == "__main__":
    sys.exit(main())
