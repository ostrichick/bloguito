"""Regression checks for the actual WordPress article HTML presentation."""
import copy
import sys
import unittest
from pathlib import Path

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agents.editorial import render


class ArticleLayoutTests(unittest.TestCase):
    def setUp(self):
        self.sources = [{'id': 's0', 'url': 'https://example.org/source',
                         'title': '기관 안내', 'text': '참고 원문'}]
        self.block = {'text': '내용입니다.',
                      'evidence': [{'source_id': 's0', 'quote': '참고 원문'}],
                      'answers': ['q1']}

    def plan(self):
        return {'title': '정보글', 'lead': copy.deepcopy(self.block),
                'sections': [
                    {'kind': 'overview', 'heading': '한눈에 보기', 'paragraphs': [copy.deepcopy(self.block)]},
                    {'kind': 'comparison', 'heading': '차이점', 'paragraphs': [copy.deepcopy(self.block)]},
                    {'kind': 'procedure', 'heading': '방문 전에 준비', 'paragraphs': [copy.deepcopy(self.block)]},
                    {'kind': 'exceptions', 'heading': '예외', 'paragraphs': [copy.deepcopy(self.block)]},
                ], 'faq': [{'question_id': 'q1', 'question': '질문인가요?',
                           'answer': copy.deepcopy(self.block)}]}

    def test_all_headings_have_consistent_typography_and_single_step_is_unnumbered(self):
        soup = BeautifulSoup(render(self.plan(), self.sources), 'html.parser')
        article = soup.select_one('.bloguito-article')
        self.assertIn('Malgun Gothic', article['style'])
        self.assertIn('letter-spacing:normal', article['style'])
        for heading in article.select('h2'):
            self.assertIn('font-family:inherit', heading['style'])
            self.assertIn('font-weight:700', heading['style'])
            self.assertIn('letter-spacing:normal', heading['style'])
        for paragraph in article.select(':scope > p'):
            self.assertIn('font-size:16px', paragraph['style'])
        self.assertNotIn('STEP 1', article.get_text(' ', strip=True))
        self.assertEqual(len(soup.select('nav.bloguito-toc')), 1)
        toc = soup.select_one('nav.bloguito-toc')
        self.assertNotIn('공식 출처', toc.get_text())
        self.assertIn('방문 전에 준비', toc.get_text())
        for link in toc.select('a[href^="#"]'):
            self.assertIsNotNone(soup.find(id=link['href'][1:]))

    def test_multiple_real_procedures_keep_matching_step_labels(self):
        plan = self.plan()
        plan['sections'].insert(3, {'kind': 'procedure', 'heading': '다음 단계',
                                     'paragraphs': [copy.deepcopy(self.block)]})
        soup = BeautifulSoup(render(plan, self.sources), 'html.parser')
        self.assertEqual([h.get_text(' ', strip=True) for h in soup.select('.bloguito-article > h2')
                          if 'STEP' in h.get_text()],
                         ['STEP 1 방문 전에 준비', 'STEP 2 다음 단계'])
        toc = soup.select_one('nav.bloguito-toc').get_text(' ', strip=True)
        self.assertIn('STEP 1. 방문 전에 준비', toc)
        self.assertIn('STEP 2. 다음 단계', toc)

    def test_paragraphs_tables_and_faq_are_preserved(self):
        plan = self.plan()
        plan['sections'][0]['table'] = {'caption': '기준 비교', 'headers': ['항목', '내용'],
                                        'rows': [{'cells': ['A', 'B'], 'evidence': [], 'answers': []}]}
        soup = BeautifulSoup(render(plan, self.sources), 'html.parser')
        self.assertEqual(len(soup.select('table caption')), 1)
        self.assertEqual(len(soup.select('th[scope="row"]')), 1)
        self.assertEqual(len(soup.select('.bloguito-faq')), 1)
        self.assertEqual(len(soup.select('.bloguito-summary')), 1)
        self.assertEqual(len(soup.select('#sources')), 1)


if __name__ == '__main__':
    unittest.main()
