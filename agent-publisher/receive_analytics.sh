#!/usr/bin/env bash
# Forced command for a dedicated restricted SSH public key. No arbitrary SSH.
set -euo pipefail
umask 077
if [[ -n "${SSH_ORIGINAL_COMMAND:-}" ]]; then
  echo 'analytics_ingest_failed:remote_commands_disabled' >&2
  exit 1
fi
exec /home/ubuntu/agent-publisher/venv/bin/python /home/ubuntu/agent-publisher/analytics_receiver.py
