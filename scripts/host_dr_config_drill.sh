#!/usr/bin/env bash
set -euo pipefail

# Disposable host-configuration recovery drill. The actual checks live in
# host_dr_validate.sh so CI/drill validation cannot drift apart.

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
DR_IMAGE="${BLOGUITO_HOST_DR_IMAGE:-ubuntu:24.04}"

command -v docker >/dev/null 2>&1 || {
    echo "ERROR: docker is required for the isolated host DR drill." >&2
    exit 1
}

docker run --rm -i --network bridge \
    --mount "type=bind,src=${REPO_ROOT},dst=/repo,readonly" \
    "$DR_IMAGE" bash /repo/scripts/host_dr_validate.sh --with-wp-cli
