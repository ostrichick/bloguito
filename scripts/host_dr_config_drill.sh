#!/usr/bin/env bash
set -euo pipefail

# Disposable host-configuration recovery drill.
# This never connects to production and mounts the repository read-only.

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
DR_IMAGE="${BLOGUITO_HOST_DR_IMAGE:-ubuntu:24.04}"

command -v docker >/dev/null 2>&1 || {
    echo "ERROR: docker is required for the isolated host DR drill." >&2
    exit 1
}

docker run --rm -i --network bridge \
    --mount "type=bind,src=${REPO_ROOT},dst=/repo,readonly" \
    "$DR_IMAGE" bash -s <<'DRILL'
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

apt-get update -qq
apt-get install -y -qq \
    ca-certificates curl fail2ban iptables nginx openssh-server openssl systemd >/dev/null

# Nginx: provide disposable TLS material so the checked-in production vhost can
# be parsed exactly without copying production private keys into the drill.
mkdir -p /etc/letsencrypt/live/lifeinfo24.org /run/sshd
openssl req -x509 -newkey rsa:2048 -nodes \
    -keyout /etc/letsencrypt/live/lifeinfo24.org/privkey.pem \
    -out /etc/letsencrypt/live/lifeinfo24.org/fullchain.pem \
    -subj /CN=lifeinfo24.org -days 1 >/dev/null 2>&1
printf 'ssl_protocols TLSv1.2 TLSv1.3;\n' > /etc/letsencrypt/options-ssl-nginx.conf
openssl dhparam -dsaparam -out /etc/letsencrypt/ssl-dhparams.pem 2048 >/dev/null 2>&1
install -m 0644 /repo/wordpress/nginx/lifeinfo24.org.conf /etc/nginx/sites-enabled/lifeinfo24.org
rm -f /etc/nginx/sites-enabled/default
nginx -t

# SSH, Fail2ban and the private-SSH systemd unit are syntax/config validated in
# the disposable environment. The unit is not started because tailscale0 is not
# present here; enabling it belongs only after Tailscale bootstrap on a new host.
install -m 0644 /repo/wordpress/ssh/99-bloguito-hardening.conf \
    /etc/ssh/sshd_config.d/99-bloguito-hardening.conf
sshd -t
install -m 0644 /repo/wordpress/fail2ban/jail.d/bloguito-sshd.conf \
    /etc/fail2ban/jail.d/bloguito-sshd.conf
fail2ban-client -t
install -m 0644 /repo/wordpress/ssh/bloguito-ssh-private-only.service \
    /etc/systemd/system/bloguito-ssh-private-only.service
systemd-analyze verify /etc/systemd/system/bloguito-ssh-private-only.service

# WP-CLI: exercise a real pinned download, idempotent second run, and the
# fail-closed path that must preserve an existing destination on bad content.
export WP_CLI_DESTINATION=/tmp/wp-cli.phar
unset WP_CLI_DOWNLOAD_URL || true
bash /repo/wordpress/provision-wp-cli.sh
bash /repo/wordpress/provision-wp-cli.sh
test "$(sha256sum /tmp/wp-cli.phar | awk '{print $1}')" = \
    ce34ddd838f7351d6759068d09793f26755463b4a4610a5a5c0a97b68220d85c

printf 'preserve-me' > /tmp/existing-wp-cli
printf 'bad-download' > /tmp/bad-wp-cli
if WP_CLI_DESTINATION=/tmp/existing-wp-cli \
   WP_CLI_DOWNLOAD_URL=file:///tmp/bad-wp-cli \
   bash /repo/wordpress/provision-wp-cli.sh >/tmp/bad-provision.out 2>&1; then
    echo "ERROR: checksum-mismatched WP-CLI unexpectedly installed." >&2
    exit 1
fi
test "$(cat /tmp/existing-wp-cli)" = 'preserve-me'

echo "HOST_DR_ISOLATED_CONFIG_OK"
DRILL
