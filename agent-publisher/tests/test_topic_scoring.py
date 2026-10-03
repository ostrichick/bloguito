"""Offline P2 topic-demand scoring and scheduler-gate tests."""

from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import tempfile
import unittest

from agents.growth_analysis import load_policy
from agents.topic_scoring import (
    TopicScoringError,
    brief_value_gate_reasons,
    brief_growth_gate_reasons,
    save_topic_scores,
    score_candidates,
    topic_gate_digest,
)


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "growth_policy.json"


def growth_report(*, end="2026-09-29", queries=None):
    return {
        "schema_version": 1,
        "period": {"start": "2026-09-02", "end": end,
                   "timezone": "Google-property-specific"},
        "top_queries_global": queries or [],
    }


def candidate(**overrides):
    value = {
        "id": "resident-docs-candidate",
        "brief_id": "resident-docs-brief",
        "category_key": "life-admin",
        "topic": "주민등록등본 인터넷 발급",
        "primary_keyword": "주민등록등본 인터넷 무료 발급",
        "gsc_terms": ["주민등록등본"],
        "demand_evidence": [{
            "source": "keyword_planner",
            "metric": "avg_monthly_searches",
            "value": 1000,
            "collected_at": "2026-10-01",
            "measured": True,
        }],
        "click_need": "high",
        "ai_answerability": "low",
        "added_value": ["official_action", "troubleshooting", "comparison"],
        "cluster_fit": "high",
        "useful_lifetime_days": 365,
        "competition_differentiation": "high",
    }
    value.update(overrides)
    return value


class TopicScoringTests(unittest.TestCase):
    def setUp(self):
        self.policy = load_policy(POLICY)
        self.as_of = date(2026, 10, 3)

    def test_measured_external_and_gsc_signal_can_pass_automation_gate(self):
        report = growth_report(queries=[{
            "query": "주민등록등본 인터넷 발급",
            "clicks": 1,
            "impressions": 30,
            "ctr": 1 / 30,
            "position": 6.1,
        }])
        scored = score_candidates(
            {"schema_version": 1, "candidates": [candidate()]},
            report,
            self.policy,
            as_of=self.as_of,
        )
        row = scored["candidates"][0]
        self.assertEqual(92, row["score"])
        self.assertEqual("high", row["confidence"])
        self.assertTrue(row["measured_demand_present"])
        self.assertTrue(row["eligible_for_automation"])
        self.assertEqual(1, scored["summary"]["eligible_for_automation"])

    def test_good_idea_without_measured_demand_is_held_not_invented(self):
        held = candidate(demand_evidence=[], gsc_terms=[])
        scored = score_candidates(
            {"schema_version": 1, "candidates": [held]},
            growth_report(),
            self.policy,
            as_of=self.as_of,
        )["candidates"][0]
        self.assertEqual(60, scored["score"])
        self.assertEqual("low", scored["confidence"])
        self.assertFalse(scored["measured_demand_present"])
        self.assertFalse(scored["eligible_for_automation"])
        self.assertIn("no_fresh_measured_demand_evidence", scored["reasons"])
        self.assertIn("score_below_automation_threshold", scored["reasons"])

    def test_stale_external_and_stale_gsc_are_ignored(self):
        stale = candidate(demand_evidence=[{
            "source": "google_trends",
            "metric": "relative_interest",
            "value": 80,
            "collected_at": "2026-01-01",
            "measured": True,
        }])
        row = score_candidates(
            {"schema_version": 1, "candidates": [stale]},
            growth_report(end="2026-08-01", queries=[{
                "query": "주민등록등본 발급", "clicks": 5, "impressions": 100,
                "ctr": 0.05, "position": 5,
            }]),
            self.policy,
            as_of=self.as_of,
        )["candidates"][0]
        self.assertFalse(row["eligible_for_automation"])
        self.assertFalse(row["measured_demand_present"])
        self.assertIn("stale_external_demand_evidence_ignored", row["reasons"])
        self.assertIn("stale_gsc_report_ignored", row["reasons"])

    def test_unmeasured_or_unknown_demand_claim_fails_closed(self):
        for evidence in ([{
            "source": "google_trends", "metric": "relative_interest", "value": 50,
            "collected_at": "2026-10-01", "measured": False,
        }], [{
            "source": "internet_guess", "metric": "volume", "value": 500,
            "collected_at": "2026-10-01", "measured": True,
        }]):
            with self.subTest(evidence=evidence), self.assertRaises(TopicScoringError):
                score_candidates(
                    {"schema_version": 1, "candidates": [candidate(demand_evidence=evidence)]},
                    growth_report(), self.policy, as_of=self.as_of,
                )

    def test_source_specific_metric_contract_rejects_wrong_metric(self):
        for evidence in ([{
            "source": "google_trends", "metric": "avg_monthly_searches", "value": 50,
            "collected_at": "2026-10-01", "measured": True,
        }], [{
            "source": "naver_datalab", "metric": "avg_monthly_searches", "value": 50,
            "collected_at": "2026-10-01", "measured": True,
        }], [{
            "source": "keyword_planner", "metric": "relative_interest", "value": 50,
            "collected_at": "2026-10-01", "measured": True,
        }]):
            with self.subTest(evidence=evidence), self.assertRaisesRegex(
                    TopicScoringError, "unsupported_topic_demand_metric"):
                score_candidates(
                    {"schema_version": 1, "candidates": [candidate(demand_evidence=evidence)]},
                    growth_report(), self.policy, as_of=self.as_of,
                )

    def test_scheduler_gate_binds_score_to_brief_keyword_category_and_freshness(self):
        score_report = score_candidates(
            {"schema_version": 1, "candidates": [candidate()]},
            growth_report(queries=[{
                "query": "주민등록등본 발급", "clicks": 1, "impressions": 30,
                "ctr": 1 / 30, "position": 6,
            }]),
            self.policy,
            as_of=self.as_of,
        )
        brief = {
            "id": "resident-docs-brief",
            "category_key": "life-admin",
            "primary_keyword": "주민등록등본 인터넷 무료 발급",
        }
        self.assertEqual([], brief_growth_gate_reasons(
            brief, score_report, self.policy, today=self.as_of))
        tampered_policy = json.loads(json.dumps(self.policy))
        tampered_policy["topic_gate"]["min_score"] = 71
        self.assertEqual(["growth_score_policy_digest_mismatch"], brief_growth_gate_reasons(
            brief, score_report, tampered_policy, today=self.as_of))
        changed = dict(brief, primary_keyword="전혀 다른 키워드")
        self.assertIn("growth_score_keyword_mismatch", brief_growth_gate_reasons(
            changed, score_report, self.policy, today=self.as_of))
        self.assertEqual(["growth_score_report_stale"], brief_growth_gate_reasons(
            brief, score_report, self.policy, today=date(2026, 10, 20)))

    def test_value_gate_requires_explicit_scheduler_metadata(self):
        base = {
            "intent_type": "application",
            "ai_answerability": "high",
            "added_value": ["official_action"],
        }
        self.assertEqual([], brief_value_gate_reasons(base, self.policy))
        self.assertIn(
            "high_ai_answerability_without_added_value",
            brief_value_gate_reasons(dict(base, added_value=[]), self.policy),
        )
        self.assertIn(
            "brief_intent_type_missing_or_invalid",
            brief_value_gate_reasons({"ai_answerability": "low", "added_value": []}, self.policy),
        )
        self.assertIn(
            "brief_added_value_missing_or_invalid",
            brief_value_gate_reasons(dict(base, added_value=["generic_summary"]), self.policy),
        )

    def test_private_score_report_round_trip(self):
        report = score_candidates(
            {"schema_version": 1, "candidates": []}, growth_report(),
            self.policy, as_of=self.as_of,
        )
        with tempfile.TemporaryDirectory() as root:
            path = save_topic_scores(report, Path(root) / "growth")
            self.assertEqual("topic-candidate-scores.json", path.name)
            self.assertEqual(report, json.loads(path.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
