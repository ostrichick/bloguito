#!/bin/bash
set -euo pipefail
umask 077 # database, uploads and credentials in configs must never be world-readable

# Configurable paths with defaults
BACKUP_DIR="${BACKUP_DIR:-/home/ubuntu/backups}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
WORDPRESS_DIR="${WORDPRESS_DIR:-/home/ubuntu/wordpress}"
AGENT_DIR="${AGENT_DIR:-/home/ubuntu/agent-publisher}"
CONTAINER_DB="${CONTAINER_DB:-wordpress_db}"
CONTAINER_APP="${CONTAINER_APP:-wordpress_app}"
FINAL_ARCHIVE="${BACKUP_DIR}/bloguito_backup_${TIMESTAMP}.tar.gz"

mkdir -p "$BACKUP_DIR"

echo "=================================================="
echo "[BACKUP] Bloguito Unified Backup Started at: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=================================================="

# 1. Resolve DB credentials
# Priority: 1) $MYSQL_ROOT_PASSWORD if already set, 2) $WORDPRESS_DIR/.env if exists
if [ -f "${WORDPRESS_DIR}/.env" ]; then
    # shellcheck disable=SC1090
    source "${WORDPRESS_DIR}/.env"
fi

# Determine Docker command (use direct docker if available, fallback to sudo docker on Linux)
DOCKER_CMD="docker"
if ! $DOCKER_CMD ps >/dev/null 2>&1; then
    if [ "$(uname -s)" = "Linux" ] && [ "$EUID" -ne 0 ] && command -v sudo >/dev/null 2>&1; then
        DOCKER_CMD="sudo docker"
    fi
fi

if [ -z "${MYSQL_ROOT_PASSWORD:-}" ]; then
    if command -v docker >/dev/null 2>&1; then
        CONTAINER_ENV_PASS=$($DOCKER_CMD inspect --format '{{range .Config.Env}}{{println .}}{{end}}' "$CONTAINER_DB" 2>/dev/null | grep '^MYSQL_ROOT_PASSWORD=' | cut -d= -f2- || true)
        if [ -n "$CONTAINER_ENV_PASS" ]; then
            MYSQL_ROOT_PASSWORD="$CONTAINER_ENV_PASS"
        fi
    fi
fi

: "${MYSQL_ROOT_PASSWORD:?ERROR: MYSQL_ROOT_PASSWORD could not be resolved from environment, ${WORDPRESS_DIR}/.env, or ${CONTAINER_DB}}"

# 2. Create isolated staging directory
STAGING_DIR=$(mktemp -d "${BACKUP_DIR}/staging_${TIMESTAMP}_XXXXXX")
cleanup() {
    rm -rf "$STAGING_DIR"
}
trap cleanup EXIT

echo "[BACKUP] 📂 Staging directory: $STAGING_DIR"

# Component A: MariaDB Database Dump
echo "[BACKUP] 🗄️ (1/3) Dumping MariaDB database..."
DB_ARCHIVE="${STAGING_DIR}/db.sql.gz"
$DOCKER_CMD exec "$CONTAINER_DB" mariadb-dump -u root -p"$MYSQL_ROOT_PASSWORD" --single-transaction --quick wordpress | gzip -9 > "$DB_ARCHIVE"
if [ ! -s "$DB_ARCHIVE" ]; then
    echo "[BACKUP] ❌ Database dump failed or empty!"
    exit 1
fi
DB_SIZE=$(wc -c < "$DB_ARCHIVE")
echo "[BACKUP]   ✅ DB dump completed ($DB_SIZE bytes)"

# Component B: WordPress Media Uploads
echo "[BACKUP] 🖼️ (2/3) Archiving WordPress media uploads (wp-content/uploads)..."
UPLOADS_ARCHIVE="${STAGING_DIR}/uploads.tar.gz"
$DOCKER_CMD exec "$CONTAINER_APP" tar -czf - -C /var/www/html/wp-content uploads > "$UPLOADS_ARCHIVE" 2>/dev/null || {
    echo "[BACKUP] ERROR: Media archive failed; refusing to create an incomplete backup."
    exit 1
}
if [ ! -s "$UPLOADS_ARCHIVE" ]; then
    echo "[BACKUP] ❌ Media uploads archive failed or empty!"
    exit 1
fi
UPLOADS_SIZE=$(wc -c < "$UPLOADS_ARCHIVE")
echo "[BACKUP]   ✅ Uploads archive completed ($UPLOADS_SIZE bytes)"

# Component C: Agent Configurations and Runtime Data
echo "[BACKUP] ⚙️ (3/3) Archiving agent configurations and runtime data..."
CONFIGS_ARCHIVE="${STAGING_DIR}/configs.tar.gz"
CONFIG_STAGING="${STAGING_DIR}/configs_staging"
mkdir -p "${CONFIG_STAGING}/agent-publisher" "${CONFIG_STAGING}/wordpress"

[ -f "${AGENT_DIR}/config.py" ] && cp "${AGENT_DIR}/config.py" "${CONFIG_STAGING}/agent-publisher/"
[ -f "${AGENT_DIR}/.env" ] && cp "${AGENT_DIR}/.env" "${CONFIG_STAGING}/agent-publisher/"
if [ -d "${AGENT_DIR}/data" ]; then
    mkdir -p "${CONFIG_STAGING}/agent-publisher/data"
    cp -r "${AGENT_DIR}/data/"*.json "${CONFIG_STAGING}/agent-publisher/data/" 2>/dev/null || true
fi

[ -f "${WORDPRESS_DIR}/docker-compose.yml" ] && cp "${WORDPRESS_DIR}/docker-compose.yml" "${CONFIG_STAGING}/wordpress/"
[ -f "${WORDPRESS_DIR}/mysql_custom.cnf" ] && cp "${WORDPRESS_DIR}/mysql_custom.cnf" "${CONFIG_STAGING}/wordpress/"
[ -f "${WORDPRESS_DIR}/uploads.ini" ] && cp "${WORDPRESS_DIR}/uploads.ini" "${CONFIG_STAGING}/wordpress/"
[ -f "${WORDPRESS_DIR}/.env" ] && cp "${WORDPRESS_DIR}/.env" "${CONFIG_STAGING}/wordpress/"

tar -czf "$CONFIGS_ARCHIVE" -C "$STAGING_DIR" configs_staging
rm -rf "$CONFIG_STAGING"
CONFIGS_SIZE=$(wc -c < "$CONFIGS_ARCHIVE")
echo "[BACKUP]   ✅ Configurations archive completed ($CONFIGS_SIZE bytes)"

# Component D: Generate manifest.json with SHA256 checksums
echo "[BACKUP] 📜 Generating manifest.json..."
MANIFEST_FILE="${STAGING_DIR}/manifest.json"

sha256_file() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1" | awk '{print $1}'
    elif command -v shasum >/dev/null 2>&1; then
        shasum -a 256 "$1" | awk '{print $1}'
    else
        openssl dgst -sha256 "$1" | awk '{print $NF}'
    fi
}

DB_SHA=$(sha256_file "$DB_ARCHIVE")
UPLOADS_SHA=$(sha256_file "$UPLOADS_ARCHIVE")
CONFIGS_SHA=$(sha256_file "$CONFIGS_ARCHIVE")

cat <<EOF > "$MANIFEST_FILE"
{
  "version": "2.0",
  "created_at": "$(date -u +'%Y-%m-%dT%H:%M:%SZ')",
  "timestamp": "${TIMESTAMP}",
  "components": {
    "db": {
      "file": "db.sql.gz",
      "size_bytes": ${DB_SIZE},
      "sha256": "${DB_SHA}"
    },
    "uploads": {
      "file": "uploads.tar.gz",
      "size_bytes": ${UPLOADS_SIZE},
      "sha256": "${UPLOADS_SHA}"
    },
    "configs": {
      "file": "configs.tar.gz",
      "size_bytes": ${CONFIGS_SIZE},
      "sha256": "${CONFIGS_SHA}"
    }
  }
}
EOF
echo "[BACKUP]   ✅ manifest.json created"

# 3. Package into final unified snapshot archive
echo "[BACKUP] 📦 Bundling into final snapshot: $FINAL_ARCHIVE..."
tar -czf "$FINAL_ARCHIVE" -C "$STAGING_DIR" db.sql.gz uploads.tar.gz configs.tar.gz manifest.json
chmod 600 "$FINAL_ARCHIVE"

FINAL_SIZE=$(ls -lh "$FINAL_ARCHIVE" | awk '{print $5}')
echo "[BACKUP] ✅ Backup completed successfully: $FINAL_ARCHIVE ($FINAL_SIZE)"

# 4. Purge snapshots older than 7 days
DELETED_SNAPS=$(find "$BACKUP_DIR" -type f -name "bloguito_backup_*.tar.gz" -mtime +7 -print -delete 2>/dev/null | wc -l || echo 0)
DELETED_LEGACY=$(find "$BACKUP_DIR" -type f -name "db_backup_*.sql.gz" -mtime +7 -print -delete 2>/dev/null | wc -l || echo 0)
TOTAL_PURGED=$((DELETED_SNAPS + DELETED_LEGACY))
echo "[BACKUP] 🧹 Cleaned up $TOTAL_PURGED old backup archive(s) (>7 days)"
echo "[BACKUP] Daily Backup Finished at: $(date '+%Y-%m-%d %H:%M:%S')"