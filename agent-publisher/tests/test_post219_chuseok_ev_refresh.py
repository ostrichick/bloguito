"""Guards for the explicitly authorized short-lived refresh of existing post #219."""
import unittest
from datetime import date

from agents.editorial import dated_post_exception, topic_reasons


class Post219ChuseokEvRefreshTests(unittest.TestCase):
    def setUp(self):
        self.urls = [
            'https://www.korea.kr/news/policyNewsView.do?newsId=148972359',
            'https://www.kecowebzine.kr/data/vol53/sub0108.php',
            'https://www.opinet.co.kr/user/cusmartapp/cusmartappView.do',
        ]
        self.brief = {
            'id': '2026-chuseok-ev-post-219-refresh',
            'existing_post_id': 219,
            'content_type': 'dated',
            'useful_until': '2026-09-27',
            'official_urls': self.urls,
            'approved': True,
            'reviewed_at': '2026-09-24',
            'review_until': '2026-09-27',
            'category_key': 'life-health',
            'entity': '2026 추석 전기차 충전 할인·고속도로 휴게소 충전 계획',
            'primary_keyword': '2026 추석 전기차 충전 할인 휴게소 충전소',
            'question': '2026 추석 고속도로에서 전기차 충전 할인은 언제 어디에 적용되나?',
            'angle': '무료 오해를 바로잡고 할인 조건과 휴게소 충전 계획을 설명한다.',
            'required_title_terms': ['2026', '추석', '전기차'],
            'reader_questions': [{'id': 'q1', 'question': '무료 충전인가요?'}],
        }

    def test_only_exact_existing_post_219_gets_short_lifetime_exception(self):
        self.assertTrue(dated_post_exception(self.brief, date(2026, 9, 24)))
        self.assertFalse(dated_post_exception({**self.brief, 'existing_post_id': 220}, date(2026, 9, 24)))
        self.assertFalse(dated_post_exception({**self.brief, 'useful_until': '2026-09-28'}, date(2026, 9, 24)))
        self.assertFalse(dated_post_exception({**self.brief, 'official_urls': self.urls[:-1]}, date(2026, 9, 24)))
        self.assertFalse(dated_post_exception(self.brief, date(2026, 9, 28)))

    def test_other_short_lived_posts_still_fail_30_day_rule(self):
        self.assertNotIn('insufficient_useful_lifetime', topic_reasons(self.brief, date(2026, 9, 24)))
        other = {**self.brief, 'id': 'another-ev-post', 'existing_post_id': 220}
        self.assertIn('insufficient_useful_lifetime', topic_reasons(other, date(2026, 9, 24)))


if __name__ == '__main__':
    unittest.main()
