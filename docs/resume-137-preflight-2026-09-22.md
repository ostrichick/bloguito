# #137 fresh read-only preflight — 2026-09-22 15:50 KST

## Result: reviewed body already applied; do not run another update

At `2026-09-22T15:50:31+09:00`, the fresh read-only SSH preflight returned `ready`, `reasons=[]`, and `source_hashes_match_live=true`. **The live WordPress DB's stored `post_content` equals the reviewed renderer's HTML byte-for-byte as a decoded string**, not merely by SHA comparison. Their SHA256 is `19654865151823398b1dcd3a7661a5e1b3016ee5964048b76494c114d96da6df`. The resulting comparison contains 43 old/current and 43 proposed structured blocks with **zero diff lines**. The previous DB stored-body SHA at 13:00 and 15:26 was `4ad2b39e55b9b483bd7e5b1c1c70613d5965df7ec88ed74194923925fb0dad7b`. The post's current `post_modified` is `2026-09-22 15:29:30` (formerly `2026-09-21 09:01:59`). These are direct observations of an intervening live update; this audit did not perform it and cannot independently attribute the actor.

**Fresh exact package:** `tmp/legacy_audit_20260922/pilot137/worker1-fresh-preflight-20260922-155016/`:

- `approval-manifest.json`: capture time, source and policy validation, all relevant hashes, stored WordPress metadata and zero-diff counts.
- `post-original.PRIVATE.json`: full 15:50 live backup, SHA256 `32d5eb335b850b90acb4ad4d5022f26bcc50b7ab11137947b811e776e573040d` (independently recomputed and matched); keep Git-ignored and private. **This is a post-update snapshot, not a substitute for the pre-update rollback original.**
- `proposed-reviewed.html`: exact reviewed renderer HTML; `compare-preview.html` and `content-diff.txt`: static comparison, showing zero differences with current stored HTML.
- Reviewed input: `tmp/legacy_audit_20260922/pilot137/bundle.reviewed.json`. Its AI review at `2026-09-22T12:51:05.903138+09:00` has all six editorial checks `true`, `issues=[]`; still within the configured 24-hour review limit at preflight. All three official National Tax Service sources were fetched again by the preflight and their URL-to-SHA256 mapping matched the reviewed sources. `validation_report.status=ready`, no reasons/details. Source content and review are only confirmed as of this capture, not indefinitely.

## Complete inventory and live metadata

The SSH `wp post list` read queried **all five normal states** `publish,draft,pending,future,private`, `posts_per_page=-1` and fields `ID,post_title,post_status,post_content`. A separate count of that returned JSON found **40 unique IDs: 30 publish, 10 draft, 0 pending, 0 future, 0 private**; target ID 137 appears exactly once and remains `publish`. The preflight additionally fetched `wp post get 137 --format=json`, required stored body/title agreement with the list and excluded #137 from duplicate checks.

Comparing the old original in `pilot137/approval-live-20260922-1524/post-original.PRIVATE.json` against the 15:50 full WordPress post: ID, title, slug, published date (`2026-09-17 16:25:57`), published status, parent, author, password, menu order, comments/ping state and GUID are unchanged. The formerly empty excerpt is populated and **exactly equals the shared renderer's `excerpt_from_lead(bundle.plan.lead)` output** (135 characters). Public REST `wp-json/wp/v2/posts/137?context=view` also returned ID 137, `publish`, modified `2026-09-22T15:29:30`, and preserved title, slug, publication date, categories, tags, featured media, author, sticky setting and format relative to `pilot137/post137-public-rest.json`. The public REST rendered HTML is not the DB stored-body string and must not be used for the compare-and-swap SHA.

Read-only revision inventory (`wp post list --post_type=revision --post_parent=137`) showed **six revisions**. Latest revision **ID 366** has date `2026-09-22 15:29:30`, parent 137; preceding revision ID 326 is dated `2026-09-21 09:01:59`. Revision presence is evidence of a saved revision but is not a verified restore drill.

## Operational implication and restoration boundary

**No `update-existing` command is presently needed or appropriate for #137:** the reviewed body and lead excerpt are already saved. In particular, do not pass the historic pre-update SHA `4ad2b39e...` to a new update; the updater correctly rejects a changed original. Do not invoke a second live write merely to make the progress plan advance. Existing `scripts/update_existing_via_ssh.py` runs the regular local `editorial_updater.update_existing_public_post()` with a restricted SSH transport and fresh full inventory/source/review checks. It is the valid Windows-to-SSH adapter for a *different post that still needs updating*, subject to that post's exact reviewed bundle, current stored SHA and established authorization; direct WP-CLI editing would bypass the shared editorial gate. A canonical command pattern is:

```powershell
./agent-publisher/.venv/Scripts/python.exe -B scripts/update_existing_via_ssh.py <reviewed-bundle.json> --post-id <specific-id> --expected-content-sha256 <fresh-DB-stored-content-SHA256> --ssh-host bloguito --confirm-update
```

The independent **pre-update** #137 original and its evidence remain in `pilot137/approval-live-20260922-1524/post-original.PRIVATE.json` (also `approval-20260922-1/post-original.PRIVATE.json`), with documented old whole-file SHA256 `6e01fb2f0f2a965a7487a8cbd60b92c1be3e66dc8bc95bd5ad7af034f5e5cfb6`. Before a rollback, check the then-current live body still equals the applied reviewed HTML and that no other edits intervened. Restore the original content and excerpt only through a separately reviewed operational procedure, then verify stable metadata; no rollback or WordPress write occurred in this worker audit.

**Remaining #137 work for the prime:** verify the live theme at desktop, 360/390px and 200% zoom, tables/TOC/CTA/keyboard and screenshot evidence. `preflight_status=ready` proves the content contract and current stored-body match, not real-device layout or a complete recovery test. A preflight generator always labels `approval_status=prepared_not_authorized`, including when it observes already updated content; that field is not proof of whether the earlier live change had user approval.
