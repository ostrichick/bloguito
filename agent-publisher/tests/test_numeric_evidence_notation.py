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

    def test_compact_source_date_supports_reader_friendly_korean_date_without_year(self):
        quote = '기간 10.9.(금)~10.11.(일) / 2026-10-17 / 2026.11.01'
        body = '10월 9일(금)~10월 11일(일), 10월 17일(토), 11월 1일(일)'
        candidates = {'10', '9', '11', '17', '1'}
        self.assertEqual(
            candidates,
            supported_official_number_notations(body, quote, candidates),
        )

    def test_compact_source_date_supports_short_slash_table_date(self):
        quote = '기간 10.9.(금)~10.11.(일) / 2026-10-17 / 2026.11.01'
        body = '10/9(금)~10/11(일), 10/17(토), 11/1(일)'
        candidates = {'10', '9', '11', '17', '1'}
        self.assertEqual(
            candidates,
            supported_official_number_notations(body, quote, candidates),
        )

    def test_korean_ampm_source_time_supports_exact_24_hour_table_notation(self):
        quote = '매주 토요일 오후 2시, 10월 31일에는 오후 1시와 3시 두 차례'
        body = '14:00 / 13:00, 15:00'
        candidates = {'14', '13', '15', '00'}
        self.assertEqual(
            candidates,
            supported_official_number_notations(body, quote, candidates),
        )

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
