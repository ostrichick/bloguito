#!/usr/bin/env bash
# Daily, read-only Google reporting. Install in cron only after a real API smoke test.
set -euo pipefail
umask 077
base_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
report_dir="$base_dir/data/analytics"
credential_file="$report_dir/reader-credentials.json"

if [[ ! -f "$credential_file" || -L "$credential_file" ]]; then
  echo 'analytics_collection_failed:credential_file_unavailable' >&2
  exit 1
fi
if [[ "$(stat -c '%a' -- "$credential_file")" != '600' ]]; then
  echo 'analytics_collection_failed:credential_file_permissions' >&2
  exit 1
fi
if [[ "$(stat -c '%a' -- "$report_dir")" != '700' ]]; then
  echo 'analytics_collection_failed:report_directory_permissions' >&2
  exit 1
fi

export GOOGLE_APPLICATION_CREDENTIALS="$credential_file"
exec "$base_dir/venv/bin/python" "$base_dir/analytics_collector.py" \
  --site-url 'https://lifeinfo24.org/' \
  --ga4-property '554325332' \
  --output-dir "$report_dir"
