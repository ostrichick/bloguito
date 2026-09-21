"""Offline Google report tests: no credentials or live provider calls."""

from datetime import date
import json
import os
from pathlib import Path
import tempfile
import unittest

from analytics_collector import (
    CollectionError, classify_traffic, collect, date_window, markdown_report, save_report,
    save_snapshot, validate_configuration,
)


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.calls = []

    def fake_request(self, url, data):
        self.calls.append((url, data))
        if "searchAnalytics/query" in url:
            dimension = data["dimensions"][0]
            key = {"query": "김건모 공연", "page": "https://lifeinfo24.org/?p=349",
                   "date": "2026-09-18"}[dimension]
            return {"rows": [{"keys": [key], "clicks": 3, "impressions": 30,
                              "ctr": 0.1, "position": 8.2}]}
        dimension = data["dimensions"][0]["name"]
        if dimension == "sessionManualSourceMedium":
            return {"rows": [{"dimensionValues": [
                {"value": "bloguito_qa_agent / internal_test"}, {"value": "Unassigned"}],
                "metricValues": [{"value": "2"}]}], "rowCount": 1}
        value = {"date": "20260918", "sessionDefaultChannelGroup": "Organic Search",
                 "pagePath": "/"}[dimension]
        return {"rows": [{"dimensionValues": [{"value": value}],
                          "metricValues": [{"value": "3"} for _ in data["metrics"]]}]}

    def test_complete_snapshot_and_only_read_only_google_endpoints(self):
        snapshot = collect("https://lifeinfo24.org/", "123456789", date(2026, 9, 18),
                           self.fake_request)
        self.assertEqual(len(self.calls), 7)
        self.assertEqual(snapshot["schema_version"], 2)
        self.assertEqual(snapshot["period"], {
            "start": "2026-08-22", "end": "2026-09-18",
            "timezone": "Google-property-specific",
        })
        self.assertEqual(snapshot["search_console"]["queries"][0]["clicks"], 3)
        self.assertEqual(snapshot["ga4"]["channels"][0]["sessions"], "3")
        self.assertEqual(snapshot["ga4"]["pages"][0]["pagePath"], "/")
        self.assertEqual(classify_traffic(snapshot["ga4"])["agent_sessions"], 2)
        self.assertFalse(classify_traffic(snapshot["ga4"])["complete"])
        for url, data in self.calls:
            self.assertTrue(url.startswith(("https://www.googleapis.com/webmasters/v3/sites/",
                                            "https://analyticsdata.googleapis.com/v1beta/properties/")))
            self.assertEqual(data.get("endDate", "2026-09-18"), "2026-09-18")

    def test_failed_second_source_does_not_return_partial_snapshot(self):
        def fail_on_ga4(url, data):
            if "analyticsdata" in url:
                raise CollectionError("google_api_http_403")
            return self.fake_request(url, data)
        with self.assertRaisesRegex(CollectionError, "google_api_http_403"):
            collect("https://lifeinfo24.org/", "123456789", date(2026, 9, 18),
                    fail_on_ga4)

    def test_empty_rows_are_legitimate_not_fabricated(self):
        snapshot = collect("https://lifeinfo24.org/", "123456789", date(2026, 9, 18),
                           lambda url, data: {})
        self.assertEqual(snapshot["search_console"]["queries"], [])
        self.assertEqual(snapshot["ga4"]["daily"], [])

    def test_labelled_agent_owner_and_unverified_are_separate_not_human(self):
        summary = classify_traffic({"channels": [{"sessions": "11"}], "traffic_identity": [
            {"sessionManualSourceMedium": "bloguito_qa_agent / internal_test",
             "sessionDefaultChannelGroup": "Unassigned", "sessions": "2"},
            {"sessionManualSourceMedium": "bloguito_qa_owner / internal_test",
             "sessionDefaultChannelGroup": "Unassigned", "sessions": "1"},
            {"sessionManualSourceMedium": "(not set)", "sessionDefaultChannelGroup": "Direct",
             "sessions": "6"},
            {"sessionManualSourceMedium": "google / organic",
             "sessionDefaultChannelGroup": "Organic Search", "sessions": "2"},
        ]})
        self.assertEqual(summary["agent_sessions"], 2)
        self.assertEqual(summary["owner_sessions"], 1)
        self.assertEqual(summary["unverified_direct_sessions"], 6)
        self.assertEqual(summary["unverified_other_sessions"], 2)
        self.assertTrue(summary["complete"])

    def test_truncated_source_report_rejects_false_full_coverage(self):
        def request(url, data):
            response = self.fake_request(url, data)
            if data.get("dimensions") == [{"name": "sessionManualSourceMedium"},
                                           {"name": "sessionDefaultChannelGroup"}]:
                response["rowCount"] = 300
            return response
        with self.assertRaisesRegex(CollectionError, "ga4_traffic_identity_report_truncated"):
            collect("https://lifeinfo24.org/", "123456789", date(2026, 9, 18), request)

    def test_invalid_row_fails_closed(self):
        with self.assertRaisesRegex(CollectionError, "search_console_invalid_dimensions"):
            collect("https://lifeinfo24.org/", "123456789", date(2026, 9, 18),
                    lambda url, data: {"rows": [{"keys": []}]})

    def test_property_and_date_validation(self):
        for site, prop in (("http://example.org/", "1"), ("https://evil.test/x", "1"),
                           ("https://example.org/", "123:abc")):
            with self.subTest(site=site, prop=prop), self.assertRaises(CollectionError):
                validate_configuration(site, prop)
        with self.assertRaises(CollectionError):
            date_window(date(2026, 9, 21), today=date(2026, 9, 21))
        self.assertEqual(date_window(date(2026, 9, 18), 3,
                                     date(2026, 9, 21)), ("2026-09-16", "2026-09-18"))

    def test_private_atomic_snapshot(self):
        with tempfile.TemporaryDirectory() as root:
            out = Path(root) / "analytics"
            snapshot = collect("https://lifeinfo24.org/", "123456789", date(2026, 9, 18),
                               self.fake_request)
            target = save_snapshot(snapshot, out)
            self.assertEqual(json.loads(target.read_text(encoding="utf-8")), snapshot)
            self.assertEqual(target.name, "google-analytics-2026-09-18.json")
            if os.name == "posix":
                self.assertEqual(out.stat().st_mode & 0o777, 0o700)
                self.assertEqual(target.stat().st_mode & 0o777, 0o600)
            snapshot["limitations"].append("overwrite verification")
            self.assertEqual(save_snapshot(snapshot, out), target)
            self.assertIn("overwrite verification",
                          json.loads(target.read_text(encoding="utf-8"))["limitations"])
            self.assertEqual(len(list(out.iterdir())), 1)

    def test_human_report_is_private_and_does_not_invent_metrics(self):
        with tempfile.TemporaryDirectory() as root:
            snapshot = collect("https://lifeinfo24.org/", "123456789", date(2026, 9, 18),
                               self.fake_request)
            report = markdown_report(snapshot)
            self.assertIn("김건모 공연", report)
            self.assertIn("| 3 | 30 | 10.0% | 8.2 |", report)
            self.assertIn("Organic Search", report)
            self.assertIn("QA 태그: 에이전트 | 2", report)
            self.assertIn("분류 결과는 불완전", report)
            self.assertIn("정의가 달라", report)
            path = save_report(snapshot, Path(root) / "analytics")
            self.assertTrue(path.read_text(encoding="utf-8").startswith("# Bloguito"))
            if os.name == "posix":
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_reject_link_targets(self):
        with tempfile.TemporaryDirectory() as root:
            out = Path(root) / "analytics"
            out.mkdir(mode=0o700)
            snapshot = {"period": {"end": "2026-09-18"}}
            target = out / "google-analytics-2026-09-18.json"
            innocent = Path(root) / "innocent.json"
            innocent.write_text("safe", encoding="utf-8")
            try:
                target.symlink_to(innocent)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks unavailable")
            with self.assertRaisesRegex(CollectionError, "report_target_symlink_not_allowed"):
                save_snapshot(snapshot, out)
            self.assertEqual(innocent.read_text(encoding="utf-8"), "safe")


if __name__ == "__main__":
    unittest.main()
