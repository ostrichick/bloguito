#!/usr/bin/python3 -I
"""Proposed forced-command endpoint for a dedicated read-only SSH identity.

Install as root-owned, non-writable code. Never use this gate for the current
editorial_cli_via_ssh.py write transport or scheduled publisher.
"""

import json
import os
import re
import subprocess
import sys


READER = "/usr/local/libexec/bloguito/wp_readonly.py"
SUDO = "/usr/bin/sudo"
ORIGINAL_PATTERN = re.compile(
    r"wp-read (?:health|inventory|post-(?:get|status) [1-9][0-9]{0,8})\Z",
    re.ASCII,
)


def parse_original(value):
    if not isinstance(value, str) or len(value) > 64 or not ORIGINAL_PATTERN.fullmatch(value):
        raise ValueError("unsupported_ssh_command")
    pieces = value.split(" ")
    return pieces[1:]


def dispatch(value, *, runner=subprocess.run):
    command = parse_original(value)
    payload = json.dumps(command, separators=(",", ":")).encode("ascii")
    # This sudo invocation has no arguments after the fixed executable. The
    # root-owned counterpart independently parses and constrains stdin.
    return runner(
        [SUDO, "-n", READER],
        input=payload,
        check=False,
        timeout=45,
    ).returncode


def main():
    try:
        return dispatch(os.environ.get("SSH_ORIGINAL_COMMAND"))
    except (ValueError, OSError, subprocess.TimeoutExpired):
        print("restricted_ssh_command_denied", file=sys.stderr)
        return 126


if __name__ == "__main__":
    sys.exit(main())
