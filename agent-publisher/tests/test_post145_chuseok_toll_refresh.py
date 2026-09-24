"""Guards for the explicitly authorized short-lived refresh of existing post #145."""
import unittest
from datetime import date

from agents.editorial import dated_post_exception, topic_reasons


class Post145ChuseokTollRefreshTests(unittest.TestCase):
    def setUp(self):
        self.urls = [
            'https://www.korea.kr/common/download.do?fileId=198558067&tblKey=GMN',
        ]
        self.brief = {
            'id': '2026-chuseok-toll-post-145-refresh',
            'existing_post_id': 145,
            'content_type': 'dated',
            'useful_until': '2026-09-27',
            'official_urls': self.urls,
            'approved': True,
            'reviewed_at': '2026-09-24',
            'review_until': '2026-09-27',
            'category_key': 'life-health',
            'entity': '2026 추석 고속도로 통행료',
            'primary_keyword': '2026 추석 고속도로 통행료 무료 기간',
            'question': '2026 추석 고속도로 통행료는 언제부터 언제까지 무료이고 하이패스와 일반차로는 어떻게 이용하나요?',
            'angle': '9월 22일 국무회의 확정 자료로 무료 시간, 경계 차량, 민자고속도로, 하이패스 이용법을 정리',
            'required_title_terms': ['2026', '추석', '고속도로', '통행료'],
            'reader_questions': [{'id': 'q1', 'question': '무료 기간은 언제인가요?'}],
        }

    def test_only_exact_existing_post_145_gets_short_lifetime_exception(self):
        self.assertTrue(dated_post_exception(self.brief, date(2026, 9, 24)))
        self.assertFalse(dated_post_exception({**self.brief, 'existing_post_id': 146}, date(2026, 9, 24)))
        self.assertFalse(dated_post_exception({**self.brief, 'useful_until': '2026-09-28'}, date(2026, 9, 24)))
        self.assertFalse(dated_post_exception({**self.brief, 'official_urls': []}, date(2026, 9, 24)))
        self.assertFalse(dated_post_exception(self.brief, date(2026, 9, 28)))

    def test_other_short_lived_posts_still_fail_30_day_rule(self):
        self.assertNotIn('insufficient_useful_lifetime', topic_reasons(self.brief, date(2026, 9, 24)))
        other = {**self.brief, 'id': 'another-toll-post', 'existing_post_id': 146}
        self.assertIn('insufficient_useful_lifetime', topic_reasons(other, date(2026, 9, 24)))


if __name__ == '__main__':
    unittest.main()
