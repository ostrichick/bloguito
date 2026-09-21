import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from agents import editorial_updater as updater


class ExistingPublicPostUpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.post = {'ID': 243, 'post_status': 'publish', 'post_title': 'Existing title',
                     'post_content': 'Original body', 'post_name': 'stable-slug'}
        self.bundle = {'brief': {'official_urls': ['https://example.org/official']},
                       'sources': [{'url': 'https://example.org/official', 'sha256': 'verified'}],
                       'plan': {}}
        self.sha = hashlib.sha256(self.post['post_content'].encode()).hexdigest()

    def test_preserves_identity_and_verifies_content(self):
        updated = {**self.post, 'post_content': 'Reviewed HTML'}
        calls = []

        def execute(args, **kwargs):
            calls.append(args)
            if args[5:7] == ['post', 'get']:
                count = sum(c[5:7] == ['post', 'get'] for c in calls)
                return Mock(stdout=json.dumps(self.post if count == 1 else updated))
            return Mock(stdout='Success')

        with patch.object(updater, 'ROOT', Path(self.temp.name)), \
             patch.object(updater, 'sync_inventory'), \
             patch.object(updater, 'load_inventory', return_value={'posts': [self.post]}), \
             patch.object(updater, 'validate_bundle', return_value={'status': 'ready', 'reasons': []}), \
             patch.object(updater, 'fetch_sources', return_value=self.bundle['sources']), \
             patch.object(updater, 'render', return_value='Reviewed HTML'), \
             patch.object(updater, 'save_report'), \
             patch.object(updater.subprocess, 'run', side_effect=execute):
            self.assertEqual(243, updater.update_existing_public_post(243, self.bundle, self.sha, confirmed=True))
        updates = [c for c in calls if c[5:7] == ['post', 'update']]
        self.assertEqual(1, len(updates))
        self.assertIn('--post_content=Reviewed HTML', updates[0])
        self.assertFalse(any(a.startswith('--post_status=') for a in updates[0]))
        self.assertEqual(1, len(list((Path(self.temp.name) / 'data/editorial_runs').glob('public-edit-*.json'))))

    def test_rejects_changed_post_before_any_update(self):
        changed = {**self.post, 'post_content': 'Another editor changed this'}
        with patch.object(updater, 'ROOT', Path(self.temp.name)), \
             patch.object(updater, 'sync_inventory'), \
             patch.object(updater, 'load_inventory', return_value={'posts': [changed]}), \
             patch.object(updater.subprocess, 'run') as command:
            with self.assertRaisesRegex(ValueError, 'target_missing_changed_or_not_public'):
                updater.update_existing_public_post(243, self.bundle, self.sha, confirmed=True)
            command.assert_not_called()

    def test_requires_explicit_confirmation(self):
        with self.assertRaisesRegex(ValueError, 'specific_public_post_update_confirmation_required'):
            updater.update_existing_public_post(243, self.bundle, self.sha)


if __name__ == '__main__':
    unittest.main()
