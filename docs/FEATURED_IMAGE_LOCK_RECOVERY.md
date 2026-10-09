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

## 2026-10-09 actual release comparison and predeployment boundary

- 2026-10-09 13:59 KST SSH observation: the operating `data/editorial-release.json` revision is `b9de4709fff354f7449d6f275b36ea17fdec5b7c`. All **80/80** installed managed file SHA-256 hashes match the operating release manifest, with no missing file. This verifies the installed release's internal integrity, not parity with local HEAD.
- At investigation start local HEAD was `bd1dfd5`; during investigation a separate docs-only commit `720d7a1` advanced local `main`. In both commits the updated local `main.py` handles `held_image_generation_unavailable`, `designer.py` defines `ScheduledImageGenerationUnavailable`, and `featured_image.py` defines `recover_imported_featured_image_outcome`; the installed three files contain none of these. Their AST hashes and LF-normalized hashes also differ, while operating bytes match Git blob `b9de470`. This is a **real code-version difference**, not CRLF or archive packaging. `config.py`, `growth_analysis.py` and `growth_planner.py` match exactly.
- The operating `data/search_briefs.json` differs from the Git blob and is intentionally excluded from release inventory. Release builder packages reviewed policy/runtime, `renderer_provenance.json` and `reviewed_content_provenance.json`, but excludes private `draft_posts.json`, `published_posts.json`, `search_briefs.json`, analytics/growth runtime, `.env` and task state. Installer preserves these excluded files; it **does replace the two tracked provenance registries**, so their validator and digest parity require preflight. Local reviewed state is the editorial source of truth and must not be replaced by older remote copies.
- Read-only `python scripts/ops/featured_image_lock_preflight.py` at the observation date returned `wp_options=InnoDB`, `wp_postmeta=InnoDB`, **0 image locks**, `blockers=[]` (exit 0). Re-run immediately before an authorized deployment; a later pending lock blocks rollout even if expired.
- **Required before GO:** (1) freeze and identify the exact clean Git target revision, package the full current HEAD using `build_editorial_release.py` into a fresh directory and verify schema/inventory/hash/retired list; (2) run image-generation hold, failed import/SSH 255 reconciliation, post CAS, image lock and publication-gate targeted tests followed by the required common-code regression; (3) verify a completely isolated WordPress/MariaDB concurrency/fault rehearsal with synthetic posts and no production URL/side effects; (4) verify latest full v3 backup covers DB/uploads/MU plugins/config, has a recoverable restore path, and preserve the existing backup and scheduler schedule; (5) check production pre-hashes, externalized config, `search_briefs.json`, reviewed state and both provenance registries, plus exact plugin compatibility and image-lock preflight; (6) only in a separately authorized deployment, install and read back actual hashes, CLI/provenance validation and scheduler status. The editorial installer does not deploy WordPress MU plugins, so plugin compatibility/rollback must be covered separately if plugin files change.
- **Stop/rollback criteria:** any manifest/target mismatch, inline credential config, unexpected module, registry validation failure, staging fault/concurrency failure, missing verified backup or pending image import prevents GO. After installation, failed CLI/renderer/provenance/readback requires restoring the installer's per-file backup manifest; this does **not** reverse WordPress DB, media, options or task state. Never roll back to a lock-unaware runtime while a media import could remain in flight; reconcile pending import liveness and per-post receipts first, then choose verified full-backup recovery or carefully reviewed forward recovery for any data-side mutation.

No production deploy, cron/service change, image import or WordPress mutation was performed during this audit. Nonsecret read-only diagnostic evidence is in ignored `scratch/tasks/bloguito-readonly-audit-20261009/`.
