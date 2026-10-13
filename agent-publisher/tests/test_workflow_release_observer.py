"""No synthetic speedup when runtime metrics lack homogeneous samples."""
import math
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.ops.workflow_release_observer import release_report, read_rows, metrics_bytes

OLD, NEW = 'a'*40, 'b'*40


def sample(release, *, time=100, route='fast', workload='sources-2/image-no', status='ok', **other):
    return {'run_context': 'live', 'status': status, 'release_revision': release,
            'action': 'edit-post', 'route': route, 'transport': 'direct',
            'workload_signature': workload, 'total_ms': time,
            'code_version': ('c' if release == OLD else 'd') * 64,
            'counters': {'wp_roundtrips': 3, 'ssh_roundtrips': 1}, **other}


class ObserverTests(unittest.TestCase):
    def test_same_workload_five_each_reports_timing_and_counters(self):
        rows = [sample(OLD, time=200) for _ in range(5)] + [sample(NEW) for _ in range(5)]
        result = release_report(rows, NEW, before_revision=OLD)
        self.assertEqual(1, result['comparable_cohort_count'])
        comparison, = result['comparisons']
        self.assertEqual(-50, comparison['change_percent']['total_ms'])
        self.assertEqual(0, comparison['change_percent']['ssh_roundtrips'])

    def test_different_workload_or_route_cannot_be_pooled(self):
        rows = [sample(OLD) for _ in range(5)] + [sample(NEW, workload='sources-5/image-yes') for _ in range(5)]
        rows += [sample(NEW, route='standard') for _ in range(5)]
        result = release_report(rows, NEW, before_revision=OLD)
        self.assertEqual(0, result['comparable_cohort_count'])
        self.assertEqual('unmeasured', result['performance_claim'])

    def test_missing_workload_or_counters_never_claims_improvement(self):
        rows = [sample(OLD, time=100) for _ in range(5)]
        rows += [sample(NEW, time=20, workload=None) for _ in range(5)]
        result = release_report(rows, NEW, before_revision=OLD)
        self.assertEqual(5, result['missing_comparison_dimensions']['after'])
        self.assertEqual(0, result['comparable_cohort_count'])
        rows = [sample(OLD) for _ in range(5)] + [sample(NEW, counters={}) for _ in range(5)]
        result = release_report(rows, NEW, before_revision=OLD)
        comparison, = result['comparisons']
        self.assertIsNone(comparison['change_percent']['wp_roundtrips'])

    def test_invalid_input_and_test_rows_are_excluded(self):
        with self.assertRaisesRegex(ValueError, 'invalid_metric_record'):
            read_rows(b'{bad\n')
        with self.assertRaisesRegex(ValueError, 'invalid_ssh_host'):
            metrics_bytes(ssh_host='host;rm')
        with self.assertRaisesRegex(ValueError, 'invalid_ssh_host'):
            metrics_bytes(ssh_host='-V')
        rows = [sample(NEW), sample(OLD, status='error'),
                {**sample(NEW), 'run_context': 'test'}]
        result = release_report(rows, NEW, before_revision=OLD)
        self.assertEqual(1, result['installed_release_success_rows'])
        self.assertEqual(0, result['previous_release_success_rows'])

    def test_mixed_runtime_code_with_same_release_must_not_make_speedup_claim(self):
        old = [sample(OLD, time=200) for _ in range(5)]
        new = [sample(NEW, time=100) for _ in range(4)]
        new.append(sample(NEW, time=100, code_version='e'*64))
        report = release_report(old + new, NEW, before_revision=OLD)
        self.assertEqual('unmeasured', report['performance_claim'])
        self.assertEqual(0, report['comparable_cohort_count'])

    def test_missing_or_nonfinite_timing_cannot_qualify_comparison(self):
        old = [sample(OLD) for _ in range(5)]
        for bad_time in (None, float('nan'), float('inf'), -1):
            new = [sample(NEW) for _ in range(4)] + [sample(NEW, time=bad_time)]
            report = release_report(old + new, NEW, before_revision=OLD)
            self.assertEqual('unmeasured', report['performance_claim'])
            self.assertEqual(0, report['comparable_cohort_count'])

    def test_unrecognized_actions_or_forged_workloads_do_not_create_comparisons(self):
        for changed in ({'action': 'list-drafts'}, {'workload_signature': 'secret-topic'},
                        {'code_version': None}):
            old = [sample(OLD) for _ in range(5)]
            new = [{**sample(NEW), **changed} for _ in range(5)]
            report = release_report(old + new, NEW, before_revision=OLD)
            self.assertEqual('unmeasured', report['performance_claim'])

    def test_missing_some_counters_never_reports_partial_mean_as_complete(self):
        old = [sample(OLD) for _ in range(5)]
        new = [sample(NEW) for _ in range(4)] + [sample(NEW, counters={})]
        report = release_report(old + new, NEW, before_revision=OLD)
        comparison, = report['comparisons']
        self.assertEqual(1, report['comparable_cohort_count'])
        self.assertIsNone(comparison['change_percent']['ssh_roundtrips'])
        self.assertIsNone(comparison['change_percent']['wp_roundtrips'])


if __name__ == '__main__':
    unittest.main()
