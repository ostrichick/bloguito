"""Cron can distinguish processing failures from legitimate editorial holds."""
import io
import json
import tempfile
import unittest
from contextlib import ExitStack, redirect_stdout
from pathlib import Path
from unittest.mock import ANY, patch

import main as pipeline
from notifier import AlertDelivery


class PipelineExitTests(unittest.TestCase):
    def test_growth_refresh_failure_fails_closed_before_planner_reads_private_state(self):
        with tempfile.TemporaryDirectory() as root, patch.object(pipeline, 'GROWTH_DIR', Path(root)):
            stale = Path(root) / 'daily-growth-plan.json'
            stale.write_text(json.dumps({'action': 'new_draft', 'target': {'brief_id': 'old'}}),
                             encoding='utf-8')
            with patch.object(
                    pipeline, 'refresh_growth_inputs',
                    side_effect=pipeline.GrowthAnalysisError('growth_wordpress_catalog_unavailable')):
                plan = pipeline.build_scheduled_growth_plan(['health'])
            self.assertEqual(plan, json.loads(stale.read_text(encoding='utf-8')))
        self.assertEqual('no_action', plan['action'])
        self.assertEqual('growth_planner_runtime_unavailable', plan['reason'])
        self.assertIn('growth_wordpress_catalog_unavailable', plan['details'])
        self.assertTrue(plan['plan_persisted'])

    def test_mismatched_growth_refresh_pair_fails_closed(self):
        with tempfile.TemporaryDirectory() as root, patch.object(pipeline, 'GROWTH_DIR', Path(root)), patch.object(pipeline, 'refresh_growth_inputs', return_value={
                'analytics_snapshot': 'google-analytics-2026-10-02.json',
                'opportunities_refreshed': False,
                'topic_scores_refreshed': True,
        }), patch.object(pipeline, '_load_private_json', side_effect=[
                {'refresh_id': 'a' * 64}, {'refresh_id': 'b' * 64},
        ]):
            plan = pipeline.build_scheduled_growth_plan(['health'])
            self.assertEqual(plan, json.loads((Path(root) / 'daily-growth-plan.json').read_text(encoding='utf-8')))
        self.assertEqual('no_action', plan['action'])
        self.assertIn('growth_input_pair_not_committed', plan['details'])

    def test_stale_inputs_are_saved_as_a_failure_decision(self):
        with tempfile.TemporaryDirectory() as root, patch.object(pipeline, 'GROWTH_DIR', Path(root)), patch.object(pipeline, 'GROWTH_WORK_LOG', Path(root) / 'absent.json'), patch.object(pipeline, 'refresh_growth_inputs', return_value={}), patch.object(pipeline, '_load_private_json', side_effect=[{'refresh_id': 'a' * 64, 'opportunity_payload_sha256': 'b' * 64}, {'refresh_id': 'a' * 64, 'opportunity_payload_sha256': 'b' * 64}]), patch.object(pipeline, 'load_policy', return_value={}), patch.object(pipeline, 'decide_daily_action', return_value={'schema_version': 1, 'action': 'no_action', 'reason': 'growth_inputs_unavailable_or_stale', 'details': ['topic_score_report_stale'], 'target': None}):
            plan = pipeline.build_scheduled_growth_plan(['health'])
            self.assertEqual('growth_inputs_unavailable_or_stale', plan['reason'])
            self.assertEqual(plan, json.loads((Path(root) / 'daily-growth-plan.json').read_text(encoding='utf-8')))

    def test_malformed_json_shape_and_unexpected_planner_error_are_fail_closed(self):
        for invalid in ('malformed_shape', 'planner_exception'):
            with self.subTest(case=invalid), tempfile.TemporaryDirectory() as root, patch.object(pipeline, 'GROWTH_DIR', Path(root)), patch.object(pipeline, 'GROWTH_WORK_LOG', Path(root) / 'absent.json'), patch.object(pipeline, 'refresh_growth_inputs', return_value={}), patch.object(pipeline, '_load_private_json', side_effect=[{'refresh_id': 'a' * 64, 'opportunity_payload_sha256': 'b' * 64}, [] if invalid == 'malformed_shape' else {'refresh_id': 'a' * 64, 'opportunity_payload_sha256': 'b' * 64}]):
                stale = Path(root) / 'daily-growth-plan.json'
                stale.write_text('{"action":"existing_improvement"}', encoding='utf-8')
                with patch.object(pipeline, 'load_policy', return_value={}), patch.object(pipeline, 'decide_daily_action', side_effect=RuntimeError('unexpected issue')):
                    plan = pipeline.build_scheduled_growth_plan(['health'])
                self.assertEqual('no_action', plan['action'])
                self.assertEqual('growth_planner_runtime_unavailable', plan['reason'])
                self.assertTrue(plan['plan_persisted'])
                self.assertEqual(plan, json.loads(stale.read_text(encoding='utf-8')))

    def test_failed_decision_save_invalidates_previous_actionable_file(self):
        with tempfile.TemporaryDirectory() as root, patch.object(pipeline, 'GROWTH_DIR', Path(root)), patch.object(pipeline, 'refresh_growth_inputs', side_effect=OSError('unavailable')), patch.object(pipeline, 'save_daily_plan', side_effect=OSError('read-only directory')), redirect_stdout(io.StringIO()):
            stale = Path(root) / 'daily-growth-plan.json'
            stale.write_text('{"action":"new_draft"}', encoding='utf-8')
            plan = pipeline.build_scheduled_growth_plan(['health'])
            self.assertFalse(plan['plan_persisted'])
            self.assertIn('daily_growth_plan_persist_failed', plan['details'])
            self.assertFalse(stale.exists())

    def exercise(self, *, candidate=True, held=False, failed=False, notification_failed=False,
                 published_delivery=None, summary_delivery=None):
        with ExitStack() as stack, redirect_stdout(io.StringIO()):
            notices = {}
            for name in ('sync_inventory', 'ensure_inventory', 'notify_published', 'notify_error'):
                notices[name] = stack.enter_context(patch.object(pipeline, name))
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
            if published_delivery is not None:
                notices['notify_published'].return_value = published_delivery
            if summary_delivery is not None:
                summary.return_value = summary_delivery
            radar.search_news.return_value = [{'keyword': 'test', 'link': 'https://example.org'}] if candidate else []
            curator.curate.return_value = {
                'link': 'https://example.org',
                'reviewed_poster_url': 'https://official.example.org/poster.jpg',
            }
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
        self.assertEqual('editorial_hold', stats['growth_outcome'])

    def test_empty_candidate_list_is_success(self):
        stats = self.exercise(candidate=False)
        self.assertEqual(0, stats['candidates'])
        self.assertEqual(0, stats['errors'])

    def test_success_is_preserved_when_summary_delivery_raises(self):
        stats = self.exercise(notification_failed=True)
        self.assertEqual(1, stats['published'])
        self.assertEqual(0, stats['errors'])
        self.assertEqual(1, stats['notification_errors'])

    def test_configured_delivery_failure_after_success_is_not_publication_failure(self):
        stats = self.exercise(published_delivery=AlertDelivery(2, 1, 1),
                              summary_delivery=AlertDelivery(0, 0, 0))
        self.assertEqual(1, stats['published'])
        self.assertEqual(0, stats['errors'])
        self.assertEqual(1, stats['notification_errors'])
        self.assertEqual(1, stats['notification_channel_failures'])
        self.assertEqual(1, stats['notification_unconfigured'])

    def test_notification_result_counts_unconfigured_and_partial_failures(self):
        stats = {'notification_errors': 0, 'notification_channel_failures': 0,
                 'notification_unconfigured': 0}
        pipeline._record_notification(stats, lambda: AlertDelivery())
        pipeline._record_notification(stats, lambda: AlertDelivery(2, 1, 1))
        pipeline._record_notification(stats, lambda: AlertDelivery(2, 0, 2))
        pipeline._record_notification(stats, lambda: AlertDelivery(1, 1, 0))
        self.assertEqual(2, stats['notification_errors'])
        self.assertEqual(3, stats['notification_channel_failures'])
        self.assertEqual(1, stats['notification_unconfigured'])

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
            curator.curate.return_value = {
                'link': 'https://example.org',
                'reviewed_poster_url': 'https://official.example.org/poster.jpg',
            }
            writer.write_article.return_value = {'title': '검토된 원고'}
            publisher.publish.return_value = 393
            stats = pipeline.run_pipeline(['health'])
            self.assertEqual(1, stats['published'])
            self.assertEqual(0, stats['errors'])
            self.assertEqual(1, stats['growth_log_errors'])

    def test_generic_scheduled_image_is_held_before_writer_or_wordpress_mutation(self):
        with ExitStack() as stack, redirect_stdout(io.StringIO()) as out:
            for name in ('sync_inventory', 'ensure_inventory', 'notify_published',
                         'notify_error', 'record_scheduled_new_draft_completion'):
                stack.enter_context(patch.object(pipeline, name))
            stack.enter_context(patch.object(pipeline, 'notify_pipeline_summary'))
            stack.enter_context(patch.object(
                pipeline, 'build_scheduled_growth_plan', return_value={
                    'action': 'new_draft', 'reason': 'test',
                    'target': {'brief_id': 'health-brief', 'category_key': 'health'},
                }))
            radar = stack.enter_context(patch.object(pipeline, 'RadarAgent')).return_value
            curator = stack.enter_context(patch.object(pipeline, 'CuratorAgent')).return_value
            writer = stack.enter_context(patch.object(pipeline, 'CopywriterAgent')).return_value
            designer = stack.enter_context(patch.object(pipeline, 'DesignerAgent')).return_value
            publisher = stack.enter_context(patch.object(pipeline, 'PublisherAgent')).return_value
            summary = pipeline.notify_pipeline_summary
            growth_complete = pipeline.record_scheduled_new_draft_completion
            notify_error = pipeline.notify_error
            radar.search_news.return_value = [{'keyword': '건강관리', 'link': 'https://example.org'}]
            curator.curate.return_value = {
                'link': 'https://example.org',
                'poster_url': 'https://unreviewed.example.org/cover.jpg',
            }
            stats = pipeline.run_pipeline(['health'])
            self.assertEqual((1, 0, 0), (stats['held'], stats['published'], stats['errors']))
            self.assertEqual('held_image_generation_unavailable', stats['image_generation_status'])
            self.assertEqual('editorial_hold', stats['growth_outcome'])
            self.assertIn('held_image_generation_unavailable', stats['held_reasons'][0])
            writer.write_article.assert_not_called()
            designer.generate_image.assert_not_called()
            publisher.publish.assert_not_called()
            growth_complete.assert_not_called()
            notify_error.assert_not_called()
            summary.assert_called_once()
            self.assertIn('no draft created', out.getvalue())

    def test_official_poster_fallback_to_unavailable_image_is_hold_not_retry(self):
        with ExitStack() as stack, redirect_stdout(io.StringIO()):
            for name in ('sync_inventory', 'ensure_inventory', 'notify_published',
                         'notify_error', 'notify_pipeline_summary'):
                stack.enter_context(patch.object(pipeline, name))
            complete = stack.enter_context(patch.object(
                pipeline, 'record_scheduled_new_draft_completion'))
            stack.enter_context(patch.object(
                pipeline, 'build_scheduled_growth_plan', return_value={
                    'action': 'new_draft', 'reason': 'test',
                    'target': {'brief_id': 'concert-brief', 'category_key': 'concert'},
                }))
            radar = stack.enter_context(patch.object(pipeline, 'RadarAgent')).return_value
            curator = stack.enter_context(patch.object(pipeline, 'CuratorAgent')).return_value
            writer = stack.enter_context(patch.object(pipeline, 'CopywriterAgent')).return_value
            designer = stack.enter_context(patch.object(pipeline, 'DesignerAgent')).return_value
            publisher = stack.enter_context(patch.object(pipeline, 'PublisherAgent')).return_value
            error_notice = pipeline.notify_error
            radar.search_news.return_value = [{'keyword': '콘서트', 'link': 'https://example.org'}]
            curator.curate.return_value = {
                'link': 'https://example.org',
                'reviewed_poster_url': 'https://official.example.org/poster.jpg',
            }
            writer.write_article.return_value = {'title': '실제 콘서트'}
            designer.generate_image.side_effect = pipeline.ScheduledImageGenerationUnavailable(
                'chatgpt_image_gen_required_unavailable_in_server_scheduler')
            stats = pipeline.run_pipeline(['concert'])
            self.assertEqual(1, stats['held'])
            self.assertEqual(0, stats['errors'])
            self.assertEqual(0, stats['published'])
            writer.write_article.assert_called_once()
            designer.generate_image.assert_called_once()
            self.assertEqual(
                'https://official.example.org/poster.jpg',
                designer.generate_image.call_args.kwargs['reviewed_poster_url'])
            publisher.publish.assert_not_called()
            complete.assert_not_called()
            error_notice.assert_not_called()

    def test_generic_hold_does_not_prevent_later_reviewed_official_poster(self):
        with ExitStack() as stack, redirect_stdout(io.StringIO()):
            for name in ('sync_inventory', 'ensure_inventory', 'notify_published',
                         'notify_error', 'notify_pipeline_summary'):
                stack.enter_context(patch.object(pipeline, name))
            complete = stack.enter_context(patch.object(
                pipeline, 'record_scheduled_new_draft_completion'))
            stack.enter_context(patch.object(
                pipeline, 'build_scheduled_growth_plan', return_value={
                    'action': 'new_draft', 'reason': 'test',
                    'target': {'brief_id': 'concert-brief', 'category_key': 'concert'},
                }))
            radar = stack.enter_context(patch.object(pipeline, 'RadarAgent')).return_value
            curator = stack.enter_context(patch.object(pipeline, 'CuratorAgent')).return_value
            writer = stack.enter_context(patch.object(pipeline, 'CopywriterAgent')).return_value
            designer = stack.enter_context(patch.object(pipeline, 'DesignerAgent')).return_value
            publisher = stack.enter_context(patch.object(pipeline, 'PublisherAgent')).return_value
            radar.search_news.return_value = [
                {'keyword': '콘서트', 'link': 'https://first.example'},
                {'keyword': '콘서트', 'link': 'https://second.example'},
            ]
            curator.curate.side_effect = [
                {'link': 'https://first.example', 'poster_url': 'https://unreviewed.example/cover.jpg'},
                {'link': 'https://second.example', 'reviewed_poster_url': 'https://official.example/poster.jpg'},
            ]
            writer.write_article.return_value = {'title': '공식 콘서트'}
            publisher.publish.return_value = 912
            stats = pipeline.run_pipeline(['concert'], limit_per_cat=1)
            self.assertEqual((1, 1, 0), (stats['held'], stats['published'], stats['errors']))
            writer.write_article.assert_called_once()
            designer.generate_image.assert_called_once()
            publisher.publish.assert_called_once()
            complete.assert_called_once_with(ANY, post_id=912, title='공식 콘서트')

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
            self.assertEqual('editorial_hold', stats['growth_outcome'])
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
            self.assertEqual('no_action', stats['growth_outcome'])
            self.assertEqual(0, stats['errors'])
            sync.assert_not_called()

    def test_input_failure_skips_wordpress_and_reports_failure_reason(self):
        with ExitStack() as stack, redirect_stdout(io.StringIO()):
            sync = stack.enter_context(patch.object(pipeline, 'sync_inventory'))
            writer = stack.enter_context(patch.object(pipeline, 'CopywriterAgent'))
            summary = stack.enter_context(patch.object(pipeline, 'notify_pipeline_summary'))
            stack.enter_context(patch.object(pipeline, 'build_scheduled_growth_plan', return_value={
                'action': 'no_action', 'reason': 'growth_inputs_unavailable_or_stale',
                'details': ['opportunity_report_stale'], 'target': None,
                'plan_persisted': True,
            }))
            stats = pipeline.run_pipeline(['health'])
        self.assertEqual('input_failure', stats['growth_outcome'])
        self.assertEqual('growth_inputs_unavailable_or_stale', stats['growth_reason'])
        self.assertEqual(0, stats['errors'])
        sync.assert_not_called()
        writer.assert_not_called()
        self.assertEqual('input_failure', summary.call_args.args[0]['growth_outcome'])

    def test_cli_returns_failure_after_partial_success(self):
        stats = {'candidates': 2, 'published': 1, 'held': 0, 'errors': 1, 'notification_errors': 0}
        with patch.object(pipeline, 'run_pipeline', return_value=stats), redirect_stdout(io.StringIO()) as out:
            self.assertEqual(1, pipeline.main(['--category', 'health']))
        self.assertIn('"status": "failed"', out.getvalue())

    def test_cli_distinguishes_normal_no_action_policy_hold_and_input_failure(self):
        for action, reason, outcome, return_code in (
                ('no_action', 'no_actionable_existing_or_eligible_new_topic', 'no_action', 0),
                ('existing_improvement', 'existing_opportunity_only', 'editorial_hold', 0),
                ('no_action', 'growth_inputs_unavailable_or_stale', 'input_failure', 1),
                ('no_action', 'growth_planner_runtime_unavailable', 'input_failure', 1)):
            with self.subTest(reason=reason):
                stats = {'candidates': 0, 'published': 0, 'held': 0, 'errors': 0,
                         'notification_errors': 0, 'growth_action': action,
                         'growth_reason': reason, 'growth_details': ['source_unavailable'],
                         'growth_outcome': outcome, 'growth_plan_persisted': True}
                with patch.object(pipeline, 'run_pipeline', return_value=stats), redirect_stdout(io.StringIO()) as out:
                    self.assertEqual(return_code, pipeline.main(['--category', 'health']))
                result = json.loads(out.getvalue().split('PIPELINE_RESULT ', 1)[1])
                self.assertEqual(reason, result['growth_reason'])
                self.assertEqual(outcome, result['growth_outcome'])
                self.assertEqual('failed' if return_code else 'completed', result['status'])
                self.assertTrue(result['growth_plan_persisted'])

    def test_cli_returns_success_for_holds(self):
        stats = {'candidates': 2, 'published': 0, 'held': 2, 'errors': 0, 'notification_errors': 0}
        with patch.object(pipeline, 'run_pipeline', return_value=stats), redirect_stdout(io.StringIO()):
            self.assertEqual(0, pipeline.main(['--category', 'health']))

    def test_cli_emits_explicit_unavailable_status_without_error_exit(self):
        stats = {'candidates': 1, 'published': 0, 'held': 1, 'errors': 0,
                 'notification_errors': 0, 'growth_action': 'new_draft',
                 'image_generation_status': 'held_image_generation_unavailable'}
        with patch.object(pipeline, 'run_pipeline', return_value=stats), redirect_stdout(io.StringIO()) as out:
            self.assertEqual(0, pipeline.main(['--category', 'health']))
        payload = out.getvalue()
        self.assertIn('"status": "held_image_generation_unavailable"', payload)
        self.assertIn('"published": 0', payload)


if __name__ == '__main__':
    unittest.main()
