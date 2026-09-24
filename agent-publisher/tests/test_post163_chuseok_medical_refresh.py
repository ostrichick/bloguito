import unittest
from datetime import date
from unittest.mock import patch

from agents.editorial import dated_post_exception
from agents.editorial_writer import fetch_sources


class Post163ChuseokMedicalRefreshTests(unittest.TestCase):
    def setUp(self):
        self.brief = {
            'id': '2026-chuseok-medical-post-163-refresh',
            'existing_post_id': 163,
            'content_type': 'dated',
            'useful_until': '2026-09-27',
            'official_urls': [
                'https://admin2.korea.kr/briefing/pressReleaseView.do?newsId=156782659&pWise=mSub&pWiseSub=C1',
                'https://www.e-gen.or.kr/egen/holiday_medical.do?searchType=general&emergencyViewYn=N',
                'https://www.e-gen.or.kr/moonlight/main.do',
            ],
        }

    def test_exact_existing_post_scope_is_allowed(self):
        self.assertTrue(dated_post_exception(self.brief, date(2026, 9, 24)))

    def test_scope_does_not_transfer_to_other_post_or_source_set(self):
        other_post = {**self.brief, 'existing_post_id': 164}
        other_sources = {**self.brief, 'official_urls': self.brief['official_urls'][:-1]}
        self.assertFalse(dated_post_exception(other_post, date(2026, 9, 24)))
        self.assertFalse(dated_post_exception(other_sources, date(2026, 9, 24)))

    def test_exception_expires_after_holiday_window(self):
        self.assertFalse(dated_post_exception(self.brief, date(2026, 9, 28)))

    def test_koreakr_press_release_ignores_rotating_news_rail_but_hashes_article(self):
        class Response:
            status_code = 200

            def __init__(self, rail, total):
                self.content = (
                    '<html><head><title>정책브리핑</title></head><body>'
                    '<div class="article_wrap">'
                    '<div class="article_head">'
                    '<h1>추석 연휴에도 응급의료체계 24시간 가동</h1>'
                    '<div class="info"><span>2026.09.21</span><span>보건복지부</span></div>'
                    '</div><div class="article_body"><div class="view_cont">'
                    '<p>추석 연휴인 9월 24일부터 9월 27일까지 운영합니다.</p>'
                    f'<p>병원과 약국 하루 평균 총 {total}곳이 운영될 계획입니다.</p>'
                    '<p>운영 일정이 변경될 수 있어 방문 전 전화 확인이 필요합니다.</p>'
                    '</div></div></div>'
                    f'<aside>실시간 인기뉴스 {rail}</aside>'
                    '</body></html>'
                ).encode('utf-8')

        url = self.brief['official_urls'][0]
        with patch('agents.editorial_writer.requests.get', side_effect=[
            Response('14:07', '8,294'),
            Response('14:12', '8,294'),
            Response('14:17', '8,295'),
        ]):
            first, second, changed = (
                fetch_sources({'official_urls': [url], 'entity': '추석 비상진료'})[0]
                for _ in range(3)
            )
        self.assertEqual(first['sha256'], second['sha256'])
        self.assertNotEqual(first['sha256'], changed['sha256'])
        self.assertNotIn('실시간 인기뉴스', first['text'])
        self.assertIn('8,294', first['text'])


if __name__ == '__main__':
    unittest.main()
