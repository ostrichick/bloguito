import copy
import hashlib
import unittest
from datetime import datetime

from bs4 import BeautifulSoup

from agents.editorial import digest, policy, policy_fingerprint, render, validate_bundle
from agents.reader_tools import (
    minimum_wage_monthly_projection, rent_comparison_projection,
    validate_reader_tools, render_reader_tools,
)
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


class RentComparisonReaderToolTests(unittest.TestCase):
    def sample(self):
        sources = [{
            'id': sid, 'source_type': 'official', 'text': '2026년 관련 법률 확인 및 공제 요건',
        } for sid in ('s2', 's3', 's5', 's6')]
        tool = {
            'kind': 'rent_tax_comparison', 'title': '월세 비교 간이 계산기',
            'formula_version': 'rent_credit_receipt_2026_v1',
            'monthly_gross_default_man': 420, 'annual_bonus_default_man': 0,
            'monthly_rent_default_man': 50, 'months_default': 12,
            'marginal_percent_default': 15, 'card_deduction_used_default_man': 0,
            'other_card_floor_met_default': True, 'rent_eligible_default': True,
            'evidence': [{'source_id': s['id'], 'quote': s['text']} for s in sources],
        }
        brief = {'intent_type': 'comparison', 'primary_keyword': '월세 세액공제',
                 'entity': '월세 세액공제', 'added_value': ['comparison', 'calculator']}
        return {'reader_tools': [tool]}, sources, brief

    def test_simplified_fixture_and_no_standard_credit(self):
        actual = rent_comparison_projection(420, 50, 12, 15, 0, True, True)
        self.assertEqual(5040, actual['salary_man'])
        self.assertEqual(102, actual['rent_nominal_man'])
        self.assertEqual(27, actual['receipt_tax_simple_man'])
        self.assertEqual(17, actual['credit_percent'])

    def test_annual_salary_threshold_and_card_limit(self):
        cases = [
            (458, 80, 0, 17, 300),   # below 55m annual
            (459, 80, 0, 15, 300),   # above 55m annual
            (583, 80, 0, 15, 300),   # <=70m cap
            (584, 80, 0, 15, 250),   # >70m cap
            (666, 80, 0, 15, 250),   # <=80m credit
            (667, 80, 0, None, 250), # >80m ineligible
            (420, 80, 2000, 15, 250), # annual bonus changes pay bracket
        ]
        for salary, rent, bonus, credit, cap in cases:
            with self.subTest(salary=salary, bonus=bonus):
                actual = rent_comparison_projection(salary, rent, 12, 15, 0, True, True, bonus)
                self.assertEqual(credit, actual['credit_percent'])
                self.assertEqual(cap, actual['base_card_cap_man'])
        high = rent_comparison_projection(750, 80, 12, 24, 0, True, True)
        self.assertIsNone(high['rent_nominal_man'])
        self.assertEqual(60, high['receipt_tax_simple_man'])

    def test_rent_annual_limit_partial_months_and_used_card_cap(self):
        self.assertEqual(170, rent_comparison_projection(
            420, 100, 12, 15, 0, True, True)['rent_nominal_man'])
        self.assertEqual(25.5, rent_comparison_projection(
            420, 50, 3, 15, 0, True, True)['rent_nominal_man'])
        self.assertEqual(7.5, rent_comparison_projection(
            750, 80, 12, 15, 200, True, True)['receipt_tax_simple_man'])
        self.assertEqual(0, rent_comparison_projection(
            750, 80, 12, 15, 300, True, True)['receipt_tax_simple_man'])

    def test_unknown_eligibility_or_card_threshold_returns_unknown(self):
        self.assertIsNone(rent_comparison_projection(
            420, 50, 12, 15, 0, False, True)['receipt_tax_simple_man'])
        self.assertIsNone(rent_comparison_projection(
            420, 50, 12, 15, 0, True, False)['rent_nominal_man'])

    def test_bounds_and_arbitrary_content_fail_closed(self):
        for bad in [(-1,50,12,15,0,True,True), (420,0,12,15,0,True,True),
                    (420,50,13,15,0,True,True), (420,50,12,12,0,True,True),
                    (420,50,12,15,-1,True,True)]:
            with self.assertRaises(ValueError):
                rent_comparison_projection(*bad)
        plan, sources, brief = self.sample()
        self.assertEqual([], validate_reader_tools(plan, sources, brief))
        for change in ('script', 'formula_version', 'source', 'scope'):
            p,s,b = copy.deepcopy((plan,sources,brief))
            if change == 'script':
                p['reader_tools'][0]['script'] = 'alert(1)'
            elif change == 'formula_version':
                p['reader_tools'][0]['formula_version'] = 'arbitrary_js'
            elif change == 'source':
                p['reader_tools'][0]['evidence'][0]['quote'] = 'injected'
            else:
                b['primary_keyword'] = '연금'; b['entity'] = '연금'
            self.assertNotEqual([], validate_reader_tools(p,s,b))

    def test_stable_accessible_widget_no_network_or_script_injection(self):
        plan, sources, brief = self.sample()
        self.assertEqual([], validate_reader_tools(plan, sources, brief))
        markup = render_reader_tools(plan)
        soup = BeautifulSoup(markup, 'html.parser')
        widget = soup.select_one('[data-reader-tool="rent_tax_comparison"]')
        self.assertIsNotNone(widget)
        self.assertEqual(1, len(widget.find_all('script')))
        self.assertTrue(widget.find('noscript'))
        self.assertTrue(widget.select('[aria-live="polite"]'))
        self.assertEqual(7, len(widget.find_all('input')))
        self.assertEqual(1, len(widget.find_all('select')))
        self.assertEqual(2, len(widget.find_all('output')))
        for forbidden in ('fetch(', 'eval(', 'XMLHttpRequest', 'innerHTML', 'document.cookie'):
            self.assertNotIn(forbidden, markup)
