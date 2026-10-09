# Bloguito SSH / sudo least privilege — proposed staged migration

**Status: OFFLINE PROPOSAL, NOT DEPLOYED.** This document and the two scripts in
`scripts/security/` are candidate artifacts. Do not install them as a side effect
of a normal application deployment. Keep the admin `ubuntu` account, existing
`ssh.service`, scheduled tasks, sudo configuration, firewall, and Tailscale
recovery intact until independent credential and rollback verification succeeds.

## Evidence and remaining exposure (2026-10-09)

- `ssh -o BatchMode=yes -o ConnectTimeout=8 bloguito` connected as `ubuntu` on
  `wordpress-blog`; `id -Gn` included `sudo`, `docker`, and `lxd`; `sudo -n true`
  succeeded and `ssh.service` was active. This establishes **host-equivalent
  privilege exposure** when those same credentials are available to automation.
  The observed commands were read-only apart from sudo's `true` no-op.
- `scripts/editorial_cli_via_ssh.py` restricts commands *in local Python* but
  invokes `ssh ... sudo docker exec wordpress_app wp ...`; its paths include
  dynamic `wp eval` PHP code and `docker exec -i wordpress_app sh -c 'cat > ...'`.
  A compromised local process with the same SSH private key can bypass local
  validation by issuing arbitrary SSH commands as the privileged `ubuntu` user.
- `agent-publisher/run_daily.sh` executes the scheduled `main.py` from
  `/home/ubuntu/agent-publisher`. The production scheduler and
  `agent-publisher/backup_daily.sh` rely on access to Docker; the backup script
  uses `sudo docker` if direct Docker access fails and reads protected config.
  Both require a separate migration design. These scripts are unchanged here.
- The current editorial publication policy requires draft by default,
  per-post approval and canonical guarded promotion. This is application
  validation only; `ubuntu` host/Docker privileges are a stronger bypass.

**Security conclusion:** The proposed read-only SSH identity reduces its own
allowed actions, but end-to-end OS privilege separation is **not yet achieved**.
Neither this proposal nor passing its tests is evidence that unattended content
generation and general editorial writes can use the new identity. Do not claim
the production least-privilege gate is cleared while an AI-capable session
still has access to the unrestricted `ubuntu` private key or scheduled publisher
runs with host-equivalent privileges.

## Stage A — dedicated read-only SSH identity (proposed)

The staged files are:

| Repository artifact | Installation path (root-owned; never service-user writable) | Purpose |
| --- | --- | --- |
| `scripts/security/bloguito_ssh_gate.py` | `/usr/local/libexec/bloguito/ssh_gate.py` | OpenSSH forced command parses exactly `wp-read health`, `wp-read inventory`, `wp-read post-get <ID>`, `wp-read post-status <ID>` and invokes fixed `sudo -n` target. |
| `scripts/security/bloguito_wp_readonly.py` | `/usr/local/libexec/bloguito/wp_readonly.py` | Privileged target independently validates short JSON stdin; invokes `/usr/bin/docker exec wordpress_app wp` with a fixed validated read command and no interactive stdin. |
| `scripts/security/sudoers.bloguito-ssh-read.example` | `/etc/sudoers.d/bloguito-ssh-read` | Permits *only* invoking the fixed reader executable with **zero argv**, never arbitrary `sudo docker`. |
| `scripts/security/sshd.bloguito-ssh-read.example` | Reviewed sshd config with this `Match User` block at a valid position | Enforces forced command and disables password, TTY, forwarding and user rc. |

The dedicated `bloguito-ssh-read` Linux account must have no membership in
`sudo`, `docker`, `lxd`, site-data-write groups or login credentials shared with
`ubuntu`. Give it only its own scoped public key. Use a root-owned
`/etc/ssh/authorized_keys/bloguito-ssh-read` and ensure no other
`AuthorizedKeysCommand` or access route can add a broader identity. The account
requires a valid restricted shell for OpenSSH forced-command execution; do not
assume `/usr/sbin/nologin` can execute this forced command. Confirm the key
fingerprint and effective sshd Match rules before adding any account to service.

Place all installed scripts and every parent of those paths under root control,
for example root:root with directories `0755`, executable scripts `0755`,
authorized-key directory root:root `0755` and per-account public-key file
root:root `0600`. Ensure `/usr/bin/python3`, `/usr/bin/sudo`,
`/usr/bin/docker` exist at these precise paths. Never add custom shell aliases,
SSH environment overrides or a service-user-owned executable to `sudoers`.

The privileged reader permits fixed post and inventory reads only. A read
operation can still execute WordPress PHP hooks and return private draft data;
the role is intended for a trusted editorial operator, not anonymous public
access. There are no `eval`, `wp option`, generic WP flags, plugin/theme
management, uploads, file writes, container selection or status mutations.
The caller cannot provide Docker flags or shell syntax. `sudoers` allowing an
exact root-owned program is acceptable only after independent code review and
ownership/permission verification; a root-level implementation flaw would
still be dangerous.

## Stage A independent preflight / recovery requirements

1. From an operator session, verify a *separate* admin SSH connection and
   Tailscale emergency connection, known-good SSH host key and fresh validated
   recoverable backup. Record current `id`, `sshd -T`, `sudo -l`, `crontab -l`,
   scheduled services, current release SHA, active listeners and firewall
   rules. Do not export private keys or environment/secrets into reports.
2. On a disposable Ubuntu host first, copy only the proposed artifacts into
   the expected root-owned paths and configure a fresh read-only account. Run
   `visudo -cf <candidate-sudoers>`, `sshd -t -f <candidate-config>`, and
   `sshd -T -f <candidate-config> -C user=bloguito-ssh-read,host=wordpress-blog,addr=<test-IP>`.
   Test `sudo -n -l -U bloguito-ssh-read` and validate the effective config
   *before* any SSH reload. Avoid sshd config snippets that cause a `Match`
   scope to consume later unrelated global directives; include ordering varies.
3. On that disposable host, verify `ssh -l bloguito-ssh-read ... 'wp-read health'`
   and a test `post-status` succeed with only the designated identity. Verify
   `id`, `sudo -l`, `docker ps`, `wp-read eval`, direct SSH shell, SFTP, SCP,
   port forwarding, malicious quotes/newlines and oversized commands are
   denied. Check that the new account cannot change its key, gate, sudoers,
   reader or Docker socket. Run a negative test where the gate is bypassed and
   sudo is invoked directly with invalid stdin; the privileged reader must
   still reject it.
4. Only after independent review, repeat the account addition on production
   while preserving the working `ubuntu`/Tailscale connections. Test the new
   account in a new SSH connection *before* finalizing a reload. Never restart
   or change the active `ssh.service` / `ssh.socket` mode as part of this
   experiment; use a validated `sshd` reload if required.
5. If any step fails, stop using the new identity; restore the previous
   sshd config and sudoers candidate atomically from a verified root backup,
   revalidate with `sshd -t` before reload, and verify the unaffected admin
   and emergency connections. Retain the service-user account/key for forensic
   review until a separate cleanup is approved. Do not touch the functioning
   admin/cron path during rollback.

## Stage B — editorial writes and scheduler (not implemented)

The existing `editorial_cli_via_ssh.py` protocol **cannot use Stage A**: it
sends arbitrary shell-formatted `sudo docker exec` / `wp eval` strings. Do not
weaken the forced command to allow them. Before moving editorial mutations,
design an authenticated, dedicated server-side API or fixed reviewed command
IDs with independently checked payload schemas, target post ID/status,
expected CAS tokens, immutable known PHP routines, publication-gate policies,
and post-write readback. Reject arbitrary PHP code and host shell execution.
Use per-purpose WordPress capabilities to separate read/draft/write/publish;
keep per-post human approval for publication. The account must not join
`docker`/`lxd` or have broad sudo access. If Docker control is unavoidable,
put all privilege behind a root-owned narrowly validated helper and verify
whether a container compromise can still escape its intended boundary.

Migrate scheduled `run_daily.sh` separately to a dedicated service identity
with its own writable runtime state, paths and tokens. Code currently assumes
`/home/ubuntu/agent-publisher` and direct `sudo docker` and would require
changes before such a move. Backup is a distinct highly privileged operation:
its access to DB dump, uploads and secrets should be managed by an isolated
root-controlled service/backup role, not shared with the editorial SSH key.
Verify full cron parity, readback, fail-closed behavior, backup restoration,
scheduled 04:00/08:00 execution and rollback before swapping service identities.
No existing `ubuntu` sudo, group membership, SSH key or cron may be revoked
before these independently proved cutovers, and the AI/operator must stop
using the old privileged key in ordinary workflows before claiming isolation.

## Tests and security gates

Offline regression: `python -m unittest discover -s agent-publisher/tests -p test_ssh_least_privilege_proposal.py -v`.
Run `python -m py_compile scripts/security/bloguito_ssh_gate.py scripts/security/bloguito_wp_readonly.py`,
`git diff --check`, and static configuration validation on an appropriate
disposable Ubuntu system. The tests cannot prove real sshd/sudoers integration,
Docker isolation, privilege revocation, runtime API parity or unattended
production behavior. Full OS-level isolation remains a deployment risk to be
accepted explicitly by the owner or a rollout blocker until Stage B passes.
