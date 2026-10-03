"""P4 private growth-work completion log tests."""

from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import tempfile
import unittest

from agents.growth_analysis import load_policy
from agents.growth_planner import daily_planner_digest
from agents.growth_work_log import (
    completed_new_brief_ids,
    GrowthWorkLogError,
    empty_work_log,
    record_existing_completion,
    record_new_draft_completion,
    recent_work_mix,
    save_work_log,
    suppressed_post_ids,
)


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "growth_policy.json"


def plan(policy, post_id=345):
    return {
        "schema_version": 1,
        "as_of_date": "2026-10-03",
        "action": "existing_improvement",
        "daily_planner_digest": daily_planner_digest(policy),
        "inputs": {"opportunity_period_end": "2026-09-29"},
        "target": {
            "post_id": post_id,
            "title": "고속버스 취소표",
            "classification": "quick_win",
            "recommended_action": "inspect_title_snippet_and_search_intent",
        },
    }


def new_plan(policy, brief_id="new-brief"):
    return {
        "schema_version": 1,
        "as_of_date": "2026-10-03",
        "action": "new_draft",
        "daily_planner_digest": daily_planner_digest(policy),
        "inputs": {"opportunity_period_end": "2026-09-29"},
        "target": {
            "brief_id": brief_id,
            "candidate_id": "candidate-1",
            "category_key": "welfare",
        },
    }


class GrowthWorkLogTests(unittest.TestCase):
    def setUp(self):
        self.policy = load_policy(POLICY)
        self.completed_on = date(2026, 10, 3)

    def test_completion_is_bound_to_selected_post_and_is_idempotent(self):
        log = record_existing_completion(
            empty_work_log(), plan(self.policy), self.policy,
            post_id=345, completed_on=self.completed_on, note="readback verified")
        again = record_existing_completion(
            log, plan(self.policy), self.policy,
            post_id=345, completed_on=self.completed_on, note="readback verified")
        self.assertEqual(1, len(again["entries"]))
        row = again["entries"][0]
        self.assertEqual("2026-10-17", row["recheck_after"])
        self.assertEqual("readback verified", row["note"])

    def test_wrong_post_or_non_existing_plan_is_rejected(self):
        with self.assertRaisesRegex(GrowthWorkLogError, "daily_growth_plan_post_mismatch"):
            record_existing_completion(
                empty_work_log(), plan(self.policy), self.policy,
                post_id=400, completed_on=self.completed_on)
        not_existing = dict(plan(self.policy), action="new_draft")
        with self.assertRaisesRegex(GrowthWorkLogError, "daily_growth_plan_not_existing_improvement"):
            record_existing_completion(
                empty_work_log(), not_existing, self.policy,
                post_id=345, completed_on=self.completed_on)

    def test_policy_change_invalidates_old_daily_plan_for_completion(self):
        changed = json.loads(json.dumps(self.policy))
        changed["daily_planner"]["existing_recheck_days"] = 21
        with self.assertRaisesRegex(GrowthWorkLogError, "daily_growth_plan_policy_mismatch"):
            record_existing_completion(
                empty_work_log(), plan(self.policy), changed,
                post_id=345, completed_on=self.completed_on)

    def test_completion_requires_a_plan_from_the_same_operator_day(self):
        stale_plan = dict(plan(self.policy), as_of_date="2026-10-02")
        with self.assertRaisesRegex(
                GrowthWorkLogError, "daily_growth_plan_not_current_for_completion"):
            record_existing_completion(
                empty_work_log(), stale_plan, self.policy,
                post_id=345, completed_on=self.completed_on)

    def test_suppression_expires_only_when_opportunity_period_reaches_recheck_date(self):
        log = record_existing_completion(
            empty_work_log(), plan(self.policy), self.policy,
            post_id=345, completed_on=self.completed_on)
        self.assertEqual(
            {345}, suppressed_post_ids(
                log, opportunity_period_end=date(2026, 10, 16), as_of=date(2026, 10, 16)))
        self.assertEqual(
            set(), suppressed_post_ids(
                log, opportunity_period_end=date(2026, 10, 17), as_of=date(2026, 10, 17)))

    def test_new_draft_completion_blocks_same_brief_and_updates_mix(self):
        log = record_new_draft_completion(
            empty_work_log(), new_plan(self.policy), self.policy,
            post_id=901, completed_on=self.completed_on, title="신규 글")
        self.assertEqual({"new-brief"}, completed_new_brief_ids(log, as_of=self.completed_on))
        mix = recent_work_mix(log, as_of=self.completed_on, limit=8)
        self.assertEqual(0, mix["existing_improvement"])
        self.assertEqual(1, mix["new_draft"])
        self.assertEqual("new_draft", mix["last_action"])
        with self.assertRaisesRegex(GrowthWorkLogError, "growth_new_brief_already_completed"):
            record_new_draft_completion(
                log, new_plan(self.policy), self.policy,
                post_id=902, completed_on=self.completed_on, title="중복")

    def test_new_draft_completion_requires_current_matching_plan(self):
        wrong_action = dict(new_plan(self.policy), action="existing_improvement")
        with self.assertRaisesRegex(GrowthWorkLogError, "daily_growth_plan_not_new_draft"):
            record_new_draft_completion(
                empty_work_log(), wrong_action, self.policy,
                post_id=901, completed_on=self.completed_on)

    def test_work_log_round_trip(self):
        log = record_existing_completion(
            empty_work_log(), plan(self.policy), self.policy,
            post_id=345, completed_on=self.completed_on)
        log = record_new_draft_completion(
            log, new_plan(self.policy), self.policy,
            post_id=901, completed_on=self.completed_on)
        with tempfile.TemporaryDirectory() as root:
            target = save_work_log(log, Path(root) / "growth-work-log.json")
            self.assertEqual(log, json.loads(target.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
