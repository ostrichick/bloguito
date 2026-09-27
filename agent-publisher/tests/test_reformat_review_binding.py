"""Renderer migrations cannot turn an old review into a current approval."""
import copy
import json
import shutil
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import Mock, patch

from agents import editorial
from agents.publisher import PublisherAgent
from tests.test_editorial_system import NOW, sample


class ReformatReviewBindingTests(unittest.TestCase):
    def exercise(self, bundle, rejected=None):
        source_root = editorial.ROOT
        review_before = copy.deepcopy(bundle.get('review'))
        with tempfile.TemporaryDirectory() as folder, ExitStack() as stack:
            root = Path(folder) / 'agent-publisher'
            root.mkdir()
            (root.parent / 'docs').mkdir()
            shutil.copy2(source_root / 'editorial_policy.json', root / 'editorial_policy.json')
            shutil.copy2(source_root.parent / 'docs' / 'EDITORIAL_SYSTEM.md',
                         root.parent / 'docs' / 'EDITORIAL_SYSTEM.md')
            index = root / 'drafts.json'
            index.write_text(json.dumps([{'id': 393, 'fact_manifest': {'editorial_bundle': bundle}}]),
                             encoding='utf-8')
            before = index.read_bytes()
            old = editorial.render_legacy(bundle['plan'], bundle['sources'])
            desired = editorial.render(bundle['plan'], bundle['sources'])
            live = {'ID': 393, 'post_status': 'draft', 'post_title': bundle['plan']['title'],
                    'post_content': old}
            inventory = {'checked_on': NOW.date().isoformat(), 'posts': [live]}
            calls = []

            def run(args, **kwargs):
                calls.append(args)
                if 'update' in args:
                    live['post_content'] = desired
                return Mock(stdout=json.dumps(live))

            real_validator = editorial.validate_bundle
            stack.enter_context(patch('agents.editorial.ROOT', root))
            stack.enter_context(patch('agents.publisher.DRAFTS_INDEX_FILE', index))
            stack.enter_context(patch('agents.editorial_writer.load_inventory', return_value=inventory))
            stack.enter_context(patch('sync_wordpress_inventory.sync_inventory'))
            stack.enter_context(patch('sync_wordpress_inventory.hydrate_post', side_effect=lambda i, p: i))
            stack.enter_context(patch('sync_wordpress_inventory.invalidate_inventory'))
            stack.enter_context(patch('agents.editorial.validate_bundle',
                                     side_effect=lambda b, i: real_validator(b, i, NOW)))
            stack.enter_context(patch('agents.publisher.subprocess.run', side_effect=run))
            record = stack.enter_context(patch.object(PublisherAgent, '_record_post'))
            if rejected:
                with self.assertRaisesRegex(ValueError, rejected):
                    PublisherAgent().reformat_draft(393)
                self.assertFalse(any('update' in args for args in calls))
                record.assert_not_called()
                self.assertEqual(before, index.read_bytes())
                self.assertEqual(old, live['post_content'])
            else:
                self.assertEqual(393, PublisherAgent().reformat_draft(393))
                self.assertEqual(desired, live['post_content'])
                self.assertTrue(any('update' in args for args in calls))
                stored = record.call_args.kwargs['fact_manifest']['editorial_bundle']
                self.assertEqual(review_before, stored['review'])

    def test_current_review_allows_renderer_migration_without_resigning(self):
        self.exercise(sample())

    def test_wrong_content_digest_is_rejected(self):
        bundle = sample()
        bundle['review']['digest'] = 'unreviewed-content'
        self.exercise(bundle, 'review_not_bound_to_current_content')

    def test_changed_policy_is_rejected(self):
        bundle = sample()
        bundle['review']['policy_digest'] = 'older-policy'
        self.exercise(bundle, 'review_not_bound_to_current_content')

    def test_expired_review_is_rejected(self):
        bundle = sample()
        bundle['review']['checked_at'] = '2026-09-12T12:00:00+09:00'
        self.exercise(bundle, 'review_stale')


if __name__ == '__main__':
    unittest.main()
