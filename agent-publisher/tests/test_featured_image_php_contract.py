"""Offline contract checks for the fixed R3 PHP runtime.

These tests cannot prove PHP/WordPress/MariaDB behavior. A real `php -l` check
is run only when PHP is installed; integration remains a Docker-PC handoff.
"""

import hashlib
import importlib.util
from pathlib import Path
import re
import shutil
import subprocess
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[2]
PHP = ROOT / "scripts" / "security" / "featured_image_set.php"
WRITER = ROOT / "scripts" / "security" / "bloguito_wp_image_writer.py"


def load_writer():
    spec = importlib.util.spec_from_file_location("r3_wp_image_writer_for_php_contract", WRITER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FeaturedImagePhpContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = PHP.read_text(encoding="utf-8")

    def test_fixed_runtime_path_matches_sha_locked_writer_and_has_stable_digest(self):
        writer = load_writer()
        self.assertEqual("featured_image_set.php", PHP.name)
        self.assertEqual("/usr/local/libexec/bloguito/featured_image_set.php",
                         str(writer.PHP_RUNTIME).replace('\\', '/'))
        self.assertEqual(str(writer.PHP_RUNTIME).replace('\\', '/'), writer.CONTAINER_RUNTIME)
        self.assertTrue(self.source.startswith("<?php\n"))
        self.assertLess(len(PHP.read_bytes()), 65536)
        self.assertRegex(hashlib.sha256(PHP.read_bytes()).hexdigest(), r"\A[a-f0-9]{64}\Z")

    def test_stdin_schema_matches_root_writer_approved_request_keys(self):
        # Static shape regression: adding an unreviewed PHP argument must fail.
        segment = self.source.split("$bloguito_image_request_keys = [", 1)[1].split("];", 1)[0]
        keys = re.findall(r"'([a-z_0-9]+)'", segment)
        expected = {
            'protocol', 'action', 'request_id', 'task_id', 'post_id', 'attachment_id',
            'candidate_number', 'candidate_count', 'candidates', 'image_sha256',
            'source_sha256', 'staged_sha256', 'alt_text', 'expected', 'release_sha256',
            'origin', 'review', 'task_created_at', 'target', 'generator_policy_sha256',
            'manifest_sha256', 'review_receipt_sha256', 'selection_mode', 'review_actor',
        }
        self.assertEqual(expected, set(keys))
        self.assertEqual(len(keys), len(set(keys)))
        expected_segment = self.source.split("$bloguito_image_expected_keys = [", 1)[1].split("];", 1)[0]
        self.assertEqual({'post_status', 'content_sha256', 'title_sha256', 'slug_sha256',
                          'excerpt_sha256', 'thumbnail_id', 'alt_sha256'},
                         set(re.findall(r"'([a-z_0-9]+)'", expected_segment)))
        self.assertIn("JSON_THROW_ON_ERROR", self.source)
        self.assertIn("strlen($bloguito_image_raw) > 8192", self.source)
        self.assertIn("$bloguito_image_exact_keys($bloguito_image_req, $bloguito_image_request_keys)",
                      self.source)

    def test_nonadmin_identity_and_independent_capability_required(self):
        for clause in (
            "'bloguito-image-writer'", "current_user_can('bloguito_write_featured_image')",
            "current_user_can('upload_files')", "current_user_can('edit_post', $bloguito_image_req['post_id'])",
            "current_user_can('edit_post', $bloguito_image_req['attachment_id'])",
            "is_super_admin($bloguito_image_user->ID)", "current_user_can('manage_options')",
            "current_user_can('edit_users')", "current_user_can('install_plugins')",
        ):
            with self.subTest(clause=clause):
                self.assertIn(clause, self.source)

    def test_only_two_metadata_keys_are_mutated_without_shell_or_post_write(self):
        self.assertRegex(self.source, r"\$bloguito_image_apply_meta\(\$bloguito_image_attachment_id, '_wp_attachment_image_alt'")
        self.assertRegex(self.source, r"\$bloguito_image_apply_meta\(\$bloguito_image_post_id, '_thumbnail_id'")
        for forbidden in (r"\beval\s*\(", r"\bexec\s*\(", r"\bsystem\s*\(",
                          r"\bshell_exec\s*\(", r"\bpassthru\s*\(",
                          r"\bwp_update_post\s*\(", r"\bwp_insert_post\s*\(",
                          r"\bmedia_handle_(?:upload|sideload)\s*\(",
                          r"\bwp_insert_attachment\s*\(", r"\bfile_put_contents\s*\(",
                          r"\bunlink\s*\(", r"\bwp_set_post_terms\s*\(",
                          r"\bupdate_option\s*\(", r"\bWP_CLI::runcommand\s*\(",
                          r"\$_(?:GET|POST|REQUEST|COOKIE)\b", r"\$argv\b"):
            with self.subTest(forbidden=forbidden):
                self.assertNotRegex(self.source, forbidden)

    def test_cas_and_attachment_bytes_rechecked_before_mutation(self):
        for assertion in (
            "post_status'] !== $bloguito_image_exp['post_status']",
            "post_type'] !== 'post'", "post_type'] !== 'attachment'",
            "post_parent'] !== $bloguito_image_post_id", "post_cas_mismatch",
            "thumbnail_or_alt_cas_mismatch", "attachment_file_sha_or_path_mismatch",
            "get_attached_file($bloguito_image_attachment_id)",
            "hash_file('sha256', $bloguito_image_real_file)",
            "realpath($bloguito_image_attached)", "wp_get_upload_dir()",
            "getimagesize($bloguito_image_real_file)",
            "hash('sha256', $bloguito_image_old_alt)",
        ):
            with self.subTest(assertion=assertion):
                self.assertIn(assertion, self.source)
        self.assertIn("['image/jpeg', 'image/png', 'image/webp']", self.source)

    def test_transaction_claimed_before_meta_writes_with_rollback_and_verified_response(self):
        positions = [
            self.source.index("$wpdb->query('START TRANSACTION')"),
            self.source.index("WHERE ID=%d FOR UPDATE"),
            self.source.index("$bloguito_image_old_meta = $bloguito_image_verify_meta()"),
            self.source.index("$bloguito_image_apply_meta($bloguito_image_attachment_id"),
            self.source.index("$bloguito_image_new_meta = $bloguito_image_verify_meta()"),
            self.source.index("$wpdb->query('COMMIT')"),
            self.source.index("'status' => 'verified'"),
        ]
        self.assertEqual(sorted(positions), positions)
        self.assertIn("$wpdb->query('ROLLBACK')", self.source)
        self.assertIn("'transaction_readback_mismatch'", self.source)
        self.assertIn("'post_commit_readback_mismatch'", self.source)
        self.assertIn("ORDER BY meta_id FOR UPDATE", self.source)
        self.assertIn('information_schema.TABLES', self.source)
        self.assertIn("($row['ENGINE'] ?? null) === 'InnoDB'", self.source)
        self.assertIn("'transactional_innodb_required'", self.source)

    def test_bad_release_sha_blocks_docker_and_php_execution(self):
        writer = load_writer()
        request = {"release_sha256": "a" * 64}
        approved = 'b' * 64
        fake_lock = ('{"protocol":1,"runtime_sha256":"' + approved + '"}').encode()
        runner = Mock()
        def files(path, size, **kwargs):
            return fake_lock if path == writer.RELEASE_LOCK else PHP.read_bytes()
        with patch.object(writer, "_trusted_file", side_effect=files):
            with self.assertRaisesRegex(ValueError, "release_not_approved"):
                writer.locked_runtime_hash(request)
        runner.assert_not_called()

    def test_fixed_runtime_cannot_claim_wordpress_e2e_without_php(self):
        php = shutil.which('php')
        if not php:
            self.skipTest('PHP CLI absent on no-Docker laptop; syntax/integration handoff required')
        result = subprocess.run([php, '-l', str(PHP)], check=False,
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
