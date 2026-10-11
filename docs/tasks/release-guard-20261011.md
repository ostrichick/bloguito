# Editorial release installation exclusivity (2026-10-11)

- `scripts/install_editorial_release.py` now requires both the existing editorial writer mutex (`data/.editorial-publish.lock` directory) and the scheduler/main shared OS lock (`data/growth/.scheduler-run.lock`) for the entire multi-file write, import smoke, SHA readback and rollback window.
- Preflight remains read-only and checks signed assets + actual WordPress MU SHA before locks or runtime mutation.
- Lock acquisition is nonblocking, symlink paths fail closed, an existing editor/scheduler yields a visible error, and failure leaves prior runtime bytes in place. `growth/.scheduler-run.lock` remains after unlock for OS-safe lock identity; it is never unlinked to "fix" an in-use process.
- Acquiring the editorial directory first cannot deadlock an active growth writer because the OS scheduler lock is immediately tested nonblocking; the editorial directory is removed before reporting busy.
- New disposable tests assert editorial writer conflict and release failure cleanup. Actual Ubuntu subprocess lock behavior should be checked in isolated CI or `/tmp` staging before operational rollout.
- This guard does not prevent WordPress administrator UI edits or uncooperative raw WP-CLI from running. Operational deploy must inspect active tasks and recheck WP/CAS evidence afterward.
