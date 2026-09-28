import unittest
from datetime import datetime

from agents.temporal_validation import KST, validate_reference_period


class ReferencePeriodTests(unittest.TestCase):
    def setUp(self):
        self.url = 'https://official.example/rule'
        self.quote = "적용연도\n'27.01.01\n~'27.12.31\n10,700"
        self.brief = {
            'content_type': 'dated',
            'category_key': 'life-health',
            'useful_until': '2027-12-31',
            'official_urls': [self.url],
        }
        self.sources = [{
            'id': 's0', 'url': self.url, 'source_type': 'official',
            'text': '앞부분\n' + self.quote + '\n뒷부분',
        }]
        self.temporal = {
            'reference_period': {
                'kind': 'annual_rule',
                'start_date': '2027-01-01',
                'end_date': '2027-12-31',
                'evidence': {'source_id': 's0', 'quote': self.quote},
            }
        }
        self.plan = {'title': '2027 기준', 'lead': {'text': '2027 기준 안내'},
                     'sections': [], 'faq': []}
        self.now = datetime(2026, 9, 28, 12, 0, tzinfo=KST)

    def test_future_annual_rule_is_valid_before_effective_date(self):
        self.assertEqual([], validate_reference_period(
            self.brief, self.sources, self.temporal, self.plan, self.now))

    def test_unbound_dates_fail(self):
        self.temporal['reference_period']['end_date'] = '2028-12-31'
        reasons = validate_reference_period(
            self.brief, self.sources, self.temporal, self.plan, self.now)
        self.assertIn('reference_period_dates_not_in_official_quote', reasons)
        self.assertIn('reference_period_useful_until_mismatch', reasons)

    def test_live_application_claim_is_not_certified(self):
        self.plan['lead']['text'] = '현재 신청 가능'
        reasons = validate_reference_period(
            self.brief, self.sources, self.temporal, self.plan, self.now)
        self.assertIn('reference_period_misleading_live_status_claim', reasons)


if __name__ == '__main__':
    unittest.main()
