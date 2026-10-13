# Bloguito Git integration and unfinished-work handoff — 2026-10-13 KST

## Scope and immutable exclusions

- User authorized integration of historical branches/worktrees and non-content follow-up.
- **Excluded:** WordPress drafts #926, #928, #932, their source bundles, active fact-check/SEO work, and current draft publication. No production WordPress writes were performed.
- Keep the pre-existing `main` edits `docs/INDEX.md`, `docs/POST_CATALOG.md`, `docs/clarity-integration-2026-09-29.md`, and its four untracked docs (especially `docs/post-932-928-926-factcheck-content-seo-plan-2026-10-13.md`). Never reset, stash, or auto-commit them.

## Integration A: workflow baseline

- Starting `main`: `9fd0201d98a7ea29e64a32cdae7e28e252d2faa6`.
- Merge input `feat/bloguito-workflow-integration-20261011`: `3dcb5f4b13c0b8a4efbb730520576d88f4459a75` (52 commits not in prior main).
- Resolved nine merge conflicts while preserving newer image-task authority and PDF raw-page support from main and workflow locking, CAS, provenance, telemetry, browser QA and release safeguards from the input.
- Merge commit `4b4c8ea2f05e2451ab50009ec1f0cc3c7add0fe3`; local main fast-forwarded to it without touching the user documents.
- Full unittest discovery: **1,433 tests, 0 failures/errors, 2 skipped**, on Windows/Python 3.12. Two original test fixture incompatibilities were corrected: missing selection actor and an expired 2026-10-11 synthetic intent approval tested with a pinned historical clock, **without extending production validity**.
- Runtime inventory had 97 entries with digest `5a787314c492dfc7aad16705dcaa49929fd4520e00870b0b34d5450bfa7f68f3`.

## Integration B: image-security scaffolding

- Input `feat/featured-image-r1-r5-20261012`: `c19dc333338d1ac7dc2f04fefd298b40a3d936aa` (four commits not in prior main), integrated on top of the workflow merge in `C:/Projects/Bloguito-image-integration-20261013`.
- Three conflicts: choose fail-closed denial of existing-image self-attestation over the legacy write-capable helper; retain the workflow release-exclusive lock while updating inventory; retain both maintained-script registries.
- Combined runtime inventory: **98 files**, digest `0ecf9d5d50d74c27d9bd36ea693163acedd5fd80d8adf9881c2ba0ad5712ef7c`.
- Full unittest discovery: **1,497 tests, 0 failures/errors, 3 skips**. Native PHP runtime is absent on laptop, so PHP lint and actual WordPress/MariaDB isolation are not certified. Existing-cover tests were changed to assert early denial/no read/no mutation under the updated policy. `scripts/archive/attach_remaining_thumbs.py` remains a pre-existing archived non-runnable file; broad `compileall scripts` can report its historical indentation issue, not a current maintained-runtime defect.
- Actual new host image_gen generator evidence issuer, independent user/reviewer approval issuer and protected signing keys are unavailable. R3 PHP image setter covers **existing attachments only**, not safe new-media import. R4 Docker/PHP absent on this laptop. R5 actual separate-topic WP-verified pilot images: **0/3**.
- **Operational image upload: NO-GO**, and no protected SSH/sudo/WordPress production rollout may be inferred from local tests. Follow `docs/featured-image-pc-handoff-2026-10-13.md` and `docs/featured-image-r4-pc-runbook-2026-10-13.md` on a Docker PC, with isolated disposable WP/MariaDB, before considering deployment.

## Independent historical-branch audit

- 26 historical `feat/bloguito-*` branch worktrees contain no unique implementation absent from workflow-integration (23 identical tip patch IDs; three context/inventory-digest differences).
- `feat/image-r0-quality-20261012` has a patch-equivalent main change, but its retirement remains subject to the safe tool's own dry-run.
- A fresh `scripts/ops/retire_worktree.py` dry-run evaluated 27 workflow-related worktrees: **24 SAFE**, **3 BLOCKED** (`q1-qa`, `s3-draft`, `t1-topic` not considered patch-equivalent by the tool). Do not force-remove blocked worktrees.
- **Execution result:** the SHA-preserving retirement tool successfully retired **26 historical/integration worktrees** in total (22 workflow worktrees plus R0-quality, R1–R5 original and both isolated integration worktrees). All successful retirements created ignored-file receipts and archives beneath main `scratch/tasks/worktree-retirement/`; their corresponding local branches were removed by the reviewed tool. Remote branches were not deleted.
- **Two automatic retirement failures remain**, with source worktrees retained: `Bloguito-q1-full-20261011` hit Windows `WinError 206` copying very long ignored Edge browser profile paths; `Bloguito-real-db-20261011` hit `WinError 5` when renaming its temporary archival directory during its second pre-removal check. Both have partial or staged archive directories present; inspect those with explicit source/hash checks before any retry. No `--force`, recursive cleanup, or archive overwrite to bypass these blockers.
- Additionally preserve the three `q1-qa`/`s3-draft`/`t1-topic` worktrees blocked by conservative patch-equivalence checks and the dirty image-R0 worktree. Both integration worktrees have now been retired after their final commits were incorporated into main.
- Preserve `chore/eldercare-pdf-excerpt-20261011` because it has a unique PDF module and tests; preserve `chore/eldercare-t4-compat-20261011` until the other chat completes #932. Also preserve the dirty `feat/featured-image-r0-20261012` worktree and any concurrent active worktree. Worktree cleanup happens only through the SHA-preserving retirement tool after integration, no `git clean` or force delete.

## Remaining acceptance gates

1. Finish R1/R2 trusted independent source/approval issuer and test signing authority boundaries. Self-authored JSON, test private keys and image-detector scores are not authoritative.
2. Implement R3 new-media import under fixed root-owned command IDs/least privilege, independently validate WordPress capability, SSH forced-command, sudoers and idempotency/CAS receipts.
3. R4 actual Docker PC isolated fixture: positive and adversarial races, transport outages vs exact stale-CAS denial, DB rollback and readback. R5 actual different-topic verified evidence 3/3, only with authenticated origin/approval and authorized non-draft test targets.
4. F1/F2 require live apples-to-apples workload and release cohorts (five comparable successes on each side); no synthetic productivity claim. Q1 native browser-menu 200% and authenticated WP preview need an authorized existing browser tab. Q3 unknown remote create/media ownership remains fail-closed, cannot be guessed from SHA/title.
5. SSH least privilege Stage A/B and separate cron/backup identities remain unproven on production. Actual full new Ubuntu VM boot/ACME/Tailscale/fail2ban/systemd disaster-recovery drill remains unperformed.
6. Before any production deployment, verify exact runtime revision, rollback backup, release/cron/MU compatibility, and absence of concurrent editorial writes. Current production `editorial-release.json` was read-only checked on 2026-10-13 and still reported `906ad0c415478a72059f8067083521d03821580e`; this session did not deploy or modify WordPress.

## Final read-only operational observation (2026-10-13)

- `python scripts/ops/workflow_release_observer.py --ssh-host bloguito --installed-revision 906ad0c415478a72059f8067083521d03821580e`: 9 raw telemetry rows, 6 live successes, only one matching installed-release success, **zero comparable release/workload cohorts**, `performance_claim=unmeasured`. Input SHA-256 `bafdd3d813178aed4e00df49fada70a4d93478882f24e91e9c1a2b9ff86febbe`.
- Production `cron.log` shows 2026-10-13 08:00 KST `SCHEDULER_RUN state=no_action`, `PIPELINE_RESULT status=completed`, zero candidates, zero drafts and zero errors, exit 0; `growth_reason=no_actionable_existing_or_eligible_new_topic`. Read-only cron listing still has 04:00 backup, 07:10 Clarity and 08:00 publisher entries.
- Laptop `test_ssh_least_privilege_proposal.py`: nine offline tests passed; this does not establish real server privilege separation. Original latest production revision and no-production-write/NO-GO assessments are unchanged.

**Do not report code integration or offline tests as operational authorization or completion of the six remaining business acceptance conditions.**
