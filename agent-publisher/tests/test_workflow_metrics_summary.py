import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.summarize_workflow_metrics import summarize


class WorkflowMetricsSummaryTests(unittest.TestCase):
    def test_groups_successful_live_runs_and_ignores_test_rows(self):
        rows = [
            {"action": "edit-post", "run_context": "live", "status": "ok", "total_ms": 100,
             "timings_ms": {"wp_target_read": 40}, "counters": {"wp_roundtrips": 2}},
            {"action": "edit-post", "run_context": "live", "status": "ok", "total_ms": 300,
             "timings_ms": {"wp_target_read": 60}, "counters": {"wp_roundtrips": 2}},
            {"action": "edit-post", "run_context": "test", "status": "ok", "total_ms": 1,
             "timings_ms": {}, "counters": {"wp_roundtrips": 99}},
            {"action": "edit-post", "run_context": "live", "status": "error", "total_ms": 2,
             "timings_ms": {}, "counters": {}},
        ]
        result = summarize(rows)
        action = result["actions"]["edit-post"]
        self.assertEqual(2, result["rows"])
        self.assertEqual(200.0, action["total_ms_median"])
        self.assertEqual(2.0, action["wp_roundtrips_mean"])
        self.assertEqual(50.0, action["timings_ms_mean"]["wp_target_read"])
        self.assertEqual(100.0, action["timing_categories"]["category_totals_ms"]["wp"])
        self.assertEqual(50.0, action["timing_categories"]["category_mean_per_run_ms"]["wp"])


if __name__ == "__main__":
    unittest.main()
