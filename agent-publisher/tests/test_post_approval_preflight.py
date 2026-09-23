"""Approval preparation is read-only and fails closed on concurrent changes."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from scripts import prepare_post_approval as approval


class ApprovalPreparationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / 'tmp').mkdir()
        self.out = self.root / 'tmp' / 'pilot'
        self.original = {'ID': 137, 'post_title': 'Original title',
            'post_content': '<h2>Old</h2><p>Original content</p>',
            'post_status': 'publish', 'post_name': 'stable-slug',
            'post_date': '2026-09-10 10:00:00', 'post_excerpt': ''}
        self.draft = {'ID': 55, 'post_title': 'Another private draft',
            'post_content': 'Sensitive private draft', 'post_status': 'draft'}
        self.bundle = {'brief': {'existing_post_id': 137, 'official_urls':
             ['https://example.org/official']}, 'plan': {'title': 'Original title',
              'lead': {'text': 'Reviewed answer'}},
              'sources': [{'url': 'https://example.org/official', 'sha256': 'a' * 64}]}
        self.bundle_path = self.root / 'tmp' / 'bundle.json'
        self.bundle_path.write_text(json.dumps(self.bundle), encoding='utf-8')

    def _patch(self, *, report=None, sources=None, post=None, inventory=None):
        report = report or {'status': 'ready', 'reasons': [], 'details': []}
        sources = sources if sources is not None else self.bundle['sources']
        self.stack = self.enterContext(patch.object(approval, 'ROOT', self.root))
        self.fetch = self.enterContext(patch.object(approval, 'fetch_sources', return_value=sources))
        self.validate = self.enterContext(patch.object(approval, 'validate_bundle', return_value=report))
        self.render = self.enterContext(patch.object(approval, 'render', return_value='<h2>New</h2><p>Reviewed answer</p>'))
        self.wp = self.enterContext(patch.object(approval, 'live_post_and_inventory',
                            return_value=(post or self.original, inventory or [self.original, self.draft])))

    def test_full_read_only_preflight_preserves_original_and_excludes_private_draft(self):
        self._patch()
        result = approval.prepare(137, self.bundle_path, self.out)
        self.assertEqual('ready', result['preflight_status'])
        self.assertEqual(hashlib.sha256(self.original['post_content'].encode()).hexdigest(),
                         result['original_stored_content_sha256'])
        self.assertEqual(self.original, json.loads((self.out / 'post-original.PRIVATE.json').read_text(encoding='utf-8')))
        self.assertIn('Old', (self.out / 'content-diff.txt').read_text(encoding='utf-8'))
        self.assertIn('Reviewed answer', (self.out / 'compare-preview.html').read_text(encoding='utf-8'))
        self.assertNotIn('Sensitive private draft', (self.out / 'approval-manifest.json').read_text(encoding='utf-8'))
        self.assertNotIn('Sensitive private draft', (self.out / 'compare-preview.html').read_text(encoding='utf-8'))
        self.assertEqual([self.draft], self.validate.call_args.args[1]['posts'])
        self.assertEqual('prepared_not_authorized', result['approval_status'])
        self.assertFalse(result['wordpress_write_performed'])

    def test_source_change_blocks_but_preserves_backup(self):
        self._patch(sources=[{'url': 'https://example.org/official', 'sha256': 'b' * 64}])
        result = approval.prepare(137, self.bundle_path, self.out)
        self.assertEqual('blocked', result['preflight_status'])
        self.assertIn('official_sources_changed_since_review', result['reasons'])
        self.assertTrue((self.out / 'post-original.PRIVATE.json').exists())

    def test_semantic_review_failure_blocks(self):
        self._patch(report={'status': 'needs_review', 'reasons': ['semantic_review_failed'], 'details': []})
        result = approval.prepare(137, self.bundle_path, self.out)
        self.assertIn('semantic_review_failed', result['reasons'])

    def test_wrong_id_and_outside_tmp_fail_before_remote_access(self):
        self._patch()
        with self.assertRaisesRegex(ValueError, 'bundle_target_post_id_mismatch'):
            approval.prepare(244, self.bundle_path, self.out)
        with self.assertRaisesRegex(ValueError, 'approval_output_must_be_inside_gitignored_tmp'):
            approval.prepare(137, self.bundle_path, self.root / 'docs' / 'public')
        self.wp.assert_not_called()

    def test_never_overwrites_existing_package(self):
        self._patch()
        self.out.mkdir()
        (self.out / 'post-original.PRIVATE.json').write_text('keep', encoding='utf-8')
        with self.assertRaises(FileExistsError):
            approval.prepare(137, self.bundle_path, self.out)
        self.wp.assert_not_called()
        self.assertEqual('keep', (self.out / 'post-original.PRIVATE.json').read_text(encoding='utf-8'))

    def test_live_inventory_disagreement_fails_closed(self):
        with patch.object(approval, 'read_wp_json', side_effect=[
            [{**self.original, 'post_content': 'Another editor changed body'}], self.original]):
            with self.assertRaisesRegex(ValueError, 'live_post_inventory_disagree'):
                approval.live_post_and_inventory('bloguito', 137)

    def test_ssh_command_allowlist_and_alias_rejection(self):
        with self.assertRaisesRegex(ValueError, 'read_only_wp_commands_only'):
            approval.read_wp_json('bloguito', ['post', 'update', '137'])
        with self.assertRaisesRegex(ValueError, 'read_only_wp_commands_only'):
            approval.read_wp_json('bloguito', ['post', 'get', '137;touch /tmp/unsafe', '--format=json'])
        with self.assertRaisesRegex(ValueError, 'invalid_ssh_alias'):
            approval.read_wp_json('bloguito; echo breach', ['post', 'get', '137'])


if __name__ == '__main__':
    unittest.main()
