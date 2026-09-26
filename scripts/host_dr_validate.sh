#!/usr/bin/env bash
set -euo pipefail

# Run inside a disposable Ubuntu 24.04 container with the repository mounted
# read-only at /repo. This validates recoverable host configuration without
# touching production or requiring production secrets.

REPO_ROOT="${REPO_ROOT:-/repo}"

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq nginx openssh-server fail2ban systemd openssl iptables >/dev/null

install -d -m 0755 /etc/nginx/sites-available /etc/nginx/sites-enabled
install -m 0644 "$REPO_ROOT/wordpress/nginx/lifeinfo24.org.conf" /etc/nginx/sites-available/lifeinfo24.org.conf
rm -f /etc/nginx/sites-enabled/default
ln -s /etc/nginx/sites-available/lifeinfo24.org.conf /etc/nginx/sites-enabled/lifeinfo24.org.conf

# The production certificate is deliberately not copied into the drill. A
# disposable certificate proves the Nginx TLS configuration path can boot.
install -d -m 0755 /etc/letsencrypt/live/lifeinfo24.org
openssl req -x509 -newkey rsa:2048 -nodes -days 1 \
  -subj '/CN=lifeinfo24.org' \
  -keyout /etc/letsencrypt/live/lifeinfo24.org/privkey.pem \
  -out /etc/letsencrypt/live/lifeinfo24.org/fullchain.pem >/dev/null 2>&1
cat >/etc/letsencrypt/options-ssl-nginx.conf <<'EOF'
ssl_session_cache shared:le_nginx_SSL:10m;
ssl_session_timeout 1440m;
ssl_protocols TLSv1.2 TLSv1.3;
ssl_prefer_server_ciphers off;
EOF
openssl dhparam -dsaparam -out /etc/letsencrypt/ssl-dhparams.pem 2048 >/dev/null 2>&1

nginx -t
nginx
echo | openssl s_client -connect 127.0.0.1:443 -servername lifeinfo24.org >/tmp/tls-handshake.txt 2>&1
grep -q "BEGIN CERTIFICATE" /tmp/tls-handshake.txt || {
  echo "ERROR: disposable TLS handshake failed" >&2
  cat /tmp/tls-handshake.txt >&2
  exit 1
}
nginx -s stop

install -d -m 0755 /etc/ssh/sshd_config.d /run/sshd
install -m 0644 "$REPO_ROOT/wordpress/ssh/99-bloguito-hardening.conf" /etc/ssh/sshd_config.d/99-bloguito-hardening.conf
ssh-keygen -A >/dev/null 2>&1
sshd -t

install -d -m 0755 /etc/fail2ban/jail.d
install -m 0644 "$REPO_ROOT/wordpress/fail2ban/bloguito-sshd.conf" /etc/fail2ban/jail.d/bloguito-sshd.conf
fail2ban-client -d >/tmp/fail2ban-debug.txt 2>&1
grep -q "'add', 'sshd'" /tmp/fail2ban-debug.txt && \
grep -q "'maxretry', 5" /tmp/fail2ban-debug.txt || {
  echo "ERROR: Bloguito Fail2ban sshd jail was not parsed with maxretry=5" >&2
  tail -80 /tmp/fail2ban-debug.txt >&2
  exit 1
}

systemd-analyze verify "$REPO_ROOT/wordpress/ssh/bloguito-ssh-private-only.service"

echo "HOST_DR_CONFIG_VALIDATION_OK"
