"""Guards for the explicitly authorized short-lived refresh of existing post #217."""
import unittest
from datetime import date

from agents.editorial import dated_post_exception, topic_reasons


class Post217ChuseokRailRefreshTests(unittest.TestCase):
    def setUp(self):
        self.urls = [
            'https://m.letskorail.com/mbt/m_notice.html',
            'https://info.korail.com/info/selectBbsNttView.do?bbsNo=199&integrDeptCode=&key=911&nttNo=27291&pageIndex=1&searchCnd=all&searchCtgry=&searchKrwd=',
            'https://info.korail.com/info/selectBbsNttView.do?bbsNo=199&integrDeptCode=&key=911&nttNo=27135&pageIndex=1&searchCnd=CN&searchCtgry=&searchKrwd=%EC%82%B0%EC%B2%9C',
            'https://www.korail.com/ticket/main',
        ]
        self.brief = {
            'id': '2026-chuseok-rail-post-217-refresh',
            'existing_post_id': 217,
            'content_type': 'dated',
            'useful_until': '2026-09-27',
            'official_urls': self.urls,
            'approved': True,
            'reviewed_at': '2026-09-24',
            'review_until': '2026-09-27',
            'category_key': 'life-health',
            'entity': '2026 추석 KTX 취소표',
            'primary_keyword': '2026 추석 KTX 취소표',
            'question': '추석 KTX가 매진일 때 공식 잔여석과 반환 좌석을 어디서 확인하고 어떤 대안을 순서대로 볼 수 있나요?',
            'angle': '공식 잔여석 판매와 통합 예매 이후의 실전 조회 순서',
            'required_title_terms': ['추석', 'KTX', '취소표'],
            'reader_questions': [{'id': 'q1', 'question': '취소표를 어디서 확인하나요?'}],
        }

    def test_only_exact_existing_post_217_gets_short_lifetime_exception(self):
        self.assertTrue(dated_post_exception(self.brief, date(2026, 9, 24)))
        self.assertFalse(dated_post_exception({**self.brief, 'existing_post_id': 218}, date(2026, 9, 24)))
        self.assertFalse(dated_post_exception({**self.brief, 'useful_until': '2026-09-28'}, date(2026, 9, 24)))
        self.assertFalse(dated_post_exception({**self.brief, 'official_urls': self.urls[:-1]}, date(2026, 9, 24)))
        self.assertFalse(dated_post_exception(self.brief, date(2026, 9, 28)))

    def test_other_short_lived_posts_still_fail_30_day_rule(self):
        self.assertNotIn('insufficient_useful_lifetime', topic_reasons(self.brief, date(2026, 9, 24)))
        other = {**self.brief, 'id': 'another-rail-post', 'existing_post_id': 218}
        self.assertIn('insufficient_useful_lifetime', topic_reasons(other, date(2026, 9, 24)))


if __name__ == '__main__':
    unittest.main()
