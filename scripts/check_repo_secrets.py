#!/usr/bin/env python3
"""Fail CI when high-confidence secrets or sensitive credential files are tracked."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAX_TEXT_BYTES = 2_000_000

SECRET_PATTERNS = {
    "private key": re.compile(rb"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"),
    "AWS access key": re.compile(rb"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    "GitHub token": re.compile(rb"\b(?:gh[pousr]_[A-Za-z0-9_]{30,}|github_pat_[A-Za-z0-9_]{40,})\b"),
    "OpenAI token": re.compile(rb"\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}\b"),
    "Google API key": re.compile(rb"\bAIza[0-9A-Za-z_-]{35}\b"),
    "Slack token": re.compile(rb"\bxox[baprs]-[0-9A-Za-z-]{20,}\b"),
    "Stripe secret": re.compile(rb"\bsk_(?:live|test)_[0-9A-Za-z]{16,}\b"),
}

SENSITIVE_NAMES = re.compile(
    r"(?i)(^|/)(?:\.env(?:\.[^/]+)?|\.netrc|\.pypirc|\.htpasswd|id_rsa|id_ed25519|"
    r"credentials?[^/]*\.(?:json|ya?ml)|service[-_]?account[^/]*\.json|"
    r"client[_-]?secret[^/]*\.json)$|\.(?:pem|key|p12|pfx|kdbx)$"
)


def tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "-z"],
        check=True,
        capture_output=True,
    )
    return [item.decode("utf-8", "replace") for item in result.stdout.split(b"\0") if item]


def is_allowed_sensitive_name(path: str) -> bool:
    lowered = path.lower()
    return lowered.endswith(".env.example") or ".example." in lowered or lowered.endswith(".example")


def main() -> int:
    findings: list[str] = []
    for relative in tracked_files():
        normalized = relative.replace("\\", "/")
        if SENSITIVE_NAMES.search(normalized) and not is_allowed_sensitive_name(normalized):
            findings.append(f"tracked sensitive filename: {normalized}")

        path = ROOT / relative
        try:
            if not path.is_file() or path.stat().st_size > MAX_TEXT_BYTES:
                continue
            data = path.read_bytes()
        except OSError:
            continue
        if b"\0" in data[:8192]:
            continue
        for label, pattern in SECRET_PATTERNS.items():
            match = pattern.search(data)
            if match:
                line = data.count(b"\n", 0, match.start()) + 1
                findings.append(f"{label}: {normalized}:{line}")

    if findings:
        print("Repository secret scan failed:")
        for finding in findings:
            print(f"- {finding}")
        return 1

    print("Repository secret scan passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
