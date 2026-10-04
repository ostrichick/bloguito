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
            "editorial_provenance": {
                "classification": "reviewed_exact",
                "auto_adoptable": True,
                "live_status": "publish",
                "live_content_sha256": "a" * 64,
                "review_digest": "b" * 64,
                "bundle_digest": "c" * 64,
                "provenance_variant": "current",
                "canonical_category_key": "transport",
            },
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


def receipt(post_id=345, before="a" * 64):
    return {
        "action": "edit-post",
        "post_id": post_id,
        "target_status": "publish",
        "before_content_sha256": before,
        "after_content_sha256": "d" * 64,
        "review_digest": "e" * 64,
        "bundle_digest": "f" * 64,
        "provenance_variant": "current",
        "readback_verified": True,
    }


class GrowthWorkLogTests(unittest.TestCase):
    def setUp(self):
        self.policy = load_policy(POLICY)
        self.completed_on = date(2026, 10, 3)

    def test_completion_is_bound_to_selected_post_and_is_idempotent(self):
        log = record_existing_completion(
            empty_work_log(), plan(self.policy), self.policy,
            post_id=345, completed_on=self.completed_on, edit_receipt=receipt(),
            note="readback verified")
        again = record_existing_completion(
            log, plan(self.policy), self.policy,
            post_id=345, completed_on=self.completed_on, edit_receipt=receipt(),
            note="readback verified")
        self.assertEqual(1, len(again["entries"]))
        row = again["entries"][0]
        self.assertEqual("2026-10-17", row["recheck_after"])
        self.assertEqual("readback verified", row["note"])
        self.assertEqual("a" * 64, row["baseline_provenance"]["live_content_sha256"])
        self.assertEqual("d" * 64, row["completion_receipt"]["after_content_sha256"])

    def test_wrong_post_or_non_existing_plan_is_rejected(self):
        with self.assertRaisesRegex(GrowthWorkLogError, "daily_growth_plan_post_mismatch"):
            record_existing_completion(
                empty_work_log(), plan(self.policy), self.policy,
                post_id=400, completed_on=self.completed_on, edit_receipt=receipt(400))
        not_existing = dict(plan(self.policy), action="new_draft")
        with self.assertRaisesRegex(GrowthWorkLogError, "daily_growth_plan_not_existing_improvement"):
            record_existing_completion(
                empty_work_log(), not_existing, self.policy,
                post_id=345, completed_on=self.completed_on, edit_receipt=receipt())

    def test_existing_completion_rejects_plan_without_exact_provenance_binding(self):
        unbound = plan(self.policy)
        unbound["target"] = dict(unbound["target"])
        unbound["target"]["editorial_provenance"] = {
            **unbound["target"]["editorial_provenance"],
            "classification": "live_content_changed",
            "auto_adoptable": False,
        }
        with self.assertRaisesRegex(GrowthWorkLogError, "daily_growth_plan_provenance_unbound"):
            record_existing_completion(
                empty_work_log(), unbound, self.policy,
                post_id=345, completed_on=self.completed_on, edit_receipt=receipt())

    def test_existing_completion_rejects_edit_receipt_not_bound_to_plan_baseline(self):
        wrong = receipt(before="0" * 64)
        with self.assertRaisesRegex(GrowthWorkLogError, "growth_completion_edit_receipt_unbound"):
            record_existing_completion(
                empty_work_log(), plan(self.policy), self.policy,
                post_id=345, completed_on=self.completed_on, edit_receipt=wrong)

    def test_policy_change_invalidates_old_daily_plan_for_completion(self):
        changed = json.loads(json.dumps(self.policy))
        changed["daily_planner"]["existing_recheck_days"] = 21
        with self.assertRaisesRegex(GrowthWorkLogError, "daily_growth_plan_policy_mismatch"):
            record_existing_completion(
                empty_work_log(), plan(self.policy), changed,
                post_id=345, completed_on=self.completed_on, edit_receipt=receipt())

    def test_completion_requires_a_plan_from_the_same_operator_day(self):
        stale_plan = dict(plan(self.policy), as_of_date="2026-10-02")
        with self.assertRaisesRegex(
                GrowthWorkLogError, "daily_growth_plan_not_current_for_completion"):
            record_existing_completion(
                empty_work_log(), stale_plan, self.policy,
                post_id=345, completed_on=self.completed_on, edit_receipt=receipt())

    def test_suppression_expires_only_when_opportunity_period_reaches_recheck_date(self):
        log = record_existing_completion(
            empty_work_log(), plan(self.policy), self.policy,
            post_id=345, completed_on=self.completed_on, edit_receipt=receipt())
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
            post_id=345, completed_on=self.completed_on, edit_receipt=receipt())
        log = record_new_draft_completion(
            log, new_plan(self.policy), self.policy,
            post_id=901, completed_on=self.completed_on)
        with tempfile.TemporaryDirectory() as root:
            target = save_work_log(log, Path(root) / "growth-work-log.json")
            self.assertEqual(log, json.loads(target.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
