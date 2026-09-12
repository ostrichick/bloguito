#!/bin/bash
set -euo pipefail

BACKUP_DIR="/home/ubuntu/backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
TARGET_ARCHIVE="${BACKUP_DIR}/db_backup_${TIMESTAMP}.sql.gz"

mkdir -p "$BACKUP_DIR"

echo "=================================================="
echo "[BACKUP] Daily DB Backup Started at: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=================================================="

# 1. Stream dump from MariaDB container directly through gzip
WORDPRESS_ENV_FILE="/home/ubuntu/wordpress/.env"
if [ ! -f "$WORDPRESS_ENV_FILE" ]; then
    echo "[BACKUP] ❌ Missing required environment file: $WORDPRESS_ENV_FILE"
    exit 1
fi

# shellcheck disable=SC1090
source "$WORDPRESS_ENV_FILE"
: "${MYSQL_ROOT_PASSWORD:?MYSQL_ROOT_PASSWORD is required in $WORDPRESS_ENV_FILE}"

sudo docker exec wordpress_db mariadb-dump -u root -p"$MYSQL_ROOT_PASSWORD" --single-transaction --quick wordpress | gzip > "$TARGET_ARCHIVE"

# 2. Check backup file size
if [ -s "$TARGET_ARCHIVE" ]; then
    SIZE=$(ls -lh "$TARGET_ARCHIVE" | awk '{print $5}')
    echo "[BACKUP] ✅ Backup successful: $TARGET_ARCHIVE ($SIZE)"
else
    echo "[BACKUP] ❌ Backup failed or empty!"
    exit 1
fi

# 3. Purge backups older than 7 days
DELETED=$(find "$BACKUP_DIR" -type f -name "db_backup_*.sql.gz" -mtime +7 -print -delete | wc -l)
echo "[BACKUP] 🧹 Cleaned up $DELETED old backup file(s) (>7 days)"
echo "[BACKUP] Daily DB Backup Finished at: $(date '+%Y-%m-%d %H:%M:%S')"
