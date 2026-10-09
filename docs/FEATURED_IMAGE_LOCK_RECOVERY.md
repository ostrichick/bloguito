# Bloguito featured-image import lock: deployment and recovery procedure

Scope: the image lock introduced after editorial release `b9de470` and included in `e694eee`. The lock is a per-post WordPress `wp_options` record, updated in an SQL transaction. Never use this procedure to change the content or publication status of a real post.

## Preflight (read-only)

Run from the exact reviewed Git checkout:

```powershell
python scripts/ops/featured_image_lock_preflight.py
```

The script uses fixed read-only `wp eval` queries over `information_schema.TABLES` and lock option records. Output is sanitized: table engines, post IDs, expiration flags, pending flags and autoload modes; **no owner tokens or option JSON**. If the script exits 2, the probe itself failed and no readiness claim may be made. Exit 1 indicates a detected readiness blocker, including a non-InnoDB options table or an import-pending state.

Review output before the deploy. If any lock has `import_pending=true`, **pause deployment** and investigate; never clear the option to make preflight green. A record may remain intentionally pending even when its lease TTL is expired. Image attachment SHA, post CAS, media ownership, remote process liveness, and specific original token must all be investigated together.

## Normal lock state machine

1. Acquire: a fresh token is created; first `add_option(..., autoload=no)` succeeds, or an **expired, nonpending** lock may be replaced only within a transaction with `SELECT ... FOR UPDATE` and an exact old-value compare.
2. Read post SHA, title, status, previous thumbnail; verify selected local original SHA.
3. Copy to a **token-specific** temporary path, read remote SHA and inspect pre-existing attachments with that SHA.
4. Persist a local `image_import_attempt` checkpoint (token, previous SHA IDs, old thumbnail); mark the per-post option `import_pending=true` before invoking non-idempotent `wp media import`.
5. After definite success and attachment/post SHA verification, use WordPress CAS to update thumbnail and ALT; only when the original remote import has **definitely terminated** may the original owner mark `complete_import`, clear pending, and release the lock.
6. For SSH timeout, 255 exit, malformed stdout or process uncertainty, reconcile SHA against the previous attachment ID snapshot. Even if one matching new attachment exists, a lost SSH session does **not** prove that the original WP-CLI process has stopped. Keep the pending fence, avoid a second import, and escalate until liveness and final state are proved.

## Incident decision table

| Observed evidence | Safe action | Forbidden action |
| --- | --- | --- |
| Lease expired, `import_pending=false`, no running prior worker | Normal new work can attempt token-protected acquire | Blind direct SQL deletion |
| Pending true; original WP-CLI media import still running or liveness unknown | Stop new image writes; locate original receipt/process; preserve token privately | Retry import, forcibly release, manually delete lock |
| Pending true; process definitely terminated and exact one new SHA attachment is identified | Resume with original receipt/token; verify post/thumbnail/ALT/CAS; complete fence only after complete readback | Attach by guess, override CAS, reuse another token |
| Pending true; process terminated but no new SHA attachment | Investigate whether import never started/was rolled back; retain fence until owner-approved recovery | Assume the previous attempt was a no-op |
| Multiple new SHA matches, malformed option, stale token or state drift | Fail closed; incident review and backup comparison | Pick arbitrary attachment, mark completed, or replace owner token |

## Staging-only acceptance test before GO

Create a **disposable** WordPress + MariaDB site, seeded with a synthetic draft, not a clone that can reach production. Confirm `wp_options` and `wp_postmeta` are InnoDB. Exercise independent WP-CLI connections with two tokens for the same post:

- simultaneous first acquisitions: exactly one writer may own the token;
- second writer during active lease: busy, no import attempted;
- stale nonpending option: lease takeover only after expiry;
- expired pending option: any other token denied indefinitely;
- wrong owner cannot mark or release;
- original token `mark_import` exactly once, `complete_import` after verified import only;
- SSH response lost after remote commit, no automatic second `wp media import`;
- attachment SHA reconciliation zero/one/multiple new matching IDs, exact post/thumbnail CAS;
- low-memory/SSH latency budget exceeded, safe cleanup/fail-closed behavior.

Before staging runs, take a disposable DB snapshot and verify the test site hostname does not refer to production. Tests must assert that no production post or WordPress option was changed. A green unit test alone is not equivalent to this DB/WP integration acceptance.

## Code and data rollback are different

- The editorial installer restores **code and managed documentation** from its own manifest. It does not reverse WP posts, options, media files, or task state.
- A full WordPress backup must cover **DB + uploads + MU plugins + config** and be independently verified before deployment; record when to restore vs forward-recover.
- Never roll back code to a version that cannot recognize pending import locks while an import worker remains in flight. Block worker start until version compatibility and locks are reconciled.
- Resume the 08:00 scheduled writer only after both the current release and its recovery procedure pass; preserve the 04:00 backup cron entry.

## Remaining approval boundary

This runbook and preflight are read-only and diagnostic. Real media mutation tests use only disposable staging or an explicitly owner-approved test post. Actual production deployment, changing cron, modifying WordPress options, or force-releasing a lock require release authorization with rollback evidence.
