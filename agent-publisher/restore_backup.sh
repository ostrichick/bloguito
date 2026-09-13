#!/bin/bash
set -euo pipefail

ARCHIVE_PATH="${1:-}"
AUTO_CONFIRM="${2:-}"

if [ -z "$ARCHIVE_PATH" ] || [ ! -f "$ARCHIVE_PATH" ]; then
    echo "Usage: $0 <path_to_bloguito_backup_*.tar.gz> [--yes]"
    exit 1
fi

WORDPRESS_DIR="${WORDPRESS_DIR:-/home/ubuntu/wordpress}"
AGENT_DIR="${AGENT_DIR:-/home/ubuntu/agent-publisher}"
CONTAINER_DB="${CONTAINER_DB:-wordpress_db}"
CONTAINER_APP="${CONTAINER_APP:-wordpress_app}"

echo "=================================================="
echo "[RESTORE] Bloguito Snapshot Restoration Tool"
echo "[RESTORE] Target Archive: $ARCHIVE_PATH"
echo "=================================================="

# Resolve DB password
if [ -f "${WORDPRESS_DIR}/.env" ]; then
    # shellcheck disable=SC1090
    source "${WORDPRESS_DIR}/.env"
fi

# Determine Docker command
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

# Extract to temporary directory
RESTORE_STAGING=$(mktemp -d "/tmp/restore_staging_XXXXXX")
cleanup() {
    rm -rf "$RESTORE_STAGING"
}
trap cleanup EXIT

echo "[RESTORE] 🔍 Unpacking archive for verification..."
tar -xzf "$ARCHIVE_PATH" -C "$RESTORE_STAGING"

if [ ! -f "${RESTORE_STAGING}/manifest.json" ]; then
    echo "[RESTORE] ❌ manifest.json missing from archive!"
    exit 1
fi

# SHA256 checksum validation
sha256_file() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1" | awk '{print $1}'
    elif command -v shasum >/dev/null 2>&1; then
        shasum -a 256 "$1" | awk '{print $1}'
    else
        openssl dgst -sha256 "$1" | awk '{print $NF}'
    fi
}

echo "[RESTORE] 🛡️ Validating SHA256 checksums..."
for COMP in db uploads configs; do
    EXPECTED_HASH=$(grep -A 5 "\"$COMP\":" "${RESTORE_STAGING}/manifest.json" | grep '"sha256":' | cut -d'"' -f4)
    TARGET_FILE="${RESTORE_STAGING}/$COMP."*
    ACTUAL_HASH=$(sha256_file $TARGET_FILE)
    if [ "$EXPECTED_HASH" != "$ACTUAL_HASH" ]; then
        echo "[RESTORE] ❌ Checksum mismatch for component $COMP!"
        echo "          Expected: $EXPECTED_HASH"
        echo "          Actual:   $ACTUAL_HASH"
        exit 1
    fi
    echo "  ✅ Component '$COMP' checksum verified."
done

# Confirmation prompt unless --yes
if [ "$AUTO_CONFIRM" != "--yes" ]; then
    echo ""
    read -r -p "⚠️ WARNING: This will overwrite MariaDB database and WordPress media files. Proceed? (y/N) " CONFIRM
    if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
        echo "[RESTORE] Restoration cancelled by user."
        exit 0
    fi
fi

# 1. Restore MariaDB
echo "[RESTORE] 🗄️ (1/3) Restoring MariaDB database..."
gzip -dc "${RESTORE_STAGING}/db.sql.gz" | $DOCKER_CMD exec -i "$CONTAINER_DB" mariadb -u root -p"$MYSQL_ROOT_PASSWORD" wordpress
echo "[RESTORE]   ✅ MariaDB database restored."

# 2. Restore WordPress media uploads
echo "[RESTORE] 🖼️ (2/3) Restoring WordPress uploads..."
$DOCKER_CMD exec -i "$CONTAINER_APP" tar -xzf - -C /var/www/html/wp-content < "${RESTORE_STAGING}/uploads.tar.gz"
$DOCKER_CMD exec "$CONTAINER_APP" chown -R www-data:www-data /var/www/html/wp-content/uploads 2>/dev/null || true
echo "[RESTORE]   ✅ WordPress media uploads restored."

# 3. Restore Configs
echo "[RESTORE] ⚙️ (3/3) Restoring configurations and runtime data..."
tar -xzf "${RESTORE_STAGING}/configs.tar.gz" -C "$RESTORE_STAGING"
if [ -d "${RESTORE_STAGING}/configs_staging/agent-publisher/data" ]; then
    mkdir -p "${AGENT_DIR}/data"
    cp -r "${RESTORE_STAGING}/configs_staging/agent-publisher/data/"*.json "${AGENT_DIR}/data/" 2>/dev/null || true
    echo "[RESTORE]   ✅ Agent data JSON files restored."
fi

echo "=================================================="
echo "[RESTORE] ✅ Full blog restoration completed successfully!"
echo "=================================================="