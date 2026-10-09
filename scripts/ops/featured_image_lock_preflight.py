"""Read-only Bloguito production WordPress image-lock preflight.

The WordPress CLI eval program below queries table metadata and redacts lock
owner tokens before returning its compact JSON result. No lock state is changed.
Run only after reviewing the selected SSH host/container.
"""
from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys


READ_ONLY_PHP = r'''
global $wpdb;
$names = [$wpdb->options, $wpdb->postmeta];
$engines = [];
foreach ($names as $table) {
  $engine = $wpdb->get_var($wpdb->prepare(
    "SELECT ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s",
    $table
  ));
  $engines[$table] = $engine ?: null;
}
$pattern = $wpdb->esc_like("_bloguito_featured_image_lock_") . "%";
$rows = $wpdb->get_results($wpdb->prepare(
  "SELECT option_name, option_value, autoload FROM {$wpdb->options} WHERE option_name LIKE %s",
  $pattern
), ARRAY_A);
$locks = [];
foreach ($rows as $row) {
  $name = (string)$row["option_name"];
  if (!preg_match("/^_bloguito_featured_image_lock_([1-9][0-9]*)$/", $name, $matches)) { continue; }
  $state = json_decode((string)$row["option_value"], true);
  $locks[] = [
    "post_id" => (int)$matches[1],
    "valid_structure" => is_array($state) && isset($state["token"], $state["expires_at"]),
    "import_pending" => is_array($state) && ($state["import_pending"] ?? false) === true,
    "expired" => is_array($state) && (int)($state["expires_at"] ?? 0) < time(),
    "autoload" => (string)$row["autoload"],
  ];
}
echo wp_json_encode([
  "engines" => $engines,
  "lock_count" => count($locks),
  "locks" => $locks,
], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
'''


def command(ssh_host: str, container: str) -> list[str]:
    if not re.fullmatch(r"[a-zA-Z0-9._-]+", ssh_host):
        raise ValueError("unsafe_ssh_host")
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", container):
        raise ValueError("unsafe_container")
    remote = " ".join([
        "sudo", "docker", "exec", shlex.quote(container), "wp", "eval",
        shlex.quote(READ_ONLY_PHP), "--allow-root",
    ])
    return ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", ssh_host, remote]


def validated_report(raw: str) -> dict:
    payload = json.loads(raw.lstrip("\ufeff"))
    if not isinstance(payload, dict) or not isinstance(payload.get("engines"), dict):
        raise ValueError("invalid_wp_lock_preflight")
    if not isinstance(payload.get("locks"), list) or payload.get("lock_count") != len(payload["locks"]):
        raise ValueError("invalid_wp_lock_preflight")
    # Never trust or forward arbitrary WP/plugin stdout keys, especially tokens.
    engines = payload["engines"]
    normalized_engines = {}
    for table, engine in engines.items():
        if not re.fullmatch(r"[a-zA-Z0-9_]+", str(table)):
            raise ValueError("invalid_wp_table_name")
        normalized_engines[table] = engine if engine in {"InnoDB", "MyISAM"} else "unknown"
    locks = []
    for lock in payload["locks"]:
        if not isinstance(lock, dict) or type(lock.get("post_id")) is not int or lock["post_id"] <= 0:
            raise ValueError("invalid_wp_lock_state")
        if not all(type(lock.get(key)) is bool for key in ("valid_structure", "import_pending", "expired")):
            raise ValueError("invalid_wp_lock_state")
        autoload = lock.get("autoload") if lock.get("autoload") in {"yes", "no", "on", "off", "auto", "auto-on", "auto-off"} else "unknown"
        locks.append({"post_id": lock["post_id"], "valid_structure": lock["valid_structure"],
                      "import_pending": lock["import_pending"], "expired": lock["expired"],
                      "autoload": autoload})
    return {
        "engines": normalized_engines,
        "lock_count": len(locks),
        "locks": locks,
        "blockers": (
            ["wordpress_storage_engine_not_innodb"] if len(engines) != 2 or any(v != "InnoDB" for v in normalized_engines.values()) else []
        ) + (["image_import_pending_requires_operator_reconciliation"] if any(l["import_pending"] for l in locks) else [])
          + (["malformed_image_lock_requires_operator_review"] if any(not l["valid_structure"] for l in locks) else []),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ssh-host", default="bloguito")
    parser.add_argument("--container", default="wordpress_app")
    args = parser.parse_args(argv)
    try:
        result = subprocess.run(command(args.ssh_host, args.container), check=True,
                                capture_output=True, text=True, encoding="utf-8", timeout=40)
        report = validated_report(result.stdout)
    except (ValueError, OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        # Do not echo remote stdout/stderr, even on malformed data: it may have secrets.
        print("WP_IMAGE_LOCK_PREFLIGHT_ERROR=" + type(exc).__name__, file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report["blockers"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
