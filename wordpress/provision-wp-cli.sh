#!/usr/bin/env bash
set -euo pipefail

# Keep this file in sync with the read-only bind mount in docker-compose.yml.
# The versioned release URL avoids a moving "latest" target, and the pinned
# SHA-256 makes the download fail closed if the asset changes or is corrupted.
WP_CLI_VERSION="2.12.0"
WP_CLI_SHA256="ce34ddd838f7351d6759068d09793f26755463b4a4610a5a5c0a97b68220d85c"
WP_CLI_URL_DEFAULT="https://github.com/wp-cli/wp-cli/releases/download/v${WP_CLI_VERSION}/wp-cli-${WP_CLI_VERSION}.phar"

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DESTINATION="${WP_CLI_DESTINATION:-${SCRIPT_DIR}/wp-cli.phar}"
DOWNLOAD_URL="${WP_CLI_DOWNLOAD_URL:-${WP_CLI_URL_DEFAULT}}"

command -v curl >/dev/null 2>&1 || { echo "ERROR: curl is required." >&2; exit 1; }
command -v sha256sum >/dev/null 2>&1 || { echo "ERROR: sha256sum is required." >&2; exit 1; }

destination_dir="$(dirname -- "$DESTINATION")"
mkdir -p -- "$destination_dir"

current_sha=""
if [ -f "$DESTINATION" ]; then
    current_sha="$(sha256sum -- "$DESTINATION" | awk '{print $1}')"
fi
if [ "$current_sha" = "$WP_CLI_SHA256" ]; then
    chmod 0755 -- "$DESTINATION"
    echo "WP_CLI_ALREADY_VERIFIED version=${WP_CLI_VERSION} sha256=${WP_CLI_SHA256}"
    exit 0
fi

temporary="$(mktemp "${destination_dir}/.wp-cli-${WP_CLI_VERSION}.XXXXXX")"
cleanup() {
    rm -f -- "$temporary"
}
trap cleanup EXIT

curl --fail --location --silent --show-error --output "$temporary" "$DOWNLOAD_URL"
downloaded_sha="$(sha256sum -- "$temporary" | awk '{print $1}')"
if [ "$downloaded_sha" != "$WP_CLI_SHA256" ]; then
    echo "ERROR: WP-CLI checksum mismatch; refusing to install." >&2
    exit 1
fi

chmod 0755 -- "$temporary"
mv -f -- "$temporary" "$DESTINATION"
trap - EXIT

installed_sha="$(sha256sum -- "$DESTINATION" | awk '{print $1}')"
if [ "$installed_sha" != "$WP_CLI_SHA256" ]; then
    echo "ERROR: installed WP-CLI checksum mismatch." >&2
    exit 1
fi

echo "WP_CLI_PROVISIONED version=${WP_CLI_VERSION} sha256=${WP_CLI_SHA256} destination=${DESTINATION}"
