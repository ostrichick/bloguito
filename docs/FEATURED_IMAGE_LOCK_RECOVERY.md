# Bloguito featured-image import lock: deployment and recovery procedure

Scope: the image lock introduced after editorial release `b9de470` and included in `e694eee`. The lock is a per-post WordPress `wp_options` record, updated in an SQL transaction. Never use this procedure to change the content or publication status of a real post.

**Latest validation — 2026-10-10:** the two defects recorded below were fixed in `43bd95c` and passed PC disposable WordPress/MariaDB acceptance (15/15 groups), plus a separate real loopback SSH-disconnect safety/recovery check. This supersedes the earlier NO-GO **for those two PC acceptance blockers only**. No production deployment was performed; deployment authorization and the predeployment checks below remain separate. See [PC handoff](FEATURED_IMAGE_PC_VALIDATION_HANDOFF.md#2026-10-10-pc-재검증-완료--수정-검증-pass-운영-미적용).

**Additional PC checks — 2026-10-10:** clean `8a5714d` passed real Linux release installation, 80-file readback, tamper rejection, manual/automatic rollback, nine-MU-plugin WordPress smoke checks, synthetic DB dump restoration, and a real memory-limited disposable worker OOM (exit 137) substituted at the staging import transport. The OOM preserved the post and pending fence and prohibited reimport; it was not a production WordPress container restart drill. Current production read-only preflight found InnoDB options/postmeta and zero locks/blockers. These results and the Docker/WSL-free laptop handoff are in the final section of [PC handoff](FEATURED_IMAGE_PC_VALIDATION_HANDOFF.md). Deployment authorization, a fresh backup, and install-time production readback remain required.

## Preflight (read-only)

Run from the exact reviewed Git checkout:

```powershell
python scripts/ops/featured_image_lock_preflight.py
```

The script uses fixed read-only `wp eval` queries over `information_schema.TABLES` and lock option records. Output is sanitized: table engines, post IDs, expiration flags, pending flags and autoload modes; **no owner tokens or option JSON**. If the script exits 2, the probe itself failed and no readiness claim may be made. Exit 1 indicates a detected readiness blocker, including a non-InnoDB options table or an import-pending state.

Review output before the deploy. If any lock has `import_pending=true`, **pause deployment** and investigate; never clear the option to make preflight green. A record may remain intentionally pending even when its lease TTL is expired. Image attachment SHA, post CAS, media ownership, remote process liveness, and specific original token must all be investigated together.

## Normal lock state machine

1. Acquire: a fresh token is created; atomic `INSERT IGNORE` against the unique option name grants first ownership only when exactly one row is inserted, with autoload off. Existing state must pass strict token/expiry/pending/phase validation. An **expired, nonpending** valid lock may be replaced only within a transaction with `SELECT ... FOR UPDATE` and an exact old-value compare; malformed state is preserved and rejected.
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

## 2026-10-09 PC validation follow-up

- Host: `DubuDesktop`, Windows Python 3.12.10. Clean `main` fast-forwarded from `f9b19d5` to `bd1dfd5260192c9eab26554d8c205209d2c32dc5`; local HEAD and `origin/main` matched at validation time.
- Read `AGENTS.md`, root/scripts README, `OPERATIONS.md`, this runbook, the validation router/runner, and `.github/workflows/test.yml`. The pulled shared runtime/transport/policy changes selected `full-regression` through `scripts/run_validation.py` using the actual pulled file list.
- Validation target tests: 30 passed. Changed runtime/image/publish/SSH/growth/backup target tests: 236 passed. Full Python suite ran once: **1,142 tests, 1,141 passed, 1 skipped, 0 failures, 0 errors**. A focused follow-up identified the skip as `CollectorTests.test_reject_link_targets`: `symlinks unavailable` in this Windows session.
- Installed repository-pinned dependencies into the existing local `.venv`; the only dependency changed was `cryptography` 50.0.1 → 50.0.2. `pip check`, strict UTF-8 checks, tracked-secret scan, backup/restore Bash syntax, and Compose static configuration with placeholder credentials passed. Compose validation used `--quiet` and did not start containers.
- No system PHP was available. Ubuntu 24.04 PHP CLI/common packages were downloaded and extracted under the ignored task workspace, without privileged installation. The local WSL PHP 8.3 runtime passed `wordpress/tests/run.php` syntax and standalone contract checks. This is not a live WordPress/browser test.
- Direct SSH production **read-only** image-lock preflight passed: `wp_options` and `wp_postmeta` were InnoDB, lock count was 0, and blockers were empty. This observation does not establish which editorial revision is deployed or prove concurrent-import behavior.
- Evidence: ignored `scratch/tasks/pc-validation-2026-10-09/`, including `full-validation.json`, target/full logs, `wordpress-tests.log`, `skip-check.log`, dependency logs, and `lock-preflight.log`.
- **Still unverified:** disposable WordPress/MariaDB multi-connection acceptance and lost-response/import-reconciliation scenarios listed above. The local Docker Linux engine was not running. No staging site, production media/post mutation, deployment, cron change, or lock recovery was performed. These PC checks alone are not a deployment GO decision.

### Follow-up: Docker recovery and disposable DB acceptance — NO-GO

The user requested Docker recovery and an attempt at the remaining tests. Docker Desktop initially failed on inaccessible stale AF_UNIX runtime files under `%LOCALAPPDATA%/Docker/run` and `%LOCALAPPDATA%/docker-secrets-engine`. A bulk runtime-file deletion command was rejected by automatic approval policy. Instead, Docker processes were stopped and the two socket directories were preserved under dated `*.pc-validation-backup-20261009*` names before fresh directories were created. Neither factory reset nor data-disk/image/volume deletion was used. Docker Engine **29.7.2** subsequently responded normally.

The disposable Compose project was `bloguito-pc-validation-20261009`, using the repository's pinned WordPress **7.1.2** and MariaDB images, checksum-verified WP-CLI 2.12.0, an internal-only network, no published ports, and no production mounts or credentials. Its site URL was `http://bloguito-validation.invalid`. A pretest DB dump was saved privately in the ignored task workspace. Both options/postmeta tables were InnoDB. The test transport allowlisted only the exact disposable container IDs; production SSH/post/option commands were not used.

**Result: 15 main acceptance groups completed, 12 passed and 3 failed. The 3 failed groups represent two code defects:**

1. **First-acquire race:** independent WP-CLI processes both returned `acquired` for the same new lock in **3 of 6** natural simultaneous rounds. A separate synchronized test at WordPress's `add_option` pre-insert hook also returned `acquired/acquired`. Inspection of the actual installed WordPress `wp-includes/option.php` showed that `add_option()` uses `INSERT ... ON DUPLICATE KEY UPDATE` and can overwrite the existing option after both callers passed the earlier existence check. Therefore the current `FEATURED_IMAGE_LOCK_SCRIPT` cannot treat `add_option()` success as exclusive first ownership. Later owner checks do not make this first-acquire result correct. Exclusive non-overwriting creation and concurrent acceptance must pass before GO.
2. **Malformed existing lock:** seeding an invalid JSON lock and attempting acquisition returned `acquired` with `stale_replaced=true`. The script treats an invalid decoded state as expired/nonpending, contradicting this runbook's fail-closed incident handling. Malformed state must require explicit investigation rather than automatic replacement.

Passed groups covered active-lease contention, wrong-owner mark/release rejection, premature completion rejection, expired nonpending takeover, expired pending fence preservation, exactly-once marking, same-owner resume, normal actual media import, malformed import stdout recovery, lost-response injection after commit, zero/one/multiple SHA matches, timeout and PHP `memory_limit` allocation failure, exact body/thumbnail/ALT CAS, cleanup receipts, and post-field preservation. The synthetic PNG was only a disposable test fixture, not a generated editorial cover. There were no application runtime source changes, so the previously completed full Python suite was not rerun.

A separate **actual loopback SSH disconnection** test also passed its safety/recovery assertions: a temporary Paramiko SSH server executed the real staging import, waited for that process to exit, then closed the SSH connection without its response. Windows native OpenSSH returned **4294967295**, rather than 255. Consequently the current 255-specific automatic SHA-reconciliation branch was not reached; nevertheless the import fence remained pending, no automatic second import occurred, and independently confirmed process termination plus the original token allowed reconciliation/readback with exactly one attachment. This test used a loopback SSH fixture, not the production OpenSSH service/network. Container OOM and production network/resource behavior remain outside these checks; the memory test was an actual PHP allocation failure with an 8 MB limit.

Detailed evidence: `scratch/tasks/pc-validation-2026-10-09/staging-acceptance.json`, `staging-acceptance.log`, `staging_acceptance.py`, `staging-before.sql`, and `ssh-disconnect-acceptance.json`/`.log`/`ssh_disconnect_acceptance.py`. Failure receipts and fixture dependencies remain ignored and private. The staging containers were stopped after the tests; their volumes were preserved for diagnosis. Docker Desktop was left running in its recovered state. **This revision remains NO-GO for the image-lock acceptance criteria until the two defects are fixed and the relevant DB tests rerun.** No production deployment, cron change, media/post mutation, or production lock recovery was performed.

### Repeat verification and handoff

At the user's request, the two failed acceptance conditions were retried against new synthetic drafts in the same isolated staging project, without changing application source. Both synchronized first-acquire rounds again returned `acquired/acquired`; the malformed-lock case again returned `acquired`, `stale_replaced=true`. `blockers-recheck.json` records **execution_completed=true, acceptance_passed=false** and the diagnostic command exited 1. This is a completed test with a failed acceptance result, not an incomplete Docker/environment setup. Containers were stopped again after the retry. Local evidence remains in `scratch/tasks/pc-validation-2026-10-09/blockers-recheck.json`, `blockers-recheck.log`, and `recheck_blockers.py`. The Git-tracked, self-contained repair handoff is [FEATURED_IMAGE_PC_VALIDATION_HANDOFF.md](FEATURED_IMAGE_PC_VALIDATION_HANDOFF.md), so another device can read it after pull without copying private scratch artifacts. The next step is code correction and rerunning acceptance, not repeating unchanged tests until a favorable race happens.

## 2026-10-09 actual release comparison and predeployment boundary

- 2026-10-09 13:59 KST SSH observation: the operating `data/editorial-release.json` revision is `b9de4709fff354f7449d6f275b36ea17fdec5b7c`. All **80/80** installed managed file SHA-256 hashes match the operating release manifest, with no missing file. This verifies the installed release's internal integrity, not parity with local HEAD.
- At investigation start local HEAD was `bd1dfd5`; during investigation a separate docs-only commit `720d7a1` advanced local `main`. In both commits the updated local `main.py` handles `held_image_generation_unavailable`, `designer.py` defines `ScheduledImageGenerationUnavailable`, and `featured_image.py` defines `recover_imported_featured_image_outcome`; the installed three files contain none of these. Their AST hashes and LF-normalized hashes also differ, while operating bytes match Git blob `b9de470`. This is a **real code-version difference**, not CRLF or archive packaging. `config.py`, `growth_analysis.py` and `growth_planner.py` match exactly.
- The operating `data/search_briefs.json` differs from the Git blob and is intentionally excluded from release inventory. Release builder packages reviewed policy/runtime, `renderer_provenance.json` and `reviewed_content_provenance.json`, but excludes private `draft_posts.json`, `published_posts.json`, `search_briefs.json`, analytics/growth runtime, `.env` and task state. Installer preserves these excluded files; it **does replace the two tracked provenance registries**, so their validator and digest parity require preflight. Local reviewed state is the editorial source of truth and must not be replaced by older remote copies.
- Read-only `python scripts/ops/featured_image_lock_preflight.py` at the observation date returned `wp_options=InnoDB`, `wp_postmeta=InnoDB`, **0 image locks**, `blockers=[]` (exit 0). Re-run immediately before an authorized deployment; a later pending lock blocks rollout even if expired.
- **Required before GO:** (1) freeze and identify the exact clean Git target revision, package the full current HEAD using `build_editorial_release.py` into a fresh directory and verify schema/inventory/hash/retired list; (2) run image-generation hold, failed import/SSH 255 reconciliation, post CAS, image lock and publication-gate targeted tests followed by the required common-code regression; (3) verify a completely isolated WordPress/MariaDB concurrency/fault rehearsal with synthetic posts and no production URL/side effects; (4) verify latest full v3 backup covers DB/uploads/MU plugins/config, has a recoverable restore path, and preserve the existing backup and scheduler schedule; (5) check production pre-hashes, externalized config, `search_briefs.json`, reviewed state and both provenance registries, plus exact plugin compatibility and image-lock preflight; (6) only in a separately authorized deployment, install and read back actual hashes, CLI/provenance validation and scheduler status. The editorial installer does not deploy WordPress MU plugins, so plugin compatibility/rollback must be covered separately if plugin files change.
- **Stop/rollback criteria:** any manifest/target mismatch, inline credential config, unexpected module, registry validation failure, staging fault/concurrency failure, missing verified backup or pending image import prevents GO. After installation, failed CLI/renderer/provenance/readback requires restoring the installer's per-file backup manifest; this does **not** reverse WordPress DB, media, options or task state. Never roll back to a lock-unaware runtime while a media import could remain in flight; reconcile pending import liveness and per-post receipts first, then choose verified full-backup recovery or carefully reviewed forward recovery for any data-side mutation.

No production deploy, cron/service change, image import or WordPress mutation was performed during this audit. Nonsecret read-only diagnostic evidence is in ignored `scratch/tasks/bloguito-readonly-audit-20261009/`.

## 2026-10-10 PC acceptance of laptop lock fix

The clean candidate `43bd95c0d7a59482da36acdeae88fe54542cbcdd` was tested in a dedicated PC worktree against the retained internal-only staging project and synthetic drafts. Existing credentials/volumes were reused, a new private pretest DB dump was taken, and the old failure evidence was preserved. Docker Engine 29.7.2 was recovered from stale runtime sockets without a factory reset or volume deletion.

**All 15 DB/pipeline groups passed.** Six natural simultaneous acquisitions and the query-filter barrier at the actual INSERT each produced exactly one successful owner. Eight invalid-state variants across all four lock operations (32 combinations) returned `invalid_lock_state` and preserved the exact stored option bytes. Active/stale/pending ownership rules, exactly-once import marking, normal media import, malformed response, lost-response injection, zero/one/multiple SHA matches, timeout, PHP allocation failure, owner reconciliation and body/thumbnail/ALT CAS/readback passed. A separate actual loopback SSH-disconnect test also preserved the fence, performed one import only, and resumed under the original owner after independent process-exit confirmation. Windows native OpenSSH still returned 4294967295, so its 255-specific automatic SHA lookup was not reached; safety preservation and automatic recovery coverage are distinct.

PC targeted Python tests: 26 PASS. Full Python suite ran once: 1,143 tests, 1,142 PASS + 1 SKIP (`symlinks unavailable`), 0 failures/errors. PHP standalone syntax/contracts, encoding, tracked-secret scan and dependency checks passed. No application source changed during this PC validation. Private raw evidence is retained under ignored `scratch/tasks/pc-validation-2026-10-10/`; the detailed cross-device-readable summary is in the tracked PC handoff. Staging containers are stopped after testing, with volumes preserved. No production post/media/options/cron or deployment was changed. The two prior PC acceptance blockers are resolved for this candidate; production deployment still requires its own release/backup/provenance/plugin/lock preflight and authorization.
