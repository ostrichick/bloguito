"""Guards for the explicitly authorized short-lived publication of legacy draft #237."""
import unittest
from datetime import date

from agents.editorial import dated_post_exception, topic_reasons


class Post237ChuseokFreeParkingPublishTests(unittest.TestCase):
    def setUp(self):
        self.urls = [
            'https://admin2.korea.kr/briefing/pressReleaseView.do?gubun=pressRelease&newsId=156782886&pageIndex=1&repCode=A00031',
            'https://enews.sen.go.kr/news/view.do?bbsSn=192165&step1=3&step2=1',
        ]
        self.brief = {
            'id': '2026-chuseok-free-parking-post-237-publish',
            'existing_post_id': 237,
            'content_type': 'dated',
            'useful_until': '2026-09-27',
            'official_urls': self.urls,
            'approved': True,
            'reviewed_at': '2026-09-24',
            'review_until': '2026-09-27',
            'category_key': 'life-health',
            'entity': '2026 추석 무료 공공주차장 검색과 이용 조건',
            'primary_keyword': '2026 추석 무료 공공주차장 공유누리',
            'question': '2026 추석 무료 공공주차장을 어디서 찾고 운영시간은 어떻게 확인하나요?',
            'angle': '행정안전부의 최신 전국 무료 개방 정보와 검색 절차를 설명한다.',
            'required_title_terms': ['2026', '추석', '무료', '주차장'],
            'reader_questions': [{'id': 'q1', 'question': '무료주차장은 어디서 찾나요?'}],
        }

    def test_only_exact_existing_draft_237_gets_short_lifetime_exception(self):
        self.assertTrue(dated_post_exception(self.brief, date(2026, 9, 24)))
        self.assertFalse(dated_post_exception({**self.brief, 'existing_post_id': 238}, date(2026, 9, 24)))
        self.assertFalse(dated_post_exception({**self.brief, 'useful_until': '2026-09-28'}, date(2026, 9, 24)))
        self.assertFalse(dated_post_exception({**self.brief, 'official_urls': self.urls[:-1]}, date(2026, 9, 24)))
        self.assertFalse(dated_post_exception(self.brief, date(2026, 9, 28)))

    def test_other_short_lived_posts_still_fail_30_day_rule(self):
        self.assertNotIn('insufficient_useful_lifetime', topic_reasons(self.brief, date(2026, 9, 24)))
        other = {**self.brief, 'id': 'another-free-parking-post', 'existing_post_id': 238}
        self.assertIn('insufficient_useful_lifetime', topic_reasons(other, date(2026, 9, 24)))


if __name__ == '__main__':
    unittest.main()
