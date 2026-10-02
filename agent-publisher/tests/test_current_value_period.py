import copy
import hashlib
import unittest
from datetime import datetime
from unittest.mock import patch

from agents.editorial import policy_fingerprint, validate_bundle
from agents.editorial_writer import EditorialWriterAgent
from agents.temporal_validation import KST, infer_current_value_period, validate_current_value_period
from tests.test_editorial_system import sample


NOW = datetime(2026, 10, 2, 12, 0, tzinfo=KST)


def current_rate_bundle():
    bundle = sample()
    brief = bundle['brief']
    brief.update(
        category_key='welfare',
        content_type='evergreen',
        useful_until=None,
        evergreen_reason='상시 제도이며 현재 적용 금리만 분기별 변경',
        volatility='policy-current',
        requires_live_state=True,
    )
    quote = '대부이자율 : 연 3.21%(2026년 10월 ~ 12월)'
    bundle['sources'][0]['text'] += '\n' + quote
    bundle['sources'][0]['sha256'] = hashlib.sha256(
        bundle['sources'][0]['text'].encode()).hexdigest()
    bundle['temporal_source'] = {
        'evidence': [],
        'current_value_period': {
            'start_date': '2026-10-01',
            'end_date': '2026-12-31',
            'evidence': [{'source_id': 's0', 'quote': quote}],
        },
    }
    return bundle


class CurrentValuePeriodTests(unittest.TestCase):
    def test_quarterly_current_value_period_is_bound_without_post_expiry(self):
        bundle = current_rate_bundle()
        self.assertEqual([], validate_current_value_period(
            bundle['brief'], bundle['sources'], bundle['temporal_source'], NOW))
        self.assertIsNone(bundle['brief']['useful_until'])
        self.assertNotIn('availability_not_verified', validate_bundle(
            bundle, {}, now=NOW, require_review=False, scopes={'content'})['reasons'])

    def test_period_may_have_less_than_30_days_remaining(self):
        bundle = current_rate_bundle()
        late = datetime(2026, 12, 20, 12, 0, tzinfo=KST)
        reasons = validate_current_value_period(
            bundle['brief'], bundle['sources'], bundle['temporal_source'], late)
        self.assertEqual([], reasons)

    def test_expired_period_fails_closed(self):
        bundle = current_rate_bundle()
        expired = datetime(2027, 1, 1, 0, 0, tzinfo=KST)
        self.assertIn('current_value_period_expired', validate_current_value_period(
            bundle['brief'], bundle['sources'], bundle['temporal_source'], expired))

    def test_user_supplied_dates_without_official_period_fail(self):
        bundle = current_rate_bundle()
        bundle['temporal_source']['current_value_period']['end_date'] = '2027-01-31'
        self.assertIn('current_value_period_dates_not_in_official_quote',
                      validate_current_value_period(
                          bundle['brief'], bundle['sources'], bundle['temporal_source'], NOW))

    def test_contract_requires_live_policy_current_evergreen(self):
        bundle = current_rate_bundle()
        bundle['brief']['requires_live_state'] = False
        self.assertIn('current_value_period_requires_live_refresh',
                      validate_current_value_period(
                          bundle['brief'], bundle['sources'], bundle['temporal_source'], NOW))
        bundle = current_rate_bundle()
        bundle['brief']['content_type'] = 'dated'
        bundle['brief']['useful_until'] = '2026-12-31'
        self.assertIn('current_value_period_requires_policy_current_evergreen',
                      validate_current_value_period(
                          bundle['brief'], bundle['sources'], bundle['temporal_source'], NOW))

    def test_quarter_label_also_proves_exact_period(self):
        bundle = current_rate_bundle()
        quote = '이자율은 2026년 4분기 기준이며, 매 분기 변경됩니다.'
        bundle['sources'][0]['text'] += '\n' + quote
        bundle['sources'][0]['sha256'] = hashlib.sha256(
            bundle['sources'][0]['text'].encode()).hexdigest()
        bundle['temporal_source']['current_value_period']['evidence'] = [
            {'source_id': 's0', 'quote': quote}]
        self.assertEqual([], validate_current_value_period(
            bundle['brief'], bundle['sources'], bundle['temporal_source'], NOW))

    def test_cross_year_month_range_is_supported_when_official_quote_proves_it(self):
        bundle = current_rate_bundle()
        quote = '적용기간은 2026년 12월 ~ 3월입니다.'
        bundle['sources'][0]['text'] += '\n' + quote
        bundle['sources'][0]['sha256'] = hashlib.sha256(
            bundle['sources'][0]['text'].encode()).hexdigest()
        bundle['temporal_source']['current_value_period'] = {
            'start_date': '2026-12-01',
            'end_date': '2027-03-31',
            'evidence': [{'source_id': 's0', 'quote': quote}],
        }
        now = datetime(2026, 12, 10, 12, 0, tzinfo=KST)
        self.assertEqual([], validate_current_value_period(
            bundle['brief'], bundle['sources'], bundle['temporal_source'], now))

    def test_yearless_recurring_month_band_does_not_invent_a_year(self):
        bundle = current_rate_bundle()
        quote = '동절기(12~3월), 동절기제외(4월~11월)'
        bundle['sources'][0]['text'] += '\n' + quote
        bundle['sources'][0]['sha256'] = hashlib.sha256(
            bundle['sources'][0]['text'].encode()).hexdigest()
        bundle['temporal_source']['current_value_period']['evidence'] = [
            {'source_id': 's0', 'quote': quote}]
        self.assertIn('current_value_period_dates_not_in_official_quote',
                      validate_current_value_period(
                          bundle['brief'], bundle['sources'], bundle['temporal_source'], NOW))

    def test_contract_changes_policy_fingerprint_only_when_used(self):
        bundle = current_rate_bundle()
        with_contract = policy_fingerprint(bundle)
        without = copy.deepcopy(bundle)
        without['temporal_source'].pop('current_value_period')
        self.assertNotEqual(with_contract, policy_fingerprint(without))

    def test_required_flag_fails_when_contract_is_missing(self):
        bundle = current_rate_bundle()
        bundle['brief']['requires_current_value_period'] = True
        bundle['temporal_source'].pop('current_value_period')
        self.assertIn('current_value_period_required', validate_current_value_period(
            bundle['brief'], bundle['sources'], bundle['temporal_source'], NOW))

    def test_infer_active_period_from_exact_official_month_range_and_quarter(self):
        bundle = current_rate_bundle()
        quarter_quote = '이자율은 2026년 4분기 기준이며, 매 분기 변경됩니다.'
        bundle['sources'][0]['text'] += '\n' + quarter_quote
        inferred = infer_current_value_period(bundle['sources'], NOW)
        self.assertEqual('2026-10-01', inferred['start_date'])
        self.assertEqual('2026-12-31', inferred['end_date'])
        self.assertTrue(any('3.21%' in row['quote'] for row in inferred['evidence']))

    def test_inference_rejects_yearless_recurring_bands_and_conflicting_active_periods(self):
        bundle = current_rate_bundle()
        bundle['sources'][0]['text'] = '동절기(12~3월), 동절기제외(4월~11월)'
        self.assertIsNone(infer_current_value_period(bundle['sources'], NOW))

        bundle = current_rate_bundle()
        bundle['sources'][0]['text'] += '\n적용기간 2026년 9월 ~ 10월'
        self.assertIsNone(infer_current_value_period(bundle['sources'], NOW))

    def test_scheduled_writer_injects_required_period_before_prepare(self):
        bundle = current_rate_bundle()
        brief = bundle['brief']
        brief['requires_current_value_period'] = True
        agent = EditorialWriterAgent(writing_enabled=True)
        prepared = {**bundle, 'plan': bundle['plan']}
        with patch('agents.editorial_writer.topic_reasons', return_value=[]), \
                patch('agents.editorial_writer.fetch_sources', return_value=bundle['sources']), \
                patch('agents.editorial_writer.load_inventory', return_value={}), \
                patch.object(agent, 'prepare', return_value=prepared) as prepare, \
                patch('agents.editorial_writer.article_from_bundle', return_value={'ok': True}):
            self.assertEqual({'ok': True}, agent.write_article({'search_brief': brief}))
        temporal = prepare.call_args.args[3]
        self.assertEqual('2026-10-01', temporal['current_value_period']['start_date'])
        self.assertEqual('2026-12-31', temporal['current_value_period']['end_date'])

    def test_scheduled_writer_holds_when_required_period_is_not_proven(self):
        bundle = current_rate_bundle()
        brief = bundle['brief']
        brief['requires_current_value_period'] = True
        bundle['sources'][0]['text'] = '동절기(12~3월), 동절기제외(4월~11월)'
        agent = EditorialWriterAgent(writing_enabled=True)
        with patch('agents.editorial_writer.topic_reasons', return_value=[]), \
                patch('agents.editorial_writer.fetch_sources', return_value=bundle['sources']), \
                patch.object(agent, 'prepare') as prepare:
            with self.assertRaisesRegex(ValueError, 'current_value_period_unverified'):
                agent.write_article({'search_brief': brief})
        prepare.assert_not_called()


if __name__ == '__main__':
    unittest.main()
