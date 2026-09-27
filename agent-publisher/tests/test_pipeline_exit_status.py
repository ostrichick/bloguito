"""Cron can distinguish processing failures from legitimate editorial holds."""
import io
import unittest
from contextlib import ExitStack, redirect_stdout
from unittest.mock import patch

import main as pipeline


class PipelineExitTests(unittest.TestCase):
    def exercise(self, *, candidate=True, held=False, failed=False, notification_failed=False):
        with ExitStack() as stack, redirect_stdout(io.StringIO()):
            for name in ('sync_inventory', 'ensure_inventory', 'notify_published', 'notify_error'):
                stack.enter_context(patch.object(pipeline, name))
            stack.enter_context(patch.object(pipeline.time, 'sleep'))
            radar = stack.enter_context(patch.object(pipeline, 'RadarAgent')).return_value
            curator = stack.enter_context(patch.object(pipeline, 'CuratorAgent')).return_value
            writer = stack.enter_context(patch.object(pipeline, 'CopywriterAgent')).return_value
            stack.enter_context(patch.object(pipeline, 'DesignerAgent'))
            publisher = stack.enter_context(patch.object(pipeline, 'PublisherAgent')).return_value
            summary = stack.enter_context(patch.object(pipeline, 'notify_pipeline_summary'))
            radar.search_news.return_value = [{'keyword': 'test', 'link': 'https://example.org'}] if candidate else []
            curator.curate.return_value = {'link': 'https://example.org'}
            writer.write_article.return_value = None if held else {'title': '검토된 원고'}
            publisher.publish.return_value = 393
            if failed:
                publisher.publish.side_effect = RuntimeError('storage unavailable')
            if notification_failed:
                summary.side_effect = RuntimeError('notification unavailable')
            stats = pipeline.run_pipeline(['life-health'])
            return stats

    def test_processing_failure_is_counted_and_returned(self):
        stats = self.exercise(failed=True)
        self.assertEqual(1, stats['errors'])
        self.assertEqual(0, stats['published'])

    def test_editorial_hold_is_not_a_processing_failure(self):
        stats = self.exercise(held=True)
        self.assertEqual(1, stats['held'])
        self.assertEqual(0, stats['errors'])

    def test_empty_candidate_list_is_success(self):
        stats = self.exercise(candidate=False)
        self.assertEqual(0, stats['candidates'])
        self.assertEqual(0, stats['errors'])

    def test_success_is_preserved_when_summary_delivery_raises(self):
        stats = self.exercise(notification_failed=True)
        self.assertEqual(1, stats['published'])
        self.assertEqual(0, stats['errors'])
        self.assertEqual(1, stats['notification_errors'])

    def test_cli_returns_failure_after_partial_success(self):
        stats = {'candidates': 2, 'published': 1, 'held': 0, 'errors': 1, 'notification_errors': 0}
        with patch.object(pipeline, 'run_pipeline', return_value=stats), redirect_stdout(io.StringIO()) as out:
            self.assertEqual(1, pipeline.main(['--category', 'life-health']))
        self.assertIn('"status": "failed"', out.getvalue())

    def test_cli_returns_success_for_holds(self):
        stats = {'candidates': 2, 'published': 0, 'held': 2, 'errors': 0, 'notification_errors': 0}
        with patch.object(pipeline, 'run_pipeline', return_value=stats), redirect_stdout(io.StringIO()):
            self.assertEqual(0, pipeline.main(['--category', 'life-health']))


if __name__ == '__main__':
    unittest.main()
