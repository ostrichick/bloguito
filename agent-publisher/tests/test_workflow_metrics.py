import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agents.workflow_metrics import (
    summarize_timing_categories,
    timed,
    timing_category,
    workflow_run,
    increment,
)


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
            self.assertEqual('test', rows[0]['run_context'])
            self.assertEqual('ok', rows[0]['status'])
            self.assertEqual(2, rows[0]['counters']['wp_roundtrips'])
            self.assertIn('source_fetch', rows[0]['timings_ms'])
            self.assertIn('source', rows[0]['timing_categories_ms'])
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

    def test_common_timing_categories_cover_workflow_stages(self):
        self.assertEqual('validation', timing_category('validation_tests'))
        self.assertEqual('source', timing_category('source_recheck'))
        self.assertEqual('review', timing_category('event_delta_semantic_review'))
        self.assertEqual('wp', timing_category('wp_guarded_mutation'))
        self.assertEqual('browser', timing_category('browser_qa'))
        self.assertEqual('image', timing_category('featured_image_generate'))
        self.assertEqual('other', timing_category('misc_stage'))

    def test_category_summary_supports_new_and_legacy_metrics_rows(self):
        summary = summarize_timing_categories([
            {
                'timing_categories_ms': {'validation': 20.0, 'source': 10.0},
                'timings_ms': {'validation_tests': 999.0},
            },
            {
                'timings_ms': {
                    'semantic_review': 30.0,
                    'wp_target_read': 40.0,
                    'browser_qa': 50.0,
                    'featured_image_generate': 60.0,
                },
            },
        ])
        self.assertEqual(2, summary['runs'])
        self.assertEqual(20.0, summary['category_totals_ms']['validation'])
        self.assertEqual(10.0, summary['category_totals_ms']['source'])
        self.assertEqual(30.0, summary['category_totals_ms']['review'])
        self.assertEqual(40.0, summary['category_totals_ms']['wp'])
        self.assertEqual(50.0, summary['category_totals_ms']['browser'])
        self.assertEqual(60.0, summary['category_totals_ms']['image'])
        self.assertEqual(10.0, summary['category_mean_per_run_ms']['validation'])


if __name__ == '__main__':
    unittest.main()
