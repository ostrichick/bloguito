"""Guards for the explicitly authorized short-lived publication of legacy draft #229."""
import unittest
from datetime import date

from agents.editorial import dated_post_exception, topic_reasons


class Post229ChuseokSeoulWastePublishTests(unittest.TestCase):
    def setUp(self):
        self.urls = ['https://www.seoul.go.kr/story/thanksgiving/pc.html']
        self.brief = {
            'id': '2026-chuseok-seoul-waste-post-229-publish',
            'existing_post_id': 229,
            'content_type': 'dated',
            'useful_until': '2026-09-28',
            'official_urls': self.urls,
            'approved': True,
            'reviewed_at': '2026-09-24',
            'review_until': '2026-09-28',
            'category_key': 'life-health',
            'entity': '2026 추석 서울 생활폐기물 배출 일정',
            'primary_keyword': '2026 추석 서울 쓰레기 배출일',
            'question': '2026 추석 서울에서 날짜별로 어느 자치구가 쓰레기를 배출할 수 있나요?',
            'angle': '서울시 공식 자치구별 배출표와 시간 예외를 실전형으로 정리한다.',
            'required_title_terms': ['2026', '추석', '서울', '쓰레기'],
            'reader_questions': [{'id': 'q1', 'question': '내 자치구는 언제 배출하나요?'}],
        }

    def test_only_exact_existing_draft_229_gets_short_lifetime_exception(self):
        self.assertTrue(dated_post_exception(self.brief, date(2026, 9, 24)))
        self.assertFalse(dated_post_exception({**self.brief, 'existing_post_id': 230}, date(2026, 9, 24)))
        self.assertFalse(dated_post_exception({**self.brief, 'useful_until': '2026-09-27'}, date(2026, 9, 24)))
        self.assertFalse(dated_post_exception({**self.brief, 'official_urls': []}, date(2026, 9, 24)))
        self.assertFalse(dated_post_exception(self.brief, date(2026, 9, 29)))

    def test_other_short_lived_posts_still_fail_30_day_rule(self):
        self.assertNotIn('insufficient_useful_lifetime', topic_reasons(self.brief, date(2026, 9, 24)))
        other = {**self.brief, 'id': 'another-seoul-waste-post', 'existing_post_id': 230}
        self.assertIn('insufficient_useful_lifetime', topic_reasons(other, date(2026, 9, 24)))


if __name__ == '__main__':
    unittest.main()
