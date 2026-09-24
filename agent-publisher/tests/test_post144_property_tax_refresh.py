"""Guards for the explicitly authorized short-lived refresh of existing post #144."""
import unittest
from datetime import date

from agents.editorial import dated_post_exception, topic_reasons
from agents.editorial_writer import _normalize_seocho_property_tax_text


class Post144PropertyTaxRefreshTests(unittest.TestCase):
    def setUp(self):
        self.urls = [
            'https://www.seoul.go.kr/news/news_report.do?bbsNo=158&nttNo=466367',
            'https://www.seocho.go.kr/site/tax/ex/bbs/View.do?bcIdx=410947&cbIdx=419&pageIndex=1&searchCondition=subCont&searchKeyword=',
            'https://www.seocho.go.kr/common/board/Download.do?bcIdx=410947&cbIdx=419&streFileNm=20260827082129_jvd73uu3wlkuxqisskay0zjbtjkz5dpu.pdf',
            'https://www.wetax.go.kr/main.do',
        ]
        self.brief = {
            'id': '2026-september-property-tax-post-144-refresh',
            'existing_post_id': 144,
            'content_type': 'dated',
            'useful_until': '2026-09-30',
            'official_urls': self.urls,
            'approved': True,
            'reviewed_at': '2026-09-24',
            'review_until': '2026-09-30',
            'category_key': 'tax',
            'entity': '2026년 9월 재산세',
            'primary_keyword': '2026 9월 재산세 납부 기간 분납 위택스 ETAX',
            'question': '2026년 9월 재산세는 누가 언제까지 내고 분납과 온라인 납부는 어떻게 하나요?',
            'angle': '9월 정기분 대상, 과세기준일, 납부기한, 분납 기준과 서울·비서울 납부 경로를 구분',
            'required_title_terms': ['2026', '재산세', '9월'],
            'reader_questions': [{'id': 'q1', 'question': '언제까지 납부하나요?'}],
        }

    def test_only_exact_existing_post_144_gets_short_lifetime_exception(self):
        self.assertTrue(dated_post_exception(self.brief, date(2026, 9, 24)))
        self.assertFalse(dated_post_exception({**self.brief, 'existing_post_id': 145}, date(2026, 9, 24)))
        self.assertFalse(dated_post_exception({**self.brief, 'useful_until': '2026-10-01'}, date(2026, 9, 24)))
        self.assertFalse(dated_post_exception({**self.brief, 'official_urls': self.urls[:-1]}, date(2026, 9, 24)))
        self.assertFalse(dated_post_exception(self.brief, date(2026, 10, 1)))

    def test_other_short_lived_posts_still_fail_30_day_rule(self):
        self.assertNotIn('insufficient_useful_lifetime', topic_reasons(self.brief, date(2026, 9, 24)))
        other = {**self.brief, 'id': 'another-property-tax-post', 'existing_post_id': 145}
        self.assertIn('insufficient_useful_lifetime', topic_reasons(other, date(2026, 9, 24)))

    def test_only_standalone_view_counter_is_normalized(self):
        url = self.urls[1]
        before = '등록일\n2026.08.27\n조회수\n668\n본문\n재산세 250만원 초과\n본문의 조회수 30회 조건'
        after = before.replace('\n668\n', '\n670\n')
        first = _normalize_seocho_property_tax_text(before, url)
        second = _normalize_seocho_property_tax_text(after, url)
        self.assertEqual(first, second)
        self.assertNotIn('\n조회수\n668\n', first)
        self.assertIn('재산세 250만원 초과', first)
        self.assertIn('본문의 조회수 30회 조건', first)


if __name__ == '__main__':
    unittest.main()
