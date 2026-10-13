"""Durable fail-closed receipt for the non-idempotent WordPress draft create.

WordPress post creation and the local filesystem cannot share a transaction.
An unknown create outcome must therefore *never* trigger another post create.
Only an exact saved post ID whose WordPress state matches the original reviewed
payload can be resumed by this journal.
"""

import hashlib
import json
import os
import re
import tempfile
from contextlib import contextmanager
from pathlib import Path

from config import DATA_DIR


class DraftCreateBlocked(ValueError):
    def __init__(self, reason: str, key: str, *, post_id: int | None = None):
        super().__init__(reason)
        self.failure_stage = "draft_create_recovery"
        self.failure_receipt = {
            "workflow_key": key,
            "post_id": post_id,
            "state": "uncertain" if post_id is None else "known_post_id",
            "reason": reason,
            "automatic_retry": False,
        }


def workflow_key(bundle: dict, *, content: str, title: str, excerpt: str) -> str:
    """Bind an attempt to the *exact* reviewed article, not title similarity."""
    payload = json.dumps(
        {"bundle": bundle, "content": content, "title": title, "excerpt": excerpt},
        sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class DraftCreateJournal:
    VERSION = 1

    def __init__(self, key: str, *, directory: Path | None = None):
        if not re.fullmatch(r"[0-9a-f]{64}", key):
            raise ValueError("invalid_draft_create_workflow_key")
        self.key = key
        self.directory = directory or (DATA_DIR / "editorial_runs" / "draft-create")
        self.path = self.directory / f"{key}.json"
        self.lock_path = self.directory / f".{key}.lock"

    @contextmanager
    def _exclusive_transition(self):
        """Serialize per-key receipt transitions across independent processes.

        O_EXCL is deliberate: a crash leaves a sidecar fence, which requires
        human review of the original WordPress attempt. Never auto-expire or
        steal that lock merely because the process is no longer running.
        """
        if self.directory.is_symlink() or self.path.is_symlink() or self.lock_path.is_symlink():
            raise DraftCreateBlocked("draft_create_journal_symlink", self.key)
        self.directory.mkdir(parents=True, exist_ok=True)
        if self.directory.is_symlink():
            raise DraftCreateBlocked("draft_create_journal_symlink", self.key)
        try:
            fd = os.open(self.lock_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL
                         | getattr(os, "O_NOFOLLOW", 0), 0o600)
        except FileExistsError as exc:
            raise DraftCreateBlocked("draft_create_journal_busy_or_stale_lock", self.key) from exc
        except OSError as exc:
            raise DraftCreateBlocked("draft_create_journal_lock_unavailable", self.key) from exc
        try:
            os.write(fd, b"draft-create-journal-lock-v1\n")
            os.fsync(fd)
            if os.name == "posix":
                # The directory entry itself must survive a host crash before
                # either competing process can record a different owner ID.
                directory_fd = os.open(self.directory, os.O_RDONLY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            yield
        finally:
            os.close(fd)
            # Only the process that created this lock removes it. A hard kill
            # leaves it in place and causes future writes to fail closed.
            self.lock_path.unlink()

    def read(self) -> dict | None:
        if self.path.is_symlink() or self.directory.is_symlink():
            raise DraftCreateBlocked("draft_create_journal_symlink", self.key)
        if not self.path.exists():
            return None
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise DraftCreateBlocked("draft_create_journal_unreadable", self.key) from exc
        if (not isinstance(value, dict) or value.get("version") != self.VERSION
                or value.get("key") != self.key
                or value.get("state") not in {"creating", "created", "complete"}
                or (value.get("state") != "creating"
                    and (type(value.get("post_id")) is not int or value["post_id"] <= 0))):
            raise DraftCreateBlocked("draft_create_journal_invalid", self.key)
        return value

    def _write(self, value: dict) -> None:
        if self.directory.is_symlink() or self.path.is_symlink():
            raise DraftCreateBlocked("draft_create_journal_symlink", self.key)
        self.directory.mkdir(parents=True, exist_ok=True)
        temp: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=self.directory,
                prefix=".draft-create-", suffix=".tmp", delete=False,
            ) as handle:
                temp = Path(handle.name)
                if os.name == "posix":
                    os.chmod(temp, 0o600)
                json.dump(value, handle, ensure_ascii=False, allow_nan=False, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp, self.path)
            if os.name == "posix":
                fd = os.open(self.directory, os.O_RDONLY)
                try:
                    os.fsync(fd)
                finally:
                    os.close(fd)
        finally:
            if temp is not None:
                temp.unlink(missing_ok=True)

    def begin(self) -> None:
        with self._exclusive_transition():
            if self.read() is not None:
                raise DraftCreateBlocked("draft_create_already_started", self.key)
            self._write({"version": self.VERSION, "key": self.key, "state": "creating"})

    def created(self, post_id: int) -> None:
        if type(post_id) is not int or post_id <= 0:
            raise ValueError("draft_create_invalid_post_id")
        with self._exclusive_transition():
            previous = self.read()
            if previous is None:
                raise DraftCreateBlocked("draft_create_id_receipt_required", self.key)
            if previous["state"] in {"created", "complete"}:
                if previous["post_id"] == post_id:
                    return  # Already durably recorded: preserve its original identity.
                raise DraftCreateBlocked("draft_create_id_receipt_conflict", self.key,
                                         post_id=previous["post_id"])
            if previous["state"] != "creating":
                raise DraftCreateBlocked("draft_create_id_receipt_required", self.key)
            self._write({
                "version": self.VERSION, "key": self.key,
                "state": "created", "post_id": post_id,
            })

    def complete(self, post_id: int) -> None:
        if type(post_id) is not int or post_id <= 0:
            raise ValueError("draft_create_invalid_post_id")
        with self._exclusive_transition():
            previous = self.read()
            if previous is None or previous["state"] == "creating":
                raise DraftCreateBlocked("draft_create_id_receipt_required", self.key)
            if previous["post_id"] != post_id:
                raise DraftCreateBlocked("draft_create_id_receipt_conflict", self.key,
                                         post_id=previous["post_id"])
            if previous["state"] == "complete":
                return  # A verified exact replay must not change the saved receipt.
            self._write({
                "version": self.VERSION, "key": self.key,
                "state": "complete", "post_id": post_id,
            })
