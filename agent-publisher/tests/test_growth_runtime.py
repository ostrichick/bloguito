"""Offline fail-closed tests for scheduled growth input refresh."""

from __future__ import annotations

from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from agents.growth_analysis import _CATALOG_PHP, GrowthAnalysisError, refresh_growth_inputs
from agents.growth_planner import decide_daily_action


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "growth_policy.json"


def analytics_snapshot(end="2026-10-02"):
    return {
        "schema_version": 2,
        "collected_at_utc": "2026-10-06T00:00:00+00:00",
        "period": {"start": "2026-09-05", "end": end,
                   "timezone": "Google-property-specific"},
        "search_console": {"pages": [], "queries": [], "daily": []},
        "ga4": {
            "pages": [], "channels": [], "daily": [], "traffic_identity": [],
        },
        "limitations": [],
    }


def catalog_row(post_id=10, status="publish"):
    return {
        "ID": post_id,
        "post_title": "테스트 글",
        "post_status": status,
        "post_name": "test-post",
        "permalink": f"https://lifeinfo24.org/p/{post_id}/",
        "post_date": "2026-09-01 09:00:00",
        "content_sha256": "a" * 64,
        "category_slugs": ["life-admin"],
        "categories": ["행정/생활서비스"],
    }


class GrowthRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.analytics_dir = self.root / "analytics"
        self.growth_dir = self.root / "growth"
        self.data_dir = self.root / "data"
        self.analytics_dir.mkdir()
        self.growth_dir.mkdir(mode=0o700)
        self.data_dir.mkdir()
        (self.growth_dir / "topic_candidates.json").write_text(
            json.dumps({"schema_version": 1, "candidates": []}), encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def test_wordpress_catalog_query_requests_integer_ids(self):
        self.assertIn("'fields'=>'ids'", _CATALOG_PHP)

    def write_analytics(self, payload=None):
        path = self.analytics_dir / "google-analytics-2026-10-02.json"
        path.write_text(json.dumps(payload or analytics_snapshot()), encoding="utf-8")
        raw = path.read_bytes()
        return path, hashlib.sha256(raw).hexdigest()

    def refresh(self):
        return refresh_growth_inputs(
            analytics_dir=self.analytics_dir,
            growth_dir=self.growth_dir,
            data_dir=self.data_dir,
            policy_path=POLICY,
            as_of=date(2026, 10, 6),
            validation_now=datetime(2026, 10, 6, 6, 0, tzinfo=timezone.utc),
        )

    def test_missing_provenance_report_is_rebuilt_from_read_only_catalog(self):
        _path, checksum = self.write_analytics()
        (self.growth_dir / "latest-opportunities.json").write_text(
            json.dumps({
                "schema_version": 1,
                "policy_version": 1,
                "period": {"start": "2026-09-05", "end": "2026-10-02"},
                "pages": [],
            }), encoding="utf-8")
        with patch("agents.growth_analysis.fetch_current_catalog", return_value=[catalog_row()]) as fetch:
            result = self.refresh()
        fetch.assert_called_once_with()
        report = json.loads((self.growth_dir / "latest-opportunities.json").read_text(encoding="utf-8"))
        scores = json.loads((self.growth_dir / "topic-candidate-scores.json").read_text(encoding="utf-8"))
        self.assertTrue(result["opportunities_refreshed"])
        self.assertEqual(1, report["provenance_contract_version"])
        self.assertEqual(checksum, report["analytics_snapshot_sha256"])
        self.assertEqual(report["refresh_id"], scores["refresh_id"])
        self.assertEqual("2026-10-06", scores["as_of_date"])
        self.assertEqual(0, scores["summary"]["eligible_for_automation"])

    def test_same_analytics_digest_still_rebuilds_from_current_wordpress(self):
        _path, checksum = self.write_analytics()
        existing = {
            "schema_version": 1,
            "provenance_contract_version": 1,
            "period": {"start": "2026-09-05", "end": "2026-10-02"},
            "policy_version": 1,
            "pages": [],
            "analytics_snapshot_sha256": checksum,
        }
        (self.growth_dir / "latest-opportunities.json").write_text(
            json.dumps(existing), encoding="utf-8")
        with patch("agents.growth_analysis.fetch_current_catalog", return_value=[catalog_row()]) as fetch:
            result = self.refresh()
        fetch.assert_called_once_with()
        self.assertTrue(result["opportunities_refreshed"])
        scores = json.loads((self.growth_dir / "topic-candidate-scores.json").read_text(encoding="utf-8"))
        self.assertEqual("2026-10-06", scores["as_of_date"])

    def test_corrupt_existing_opportunity_body_is_never_reused(self):
        self.write_analytics()
        (self.growth_dir / "latest-opportunities.json").write_text(
            json.dumps({
                "schema_version": 1,
                "provenance_contract_version": 1,
                "policy_version": 1,
                "analytics_snapshot_sha256": "0" * 64,
                "pages": [{"post_id": 999, "classification": "quick_win"}],
            }), encoding="utf-8")
        with patch("agents.growth_analysis.fetch_current_catalog", return_value=[catalog_row()]):
            self.refresh()
        report = json.loads((self.growth_dir / "latest-opportunities.json").read_text(encoding="utf-8"))
        self.assertNotIn(999, [row["post_id"] for row in report["pages"]])

    def test_scoring_failure_leaves_previous_pair_untouched(self):
        self.write_analytics()
        opportunity_path = self.growth_dir / "latest-opportunities.json"
        score_path = self.growth_dir / "topic-candidate-scores.json"
        opportunity_path.write_bytes(b'{"old":"opportunities"}\n')
        score_path.write_bytes(b'{"old":"scores"}\n')
        before_opportunities = opportunity_path.read_bytes()
        before_scores = score_path.read_bytes()
        with patch("agents.growth_analysis.fetch_current_catalog", return_value=[catalog_row()]), \
                patch("agents.topic_scoring.score_candidates", side_effect=ValueError("bad score")):
            with self.assertRaisesRegex(GrowthAnalysisError, "topic_score_refresh_failed"):
                self.refresh()
        self.assertEqual(before_opportunities, opportunity_path.read_bytes())
        self.assertEqual(before_scores, score_path.read_bytes())

    def test_second_replace_failure_persists_only_a_fail_closed_pair(self):
        self.write_analytics()
        opportunity_path = self.growth_dir / "latest-opportunities.json"
        score_path = self.growth_dir / "topic-candidate-scores.json"

        with patch("agents.growth_analysis.fetch_current_catalog", return_value=[catalog_row()]):
            self.refresh()
        previous_scores = json.loads(score_path.read_text(encoding="utf-8"))

        changed = catalog_row()
        changed["post_title"] = "현재 WordPress에서 변경된 제목"
        real_replace = __import__("os").replace
        replace_calls = 0

        def fail_second_live_replace(source, destination):
            nonlocal replace_calls
            destination = Path(destination)
            if destination in {opportunity_path, score_path}:
                replace_calls += 1
                if replace_calls == 2:
                    raise OSError("simulated second replace failure")
            return real_replace(source, destination)

        with patch("agents.growth_analysis.fetch_current_catalog", return_value=[changed]), \
                patch("agents.growth_analysis.os.replace", side_effect=fail_second_live_replace):
            with self.assertRaisesRegex(OSError, "simulated second replace failure"):
                self.refresh()

        current_opportunities = json.loads(opportunity_path.read_text(encoding="utf-8"))
        current_scores = json.loads(score_path.read_text(encoding="utf-8"))
        self.assertEqual(previous_scores, current_scores)
        self.assertNotEqual(
            current_opportunities["opportunity_payload_sha256"],
            current_scores["opportunity_payload_sha256"],
        )
        policy = json.loads(POLICY.read_text(encoding="utf-8"))
        plan = decide_daily_action(
            current_opportunities,
            current_scores,
            policy,
            as_of=date(2026, 10, 6),
            work_log={"schema_version": 1, "entries": []},
            category_keys=["life-admin"],
            category_slug_map={"life-admin": "life-admin"},
        )
        self.assertEqual("no_action", plan["action"])
        self.assertIn("topic_score_opportunity_digest_mismatch", plan["details"])

    def test_malformed_latest_snapshot_fails_closed(self):
        path = self.analytics_dir / "google-analytics-2026-10-02.json"
        path.write_text("not-json", encoding="utf-8")
        with self.assertRaisesRegex(GrowthAnalysisError, "growth_latest_analytics_snapshot_invalid"):
            self.refresh()

    def test_malformed_newest_snapshot_does_not_fall_back_to_older_valid_snapshot(self):
        older = self.analytics_dir / "google-analytics-2026-10-01.json"
        payload = analytics_snapshot(end="2026-10-01")
        payload["period"]["start"] = "2026-09-04"
        older.write_text(json.dumps(payload), encoding="utf-8")
        newest = self.analytics_dir / "google-analytics-2026-10-02.json"
        newest.write_text("not-json", encoding="utf-8")
        with self.assertRaisesRegex(GrowthAnalysisError, "growth_latest_analytics_snapshot_invalid"):
            self.refresh()

    def test_structurally_incomplete_newest_snapshot_fails_closed(self):
        payload = analytics_snapshot()
        payload["ga4"].pop("traffic_identity")
        self.write_analytics(payload)
        with self.assertRaisesRegex(GrowthAnalysisError, "growth_latest_analytics_snapshot_invalid"):
            self.refresh()

    def test_filename_period_mismatch_fails_closed(self):
        payload = analytics_snapshot(end="2026-10-01")
        payload["period"]["start"] = "2026-09-04"
        self.write_analytics(payload)
        with self.assertRaisesRegex(
                GrowthAnalysisError, "growth_latest_analytics_filename_period_mismatch"):
            self.refresh()

    def test_changed_catalog_changes_opportunity_digest_and_refresh_id(self):
        self.write_analytics()
        with patch("agents.growth_analysis.fetch_current_catalog", return_value=[catalog_row()]):
            first = self.refresh()
        first_report = json.loads(
            (self.growth_dir / "latest-opportunities.json").read_text(encoding="utf-8"))
        changed = catalog_row()
        changed["post_title"] = "변경된 현재 제목"
        with patch("agents.growth_analysis.fetch_current_catalog", return_value=[changed]):
            second = self.refresh()
        second_report = json.loads(
            (self.growth_dir / "latest-opportunities.json").read_text(encoding="utf-8"))
        self.assertNotEqual(
            first_report["opportunity_payload_sha256"],
            second_report["opportunity_payload_sha256"],
        )
        self.assertNotEqual(first["refresh_id"], second["refresh_id"])


if __name__ == "__main__":
    unittest.main()
