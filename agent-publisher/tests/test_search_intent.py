import unittest
import json
from datetime import date
from unittest.mock import patch
from agents.search_intent import load_briefs, matches_brief
from agents.radar import RadarAgent
from agents.growth_analysis import load_policy
from agents.topic_scoring import topic_gate_digest
from pathlib import Path

class SearchIntentTests(unittest.TestCase):
    def setUp(self):
        self.inventory = patch('agents.search_intent.INVENTORY')
        mocked = self.inventory.start()
        mocked.read_text.return_value = '{"checked_on":"2026-09-13","posts":[]}'
        self.addCleanup(self.inventory.stop)
    def test_review_expiry(self):
        self.assertTrue(load_briefs('concert', date(2026,9,13)))
        self.assertEqual(load_briefs('concert', date(2026,9,16)), [])
    def test_no_broad_fallback(self):
        self.assertEqual(load_briefs('life-health', date(2026,9,13)), [])
    def test_other_city_rejected(self):
        brief=load_briefs('concert', date(2026,9,13))[0]
        self.assertFalse(matches_brief('무명전설 부산 앵콜', brief))
        self.assertTrue(matches_brief('무명전설 수원 앵콜 예매', brief))

    def test_scheduler_gate_blocks_brief_without_private_score_report(self):
        with patch('agents.search_intent.GROWTH_SCORE_REPORT') as score_file:
            score_file.read_text.side_effect = OSError('missing')
            self.assertEqual(
                [], load_briefs('concert', date(2026, 9, 13), require_growth_gate=True))

    def test_scheduler_gate_accepts_only_matching_current_eligible_score(self):
        policy = load_policy(Path(__file__).resolve().parents[1] / 'growth_policy.json')
        report = {
            'schema_version': 1,
            'as_of_date': '2026-09-13',
            'policy_version': 1,
            'topic_gate_digest': topic_gate_digest(policy),
            'candidates': [{
                'brief_id': 'mumyeong-suwon-2026',
                'category_key': 'concert',
                'primary_keyword': '무명전설 수원 앵콜 예매',
                'score': 80,
                'confidence': 'medium',
                'measured_demand_present': True,
                'eligible_for_automation': True,
            }],
        }
        with patch('agents.search_intent.GROWTH_SCORE_REPORT') as score_file:
            score_file.read_text.return_value = json.dumps(report, ensure_ascii=False)
            briefs = load_briefs('concert', date(2026, 9, 13), require_growth_gate=True)
        self.assertEqual(['mumyeong-suwon-2026'], [brief['id'] for brief in briefs])

    def test_invalid_inventory_shape_fails_closed_instead_of_crashing(self):
        with patch('agents.search_intent.INVENTORY') as inventory:
            inventory.read_text.return_value = '[]'
            self.assertEqual([], load_briefs('concert', date(2026, 9, 13)))

    def test_radar_always_requests_growth_gate_for_scheduled_discovery(self):
        with patch('agents.radar.load_briefs', return_value=[]) as load, patch('builtins.print'):
            self.assertEqual([], RadarAgent().search_news('welfare'))
        load.assert_called_once_with('welfare', require_growth_gate=True)
