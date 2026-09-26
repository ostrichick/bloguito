import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agents.workflow_metrics import increment, timed, workflow_run


class WorkflowMetricsTests(unittest.TestCase):
    def test_records_total_stage_and_counter_without_article_data(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'metrics.jsonl'
            with patch.dict(os.environ, {'EDITORIAL_METRICS_FILE': str(target)}):
                with workflow_run('revise-draft'):
                    with timed('source_fetch'):
                        pass
                    increment('wp_roundtrips', 2)

            rows = [json.loads(line) for line in target.read_text(encoding='utf-8').splitlines()]
            self.assertEqual(1, len(rows))
            self.assertEqual('revise-draft', rows[0]['action'])
            self.assertEqual('ok', rows[0]['status'])
            self.assertEqual(2, rows[0]['counters']['wp_roundtrips'])
            self.assertIn('source_fetch', rows[0]['timings_ms'])
            self.assertNotIn('bundle', rows[0])

    def test_failure_is_recorded_and_reraised(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'metrics.jsonl'
            with patch.dict(os.environ, {'EDITORIAL_METRICS_FILE': str(target)}):
                with self.assertRaisesRegex(ValueError, 'boom'):
                    with workflow_run('check'):
                        raise ValueError('boom')
            row = json.loads(target.read_text(encoding='utf-8').strip())
            self.assertEqual('error', row['status'])
            self.assertEqual('ValueError', row['error_type'])


if __name__ == '__main__':
    unittest.main()
