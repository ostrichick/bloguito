import unittest
from datetime import date
from agents.search_intent import load_briefs, matches_brief

class SearchIntentTests(unittest.TestCase):
    def test_review_expiry(self):
        self.assertTrue(load_briefs('concert', date(2026,9,13)))
        self.assertEqual(load_briefs('concert', date(2026,9,16)), [])
    def test_no_broad_fallback(self):
        self.assertEqual(load_briefs('life-health', date(2026,9,13)), [])
    def test_other_city_rejected(self):
        brief=load_briefs('concert', date(2026,9,13))[0]
        self.assertFalse(matches_brief('무명전설 부산 앵콜', brief))
        self.assertTrue(matches_brief('무명전설 수원 앵콜 예매', brief))
