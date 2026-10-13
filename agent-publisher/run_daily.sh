#!/bin/bash
set -e

APP_DIR="${BLOGUITO_APP_DIR:-/home/ubuntu/agent-publisher}"
LOG_FILE="${BLOGUITO_CRON_LOG_FILE:-$APP_DIR/cron.log}"
MAX_LOG_SIZE=$((5 * 1024 * 1024)) # 5MB

# The shared kernel lock lives in main.py, not here: invoking main.py directly
# or either standalone growth writer must use exactly the same lock.
finish() {
    result=$?
    trap - EXIT
    echo "[CRON] Daily Auto Publisher Finished at: $(date '+%Y-%m-%d %H:%M:%S') exit=$result" >> "$LOG_FILE"
    exit "$result"
}
trap finish EXIT

# Log rotation if exceeds 5MB
if [ -f "$LOG_FILE" ]; then
    FILE_SIZE=$(stat -c%s "$LOG_FILE" 2>/dev/null || echo 0)
    if [ "$FILE_SIZE" -gt "$MAX_LOG_SIZE" ]; then
        mv "$LOG_FILE" "${LOG_FILE}.old"
        echo "$(date '+%Y-%m-%d %H:%M:%S') - Log rotated (exceeded 5MB)" > "$LOG_FILE"
    fi
fi

echo "==================================================" >> "$LOG_FILE"
echo "[CRON] Daily Auto Publisher Started at: $(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG_FILE"
echo "==================================================" >> "$LOG_FILE"

cd "$APP_DIR"
./venv/bin/python main.py --category all --limit 1 >> "$LOG_FILE" 2>&1
