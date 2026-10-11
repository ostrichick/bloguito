import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.summarize_workflow_metrics import summarize, summarize_cohorts, compare_code_versions


class WorkflowMetricsSummaryTests(unittest.TestCase):
    def test_comparison_pairs_only_matching_successful_versioned_cohorts(self):
        def make(version, total, route='fast', counters=None):
            return {'action': 'edit-post', 'run_context': 'live', 'status': 'ok',
                    'code_version': version, 'release_revision': 'release-'+version,
                    'route': route, 'transport': 'direct',
                    'workload_signature': 'sources-2/image-no',
                    'total_ms': total, 'counters': counters or {}}
        rows = [make('old', 200, counters={'ssh_roundtrips': 4}) for _ in range(5)]
        rows += [make('new', 100, counters={'ssh_roundtrips': 2}) for _ in range(5)]
        rows += [make('old', 900, route='standard')]
        rows += [make('new', 1, route='standard')]
        result = compare_code_versions(rows, 'old', 'new')
        by_route = {r['route']: r for r in result['comparisons']}
        self.assertTrue(by_route['fast']['comparison_ready'])
        self.assertEqual(-50.0, by_route['fast']['median_change_percent'])
        self.assertEqual(-50.0, by_route['fast']['ssh_change_percent'])
        self.assertIsNone(by_route['fast']['wp_change_percent'])
        self.assertFalse(by_route['standard']['comparison_ready'])
        self.assertIsNone(by_route['standard']['median_change_percent'])
        self.assertIn('not_causal', result['interpretation'])

    def test_different_releases_with_same_code_version_are_not_pooled(self):
        rows = []
        for version in ('old', 'new'):
            for release in ('release-1', 'release-2'):
                for _ in range(5):
                    rows.append({'action':'edit-post','run_context':'live','status':'ok',
                                 'code_version':version,'release_revision':release,
                                 'route':'fast','transport':'direct','total_ms':100})
                    rows[-1]['workload_signature'] = 'sources-2/image-no'
        cohorts = summarize_cohorts(rows)['cohorts']
        self.assertEqual(4, len(cohorts))
        comparison = compare_code_versions(rows, 'old', 'new')['comparisons'][0]
        self.assertEqual('release_ambiguous', comparison['reason'])
        self.assertFalse(comparison['comparison_ready'])
        self.assertIsNone(comparison['median_change_percent'])

    def test_comparison_never_infers_missing_samples_or_counters_are_zero(self):
        rows = [{'action':'x', 'run_context':'live', 'status':'ok', 'code_version':'old',
                 'route':'fast', 'transport':'ssh', 'total_ms':100} for _ in range(6)]
        result = compare_code_versions(rows, 'old', 'new')['comparisons'][0]
        self.assertEqual(0, result['after_count'])
        self.assertFalse(result['comparison_ready'])
        self.assertIsNone(result['median_change_percent'])
        with self.assertRaisesRegex(ValueError, 'two_distinct'):
            compare_code_versions(rows, 'old', 'old')
    def test_versioned_cohorts_never_pool_routes_or_releases(self):
        rows = [
            {"action": "ssh-edit-post", "run_context": "live", "status": "ok",
             "code_version": "a", "route": "fast", "transport": "direct",
             "total_ms": 100, "counters": {"ssh_roundtrips": 2}},
            {"action": "ssh-edit-post", "run_context": "live", "status": "ok",
             "code_version": "b", "route": "fast", "transport": "direct",
             "total_ms": 300, "counters": {"ssh_roundtrips": 6}},
            {"action": "ssh-edit-post", "run_context": "live", "status": "ok",
             "code_version": "a", "route": "standard", "transport": "direct",
             "total_ms": 400, "counters": {"ssh_roundtrips": 8}},
        ]
        result = summarize_cohorts(rows)
        self.assertEqual(3, result["rows"])
        self.assertEqual(3, len(result["cohorts"]))
        self.assertTrue(all(not x["comparison_ready"] for x in result["cohorts"]))
        self.assertEqual(
            [100.0, 400.0, 300.0],
            [x["total_ms_median"] for x in result["cohorts"]])
        self.assertIn("host_imagegen", result["coverage_excludes"])

    def test_missing_counters_are_unknown_and_versions_are_visible(self):
        result = summarize([{'action': 'image', 'run_context': 'live', 'status': 'ok',
                             'code_version': 'version-a', 'total_ms': 100, 'counters': {}}])
        self.assertIsNone(result['actions']['image']['wp_roundtrips_mean'])
        self.assertIsNone(result['actions']['image']['ssh_roundtrips_mean'])
        self.assertEqual({'version-a': 1}, result['code_versions'])
        self.assertEqual(0, result['unversioned_rows'])

    def test_no_proven_workload_signature_never_compares_even_five_synthetic_runs(self):
        rows = []
        for version in ('old', 'new'):
            rows += [{'action': 'ssh-edit-post', 'run_context': 'live', 'status': 'ok',
                      'code_version': version, 'release_revision': version+'-release',
                      'route': 'fast', 'transport': 'direct', 'total_ms': 50}
                     for _ in range(5)]
        result = compare_code_versions(rows, 'old', 'new')
        self.assertFalse(result['comparisons'][0]['comparison_ready'])
        self.assertIsNone(result['comparisons'][0]['median_change_percent'])
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


if __name__ == "__main__":
    unittest.main()
