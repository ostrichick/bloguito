"""Cron can distinguish processing failures from legitimate editorial holds."""
import io
import unittest
from contextlib import ExitStack, redirect_stdout
from unittest.mock import ANY, patch

import main as pipeline


class PipelineExitTests(unittest.TestCase):
    def exercise(self, *, candidate=True, held=False, failed=False, notification_failed=False):
        with ExitStack() as stack, redirect_stdout(io.StringIO()):
            for name in ('sync_inventory', 'ensure_inventory', 'notify_published', 'notify_error'):
                stack.enter_context(patch.object(pipeline, name))
            stack.enter_context(patch.object(pipeline, 'record_scheduled_new_draft_completion'))
            stack.enter_context(patch.object(
                pipeline, 'build_scheduled_growth_plan', return_value={
                    'action': 'new_draft',
                    'reason': 'test',
                    'target': {'brief_id': 'test-brief', 'category_key': 'health'},
                }))
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
            stats = pipeline.run_pipeline(['health'])
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

    def test_pipeline_passes_only_curator_reviewed_poster_to_designer(self):
        with ExitStack() as stack, redirect_stdout(io.StringIO()):
            for name in ('sync_inventory', 'ensure_inventory', 'notify_published', 'notify_error', 'notify_pipeline_summary'):
                stack.enter_context(patch.object(pipeline, name))
            growth_record = stack.enter_context(
                patch.object(pipeline, 'record_scheduled_new_draft_completion'))
            stack.enter_context(patch.object(
                pipeline, 'build_scheduled_growth_plan', return_value={
                    'action': 'new_draft',
                    'reason': 'test',
                    'target': {'brief_id': 'concert-brief', 'category_key': 'concert'},
                }))
            radar = stack.enter_context(patch.object(pipeline, 'RadarAgent')).return_value
            curator = stack.enter_context(patch.object(pipeline, 'CuratorAgent')).return_value
            writer = stack.enter_context(patch.object(pipeline, 'CopywriterAgent')).return_value
            designer = stack.enter_context(patch.object(pipeline, 'DesignerAgent')).return_value
            publisher = stack.enter_context(patch.object(pipeline, 'PublisherAgent')).return_value
            radar.search_news.return_value = [{'keyword': '테스트 콘서트', 'link': 'https://example.org'}]
            curator.curate.return_value = {
                'link': 'https://example.org',
                'poster_url': 'https://news.example/unreviewed.jpg',
                'reviewed_poster_url': 'https://ticket.example/official.jpg',
            }
            writer.write_article.return_value = {'title': '테스트 콘서트'}
            publisher.publish.return_value = 500
            pipeline.run_pipeline(['concert'])
            designer.generate_image.assert_called_once()
            self.assertEqual(
                designer.generate_image.call_args.kwargs['reviewed_poster_url'],
                'https://ticket.example/official.jpg',
            )
            self.assertEqual(
                radar.search_news.call_args.kwargs['selected_brief_id'], 'concert-brief')
            growth_record.assert_called_once_with(
                ANY, post_id=500, title='테스트 콘서트')

    def test_growth_log_failure_after_draft_creation_is_nonfatal(self):
        with ExitStack() as stack, redirect_stdout(io.StringIO()):
            for name in ('sync_inventory', 'ensure_inventory', 'notify_published', 'notify_error', 'notify_pipeline_summary'):
                stack.enter_context(patch.object(pipeline, name))
            stack.enter_context(patch.object(
                pipeline, 'build_scheduled_growth_plan', return_value={
                    'action': 'new_draft', 'reason': 'test',
                    'target': {'brief_id': 'test-brief', 'category_key': 'health'},
                }))
            stack.enter_context(patch.object(
                pipeline, 'record_scheduled_new_draft_completion',
                side_effect=OSError('disk full')))
            radar = stack.enter_context(patch.object(pipeline, 'RadarAgent')).return_value
            curator = stack.enter_context(patch.object(pipeline, 'CuratorAgent')).return_value
            writer = stack.enter_context(patch.object(pipeline, 'CopywriterAgent')).return_value
            stack.enter_context(patch.object(pipeline, 'DesignerAgent'))
            publisher = stack.enter_context(patch.object(pipeline, 'PublisherAgent')).return_value
            radar.search_news.return_value = [{'keyword': 'test', 'link': 'https://example.org'}]
            curator.curate.return_value = {'link': 'https://example.org'}
            writer.write_article.return_value = {'title': '검토된 원고'}
            publisher.publish.return_value = 393
            stats = pipeline.run_pipeline(['health'])
            self.assertEqual(1, stats['published'])
            self.assertEqual(0, stats['errors'])
            self.assertEqual(1, stats['growth_log_errors'])

    def test_existing_improvement_plan_skips_wordpress_and_writer(self):
        with ExitStack() as stack, redirect_stdout(io.StringIO()):
            sync = stack.enter_context(patch.object(pipeline, 'sync_inventory'))
            radar = stack.enter_context(patch.object(pipeline, 'RadarAgent'))
            writer = stack.enter_context(patch.object(pipeline, 'CopywriterAgent'))
            stack.enter_context(patch.object(pipeline, 'notify_pipeline_summary'))
            stack.enter_context(patch.object(
                pipeline, 'build_scheduled_growth_plan', return_value={
                    'action': 'existing_improvement',
                    'reason': 'actionable_existing_page_before_new_content',
                    'target': {'post_id': 345, 'title': '고속버스 취소표'},
                }))
            stats = pipeline.run_pipeline(['transport'])
            self.assertEqual('existing_improvement', stats['growth_action'])
            self.assertEqual(0, stats['published'])
            sync.assert_not_called()
            radar.assert_not_called()
            writer.assert_not_called()

    def test_no_action_plan_is_success_without_wordpress_access(self):
        with ExitStack() as stack, redirect_stdout(io.StringIO()):
            sync = stack.enter_context(patch.object(pipeline, 'sync_inventory'))
            stack.enter_context(patch.object(pipeline, 'notify_pipeline_summary'))
            stack.enter_context(patch.object(
                pipeline, 'build_scheduled_growth_plan', return_value={
                    'action': 'no_action', 'reason': 'no_actionable_existing_or_eligible_new_topic',
                    'target': None,
                }))
            stats = pipeline.run_pipeline(['health'])
            self.assertEqual('no_action', stats['growth_action'])
            self.assertEqual(0, stats['errors'])
            sync.assert_not_called()

    def test_cli_returns_failure_after_partial_success(self):
        stats = {'candidates': 2, 'published': 1, 'held': 0, 'errors': 1, 'notification_errors': 0}
        with patch.object(pipeline, 'run_pipeline', return_value=stats), redirect_stdout(io.StringIO()) as out:
            self.assertEqual(1, pipeline.main(['--category', 'health']))
        self.assertIn('"status": "failed"', out.getvalue())

    def test_cli_returns_success_for_holds(self):
        stats = {'candidates': 2, 'published': 0, 'held': 2, 'errors': 0, 'notification_errors': 0}
        with patch.object(pipeline, 'run_pipeline', return_value=stats), redirect_stdout(io.StringIO()):
            self.assertEqual(0, pipeline.main(['--category', 'health']))


if __name__ == '__main__':
    unittest.main()
