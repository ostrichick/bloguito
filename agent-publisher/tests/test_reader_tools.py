import copy
import hashlib
import unittest
from datetime import datetime

from bs4 import BeautifulSoup

from agents.editorial import digest, policy, policy_fingerprint, render, validate_bundle
from agents.reader_tools import minimum_wage_monthly_projection
from agents.temporal_validation import KST


class ReaderToolTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 3, 17, tzinfo=KST)
        source_text = (
            '주휴수당 계산법은 1주일에 20시간 일하는 경우 '
            '주휴수당=(20시간/40시간) x 8시간 x 시급으로 계산합니다. '
            '주 40시간 기준 월 환산 기준시간 수는 유급주휴 8시간을 포함해 209시간입니다.'
        )
        self.bundle = {
            'brief': {
                'id': 'minimum-wage-reader-tool', 'category_key': 'finance', 'approved': True,
                'entity': '최저임금', 'primary_keyword': '최저임금 월급 계산',
                'question': '시급과 근로시간으로 월급은 얼마인가?', 'angle': '월급 직접 계산',
                'intent_type': 'calculator', 'ai_answerability': 'high',
                'added_value': ['calculator', 'official_action'],
                'official_urls': ['https://www.moel.go.kr/example'],
                'required_title_terms': ['최저임금', '월급'], 'content_type': 'evergreen',
                'useful_until': None, 'evergreen_reason': '시급 입력형 계산 도구 테스트',
                'reviewed_at': '2026-10-03', 'review_until': '2026-12-31',
                'reader_questions': [{'id': 'q1', 'question': '월급은 얼마인가?'}],
            },
            'sources': [{
                'id': 's0', 'url': 'https://www.moel.go.kr/example', 'title': '고용노동부 안내',
                'text': source_text, 'sha256': hashlib.sha256(source_text.encode()).hexdigest(),
                'source_type': 'official', 'fetched_at': self.now.isoformat(),
            }],
            'plan': {
                'title': '최저임금 월급 계산',
                'lead': {'text': '시급과 주 근로시간을 넣어 월 예상 급여를 계산할 수 있습니다.',
                         'evidence': [{'source_id': 's0', 'quote': source_text}], 'answers': ['q1']},
                'sections': [{'heading': '계산 기준', 'paragraphs': [{
                    'text': '주휴 적용 여부와 근로시간에 따라 월 환산 시간이 달라집니다.',
                    'evidence': [{'source_id': 's0', 'quote': source_text}], 'answers': []}]}],
                'faq': [], 'related_posts': [],
                'reader_tools': [{
                    'kind': 'minimum_wage_monthly', 'title': '월 예상 급여 계산기',
                    'formula_version': 'moel_weekly_holiday_v1',
                    'hourly_wage_default': 10320, 'weekly_hours_default': 40.0,
                    'weekly_holiday_default': True,
                    'evidence': [{'source_id': 's0', 'quote': source_text}],
                }],
            },
            'temporal_source': {},
        }
        body = {key: self.bundle[key] for key in ('brief', 'sources', 'plan', 'temporal_source')}
        self.bundle['review'] = {
            'digest': digest(body), 'policy_digest': policy_fingerprint(self.bundle),
            'checked_at': self.now.isoformat(),
            'checks': {key: True for key in policy()['review_checks']}, 'issues': [],
        }
        self.inventory = {'checked_on': '2026-10-03', 'posts': []}

    def test_projection_matches_official_40_hour_monthly_conversion(self):
        result = minimum_wage_monthly_projection(10320, 40, True)
        self.assertEqual(8, result['weekly_holiday_hours'])
        self.assertEqual(209, result['monthly_hours'])
        self.assertEqual(2_156_880, result['monthly_wage'])
        self.assertEqual(174, minimum_wage_monthly_projection(10320, 40, False)['monthly_hours'])

    def test_under_15_hours_does_not_add_weekly_holiday_even_when_checked(self):
        self.assertEqual(0, minimum_wage_monthly_projection(10320, 14, True)['weekly_holiday_hours'])

    def test_valid_tool_is_review_bound_and_renders_static_template(self):
        report = validate_bundle(self.bundle, self.inventory, now=self.now)
        self.assertEqual('ready', report['status'], report['reasons'])
        markup = render(self.bundle['plan'], self.bundle['sources'])
        soup = BeautifulSoup(markup, 'html.parser')
        tool = soup.select_one('[data-reader-tool="minimum_wage_monthly"]')
        self.assertIsNotNone(tool)
        self.assertEqual('number', tool.select_one('[data-role="hourly"]')['type'])
        self.assertIsNotNone(tool.select_one('[data-role="holiday"]'))
        self.assertEqual('polite', tool.select_one('[aria-live]')['aria-live'])
        self.assertIn('Math.round((w+holidayHours)*365/7/12)', markup)
        self.assertIn('<noscript>', markup)
        self.assertNotIn('eval(', markup)

    def test_arbitrary_script_or_unsupported_formula_is_rejected(self):
        for mutate in ('script', 'formula'):
            with self.subTest(mutate=mutate):
                bundle = copy.deepcopy(self.bundle)
                tool = bundle['plan']['reader_tools'][0]
                if mutate == 'script':
                    tool['script'] = 'alert(1)'
                else:
                    tool['formula_version'] = 'model_generated_v99'
                reasons = validate_bundle(bundle, self.inventory, now=self.now, require_review=False)['reasons']
                self.assertIn('invalid_reader_tools', reasons)

    def test_tool_is_scoped_to_minimum_wage_calculator_brief(self):
        bundle = copy.deepcopy(self.bundle)
        bundle['brief']['primary_keyword'] = '근로장려금 계산'
        bundle['brief']['entity'] = '근로장려금'
        reasons = validate_bundle(bundle, self.inventory, now=self.now, require_review=False)['reasons']
        self.assertIn('reader_tool_outside_brief_scope', reasons)

    def test_invalid_numeric_bound_is_rejected(self):
        bundle = copy.deepcopy(self.bundle)
        bundle['plan']['reader_tools'][0]['weekly_hours_default'] = 41
        reasons = validate_bundle(bundle, self.inventory, now=self.now, require_review=False)['reasons']
        self.assertIn('invalid_reader_tools', reasons)


if __name__ == '__main__':
    unittest.main()
