#!/usr/bin/env bash
set -euo pipefail

LOCAL_BACKUP_DIR="/mnt/c/Users/gip4k/BloguitoBackups"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SYNC_SCRIPT="${SCRIPT_DIR}/sync_backups_tailscale.py"
LOG_FILE="${LOCAL_BACKUP_DIR}/sync.log"

mkdir -p "$LOCAL_BACKUP_DIR"

log() {
    printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$1" >> "$LOG_FILE"
}

log "Scheduled Tailscale backup sync started."

ready=0
for _ in $(seq 1 30); do
    if tailscale status 2>/dev/null | grep -q 'bloguito-server'; then
        ready=1
        break
    fi
    sleep 2
done

if [ "$ready" -ne 1 ]; then
    log "Scheduled Tailscale backup sync failed: Tailscale did not become ready."
    exit 1
fi

if BLOGUITO_BACKUP_LOCAL_DIR="$LOCAL_BACKUP_DIR" python3 "$SYNC_SCRIPT" >> "$LOG_FILE" 2>&1; then
    find "$LOCAL_BACKUP_DIR" -maxdepth 1 -type f -name 'bloguito_backup_*.tar.gz' -mtime +30 -delete
    log "Scheduled Tailscale backup sync completed successfully."
else
    rc=$?
    log "Scheduled Tailscale backup sync failed with exit code $rc."
    exit "$rc"
fi
