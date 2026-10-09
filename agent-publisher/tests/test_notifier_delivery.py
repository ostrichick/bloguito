"""Notification delivery is observable without sending real network traffic."""

import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import notifier


class Response:
    def __init__(self, status):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class NotificationDeliveryTests(unittest.TestCase):
    def setUp(self):
        for key in ('TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID', 'DISCORD_WEBHOOK_URL'):
            self.enterContext(patch.object(notifier, key, ''))

    def enterContext(self, context):
        if not hasattr(self, '_patches'):
            self._patches = []
        value = context.__enter__()
        self.addCleanup(context.__exit__, None, None, None)
        return value

    def test_missing_or_incomplete_configuration_is_not_delivery_failure(self):
        with patch.object(notifier.urllib.request, 'urlopen') as network, redirect_stdout(io.StringIO()):
            self.assertEqual(notifier.AlertDelivery(), notifier.notify_error('stage', 'failed'))
            with patch.object(notifier, 'TELEGRAM_BOT_TOKEN', 'incomplete'):
                self.assertEqual(notifier.AlertDelivery(), notifier.notify_error('stage', 'failed'))
            network.assert_not_called()

    def test_configured_transport_exception_and_non_success_status_are_counted(self):
        with patch.object(notifier, 'TELEGRAM_BOT_TOKEN', 'placeholder'), patch.object(notifier, 'TELEGRAM_CHAT_ID', '123'), patch.object(notifier, 'DISCORD_WEBHOOK_URL', 'https://example.invalid/webhook'), redirect_stdout(io.StringIO()):
            with patch.object(notifier.urllib.request, 'urlopen', side_effect=[OSError('offline'), Response(403)]) as network:
                delivery = notifier.notify_error('stage', 'failed')
                self.assertEqual(notifier.AlertDelivery(2, 0, 2), delivery)
                self.assertEqual(2, network.call_count)

    def test_partial_delivery_counts_failed_channel_without_losing_success(self):
        with patch.object(notifier, 'TELEGRAM_BOT_TOKEN', 'placeholder'), patch.object(notifier, 'TELEGRAM_CHAT_ID', '123'), patch.object(notifier, 'DISCORD_WEBHOOK_URL', 'https://example.invalid/webhook'), redirect_stdout(io.StringIO()):
            with patch.object(notifier.urllib.request, 'urlopen', side_effect=[Response(200), OSError('offline')]) as network:
                delivery = notifier.notify_published('article', 'health', 'Post #1')
                self.assertEqual(notifier.AlertDelivery(2, 1, 1), delivery)
                self.assertEqual(2, network.call_count)
            with patch.object(notifier.urllib.request, 'urlopen', side_effect=[Response(200), Response(403)]):
                self.assertTrue(notifier.send_alert('test'))  # legacy any-channel bool

    def test_summary_includes_growth_reason_and_failure_details(self):
        captured = []

        def fake_send(message, title):
            captured.append((message, title))
            return notifier.AlertDelivery()

        with patch.object(notifier, 'send_alert_report', side_effect=fake_send):
            result = notifier.notify_pipeline_summary({
                'growth_action': 'no_action', 'growth_outcome': 'input_failure',
                'growth_reason': 'growth_inputs_unavailable_or_stale',
                'growth_details': ['topic_score_report_stale'],
                'notification_errors': 2, 'notification_unconfigured': 1,
            })
        self.assertEqual(notifier.AlertDelivery(), result)
        self.assertIn('growth_inputs_unavailable_or_stale', captured[0][0])
        self.assertIn('topic_score_report_stale', captured[0][0])
        self.assertIn('알림 전송 실패 (일일 요약 전)', captured[0][0])

    def test_existing_improvement_target_stays_on_planner_line(self):
        captured = []
        with patch.object(notifier, 'send_alert_report', side_effect=lambda msg, title: (
                captured.append(msg) or notifier.AlertDelivery())):
            notifier.notify_pipeline_summary({
                'growth_action': 'existing_improvement',
                'growth_target': {'post_id': 345},
                'growth_reason': 'existing_opportunity_only',
            })
        self.assertIn('Growth Planner</b>: existing_improvement (Post #345)', captured[0])
        self.assertIn('판정 사유</b>: existing_opportunity_only', captured[0])


if __name__ == '__main__':
    unittest.main()
