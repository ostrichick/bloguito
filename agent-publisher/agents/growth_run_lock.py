"""One process-level writer lock for the scheduled growth state.

The kernel owns lock lifetime. Never delete a lock file to break a perceived
stale lock: a crash, including SIGKILL, closes the descriptor automatically.
"""

from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import stat


class GrowthRunAlreadyRunning(RuntimeError):
    """Another scheduler or growth-state CLI currently owns the writer lock."""


def lock_path() -> Path:
    # The override is useful for isolated subprocess/concurrency tests. All
    # production entrypoints use the same default, not each output file's path.
    override = os.environ.get("BLOGUITO_GROWTH_LOCK_PATH")
    return (Path(override) if override else
            Path(__file__).resolve().parents[1] / "data" / "growth" / ".scheduler-run.lock")


@contextmanager
def growth_run_lock():
    """Nonblocking advisory lock; callers MUST enclose their complete RMW cycle.

    On Unix this is flock(2), shared by the cron and direct Python entrypoints.
    The Windows byte-range equivalent allows the same safety tests on a laptop.
    """
    path = lock_path().absolute()
    if path.parent.is_symlink() or path.is_symlink():
        raise OSError("growth_run_lock_symlink_not_allowed")
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.parent.is_symlink() or path.is_symlink():
        raise OSError("growth_run_lock_symlink_not_allowed")
    if os.name == "posix" and path.parent.stat().st_mode & 0o077:
        raise OSError("growth_run_lock_directory_permissions_too_open")
    flags = os.O_CREAT | os.O_RDWR
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    acquired = False
    try:
        file_mode = os.fstat(fd).st_mode
        if not stat.S_ISREG(file_mode):
            raise OSError("growth_run_lock_not_regular_file")
        if os.name == "posix" and file_mode & 0o077:
            raise OSError("growth_run_lock_permissions_too_open")
        if os.name == "posix":
            import fcntl
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise GrowthRunAlreadyRunning("growth_writer_already_running") from exc
        elif os.name == "nt":
            import msvcrt
            if os.fstat(fd).st_size == 0:
                os.write(fd, b"\0")
            os.lseek(fd, 0, os.SEEK_SET)
            try:
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                # Windows reports an occupied byte-range lock as EACCES/EDEADLK.
                if getattr(exc, "winerror", None) in (33, 36) or exc.errno in (13, 36):
                    raise GrowthRunAlreadyRunning("growth_writer_already_running") from exc
                raise
        else:
            raise OSError("growth_run_lock_platform_unsupported")
        acquired = True
        yield
    finally:
        if acquired:
            if os.name == "posix":
                fcntl.flock(fd, fcntl.LOCK_UN)
            else:
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        os.close(fd)
