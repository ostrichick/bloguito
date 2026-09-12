#!/bin/bash
set -e

BACKUP_DIR="/home/ubuntu/backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
TARGET_ARCHIVE="${BACKUP_DIR}/db_backup_${TIMESTAMP}.sql.gz"

mkdir -p "$BACKUP_DIR"

echo "=================================================="
echo "[BACKUP] Daily DB Backup Started at: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=================================================="

# 1. Stream dump from MariaDB container directly through gzip
DB_PASS="${MYSQL_ROOT_PASSWORD:-your_mysql_root_password}"
if [ -f "/home/ubuntu/wordpress/.env" ]; then
    # shellcheck disable=SC1091
    source /home/ubuntu/wordpress/.env
    DB_PASS="${MYSQL_ROOT_PASSWORD:-$DB_PASS}"
fi
sudo docker exec wordpress_db mariadb-dump -u root -p"$DB_PASS" --single-transaction --quick wordpress | gzip > "$TARGET_ARCHIVE"

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
