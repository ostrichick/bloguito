"""Policy-news article changes must affect source hashes; rotating chrome must not."""
import hashlib
import unittest
from unittest.mock import patch

from agents.editorial_writer import fetch_sources


URL = 'https://www.korea.kr/news/policyNewsView.do?newsId=148959616'
ARTICLE = ('공식 본문에는 소형 가전 5개 기준과 냉장고 1개 신청 경로가 설명되어 있습니다. '
           '전용 수거함의 표시는 배출 전에 확인해야 합니다. ' * 3)


class Response:
    status_code = 200

    def __init__(self, body):
        self.content = body.encode('utf-8')


def article_page(*, article=ARTICLE, rail='실시간 인기뉴스 오늘의 뉴스', heading='폐가전 배출 관련 정책 기사', date='2026.02.19'):
    return ('<html><head><title>정책뉴스 | 정책브리핑</title></head><body>'
            '<main id="main"><section id="container">'
            f'<div class="view_title"><h1>{heading}</h1></div>'
            '<div class="article_wrap">'
            '<div class="article_head"><h2>2026년 폐가전 수거 기준과 수거함 안내</h2>'
            f'<div class="variety"><span>{date}</span><span>정책기자단</span>'
            '<span>글자크기 최대크게</span></div></div>'
            '<div class="article_body"><div class="view_cont">'
            f'<p>{article}</p><p>수거 신청은 공식 홈페이지와 전화로 가능합니다.</p>'
            '</div></div><div class="article_footer">가변 조회수 78</div></div>'
            f'<div class="article box"><h2>정책 NOW</h2><p>{rail}</p></div>'
            '</section></main></body></html>')


def fetch_one(url, html):
    with patch('agents.editorial_writer.requests.get', return_value=Response(html)):
        return fetch_sources({'official_urls': [url], 'entity': '폐가전'})[0]


class KoreaKrArticleSourceTests(unittest.TestCase):
    def test_dynamic_news_and_view_metadata_do_not_change_hash(self):
        first = fetch_one(URL, article_page(rail='정책 NOW 20:00 인기뉴스 A'))
        second = fetch_one(URL, article_page(rail='정책 NOW 20:05 인기뉴스 B'))
        self.assertEqual(first['sha256'], second['sha256'])
        self.assertEqual(first['sha256'], hashlib.sha256(first['text'].encode()).hexdigest())
        self.assertIn('소형 가전 5개 기준', first['text'])
        self.assertIn('2026.02.19', first['text'])
        self.assertIn('공식 홈페이지와 전화', first['text'])
        self.assertNotIn('인기뉴스', first['text'])
        self.assertNotIn('글자크기', first['text'])

    def test_article_body_title_and_date_changes_change_hash(self):
        first = fetch_one(URL, article_page())
        for page in (article_page(article=ARTICLE.replace('5개 기준', '6개 기준')),
                     article_page(heading='폐가전 수거 변경 공지'),
                     article_page(date='2026.02.20')):
            with self.subTest(page=page[:90]):
                self.assertNotEqual(first['sha256'], fetch_one(URL, page)['sha256'])

    def test_missing_or_ambiguous_article_fails_closed(self):
        with self.assertRaisesRegex(ValueError, 'koreakr_article_main_missing_or_ambiguous'):
            fetch_one(URL, article_page().replace('class="view_cont"', 'class="other"'))
        with self.assertRaisesRegex(ValueError, 'koreakr_article_main_missing_or_ambiguous'):
            fetch_one(URL, article_page().replace('<div class="article_body">',
                                                   '<div class="article_body"><div class="view_cont">duplicate</div>'))

    def test_other_hosts_keep_existing_generic_extraction(self):
        html = '<html><head><title>Example</title></head><body><p>' + ARTICLE + '</p></body></html>'
        source = fetch_one('https://example.org/news/policyNewsView.do?newsId=148959616', html)
        self.assertIn(ARTICLE.strip(), source['text'])


if __name__ == '__main__':
    unittest.main()
