"""Exact official notation variants must not silently weaken numeric evidence."""
import unittest

from agents.editorial import supported_official_number_notations


class NumericEvidenceNotationTests(unittest.TestCase):
    def test_abbreviated_cohort_and_legal_year(self):
        body = '개인의 5년 기한은 2025년 부여분부터이고 법인은 2014년부터 적용됩니다.'
        quote = '소멸 기한 5년 ※ 개인납세자는 ’25년에 부여하는 포인트부터 적용(법인은 ’14년부터 적용)'
        self.assertEqual({'2025', '2014'}, supported_official_number_notations(
            body, quote, {'2025', '2014'}))
        self.assertEqual(set(), supported_official_number_notations(
            '2024년에는 한도 적용', quote, {'2024'}))

    def test_exact_written_date_and_abbreviated_reference_month(self):
        quote = '작성일자 2026.09.17. 사용처(’26.9. 기준)'
        self.assertEqual({'2026', '9', '17'}, supported_official_number_notations(
            '2026년 9월 17일 공식 발표', quote, {'2026', '9', '17'}))
        self.assertEqual({'2026', '9'}, supported_official_number_notations(
            '2026년 9월 기준', quote, {'2026', '9'}))
        self.assertEqual(set(), supported_official_number_notations(
            '2026년 8월 기준', quote, {'2026', '8'}))
        self.assertEqual({'2026', '9'}, supported_official_number_notations(
            '2026년 9월 18일', quote, {'2026', '9', '18'}))

    def test_won_equivalence_only_when_unit_and_amount_match(self):
        quote = '입장료 1천원 할인(1포인트 사용)'
        self.assertEqual({'1000'}, supported_official_number_notations(
            '1,000원 할인', quote, {'1000'}))
        self.assertEqual(set(), supported_official_number_notations(
            '1,000포인트 적립', quote, {'1000'}))
        self.assertEqual(set(), supported_official_number_notations(
            '2,000원 할인', quote, {'2000'}))


if __name__ == '__main__':
    unittest.main()
