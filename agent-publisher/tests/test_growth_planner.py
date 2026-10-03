"""Offline Daily Growth Planner tests; no WordPress or network calls."""

from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import tempfile
import unittest

from agents.growth_analysis import load_policy
from agents.growth_planner import decide_daily_action, save_daily_plan
from agents.growth_work_log import record_existing_completion, record_new_draft_completion
from agents.topic_scoring import topic_gate_digest


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "growth_policy.json"


def opportunities(pages=None, end="2026-09-29"):
    return {
        "schema_version": 1,
        "period": {"start": "2026-09-02", "end": end,
                   "timezone": "Google-property-specific"},
        "policy_version": 1,
        "pages": pages or [],
    }


def topic_scores(policy, rows=None, as_of="2026-10-03"):
    return {
        "schema_version": 1,
        "as_of_date": as_of,
        "policy_version": 1,
        "topic_gate_digest": topic_gate_digest(policy),
        "candidates": rows or [],
    }


def existing(post_id=345, classification="quick_win", confidence="high",
             impressions=53, slug="transport"):
    return {
        "post_id": post_id,
        "title": f"Post {post_id}",
        "permalink": f"https://lifeinfo24.org/p/{post_id}/",
        "category_slugs": [slug],
        "classification": classification,
        "confidence": confidence,
        "recommended_action": "inspect_title_snippet_and_search_intent",
        "search_console": {
            "clicks": 1, "impressions": impressions, "ctr": 1 / impressions,
            "position": 7.1,
        },
    }


def new_topic(brief_id="new-brief", score=90, category="welfare"):
    return {
        "id": "candidate-1",
        "brief_id": brief_id,
        "category_key": category,
        "topic": "신규 주제",
        "primary_keyword": "신규 검색어",
        "score": score,
        "confidence": "high",
        "measured_demand_present": True,
        "eligible_for_automation": True,
    }


class GrowthPlannerTests(unittest.TestCase):
    def setUp(self):
        self.policy = load_policy(POLICY)
        self.today = date(2026, 10, 3)
        self.slug_map = {"transport": "transport", "welfare": "welfare"}

    def decide(self, pages=None, topics=None, categories=None, end="2026-09-29",
               work_log=None, today=None):
        today = today or self.today
        return decide_daily_action(
            opportunities(pages, end=end),
            topic_scores(self.policy, topics, as_of=today.isoformat()), self.policy,
            as_of=today, work_log=work_log, category_keys=categories,
            category_slug_map=self.slug_map,
        )

    def test_existing_quick_win_blocks_unattended_new_draft(self):
        plan = self.decide([existing()], [new_topic()], ["transport", "welfare"])
        self.assertEqual("existing_improvement", plan["action"])
        self.assertEqual(345, plan["target"]["post_id"])
        self.assertEqual("work_mix_tie_prefer_existing", plan["reason"])

    def test_new_draft_selected_when_no_actionable_existing_page(self):
        plan = self.decide([], [new_topic()], ["welfare"])
        self.assertEqual("new_draft", plan["action"])
        self.assertEqual("new-brief", plan["target"]["brief_id"])

    def test_no_action_is_valid_when_nothing_is_eligible(self):
        plan = self.decide([], [], ["welfare"])
        self.assertEqual("no_action", plan["action"])
        self.assertEqual("no_actionable_existing_or_eligible_new_topic", plan["reason"])

    def test_stale_opportunity_report_fails_closed_even_with_new_topic(self):
        plan = self.decide([], [new_topic()], ["welfare"], end="2026-08-01")
        self.assertEqual("no_action", plan["action"])
        self.assertIn("opportunity_report_stale", plan["details"])

    def test_category_scope_does_not_let_transport_block_welfare_run(self):
        plan = self.decide([existing(slug="transport")], [new_topic(category="welfare")], ["welfare"])
        self.assertEqual("new_draft", plan["action"])
        self.assertEqual("welfare", plan["target"]["category_key"])

    def test_low_confidence_existing_does_not_block_new(self):
        plan = self.decide([existing(confidence="low")], [new_topic()], ["transport", "welfare"])
        self.assertEqual("new_draft", plan["action"])

    def test_completed_existing_is_suppressed_until_post_change_observation_window(self):
        first = self.decide([existing()], [new_topic()], ["transport", "welfare"])
        log = record_existing_completion(
            {"schema_version": 1, "entries": []}, first, self.policy,
            post_id=345, completed_on=self.today, note="verified edit-post readback",
        )
        second = self.decide(
            [existing()], [new_topic()], ["transport", "welfare"], work_log=log)
        self.assertEqual("new_draft", second["action"])
        self.assertEqual("new-brief", second["target"]["brief_id"])
        self.assertEqual("2026-10-17", log["entries"][0]["recheck_after"])

    def test_completed_existing_can_reenter_after_fresh_post_change_window(self):
        first = self.decide([existing()], [], ["transport"])
        log = record_existing_completion(
            {"schema_version": 1, "entries": []}, first, self.policy,
            post_id=345, completed_on=self.today)
        later = self.decide(
            [existing()], [], ["transport"], end="2026-10-17",
            work_log=log, today=date(2026, 10, 17))
        self.assertEqual("existing_improvement", later["action"])
        self.assertEqual(345, later["target"]["post_id"])

    def test_completed_top_candidate_allows_next_existing_candidate(self):
        first = self.decide(
            [existing(345, impressions=53), existing(400, classification="growth_candidate",
                                                     impressions=30)],
            [], ["transport"])
        log = record_existing_completion(
            {"schema_version": 1, "entries": []}, first, self.policy,
            post_id=345, completed_on=self.today)
        next_plan = self.decide(
            [existing(345, impressions=53), existing(400, classification="growth_candidate",
                                                     impressions=30)],
            [], ["transport"], work_log=log)
        self.assertEqual("existing_improvement", next_plan["action"])
        self.assertEqual(400, next_plan["target"]["post_id"])

    def test_work_mix_selects_new_after_recent_existing_completion(self):
        first = self.decide(
            [existing(345), existing(400, classification="growth_candidate", impressions=30)],
            [new_topic()], ["transport", "welfare"])
        log = record_existing_completion(
            {"schema_version": 1, "entries": []}, first, self.policy,
            post_id=345, completed_on=self.today)
        second = self.decide(
            [existing(345), existing(400, classification="growth_candidate", impressions=30)],
            [new_topic()], ["transport", "welfare"], work_log=log)
        self.assertEqual("new_draft", second["action"])
        self.assertEqual("work_mix_new_deficit", second["reason"])

    def test_work_mix_rotates_back_to_existing_after_balanced_new_completion(self):
        first = self.decide(
            [existing(345), existing(400, classification="growth_candidate", impressions=30)],
            [new_topic()], ["transport", "welfare"])
        log = record_existing_completion(
            {"schema_version": 1, "entries": []}, first, self.policy,
            post_id=345, completed_on=self.today)
        second = self.decide(
            [existing(345), existing(400, classification="growth_candidate", impressions=30)],
            [new_topic()], ["transport", "welfare"], work_log=log)
        log = record_new_draft_completion(
            log, second, self.policy, post_id=901, completed_on=self.today)
        third = self.decide(
            [existing(345), existing(400, classification="growth_candidate", impressions=30)],
            [new_topic("new-brief-2")], ["transport", "welfare"], work_log=log)
        self.assertEqual("existing_improvement", third["action"])
        self.assertEqual(400, third["target"]["post_id"])
        self.assertEqual("work_mix_tie_rotate_after_new", third["reason"])

    def test_completed_new_brief_is_not_selected_again(self):
        initial = self.decide([], [new_topic()], ["welfare"])
        log = record_new_draft_completion(
            {"schema_version": 1, "entries": []}, initial, self.policy,
            post_id=901, completed_on=self.today)
        next_plan = self.decide([], [new_topic()], ["welfare"], work_log=log)
        self.assertEqual("no_action", next_plan["action"])

    def test_malformed_work_log_fails_closed(self):
        plan = self.decide(
            [existing()], [new_topic()], ["transport", "welfare"],
            work_log={"schema_version": 1, "entries": [{"post_id": 345}]})
        self.assertEqual("no_action", plan["action"])
        self.assertIn("growth_work_log_invalid", plan["details"])

    def test_daily_plan_round_trip(self):
        plan = self.decide([], [], ["welfare"])
        with tempfile.TemporaryDirectory() as root:
            target = save_daily_plan(plan, Path(root) / "growth")
            self.assertEqual("daily-growth-plan.json", target.name)
            self.assertEqual(plan, json.loads(target.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
