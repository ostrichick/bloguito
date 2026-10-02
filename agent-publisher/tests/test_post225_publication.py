"""Regression guards for the explicitly authorized short-lived legacy draft."""
import unittest
from datetime import date

from agents.editorial import dated_post_exception, topic_reasons


class Post225PublicationTests(unittest.TestCase):
    def setUp(self):
        self.brief = {
            'id': '2026-chuseok-bank-post-225', 'existing_post_id': 225,
            'content_type': 'dated', 'useful_until': '2026-09-27',
            'official_urls': [
                'https://fsc.go.kr/no010101/87706',
                'https://fsc.go.kr/comm/getFile?srvcId=BBSTY1&upperNo=87706&fileTy=ATTACH&fileNo=2',
            ],
            'approved': True, 'reviewed_at': '2026-09-22',
            'review_until': '2026-09-27', 'category_key': 'finance',
            'entity': '추석 은행', 'primary_keyword': '추석 은행',
            'question': '어디서 이용할 수 있나?', 'angle': '공식 일정',
            'required_title_terms': ['추석', '은행'],
            'reader_questions': [{'id': 'q1', 'question': '어디서?'}],
        }

    def test_only_existing_post_225_during_the_holiday_has_short_lifetime_exception(self):
        self.assertTrue(dated_post_exception(self.brief, date(2026, 9, 22)))
        self.assertFalse(dated_post_exception({**self.brief, 'existing_post_id': 226}, date(2026, 9, 22)))
        self.assertFalse(dated_post_exception({**self.brief, 'useful_until': '2026-09-28'}, date(2026, 9, 22)))
        self.assertFalse(dated_post_exception({**self.brief, 'official_urls': ['https://example.org']}, date(2026, 9, 22)))
        self.assertFalse(dated_post_exception({**self.brief, 'official_urls': self.brief['official_urls'][:1]}, date(2026, 9, 22)))
        self.assertFalse(dated_post_exception(self.brief, date(2026, 9, 28)))

    def test_exception_does_not_make_other_short_lived_articles_eligible(self):
        self.assertNotIn('insufficient_useful_lifetime', topic_reasons(self.brief, date(2026, 9, 22)))
        other = {**self.brief, 'id': 'other-dated-post', 'existing_post_id': 226}
        self.assertIn('insufficient_useful_lifetime', topic_reasons(other, date(2026, 9, 22)))

if __name__ == '__main__':
    unittest.main()
