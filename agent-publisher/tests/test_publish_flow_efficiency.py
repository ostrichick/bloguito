import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import editorial_cli
from agents.editorial import render
from agents.publisher import PublisherAgent
from test_editorial_system import NOW, sample


class PublishFlowEfficiencyTests(unittest.TestCase):
    @staticmethod
    def _publish_without_lock(agent, article, image_path=None):
        return agent._publish_editorial(article, image_path)

    def test_publish_reuses_existing_review_without_cli_review_or_inventory_sync(self):
        bundle = sample()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'bundle.json'
            path.write_text(json.dumps(bundle, ensure_ascii=False), encoding='utf-8')
            argv = ['editorial_cli.py', 'publish', str(path)]
            with patch('sys.argv', argv), \
                    patch('editorial_cli.EditorialWriterAgent.review') as review, \
                    patch('sync_wordpress_inventory.sync_inventory') as cli_sync, \
                    patch('agents.publisher.PublisherAgent.publish', return_value=901) as publish:
                editorial_cli.main()
        review.assert_not_called()
        cli_sync.assert_not_called()
        publish.assert_called_once()

    def test_publish_without_review_stops_before_wordpress_or_ai_review(self):
        bundle = sample()
        del bundle['review']
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'bundle.json'
            path.write_text(json.dumps(bundle, ensure_ascii=False), encoding='utf-8')
            argv = ['editorial_cli.py', 'publish', str(path)]
            with patch('sys.argv', argv), \
                    patch('editorial_cli.EditorialWriterAgent.review') as review, \
                    patch('agents.publisher.PublisherAgent.publish') as publish:
                with self.assertRaisesRegex(ValueError, 'publish_requires_existing_semantic_review'):
                    editorial_cli.main()
        review.assert_not_called()
        publish.assert_not_called()

    def test_publish_flow_performs_one_full_inventory_sync_and_no_ai_review(self):
        bundle = sample()
        inventory = {'checked_on': NOW.date().isoformat(), 'posts': []}
        expected_content = render(bundle['plan'], bundle['sources'])

        def fake_subprocess(cmd, **kwargs):
            if 'create' in cmd:
                return Mock(stdout='901')
            if '--fields=post_status,post_content' in cmd:
                return Mock(stdout=json.dumps({
                    'post_status': 'draft',
                    'post_content': expected_content,
                }))
            return Mock(stdout='')

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'bundle.json'
            path.write_text(json.dumps(bundle, ensure_ascii=False), encoding='utf-8')
            argv = ['editorial_cli.py', 'publish', str(path)]
            with patch('sys.argv', argv), \
                    patch('agents.editorial.datetime') as clock, \
                    patch('editorial_cli.EditorialWriterAgent.review') as review, \
                    patch('sync_wordpress_inventory.sync_inventory') as sync, \
                    patch('sync_wordpress_inventory.invalidate_inventory') as invalidate, \
                    patch('agents.editorial_writer.load_inventory', return_value=inventory), \
                    patch.object(PublisherAgent, 'publish', autospec=True,
                                 side_effect=self._publish_without_lock), \
                    patch('agents.publisher.subprocess.run', side_effect=fake_subprocess), \
                    patch.object(PublisherAgent, '_record_post'):
                clock.now.return_value = NOW
                clock.fromisoformat = datetime.fromisoformat
                editorial_cli.main()

        review.assert_not_called()
        sync.assert_called_once()
        invalidate.assert_called_once()

    def test_bundle_changed_after_review_fails_closed_before_wordpress_write(self):
        bundle = sample()
        bundle['plan']['lead']['text'] += ' 검토 후 변경'
        inventory = {'checked_on': NOW.date().isoformat(), 'posts': []}

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'bundle.json'
            path.write_text(json.dumps(bundle, ensure_ascii=False), encoding='utf-8')
            argv = ['editorial_cli.py', 'publish', str(path)]
            with patch('sys.argv', argv), \
                    patch('agents.editorial.datetime') as clock, \
                    patch('editorial_cli.EditorialWriterAgent.review') as review, \
                    patch('sync_wordpress_inventory.sync_inventory') as sync, \
                    patch('agents.editorial_writer.load_inventory', return_value=inventory), \
                    patch.object(PublisherAgent, 'publish', autospec=True,
                                 side_effect=self._publish_without_lock), \
                    patch('agents.publisher.subprocess.run') as run:
                clock.now.return_value = NOW
                clock.fromisoformat = datetime.fromisoformat
                with self.assertRaisesRegex(ValueError, 'review_not_bound_to_current_content'):
                    editorial_cli.main()

        review.assert_not_called()
        sync.assert_called_once()
        run.assert_not_called()

    def test_policy_changed_after_review_fails_closed_before_wordpress_write(self):
        bundle = sample()
        inventory = {'checked_on': NOW.date().isoformat(), 'posts': []}

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'bundle.json'
            path.write_text(json.dumps(bundle, ensure_ascii=False), encoding='utf-8')
            argv = ['editorial_cli.py', 'publish', str(path)]
            with patch('sys.argv', argv), \
                    patch('agents.editorial.datetime') as clock, \
                    patch('agents.editorial.policy_fingerprint', return_value='changed-policy'), \
                    patch('editorial_cli.EditorialWriterAgent.review') as review, \
                    patch('sync_wordpress_inventory.sync_inventory') as sync, \
                    patch('agents.editorial_writer.load_inventory', return_value=inventory), \
                    patch.object(PublisherAgent, 'publish', autospec=True,
                                 side_effect=self._publish_without_lock), \
                    patch('agents.publisher.subprocess.run') as run:
                clock.now.return_value = NOW
                clock.fromisoformat = datetime.fromisoformat
                with self.assertRaisesRegex(ValueError, 'review_not_bound_to_current_content'):
                    editorial_cli.main()

        review.assert_not_called()
        sync.assert_called_once()
        run.assert_not_called()

    def test_stale_review_fails_closed_before_wordpress_write(self):
        bundle = sample()
        bundle['review']['checked_at'] = '2026-09-12T12:00:00+09:00'
        inventory = {'checked_on': NOW.date().isoformat(), 'posts': []}

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'bundle.json'
            path.write_text(json.dumps(bundle, ensure_ascii=False), encoding='utf-8')
            argv = ['editorial_cli.py', 'publish', str(path)]
            with patch('sys.argv', argv), \
                    patch('agents.editorial.datetime') as clock, \
                    patch('editorial_cli.EditorialWriterAgent.review') as review, \
                    patch('sync_wordpress_inventory.sync_inventory') as sync, \
                    patch('agents.editorial_writer.load_inventory', return_value=inventory), \
                    patch.object(PublisherAgent, 'publish', autospec=True,
                                 side_effect=self._publish_without_lock), \
                    patch('agents.publisher.subprocess.run') as run:
                clock.now.return_value = NOW
                clock.fromisoformat = datetime.fromisoformat
                with self.assertRaisesRegex(ValueError, 'review_stale'):
                    editorial_cli.main()

        review.assert_not_called()
        sync.assert_called_once()
        run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
