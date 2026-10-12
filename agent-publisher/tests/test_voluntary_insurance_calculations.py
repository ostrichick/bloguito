"""#922: 2026 voluntary vs regional premium examples are arithmetic, not bills."""
import copy
import hashlib
import unittest

from agents.editorial import supported_currency_sums, validate_bundle
from agents.editorial_schema import VoluntaryInsurance2026Example
from tests.test_editorial_system import NOW, sample, sign


EVIDENCE = (
    '2026년 직장가입자 건강보험료율은 7.19%이며 장기요양보험료율은 '
    '0.9448%입니다. 장기요양보험료 = 건강보험료 × 0.9448% / 7.19%. '
    '보험료 경감고시 제9조: 임의계속가입자의 보수월액보험료 100분의 50을 경감한다. '
    '국고금 관리법 제47조: 국고금의 수입 또는 지출에서 10원 미만의 끝수가 있을 때에는 그 끝수는 계산하지 않는다.'
)
CAUTION = (
    '2026년 요율을 적용한 가정, 계산 단계마다 10원 미만 버림. '
    '지역보험료는 장기요양 포함 가상 고지액이다. 보수 외 소득 보험료는 제외하며 '
    '실제 고지액과 다를 수 있다. 12개월 동일 요율과 조건을 가정한 비교.'
)
BASE = {
    'operation': 'voluntary_insurance_2026_example',
    'average_remuneration_won': 3_000_000,
    'regional_total_won': 180_000,
    'health_won': 107_850,
    'long_term_care_won': 14_170,
    'voluntary_total_won': 122_020,
    'advantage': 'voluntary',
    'monthly_gap_won': 57_980,
    'twelve_month_gap_won': 695_760,
}


def example_text(item):
    return (
        f"최근 12개월 평균 보수월액 {item['average_remuneration_won']:,}원, "
        f"지역보험료 {item['regional_total_won']:,}원 가정: "
        f"임의계속 건강보험 {item['health_won']:,}원 + 장기요양 {item['long_term_care_won']:,}원 "
        f"= 월 {item['voluntary_total_won']:,}원, 월 차액 {item['monthly_gap_won']:,}원, "
        f"12개월 차액 {item['twelve_month_gap_won']:,}원. "
        + CAUTION
    )


class VoluntaryInsuranceCalculations(unittest.TestCase):
    def setUp(self):
        self.item = copy.deepcopy(BASE)

    def evaluate(self, *, text=None, quote=EVIDENCE, shared=''):
        return supported_currency_sums(
            text if text is not None else example_text(self.item),
            quote, [self.item], shared)

    def test_verified_rates_and_50_percent_reduction(self):
        supported, errors = self.evaluate()
        self.assertEqual([], errors)
        self.assertTrue({'3000000', '180000', '107850', '14170',
                         '122020', '57980', '695760', '12'} <= supported)

    def test_regional_cheaper_and_equal_scenarios(self):
        self.item.update(regional_total_won=100_000, advantage='regional',
                         monthly_gap_won=22_020, twelve_month_gap_won=264_240)
        self.assertEqual([], self.evaluate()[1])
        self.item.update(average_remuneration_won=5_000_000, regional_total_won=203_370,
                         health_won=179_750, long_term_care_won=23_620,
                         voluntary_total_won=203_370, advantage='equal',
                         monthly_gap_won=0, twelve_month_gap_won=0)
        self.assertEqual([], self.evaluate()[1])

    def test_922_three_decision_cases(self):
        cases = [
            # salary, regional, health, LTC, voluntary, winner, month, 12-month
            (3_000_000, 250_000, 107_850, 14_170, 122_020, 'voluntary', 127_980, 1_535_760),
            (5_000_000, 150_000, 179_750, 23_620, 203_370, 'regional', 53_370, 640_440),
            (4_000_000, 170_000, 143_800, 18_890, 162_690, 'voluntary', 7_310, 87_720),
        ]
        for salary, regional, health, ltc, voluntary, winner, gap, annual in cases:
            with self.subTest(salary=salary, regional=regional):
                self.item.update(
                    average_remuneration_won=salary, regional_total_won=regional,
                    health_won=health, long_term_care_won=ltc,
                    voluntary_total_won=voluntary, advantage=winner,
                    monthly_gap_won=gap, twelve_month_gap_won=annual,
                )
                self.assertEqual([], self.evaluate()[1])

    def test_fail_closed_for_wrong_rate_or_approximate_1314_percent(self):
        self.item['long_term_care_won'] = 14_172
        self.assertIn('invalid_derived_calculation', self.evaluate()[1])
        self.item['long_term_care_won'] = 14_170
        self.assertIn('invalid_derived_calculation',
                      self.evaluate(quote=EVIDENCE.replace('0.9448', '0.9182'))[1])

    def test_bad_result_or_monthly_or_annual_gap(self):
        for field in ('health_won', 'voluntary_total_won',
                      'monthly_gap_won', 'twelve_month_gap_won'):
            with self.subTest(field=field):
                self.item[field] += 1
                self.assertIn('invalid_derived_calculation', self.evaluate()[1])
                self.item[field] -= 1

    def test_missing_official_50_percent_reduction(self):
        self.assertIn('invalid_derived_calculation',
                      self.evaluate(quote=EVIDENCE.replace('100분의 50', '100분의 40'))[1])

    def test_missing_legal_10_won_rounding_support(self):
        self.assertIn('invalid_derived_calculation',
                      self.evaluate(quote=EVIDENCE.replace('10원 미만', '1원 미만'))[1])

    def test_missing_fictional_label_or_hidden_regional_ltc(self):
        for phrase in ('가정', '장기요양 포함', '보수 외 소득', '실제 고지',
                       '10원 미만 버림', '12개월 동일'):
            with self.subTest(phrase=phrase):
                self.assertIn('invalid_derived_calculation',
                              self.evaluate(text=example_text(self.item).replace(phrase, ''))[1])

    def test_salary_and_region_inputs_must_be_won_in_this_row(self):
        for key in ('average_remuneration_won', 'regional_total_won'):
            with self.subTest(key=key):
                self.assertIn('invalid_derived_calculation',
                              self.evaluate(text=example_text(self.item).replace(
                                  f"{self.item[key]:,}원", '미공개'))[1])

    def test_illustrative_bounds_bool_and_extra_key(self):
        for key, value in [('average_remuneration_won', True),
                           ('average_remuneration_won', 20_000_000),
                           ('regional_total_won', 2_100_000),
                           ('regional_total_won', 18_000)]:
            with self.subTest(key=key, value=value):
                candidate = copy.deepcopy(self.item)
                self.item[key] = value
                self.assertIn('invalid_derived_calculation', self.evaluate()[1])
                self.item = candidate
        self.item['unverified_rebate'] = 15000
        self.assertIn('invalid_derived_calculation', self.evaluate()[1])

    def test_advantage_direction_must_match_arithmetic(self):
        self.item['advantage'] = 'regional'
        self.assertIn('invalid_derived_calculation', self.evaluate()[1])

    def test_table_row_uses_shared_caption_for_assumptions(self):
        text = example_text(self.item).replace(CAUTION, '')
        self.assertEqual([], self.evaluate(text=text, shared=CAUTION)[1])
        self.assertIn('invalid_derived_calculation',
                      self.evaluate(text=text, shared='일반 보험료 비교')[1])

    def test_schema_parses_new_operation(self):
        self.assertEqual(self.item['operation'],
                         VoluntaryInsurance2026Example.model_validate(self.item).operation)

    def test_full_bundle_check_with_cited_rates(self):
        bundle = sample()
        bundle['sources'][0]['text'] += '\n' + EVIDENCE
        bundle['sources'][0]['sha256'] = hashlib.sha256(
            bundle['sources'][0]['text'].encode()).hexdigest()
        bundle['plan']['lead']['text'] = example_text(self.item)
        bundle['plan']['lead']['evidence'] = [{'source_id': 's0', 'quote': EVIDENCE}]
        bundle['plan']['lead']['calculations'] = [self.item]
        sign(bundle)
        result = validate_bundle(bundle, {'checked_on': NOW.date().isoformat(), 'posts': []}, NOW)
        self.assertEqual('ready', result['status'], result['reasons'])


if __name__ == '__main__':
    unittest.main()
