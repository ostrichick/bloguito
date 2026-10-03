"""Offline P9 measured-demand collection tests; no live provider calls."""

from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import tempfile
import unittest

from agents.topic_demand import (
    TopicDemandError,
    collect_naver_datalab,
    measurement_window,
    save_candidate_document,
    select_measurement_candidates,
)


def candidate(candidate_id="ktx-waiting", **overrides):
    value = {
        "id": candidate_id,
        "brief_id": candidate_id + "-brief",
        "category_key": "transport",
        "topic": "KTX 예약대기 순번과 좌석 배정 확인",
        "primary_keyword": "KTX 예약대기 순번",
        "gsc_terms": ["ktx 예약대기"],
        "demand_evidence": [{
            "source": "google_trends", "metric": "relative_interest", "value": 20,
            "collected_at": "2026-10-01", "measured": True,
        }],
        "click_need": "high",
        "ai_answerability": "medium",
        "added_value": ["official_action", "troubleshooting"],
        "cluster_fit": "medium",
        "useful_lifetime_days": 365,
        "competition_differentiation": "medium",
    }
    value.update(overrides)
    return value


def growth_report(end="2026-09-29", queries=None):
    return {
        "schema_version": 1,
        "period": {"start": "2026-09-02", "end": end,
                   "timezone": "Google-property-specific"},
        "top_queries_global": queries or [],
    }


class TopicDemandTests(unittest.TestCase):
    def setUp(self):
        self.as_of = date(2026, 10, 3)
        self.report = growth_report(queries=[{
            "query": "ktx 예약대기 순번", "clicks": 0, "impressions": 1, "position": 9,
        }])

    def test_measurement_window_uses_complete_days_only(self):
        self.assertEqual(
            (date(2026, 7, 5), date(2026, 10, 2)),
            measurement_window(self.as_of, days=90),
        )

    def test_selection_requires_fresh_literal_gsc_seed_by_default(self):
        doc = {"schema_version": 1, "candidates": [candidate()]}
        selected, reason = select_measurement_candidates(
            doc, self.report, as_of=self.as_of, max_gsc_age_days=14)
        self.assertIsNone(reason)
        self.assertEqual(["ktx 예약대기 순번"], [
            row["query"] for row in selected[0]["gsc_matches"]])

        selected, reason = select_measurement_candidates(
            doc, growth_report(end="2026-09-01", queries=self.report["top_queries_global"]),
            as_of=self.as_of, max_gsc_age_days=14)
        self.assertEqual([], selected)
        self.assertEqual("gsc_seed_report_stale", reason)

        selected, _ = select_measurement_candidates(
            doc, growth_report(queries=[{"query": "전혀 다른 검색어", "impressions": 10}]),
            as_of=self.as_of, max_gsc_age_days=14)
        self.assertEqual([], selected)

    def test_collection_records_relative_interest_not_absolute_volume(self):
        calls = []

        def requester(payload):
            calls.append(payload)
            return {
                "startDate": payload["startDate"],
                "endDate": payload["endDate"],
                "timeUnit": payload["timeUnit"],
                "results": [{
                    "title": "g0",
                    "keywords": payload["keywordGroups"][0]["keywords"],
                    "data": [
                        {"period": "2026-09-21", "ratio": 25.0},
                        {"period": "2026-09-28", "ratio": 75.0},
                    ],
                }],
            }

        doc = {"schema_version": 1, "candidates": [candidate()]}
        updated, summary = collect_naver_datalab(
            doc, self.report, requester, collected_on=self.as_of,
            max_gsc_age_days=14, window_days=90, time_unit="week",
        )
        self.assertEqual(1, len(calls))
        self.assertEqual(1, summary["measured"])
        self.assertIn("not absolute search volume", summary["metric_note"])
        self.assertEqual(1, len(doc["candidates"][0]["demand_evidence"]))
        evidence = updated["candidates"][0]["demand_evidence"]
        self.assertEqual(2, len(evidence))
        measured = next(row for row in evidence if row["source"] == "naver_datalab")
        self.assertEqual("relative_interest", measured["metric"])
        self.assertEqual(50.0, measured["value"])
        self.assertTrue(measured["measured"])
        self.assertEqual("mean_period_ratio", measured["aggregation"])
        self.assertEqual(["ktx 예약대기 순번"], measured["gsc_seed_queries"])

    def test_no_data_does_not_fabricate_zero_evidence(self):
        def requester(payload):
            return {
                "startDate": payload["startDate"], "endDate": payload["endDate"],
                "timeUnit": payload["timeUnit"],
                "results": [{"title": "g0", "keywords": [], "data": []}],
            }

        doc = {"schema_version": 1, "candidates": [candidate(demand_evidence=[])]}
        updated, summary = collect_naver_datalab(
            doc, self.report, requester, collected_on=self.as_of, max_gsc_age_days=14)
        self.assertEqual(0, summary["measured"])
        self.assertEqual(["ktx-waiting"], summary["unavailable"])
        self.assertEqual([], updated["candidates"][0]["demand_evidence"])

    def test_invalid_provider_ratio_fails_closed(self):
        def requester(payload):
            return {
                "startDate": payload["startDate"], "endDate": payload["endDate"],
                "timeUnit": payload["timeUnit"],
                "results": [{"title": "g0", "data": [{"period": "x", "ratio": 101}]}],
            }
        with self.assertRaisesRegex(TopicDemandError, "naver_datalab_invalid_ratio"):
            collect_naver_datalab(
                {"schema_version": 1, "candidates": [candidate()]}, self.report, requester,
                collected_on=self.as_of, max_gsc_age_days=14,
            )

    def test_batches_at_provider_limit_and_atomic_private_save(self):
        candidates = [candidate("c" + str(index)) for index in range(6)]
        queries = [{"query": "ktx 예약대기 순번", "impressions": 1}]
        calls = []

        def requester(payload):
            calls.append(payload)
            return {
                "startDate": payload["startDate"], "endDate": payload["endDate"],
                "timeUnit": payload["timeUnit"],
                "results": [{
                    "title": group["groupName"], "keywords": group["keywords"],
                    "data": [{"period": "2026-09-28", "ratio": 10}],
                } for group in payload["keywordGroups"]],
            }

        updated, summary = collect_naver_datalab(
            {"schema_version": 1, "candidates": candidates},
            growth_report(queries=queries), requester, collected_on=self.as_of,
            max_gsc_age_days=14,
        )
        self.assertEqual([5, 1], [len(call["keywordGroups"]) for call in calls])
        self.assertEqual(6, summary["measured"])
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "growth" / "topic_candidates.json"
            save_candidate_document(updated, path)
            self.assertEqual(updated, json.loads(path.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
