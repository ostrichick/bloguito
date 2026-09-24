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
        self.bundle = {'brief': {'official_urls': ['https://example.org/official'],
                                 'existing_post_id': 243},
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

    def test_title_change_requires_separate_confirmation_and_preserves_slug(self):
        bundle = {**self.bundle, 'plan': {'title': 'Reviewed new title'}}
        updated = {**self.post, 'post_title': 'Reviewed new title', 'post_content': 'Reviewed HTML'}
        calls = []

        def execute(args, **kwargs):
            calls.append(args)
            if args[5:7] == ['post', 'get']:
                count = sum(c[5:7] == ['post', 'get'] for c in calls)
                return Mock(stdout=json.dumps(self.post if count == 1 else updated))
            return Mock(stdout='Success')

        common = [patch.object(updater, 'ROOT', Path(self.temp.name)),
                  patch.object(updater, 'sync_inventory'),
                  patch.object(updater, 'load_inventory', return_value={'posts': [self.post]}),
                  patch.object(updater, 'validate_bundle', return_value={'status': 'ready', 'reasons': []}),
                  patch.object(updater, 'fetch_sources', return_value=self.bundle['sources']),
                  patch.object(updater, 'render', return_value='Reviewed HTML'),
                  patch.object(updater, 'save_report')]
        with common[0], common[1], common[2], common[3], common[4], common[5], common[6], \
             patch.object(updater.subprocess, 'run', side_effect=execute):
            with self.assertRaisesRegex(ValueError, 'public_title_change_confirmation_required'):
                updater.update_existing_public_post(243, bundle, self.sha, confirmed=True)
        calls.clear()
        with patch.object(updater, 'ROOT', Path(self.temp.name)), \
             patch.object(updater, 'sync_inventory'), \
             patch.object(updater, 'load_inventory', return_value={'posts': [self.post]}), \
             patch.object(updater, 'validate_bundle', return_value={'status': 'ready', 'reasons': []}), \
             patch.object(updater, 'fetch_sources', return_value=self.bundle['sources']), \
             patch.object(updater, 'render', return_value='Reviewed HTML'), \
             patch.object(updater, 'save_report'), \
             patch.object(updater.subprocess, 'run', side_effect=execute):
            self.assertEqual(243, updater.update_existing_public_post(
                243, bundle, self.sha, confirmed=True, confirm_title_change=True))
        update = next(c for c in calls if c[5:7] == ['post', 'update'])
        self.assertIn('--post_title=Reviewed new title', update)
        self.assertEqual('stable-slug', updated['post_name'])

    def test_title_only_change_is_not_skipped(self):
        bundle = {**self.bundle, 'plan': {'title': 'Reviewed new title'}}
        updated = {**self.post, 'post_title': 'Reviewed new title'}
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
             patch.object(updater, 'render', return_value='Original body'), \
             patch.object(updater, 'save_report'), \
             patch.object(updater.subprocess, 'run', side_effect=execute):
            self.assertEqual(243, updater.update_existing_public_post(
                243, bundle, self.sha, confirmed=True, confirm_title_change=True))
        update = next(c for c in calls if c[5:7] == ['post', 'update'])
        self.assertIn('--post_title=Reviewed new title', update)

    def test_cannot_update_a_different_post_with_a_reviewed_bundle(self):
        with patch.object(updater, 'sync_inventory') as inventory, \
             patch.object(updater.subprocess, 'run') as command:
            with self.assertRaisesRegex(ValueError, 'reviewed_bundle_target_id_mismatch'):
                updater.update_existing_public_post(244, self.bundle, self.sha, confirmed=True)
            inventory.assert_not_called()
            command.assert_not_called()

    def test_repairs_only_blank_excerpt_from_existing_summary(self):
        original = {**self.post, 'post_excerpt': '',
                    'post_content': '<div class="bloguito-summary"><div>핵심요약</div>'
                                    '<p>실제 정보가 담긴 본문 핵심 답변입니다. 공식 조회 경로를 확인하세요.</p></div>'
                                    '<div class="bloguito-cta">광고 같은 버튼 안내</div>'}
        updated = {**original, 'post_excerpt': '실제 정보가 담긴 본문 핵심 답변입니다. 공식 조회 경로를 확인하세요.'}
        digest = hashlib.sha256(original['post_content'].encode()).hexdigest()
        calls = []

        def execute(args, **kwargs):
            calls.append(args)
            return Mock(stdout=json.dumps(original if len(calls) == 1 else updated))

        with patch.object(updater, 'ROOT', Path(self.temp.name)), \
             patch.object(updater.subprocess, 'run', side_effect=execute):
            self.assertEqual(243, updater.repair_missing_excerpt(243, digest, confirmed=True))
        update = next(args for args in calls if args[5:7] == ['post', 'update'])
        self.assertTrue(any(arg.startswith('--post_excerpt=실제 정보') for arg in update))
        self.assertFalse(any(arg.startswith('--post_content=') for arg in update))
        self.assertEqual(1, len(list((Path(self.temp.name) / 'data/editorial_runs').glob('excerpt-edit-*.json'))))

    def test_does_not_replace_human_excerpt(self):
        original = {**self.post, 'post_excerpt': '사람이 직접 설정한 요약'}
        with patch.object(updater, 'ROOT', Path(self.temp.name)), \
             patch.object(updater.subprocess, 'run', return_value=Mock(stdout=json.dumps(original))) as command:
            self.assertEqual(243, updater.repair_missing_excerpt(243, self.sha, confirmed=True))
        command.assert_called_once()

    def test_excerpt_repair_refuses_stale_content(self):
        with patch.object(updater, 'ROOT', Path(self.temp.name)), \
             patch.object(updater.subprocess, 'run', return_value=Mock(stdout=json.dumps(self.post))) as command:
            with self.assertRaisesRegex(ValueError, 'target_missing_changed_or_not_public'):
                updater.repair_missing_excerpt(243, 'f' * 64, confirmed=True)
        command.assert_called_once()


if __name__ == '__main__':
    unittest.main()
