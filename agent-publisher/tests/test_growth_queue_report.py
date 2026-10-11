import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.report_growth_queue import report_queue


class GrowthQueueReportTests(unittest.TestCase):
    def setUp(self):
        self.opps = {"schema_version": 1, "provenance_contract_version": 1,
                     "refresh_id": "r", "opportunity_payload_sha256": "a",
                     "period": {"end": "2026-10-10"}, "pages": []}
        self.scores = {
            "schema_version": 1, "refresh_id": "r", "opportunity_payload_sha256": "a",
            "growth_period_end": "2026-10-10", "as_of_date": "2026-10-11",
            "candidates": [{"id": "c1", "brief_id": "b1", "topic": "어르신 돌봄",
                            "score": 65, "confidence": "medium",
                            "eligible_for_automation": False,
                            "measured_demand_present": False,
                            "reasons": ["no_fresh_measured_demand_evidence",
                                        "score_below_automation_threshold"]}],
        }
        self.plan = {"schema_version": 1, "as_of_date": "2026-10-11",
                     "action": "no_action", "reason": "no_actionable_existing_or_eligible_new_topic",
                     "target": None, "details": []}
        self.log = {"schema_version": 1, "entries": []}

    def test_read_only_queue_reports_hold_causes_without_invented_demand(self):
        result = report_queue(self.opps, self.scores, self.plan, self.log)
        self.assertEqual("complete", result["status"])
        self.assertEqual(1, result["summary"]["candidates"])
        self.assertEqual(0, result["summary"]["eligible"])
        self.assertEqual(["collect_measured_demand", "improve_topic_differentiation"],
                         result["candidates"][0]["next_actions"])
        self.assertFalse(result["candidates"][0]["measured_demand_present"])

    def test_missing_or_mismatched_provenance_never_exposes_action_target(self):
        self.plan.update(action="new_draft", target={"brief_id": "b1"})
        mismatch = report_queue(self.opps, {**self.scores, "refresh_id": "other"},
                                self.plan, self.log)
        self.assertEqual("provenance_mismatch", mismatch["status"])
        self.assertIsNone(mismatch["daily_plan"]["target"])
        missing = report_queue(None, self.scores, self.plan, self.log)
        self.assertEqual("incomplete_inputs", missing["status"])
        self.assertIsNone(missing["daily_plan"]["target"])

    def test_invalid_candidate_is_not_silently_counted(self):
        self.scores["candidates"][0]["eligible_for_automation"] = "yes"
        with self.assertRaisesRegex(ValueError, "growth_candidate_invalid"):
            report_queue(self.opps, self.scores, self.plan, self.log)


if __name__ == "__main__":
    unittest.main()
