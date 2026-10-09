"""Read-only operational preflight must never echo a WordPress lock token."""
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "wp_lock_preflight", ROOT / "scripts/ops/featured_image_lock_preflight.py")
preflight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight)


class WordPressLockPreflightTests(unittest.TestCase):
    def test_remote_command_is_fixed_and_shell_quoted(self):
        argv = preflight.command("bloguito", "wordpress_app")
        self.assertEqual("ssh", argv[0])
        self.assertIn("wp eval", argv[-1])
        self.assertIn("information_schema.TABLES", argv[-1])
        self.assertIn("esc_like", argv[-1])
        self.assertNotIn("DELETE FROM", argv[-1])
        self.assertNotIn("START TRANSACTION", argv[-1])
        with self.assertRaisesRegex(ValueError, "unsafe_ssh_host"):
            preflight.command("bloguito;rm -rf /", "wordpress_app")

    def test_tokens_never_forwarded_and_pending_blocks_deploy(self):
        report = preflight.validated_report(json.dumps({
            "engines": {"wp_options": "InnoDB", "wp_postmeta": "InnoDB"},
            "lock_count": 1,
            "locks": [{
                "post_id": 887, "valid_structure": True,
                "import_pending": True, "expired": True,
                "autoload": "off", "token": "SECRET_NEVER_ECHO",
            }],
            "extra": "SECRET_NEVER_ECHO",
        }))
        self.assertNotIn("SECRET_NEVER_ECHO", json.dumps(report))
        self.assertIn("image_import_pending_requires_operator_reconciliation", report["blockers"])

    def test_unknown_engine_blocks(self):
        report = preflight.validated_report(json.dumps({
            "engines": {"wp_options": "MyISAM", "wp_postmeta": "InnoDB"},
            "lock_count": 0, "locks": [],
        }))
        self.assertIn("wordpress_storage_engine_not_innodb", report["blockers"])

    def test_invalid_state_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "invalid_wp_lock_state"):
            preflight.validated_report(json.dumps({
                "engines": {"wp_options": "InnoDB", "wp_postmeta": "InnoDB"},
                "lock_count": 1, "locks": [{"post_id": 1, "token": "SECRET"}],
            }))


if __name__ == "__main__":
    unittest.main()
