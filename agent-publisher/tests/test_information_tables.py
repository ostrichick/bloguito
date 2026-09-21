"""Evidence-bound schedule tables are readable without allowing raw HTML or invented dates."""
import unittest

from agents.editorial import render, validate_bundle
from tests.test_editorial_system import NOW, sample, sign


class InformationTableTests(unittest.TestCase):
    def setUp(self):
        self.bundle = sample()
        self.table = {
            'caption': '공식 안내 기준 배출 방식',
            'headers': ['품목', '처리 방식'],
            'rows': [{'cells': ['가정용 선풍기', '아파트 단지 수집 거치대'],
                      'evidence': self.bundle['plan']['lead']['evidence'], 'answers': ['q1']}],
        }
        self.bundle['plan']['sections'][0]['table'] = self.table
        self.inventory = {'checked_on': '2026-09-14', 'posts': []}

    def check(self):
        sign(self.bundle)
        return validate_bundle(self.bundle, self.inventory, NOW)

    def test_renders_accessible_responsive_evidence_table(self):
        self.assertEqual('ready', self.check()['status'])
        html = render(self.bundle['plan'], self.bundle['sources'])
        self.assertIn('class="bloguito-info-table"', html)
        self.assertIn('overflow-x:auto', html)
        self.assertIn('<th scope="col"', html)
        self.assertIn('<th scope="row"', html)
        self.assertIn('<caption', html)
        self.assertIn('<td style=', html)
        self.assertIn('아파트 단지 수집 거치대', html)

    def test_table_only_section_is_a_valid_article_section(self):
        self.bundle['plan']['sections'][0]['paragraphs'] = []
        self.assertEqual('ready', self.check()['status'])
        html = render(self.bundle['plan'], self.bundle['sources'])
        self.assertIn('<table ', html)
        self.assertIn('공식 안내 기준 배출 방식', html)

    def test_table_number_is_checked_against_original_quote(self):
        self.table['rows'][0]['cells'][1] = '2026년 12월 25일 배출'
        self.assertIn('number_without_evidence', self.check()['reasons'])

    def test_html_in_table_cell_or_heading_is_rejected_and_escaped(self):
        self.table['rows'][0]['cells'][0] = '<script>alert(1)</script>'
        self.assertIn('raw_markup_or_url_in_prose', self.check()['reasons'])
        html = render(self.bundle['plan'], self.bundle['sources'])
        self.assertNotIn('<script>', html)
        self.assertIn('&lt;script&gt;', html)

    def test_bad_row_width_is_rejected(self):
        self.table['rows'][0]['cells'] = ['가정용 선풍기']
        self.assertIn('invalid_information_table', self.check()['reasons'])

    def test_table_quote_is_checked_for_provenance(self):
        self.table['rows'][0]['evidence'] = [{'source_id': 's0', 'quote': '조작된 일정과 장소입니다.'}]
        self.assertIn('quote_not_in_source', self.check()['reasons'])

    def test_table_rows_are_covered_by_review_digest(self):
        sign(self.bundle)
        self.table['rows'][0]['cells'][1] = '수정한 처리 방식'
        self.assertIn('review_not_bound_to_current_content',
                      validate_bundle(self.bundle, self.inventory, NOW)['reasons'])


if __name__ == '__main__':
    unittest.main()
