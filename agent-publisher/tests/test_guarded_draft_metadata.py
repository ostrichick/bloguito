"""Strict creation-time SEO metadata CAS protocol (no post-body updates)."""

import hashlib
import base64
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

PUBLISHER_ROOT = Path(__file__).resolve().parents[1]
if str(PUBLISHER_ROOT) not in sys.path:
    sys.path.insert(0, str(PUBLISHER_ROOT))

from agents.wordpress_mutation import (
    GUARDED_NEW_DRAFT_META_SCRIPT, guarded_set_new_draft_metadata,
)


class GuardedDraftMetadataTests(unittest.TestCase):
    def setUp(self):
        self.expected = {
            "post_status": "draft", "post_title": "기초연금 신청",
            "post_name": "", "post_excerpt": "안내",
            "content_sha256": hashlib.sha256("본문".encode()).hexdigest(),
        }
        self.meta = {
            "_bloguito_permalink_scheme": "post-id-v1",
            "rank_math_focus_keyword": "기초연금 신청",
            "rank_math_title": "2026 기초연금 신청",
            "rank_math_description": "공식 안내",
        }

    def _call(self, status, *, saved=None):
        response = {"status": status}
        if saved is not None:
            response["saved_meta"] = saved
        with patch("agents.wordpress_mutation.run_wordpress",
                   return_value=Mock(stdout=json.dumps(response))) as run:
            if status in {"ok", "already_applied"} and saved == self.meta:
                self.assertEqual(self.meta, guarded_set_new_draft_metadata(
                    ["wp"], 901, expected=self.expected, meta=self.meta))
            else:
                with self.assertRaises(ValueError):
                    guarded_set_new_draft_metadata(
                        ["wp"], 901, expected=self.expected, meta=self.meta)
            self.assertEqual(["wp", "eval", GUARDED_NEW_DRAFT_META_SCRIPT, "--allow-root"],
                             run.call_args.args[0])
            payload = json.loads(run.call_args.kwargs["input"])
            self.assertEqual(self.expected, payload["expected"])
            self.assertEqual(self.meta, payload["meta"])
            return payload

    def test_write_and_lost_response_replay_allow_exact_verified_values(self):
        self._call("ok", saved=self.meta)
        self._call("already_applied", saved=self.meta)

    def test_drift_or_partial_state_cannot_be_silently_accepted(self):
        for state in ("cas_mismatch", "meta_conflict", "update_failed",
                      "verification_failed", "commit_ambiguous", "missing"):
            with self.subTest(state=state):
                self._call(state)
        self._call("ok", saved={"rank_math_title": "other"})

    def test_rejects_wrong_keys_and_non_draft_state_before_wordpress(self):
        invalids = [
            dict(self.meta, malicious="override"),
            dict(self.meta, _bloguito_permalink_scheme="custom-slug"),
            dict(self.meta, rank_math_title=""),
        ]
        with patch("agents.wordpress_mutation.run_wordpress") as run:
            for meta in invalids:
                with self.assertRaises(ValueError):
                    guarded_set_new_draft_metadata(["wp"], 901, expected=self.expected, meta=meta)
            with self.assertRaises(ValueError):
                guarded_set_new_draft_metadata(
                    ["wp"], 901, expected={**self.expected, "post_status": "publish"},
                    meta=self.meta)
            run.assert_not_called()

    def test_server_script_is_metadata_only_and_locks_post_before_update(self):
        self.assertIn("START TRANSACTION", GUARDED_NEW_DRAFT_META_SCRIPT)
        self.assertIn("FOR UPDATE", GUARDED_NEW_DRAFT_META_SCRIPT)
        self.assertIn("update_post_meta", GUARDED_NEW_DRAFT_META_SCRIPT)
        self.assertIn("ROLLBACK", GUARDED_NEW_DRAFT_META_SCRIPT)
        self.assertNotIn("wp_update_post", GUARDED_NEW_DRAFT_META_SCRIPT)
        self.assertNotIn("wp_insert_post", GUARDED_NEW_DRAFT_META_SCRIPT)

    @unittest.skipUnless(shutil.which("php"), "PHP CLI unavailable: run in the wordpress-test CI job")
    def test_actual_php_script_against_transaction_fixture(self):
        """Execute the production PHP source, with simulated storage and WP APIs."""
        fixture = PUBLISHER_ROOT.parent / "wordpress" / "tests" / "draft-meta-cas-fixture.php"
        script = base64.b64encode(GUARDED_NEW_DRAFT_META_SCRIPT.encode()).decode()
        result = subprocess.run(
            [shutil.which("php"), str(fixture), script],
            capture_output=True, text=True, encoding="utf-8", timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.count("PASS:"), 13, result.stdout)


if __name__ == "__main__":
    unittest.main()
