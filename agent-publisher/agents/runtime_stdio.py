"""Stable UTF-8 stdio for Windows editorial command-line entry points."""

from __future__ import annotations

import os
import sys


def configure_utf8_stdio() -> None:
    """Make Korean/emoji diagnostics safe without depending on shell code pages.

    Python launched from Windows PowerShell can inherit a legacy console encoding.
    Reconfigure the live streams when supported and set the child-process default for
    subsequent Python invocations. ``errors='replace'`` is deliberate for diagnostic
    output: a logging glyph must never turn an otherwise successful editorial action
    into a failed run.
    """

    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.environ.setdefault("PYTHONUTF8", "1")
    for stream in (getattr(sys, "stdout", None), getattr(sys, "stderr", None)):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                pass
