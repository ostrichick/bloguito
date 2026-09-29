"""Compatibility shim for the pre-P2 public-update SSH command.

New work should use `scripts/editorial_cli_via_ssh.py -- edit-post ...`.
This wrapper preserves the historical argument shape without maintaining a
second WordPress/SSH transport implementation.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UNIFIED_ADAPTER = ROOT / "scripts" / "editorial_cli_via_ssh.py"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--post-id", type=int, required=True)
    parser.add_argument("--expected-content-sha256", required=True)
    parser.add_argument("--ssh-mode", choices=["direct", "wsl", "tailscale"])
    parser.add_argument("--ssh-host")
    parser.add_argument("--ssh-user")
    parser.add_argument("--wsl-distro")
    parser.add_argument("--tailscale-ssh", action="store_true")
    parser.add_argument("--confirm-update", action="store_true")
    parser.add_argument("--confirm-title-change", action="store_true")
    args = parser.parse_args(argv)
    if not args.confirm_update:
        parser.error("explicit --confirm-update required")
    return args


def build_forwarded_command(args) -> list[str]:
    command = [sys.executable, str(UNIFIED_ADAPTER)]
    if args.ssh_mode:
        command += ["--ssh-mode", args.ssh_mode]
    if args.ssh_host:
        command += ["--ssh-host", args.ssh_host]
    if args.ssh_user:
        command += ["--ssh-user", args.ssh_user]
    if args.wsl_distro:
        command += ["--wsl-distro", args.wsl_distro]
    if args.tailscale_ssh:
        command.append("--tailscale-ssh")
    command += [
        "--",
        "update-existing",
        str(args.bundle),
        "--post-id",
        str(args.post_id),
        "--expected-content-sha256",
        args.expected_content_sha256,
        "--confirm-update",
    ]
    if args.confirm_title_change:
        command.append("--confirm-title-change")
    return command


def main(argv=None) -> int:
    args = parse_args(argv)
    completed = subprocess.run(build_forwarded_command(args), cwd=str(ROOT), check=False)
    return int(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
