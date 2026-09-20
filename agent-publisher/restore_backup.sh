#!/bin/bash
set -euo pipefail
umask 077

ARCHIVE_PATH="${1:-}"
if [ -z "$ARCHIVE_PATH" ] || [ ! -f "$ARCHIVE_PATH" ]; then
    echo "Usage: $0 <archive> [--verify-only | --yes | --export-configs NEW_DIR [--include-secrets]]"
    exit 1
fi
shift
AUTO_CONFIRM=false
VERIFY_ONLY=false
EXPORT_DIR=""
INCLUDE_SECRETS=false
while [ "$#" -gt 0 ]; do
    case "$1" in
        --yes) AUTO_CONFIRM=true ;;
        --verify-only) VERIFY_ONLY=true ;;
        --export-configs)
            shift
            [ "$#" -gt 0 ] || { echo "ERROR: --export-configs requires a directory."; exit 1; }
            EXPORT_DIR="$1" ;;
        --include-secrets) INCLUDE_SECRETS=true ;;
        *) echo "ERROR: Unknown option: $1"; exit 1 ;;
    esac
    shift
done
if [ "$INCLUDE_SECRETS" = true ] && [ -z "$EXPORT_DIR" ]; then
    echo "ERROR: --include-secrets requires --export-configs."
    exit 1
fi
if [ "$VERIFY_ONLY" = true ] && { [ -n "$EXPORT_DIR" ] || [ "$AUTO_CONFIRM" = true ]; }; then
    echo "ERROR: --verify-only cannot be combined with restore/export options."
    exit 1
fi

WORDPRESS_DIR="${WORDPRESS_DIR:-/home/ubuntu/wordpress}"
AGENT_DIR="${AGENT_DIR:-/home/ubuntu/agent-publisher}"
CONTAINER_DB="${CONTAINER_DB:-wordpress_db}"
CONTAINER_APP="${CONTAINER_APP:-wordpress_app}"
RESTORE_STAGING=$(mktemp -d "/tmp/restore_staging_XXXXXX")
cleanup() { rm -rf "$RESTORE_STAGING"; }
trap cleanup EXIT
PYTHON_BIN="${BACKUP_PYTHON:-python3}"

# Validate all components before looking up database credentials or changing any live data.
"$PYTHON_BIN" - "$ARCHIVE_PATH" "$RESTORE_STAGING" <<'PY'
import gzip
import hashlib
import json
import re
import sys
import tarfile
from pathlib import Path, PurePosixPath

archive_path, staging = Path(sys.argv[1]), Path(sys.argv[2])
filenames = {'db': 'db.sql.gz', 'uploads': 'uploads.tar.gz', 'configs': 'configs.tar.gz',
             'wp_content': 'wp-content.tar.gz', 'secrets': 'secrets.tar.gz'}
required = {'2.0': {'db', 'uploads', 'configs'}, '3.0': set(filenames)}

def safe_path(name):
    path = PurePosixPath(name)
    return bool(name) and not path.is_absolute() and '\\' not in name and '..' not in path.parts

try:
    with tarfile.open(archive_path, 'r:gz') as outer:
        members = outer.getmembers()
        by_name = {m.name: m for m in members}
        if len(by_name) != len(members) or 'manifest.json' not in by_name:
            raise ValueError('missing or duplicate manifest/archive entries')
        manifest_member = by_name['manifest.json']
        if not manifest_member.isfile() or manifest_member.size > 1024 * 1024:
            raise ValueError('invalid manifest')
        manifest = json.load(outer.extractfile(manifest_member))
        version = manifest.get('version')
        if version not in required:
            raise ValueError('unsupported snapshot version')
        comps = manifest.get('components')
        if not isinstance(comps, dict) or set(comps) != required[version]:
            raise ValueError('missing or unexpected manifest components')
        expected_names = {'manifest.json'} | {filenames[name] for name in comps}
        if set(by_name) != expected_names or any(not m.isfile() for m in members):
            raise ValueError('missing or unexpected archive entries')
        for name, info in comps.items():
            filename = filenames[name]
            member = by_name[filename]
            if not isinstance(info, dict) or info.get('file') != filename:
                raise ValueError('invalid component filename: ' + name)
            if type(info.get('size_bytes')) is not int or info['size_bytes'] != member.size:
                raise ValueError('component size mismatch: ' + name)
            expected = info.get('sha256')
            if not isinstance(expected, str) or not re.fullmatch(r'[0-9a-f]{64}', expected):
                raise ValueError('invalid SHA256: ' + name)
            with outer.extractfile(member) as source, (staging / filename).open('wb') as dest:
                digest = hashlib.sha256()
                while chunk := source.read(1024 * 1024):
                    digest.update(chunk)
                    dest.write(chunk)
            if digest.hexdigest() != expected:
                raise ValueError('checksum mismatch: ' + name)
            if name == 'db':
                with gzip.open(staging / filename, 'rb') as db:
                    while db.read(1024 * 1024):
                        pass
            else:
                with tarfile.open(staging / filename, 'r:gz') as nested:
                    names = []
                    for inner in nested:
                        if not safe_path(inner.name) or not (inner.isfile() or inner.isdir()):
                            raise ValueError('unsafe nested entry: ' + name)
                        allowed = {
                            'uploads': ('uploads',),
                            'wp_content': ('plugins', 'themes', 'mu-plugins'),
                            'configs': ('configs_staging',),
                            'secrets': ('secrets_staging',),
                        }[name]
                        if not any(inner.name == root or inner.name.startswith(root + '/') for root in allowed):
                            raise ValueError('component contains an unexpected path: ' + name)
                        names.append(inner.name)
                    if name == 'wp_content' and not all(
                        any(p == d or p.startswith(d + '/') for p in names)
                        for d in ('plugins', 'themes')
                    ):
                        raise ValueError('plugins or themes missing')
        (staging / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    print('[RESTORE] Archive verified; version=' + version)
except (OSError, ValueError, KeyError, TypeError, EOFError, tarfile.TarError) as exc:
    print('[RESTORE] Verification failed:', str(exc), file=sys.stderr)
    sys.exit(1)
PY

if [ "$VERIFY_ONLY" = true ]; then
    echo "[RESTORE] VERIFY_ONLY_OK: hashes, gzip streams and nested paths validated; no restore performed."
    exit 0
fi

# Host settings and credentials are *exported* into a new restricted directory,
# never silently applied to a potentially different server.
if [ -n "$EXPORT_DIR" ]; then
    if [ -e "$EXPORT_DIR" ]; then
        echo "[RESTORE] ERROR: Export directory already exists."
        exit 1
    fi
    if [ "$INCLUDE_SECRETS" = true ] && [ ! -f "${RESTORE_STAGING}/secrets.tar.gz" ]; then
        echo "[RESTORE] ERROR: Legacy archive lacks separate secrets."
        exit 1
    fi
    mkdir -m 700 -- "$EXPORT_DIR"
    tar -xzf "${RESTORE_STAGING}/configs.tar.gz" -C "$EXPORT_DIR"
    if [ "$INCLUDE_SECRETS" = true ]; then
        tar -xzf "${RESTORE_STAGING}/secrets.tar.gz" -C "$EXPORT_DIR"
    fi
    echo "[RESTORE] Configuration exported to restricted directory: $EXPORT_DIR"
    echo "[RESTORE] Review and manually install host/Compose/Nginx settings and credentials."
    exit 0
fi

if [ ! -f "${RESTORE_STAGING}/wp-content.tar.gz" ]; then
    echo "[RESTORE] ERROR: Legacy snapshot lacks extensions; full restore refused."
    exit 1
fi
if [ "$AUTO_CONFIRM" != true ]; then
    read -r -p "This replaces database, uploads and WordPress extensions. Proceed? (y/N) " CONFIRM
    if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
        echo "[RESTORE] Cancelled."
        exit 0
    fi
fi

# Resolve credentials for the *target*, never import snapshot secrets automatically.
if [ -f "${WORDPRESS_DIR}/.env" ]; then
    # shellcheck disable=SC1090
    source "${WORDPRESS_DIR}/.env"
fi
DOCKER_CMD="docker"
if ! $DOCKER_CMD ps >/dev/null 2>&1; then
    if [ "$(uname -s)" = "Linux" ] && [ "$EUID" -ne 0 ] && command -v sudo >/dev/null 2>&1; then
        DOCKER_CMD="sudo docker"
    fi
fi
if [ -z "${MYSQL_ROOT_PASSWORD:-}" ]; then
    CONTAINER_ENV_PASS=$($DOCKER_CMD inspect --format '{{range .Config.Env}}{{println .}}{{end}}' "$CONTAINER_DB" 2>/dev/null | grep '^MYSQL_ROOT_PASSWORD=' | cut -d= -f2- || true)
    [ -z "$CONTAINER_ENV_PASS" ] || MYSQL_ROOT_PASSWORD="$CONTAINER_ENV_PASS"
fi
: "${MYSQL_ROOT_PASSWORD:?ERROR: Target database password unavailable.}"

echo "[RESTORE] Restoring database..."
gzip -dc "${RESTORE_STAGING}/db.sql.gz" | $DOCKER_CMD exec -i "$CONTAINER_DB" mariadb -u root -p"$MYSQL_ROOT_PASSWORD" wordpress

echo "[RESTORE] Restoring WordPress uploads..."
$DOCKER_CMD exec -i "$CONTAINER_APP" tar -xzf - -C /var/www/html/wp-content < "${RESTORE_STAGING}/uploads.tar.gz"
$DOCKER_CMD exec "$CONTAINER_APP" chown -R www-data:www-data /var/www/html/wp-content/uploads

echo "[RESTORE] Restoring plugins, themes and optional MU plugins..."
WP_STAGE=$($DOCKER_CMD exec "$CONTAINER_APP" mktemp -d /var/www/html/wp-content/.bloguito-restore-XXXXXX)
$DOCKER_CMD exec -i "$CONTAINER_APP" tar -xzf - -C "$WP_STAGE" < "${RESTORE_STAGING}/wp-content.tar.gz"
$DOCKER_CMD exec "$CONTAINER_APP" sh -c '
set -eu
base=/var/www/html/wp-content
stage="$1"
prior=$(mktemp -d "$base/.bloguito-prerestore-XXXXXX")
for dir in plugins themes mu-plugins; do
    if [ -e "$base/$dir" ]; then mv "$base/$dir" "$prior/$dir"; fi
    if [ -e "$stage/$dir" ]; then mv "$stage/$dir" "$base/$dir"; fi
done
rmdir "$stage"
chown -R www-data:www-data "$base/plugins" "$base/themes"
if [ -d "$base/mu-plugins" ]; then chown -R www-data:www-data "$base/mu-plugins"; fi
echo "[RESTORE] Original extensions retained in private pre-restore directory."
' sh "$WP_STAGE"

echo "[RESTORE] Restoring runtime JSON..."
tar -xzf "${RESTORE_STAGING}/configs.tar.gz" -C "$RESTORE_STAGING"
if [ -d "${RESTORE_STAGING}/configs_staging/agent-publisher/data" ]; then
    mkdir -p "${AGENT_DIR}/data"
    for json in "${RESTORE_STAGING}/configs_staging/agent-publisher/data/"*.json; do
        [ -f "$json" ] || continue
        cp "$json" "${AGENT_DIR}/data/"
    done
fi

echo "[RESTORE] Database, uploads, extensions and runtime JSON restored."
echo "[RESTORE] Host settings and credentials require separate reviewed export/import."
