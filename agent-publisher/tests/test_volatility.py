import copy
import json
import unittest
from datetime import date
from pathlib import Path

from agents.editorial import policy_fingerprint, topic_reasons, validate_bundle
from agents.volatility import migration_candidate, migration_report, temporal_contract_reasons
from tests.test_editorial_system import NOW, sample


class VolatilityTests(unittest.TestCase):
    def test_missing_metadata_preserves_legacy_topic_result(self):
        brief = sample()['brief']
        before = topic_reasons(copy.deepcopy(brief), NOW.date())
        after = topic_reasons(brief, NOW.date())
        self.assertEqual(before, after)

    def test_invalid_explicit_metadata_fails_closed(self):
        brief = sample()['brief']
        brief['volatility'] = 'sometimes-current'
        brief['requires_live_state'] = 'yes'
        brief['requires_current_value_period'] = 'yes'
        reasons = topic_reasons(brief, NOW.date())
        self.assertIn('invalid_volatility', reasons)
        self.assertIn('invalid_requires_live_state', reasons)
        self.assertIn('invalid_requires_current_value_period', reasons)

    def test_bounded_lifecycle_cannot_use_evergreen_shape(self):
        for volatility in ('annual-policy', 'seasonal', 'one-off'):
            with self.subTest(volatility=volatility):
                brief = sample()['brief']
                brief['volatility'] = volatility
                self.assertIn(
                    'bounded_volatility_requires_dated_lifetime',
                    topic_reasons(brief, NOW.date()),
                )

    def test_timeless_procedure_requires_legacy_evergreen_shape(self):
        brief = sample()['brief']
        brief['volatility'] = 'timeless-procedure'
        self.assertNotIn('timeless_procedure_requires_evergreen', topic_reasons(brief, NOW.date()))
        brief['content_type'] = 'dated'
        brief['useful_until'] = '2026-12-31'
        self.assertIn('timeless_procedure_requires_evergreen', topic_reasons(brief, NOW.date()))

    def test_unmigrated_welfare_evergreen_keeps_legacy_category_gate(self):
        brief = sample()['brief']
        brief['category_key'] = 'welfare'
        self.assertIn('dated_category_cannot_bypass_time_check', topic_reasons(brief, NOW.date()))

    def test_explicit_policy_current_welfare_can_replace_legacy_category_gate(self):
        brief = sample()['brief']
        brief.update(
            category_key='welfare',
            volatility='policy-current',
            requires_live_state=False,
        )
        self.assertNotIn(
            'dated_category_cannot_bypass_time_check',
            topic_reasons(brief, NOW.date()),
        )

    def test_policy_current_dated_still_requires_legacy_temporal_evidence(self):
        bundle = sample()
        bundle['brief'].update(
            category_key='welfare',
            content_type='dated',
            useful_until='2026-12-31',
            volatility='policy-current',
            requires_live_state=False,
        )
        bundle['brief'].pop('evergreen_reason', None)
        bundle['temporal_source'] = {'evidence': []}
        reasons = validate_bundle(
            bundle, {}, now=NOW, require_review=False, scopes={'content'})['reasons']
        self.assertIn('temporal_source_not_bound', reasons)
        self.assertIn('availability_not_verified', reasons)

    def test_explicit_live_language_requires_live_refresh_flag(self):
        brief = sample()['brief']
        brief['volatility'] = 'policy-current'
        brief['question'] = '현재 신청 가능한가?'
        self.assertIn('live_state_claim_requires_live_refresh', topic_reasons(brief, NOW.date()))
        brief['requires_live_state'] = True
        self.assertNotIn('live_state_claim_requires_live_refresh', topic_reasons(brief, NOW.date()))

    def test_annual_policy_requires_reference_period_contract(self):
        bundle = sample()
        bundle['brief'].update(
            volatility='annual-policy', content_type='dated', useful_until='2026-12-31')
        self.assertIn('annual_policy_reference_period_required', temporal_contract_reasons(bundle))
        bundle['temporal_source']['reference_period'] = {'kind': 'annual_rule'}
        self.assertNotIn('annual_policy_reference_period_required', temporal_contract_reasons(bundle))

    def test_timeless_procedure_rejects_dated_temporal_mode(self):
        bundle = sample()
        bundle['brief']['volatility'] = 'timeless-procedure'
        bundle['temporal_source']['schedule_listing_only'] = True
        self.assertIn('timeless_procedure_temporal_contract_conflict', temporal_contract_reasons(bundle))

    def test_explicit_metadata_is_bound_to_policy_fingerprint(self):
        bundle = sample()
        before = policy_fingerprint(bundle)
        bundle['brief']['volatility'] = 'timeless-procedure'
        bundle['brief']['requires_live_state'] = False
        after = policy_fingerprint(bundle)
        self.assertNotEqual(before, after)

    def test_migration_report_is_read_only(self):
        path = Path(__file__).resolve().parents[1] / 'data' / 'search_briefs.json'
        briefs = json.loads(path.read_text(encoding='utf-8'))
        before = copy.deepcopy(briefs)
        report = migration_report(briefs, today=date(2026, 10, 2))
        self.assertEqual(before, briefs)
        self.assertEqual(len(briefs), len(report))
        self.assertTrue(all(set(row) >= {
            'id', 'existing_content_type', 'suggested_volatility',
            'suggested_requires_live_state', 'confidence', 'signals',
            'conflicts', 'requires_review', 'review_until', 'approved',
            'review_window_current', 'current_volatility',
            'current_requires_live_state', 'explicit_metadata_present',
            'suggestion_matches_current',
        } for row in report))
        self.assertEqual(
            [row.get('review_until') for row in briefs],
            [row.get('review_until') for row in report],
        )
        self.assertEqual(3, sum(row['review_window_current'] for row in report))

        rows = {row['id']: row for row in report}
        self.assertEqual('policy-current', rows['senior-implant-insurance-guide']['current_volatility'])
        self.assertFalse(rows['senior-implant-insurance-guide']['current_requires_live_state'])
        self.assertTrue(rows['senior-implant-insurance-guide']['suggestion_matches_current'])
        self.assertEqual('policy-current', rows['national-pension-silver-loan']['current_volatility'])
        self.assertTrue(rows['national-pension-silver-loan']['current_requires_live_state'])
        self.assertTrue(rows['national-pension-silver-loan']['suggestion_matches_current'])
        self.assertEqual('policy-current', rows['long-term-care-grade-guide']['current_volatility'])
        self.assertTrue(rows['long-term-care-grade-guide']['current_requires_live_state'])
        self.assertTrue(rows['long-term-care-grade-guide']['suggestion_matches_current'])

        briefs_by_id = {row['id']: row for row in briefs}
        self.assertEqual([], topic_reasons(
            briefs_by_id['long-term-care-grade-guide'], date(2026, 10, 2)))
        self.assertEqual([], rows['national-pension-silver-loan']['conflicts'])
        self.assertEqual([], topic_reasons(
            briefs_by_id['national-pension-silver-loan'], date(2026, 10, 2)))

    def test_known_migration_shapes_are_conservative(self):
        timeless = migration_candidate({
            'id': 'resident-registration-guide', 'category_key': 'life-admin',
            'content_type': 'evergreen', 'evergreen_reason': '상시 민원 절차',
        })
        self.assertEqual('timeless-procedure', timeless['suggested_volatility'])
        self.assertEqual('high', timeless['confidence'])

        concert = migration_candidate({
            'id': 'concert-2026', 'category_key': 'concert', 'content_type': 'dated',
            'question': '현재 예매 가능한가?',
        })
        self.assertEqual('one-off', concert['suggested_volatility'])
        self.assertTrue(concert['suggested_requires_live_state'])


if __name__ == '__main__':
    unittest.main()
