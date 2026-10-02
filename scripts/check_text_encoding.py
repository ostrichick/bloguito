"""Fail when tracked text files violate the repository UTF-8 contract."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {
    ".cnf", ".css", ".csv", ".env", ".example", ".html", ".ini", ".js",
    ".json", ".md", ".php", ".ps1", ".py", ".sh", ".toml", ".txt",
    ".xml", ".yaml", ".yml",
}
TEXT_NAMES = {".gitattributes", ".gitignore", ".clinerules", ".continuerules", "Dockerfile"}
EVIDENCE_PREFIXES = ("agent-publisher/data/", "backups/", "content/")
INTENTIONAL_QUESTION_MARK_RUNS = {
    "agent-publisher/tests/test_section_image.py",
    "docs/OPERATIONS.md",
}
# Keep the detector source ASCII-only for these sentinel values so the checker
# does not flag its own marker table once this file is tracked.
MOJIBAKE_MARKERS = (
    "\u00c3",
    "\u00c2",
    "\u00e2\u20ac",
    "\u00f0\u0178",
    "\u00ef\u00bb\u00bf",
)


def tracked_paths() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
    )
    return [item.decode("utf-8", "strict") for item in result.stdout.split(b"\0") if item]


def is_text_path(relative: str) -> bool:
    path = Path(relative)
    return path.name in TEXT_NAMES or path.suffix.lower() in TEXT_SUFFIXES


def scan() -> list[str]:
    issues: list[str] = []
    for relative in tracked_paths():
        if not is_text_path(relative):
            continue
        path = ROOT / relative
        raw = path.read_bytes()
        if raw.startswith(b"\xef\xbb\xbf"):
            issues.append(f"{relative}: UTF-8 BOM is not allowed")
        try:
            text = raw.decode("utf-8", "strict")
        except UnicodeDecodeError as exc:
            issues.append(f"{relative}: not strict UTF-8 ({exc})")
            continue
        if "\ufffd" in text:
            issues.append(f"{relative}: contains Unicode replacement character U+FFFD")
        if any(marker in text for marker in MOJIBAKE_MARKERS):
            issues.append(f"{relative}: contains a common mojibake marker")
        if relative.startswith(EVIDENCE_PREFIXES):
            continue
        if relative not in INTENTIONAL_QUESTION_MARK_RUNS and re.search(r"\?{3,}", text):
            issues.append(f"{relative}: contains a suspicious run of three or more question marks")
    return issues


def main() -> int:
    issues = scan()
    if issues:
        print("Repository text encoding check failed:", file=sys.stderr)
        for issue in issues:
            print(" -", issue, file=sys.stderr)
        return 1
    print("Repository text encoding check passed: strict UTF-8, no BOM or suspicious corruption.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
