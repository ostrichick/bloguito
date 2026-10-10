# 2026-10-10 Git worktree retirement and lifecycle policy

## Completed cleanup

- Baseline: `main` at `b9a8b33`, up to date with `origin/main`; all eleven registered worktrees had no tracked/untracked working changes at inventory time.
- Removed **seven** disposable worktrees and their corresponding local branches, after confirming each commit was reachable from `main` or its whole unmerged patch set was already equivalent to `main`: `feat/featured-image-pipeline-20261009`, `integrate/bloguito-wip-20261009`, `fix/featured-image-lock-concurrency-20261009`, `fix/manual-publish-permissions-20261009`, `integrate/bloguito-predeploy-20261009`, `feat/lock-recovery-predeploy-20261009`, `feat/scheduler-image-held-20261009`.
- Archived and SHA-verified **732 ignored files (13,176,162 bytes)** before removal, including prior local test receipts and staged release packages. The receipts and copied files are kept only in Git-ignored `scratch/tasks/worktree-retirement/<worktree name>/`; the contents are not appropriate for Git publication and may include private temporary runtime artifacts.
- Removed old local `backup/laptop-before-pc-pull-20261009` after `git range-diff` confirmed its two documentation changes were rebased as `1e24aae` and `6e66c31` (the second resolved a historical handoff conflict while preserving the audit content).
- Removed three remote branches already ancestrally incorporated into `main`: `codex/project-efficiency`, `feat/bloguito-predeploy-20261009`, `fix/featured-image-lock-concurrency-20261009`. No unmerged remote branches or remote `main` were removed.

## Deliberately retained

- Four registered worktrees: `main`, `fix/growth-notification-observability-20261009`, `feat/security-predeploy-20261009`, and `chore/pc-release-validation-20261009`. The three feature worktrees contain unintegrated code, security planning, or PC validation material; they are **not** complete/automatic-retirement candidates.
- Local `release/bloguito-integrated-20261009`, pending review alongside the growth notification integration. Remote `chore/pc-release-validation-20261009` and `feat/security-predeploy-20261009` remain.
- Two historical Git stashes are retained unchanged pending a separate provenance/content assessment.
- The unrelated production editorial release is unchanged by this repository cleanup.

## New default practice

- Added `scripts/ops/retire_worktree.py` with safe dry-run default and explicit `--apply`; it checks registered sibling worktree, non-main branch, unlocked status, clean Git state, full ancestry or patch-equivalence, and archives + verifies every ignored file before Git worktree/local-branch removal. It does **not** delete remote branches or stashes.
- Updated `AGENTS.md` and `scripts/README.md`: after the **last worktree-dependent work** (including tests, integration, approved deployment, readback), the responsible agent must run the dry-run and, if safe, `--apply` before finishing/reporting. Unintegrated work, pending approval or future validation keeps its worktree; blocked cleanup is reported, never bypassed by forced recursive deletion.
- Dedicated tests `test_worktree_retirement.py` confirmed a completed worktree is archived/removed, active dirty/unmerged work is blocked, and `main` is protected. Windows full Python suite later reported **1,146 tests PASS** after an earlier run encountered a transient unrelated HTTP loopback `WinError 10053`; focused HTTP test also passed when repeated.
