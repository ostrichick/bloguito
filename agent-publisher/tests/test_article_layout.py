"""The reviewed editorial plan controls the layout without inventing facts."""
import unittest

from agents.editorial import excerpt_from_lead, render, validate_bundle
from tests.test_editorial_system import NOW, sample, sign


class ArticleLayoutTests(unittest.TestCase):
    def setUp(self):
        self.bundle = sample()
        self.inventory = {'checked_on': '2026-09-14', 'posts': []}

    def test_at_a_glance_table_precedes_actions_and_navigation(self):
        evidence = self.bundle['plan']['lead']['evidence']
        overview = {
            'kind': 'overview', 'heading': '한눈에 보는 수거 기준', 'paragraphs': [],
            'table': {'caption': '공식 수거 기준', 'headers': ['구분', '처리 방법'],
                      'rows': [{'cells': ['가정용 선풍기', '아파트 단지 수집 거치대'],
                                'evidence': evidence, 'answers': ['q1']}]},
        }
        self.bundle['plan']['sections'].insert(0, overview)
        self.bundle['sources'][0]['actions'] = [
            {'kind': 'lookup', 'label': '서초구 배출 화면 조회하기', 'url': 'https://www.seocho.go.kr/apply'}]
        sign(self.bundle)
        self.assertEqual('ready', validate_bundle(self.bundle, self.inventory, NOW)['status'])
        page = render(self.bundle['plan'], self.bundle['sources'])
        self.assertLess(page.index('핵심 답변'), page.index('공식 수거 기준'))
        self.assertLess(page.index('공식 수거 기준'), page.index('bloguito-cta'))
        self.assertLess(page.index('bloguito-cta'), page.index('bloguito-toc'))
        self.assertEqual(1, page.count('href="#step-2"'))
        self.assertNotIn('href="#step-1"', page)  # The overview is already above the TOC.
        # The article has only one procedure: do not show an orphan STEP 1.
        self.assertIn('>배출 방법</h2>', page)
        self.assertNotIn('STEP 1</span>배출 방법', page)
        self.assertIn('min-width:0;font-size:15px', page)

    def test_only_procedures_receive_step_numbers(self):
        self.bundle['plan']['sections'][0]['kind'] = 'eligibility'
        self.bundle['plan']['sections'].append({
            'kind': 'procedure', 'heading': '실제 배출 순서', 'paragraphs': [self.bundle['plan']['lead']]})
        sign(self.bundle)
        self.assertEqual('ready', validate_bundle(self.bundle, self.inventory, NOW)['status'])
        page = render(self.bundle['plan'], self.bundle['sources'])
        self.assertIn('>배출 방법</h2>', page)
        self.assertNotIn('STEP 1</span>배출 방법', page)
        # One actual procedure remains unnumbered even if other sections exist.
        self.assertIn('>실제 배출 순서</h2>', page)
        self.assertNotIn('STEP 1</span>실제 배출 순서', page)
        self.assertNotIn('3초 요약', page)

    def test_three_column_table_has_visible_scroll_hint(self):
        self.bundle['plan']['sections'][0]['table'] = {
            'caption': '품목별 배출 기준', 'headers': ['품목', '장소', '비용'],
            'rows': [{'cells': ['선풍기', '아파트 단지 수집 거치대', '면제'],
                      'evidence': self.bundle['plan']['lead']['evidence'], 'answers': ['q1']}],
        }
        page = render(self.bundle['plan'], self.bundle['sources'])
        self.assertIn('bloguito-table-hint', page)
        self.assertIn('min-width:580px', page)
        self.assertIn('scope="col"', page)
        self.assertIn('scope="row"', page)

    def test_invalid_section_kind_is_rejected(self):
        self.bundle['plan']['sections'][0]['kind'] = 'invented-layout'
        sign(self.bundle)
        self.assertIn('invalid_section_kind', validate_bundle(self.bundle, self.inventory, NOW)['reasons'])

    def test_excerpt_is_only_reviewed_answer_text(self):
        lead = self.bundle['plan']['lead']
        self.assertEqual(lead['text'], excerpt_from_lead(lead))
        long_lead = {'text': '가나다 ' * 100}
        self.assertLessEqual(len(excerpt_from_lead(long_lead)), 241)
        self.assertTrue(excerpt_from_lead(long_lead).endswith('…'))

    def test_reviewed_inline_emphasis_renders_as_strong_without_changing_text(self):
        block = self.bundle['plan']['sections'][0]['paragraphs'][0]
        block['text'] = '수거함 지도에서 가까운 행정복지센터나 공동주택 수거함을 찾아보세요.'
        block['emphasis'] = ['가까운 행정복지센터나 공동주택 수거함']
        block['evidence'][0]['quote'] = block['text']
        self.bundle['sources'][0]['text'] = block['text']
        sign(self.bundle)
        page = render(self.bundle['plan'], self.bundle['sources'])
        self.assertIn(
            '<strong style="font-weight:700;color:#1f2937">가까운 행정복지센터나 공동주택 수거함</strong>',
            page,
        )
        from bs4 import BeautifulSoup
        paragraph = next(p for p in BeautifulSoup(page, 'html.parser').select('.bloguito-article > p')
                         if '행정복지센터나 공동주택 수거함' in p.get_text())
        self.assertEqual(block['text'], paragraph.get_text())

    def test_inline_emphasis_must_exist_in_reviewed_text(self):
        self.bundle['plan']['sections'][0]['paragraphs'][0]['emphasis'] = ['본문에 없는 문구']
        sign(self.bundle)
        self.assertIn('invalid_inline_emphasis', validate_bundle(self.bundle, self.inventory, NOW)['reasons'])


if __name__ == '__main__':
    unittest.main()
