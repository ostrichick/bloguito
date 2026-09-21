"""Offline tests for the restricted analytics snapshot ingestion endpoint."""

from datetime import date, datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest

from analytics_collector import collect, CollectionError
from analytics_receiver import MAX_INPUT, receive, validate_snapshot


class ReceiverTests(unittest.TestCase):
    @staticmethod
    def snapshot():
        def requester(url, params):
            if "searchAnalytics" in url:
                return {"rows": [{"keys": ["2026-09-18" if params["dimensions"] == ["date"]
                                            else "김건모 공연"], "clicks": 1,
                                  "impressions": 3, "ctr": 1 / 3, "position": 9.1}]}
            return {"rows": [{"dimensionValues": [
                {"value": "(not set)" if len(params["dimensions"]) == 2 else "Organic Search"},
                *([{"value": "Direct"}] if len(params["dimensions"]) == 2 else [])],
                              "metricValues": [{"value": "3"} for _ in params["metrics"]]}]}
        return collect("https://lifeinfo24.org/", "554325332", date(2026, 9, 18),
                       requester=requester)

    def test_restricted_private_success(self):
        data = self.snapshot()
        now = datetime.now(timezone.utc)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "private"
            end = receive(json.dumps(data, ensure_ascii=False).encode(), path, now)
            self.assertEqual(end, "2026-09-18")
            self.assertEqual(len(list(path.iterdir())), 2)
            self.assertEqual(json.loads(next(path.glob("*.json")).read_text(encoding="utf-8")), data)

    def test_backward_compatibility_with_v1(self):
        old = self.snapshot()
        old["schema_version"] = 1
        old["ga4"].pop("traffic_identity")
        self.assertIs(validate_snapshot(old), old)

    def test_v2_requires_valid_identity_rows(self):
        for bad in ("missing", "broken_label", "broken_metric", "extra"):
            snapshot = self.snapshot()
            if bad == "missing":
                snapshot["ga4"].pop("traffic_identity")
            elif bad == "broken_label":
                snapshot["ga4"]["traffic_identity"][0]["sessionDefaultChannelGroup"] = 123
            elif bad == "broken_metric":
                snapshot["ga4"]["traffic_identity"][0]["sessions"] = "-5"
            else:
                snapshot["ga4"]["traffic_identity"][0]["debug"] = "extra"
            with self.subTest(bad=bad), self.assertRaises(CollectionError):
                validate_snapshot(snapshot)

    def test_invalid_json_and_size_fail_without_files(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "report"
            for payload in (b"not-json", b"A" * (MAX_INPUT + 1)):
                with self.assertRaises(CollectionError):
                    receive(payload, out)
                self.assertFalse(out.exists())

    def test_reject_missing_or_extra_schema_and_rows(self):
        for alteration in ("remove", "extra", "broken_rows"):
            snapshot = self.snapshot()
            if alteration == "remove":
                snapshot.pop("ga4")
            elif alteration == "extra":
                snapshot["admin"] = {"cmd": "unsafe"}
            else:
                snapshot["search_console"]["queries"] = [{"query": "x"}]
                snapshot["ga4"]["channels"] = ["bad"]
            with self.subTest(alteration=alteration), self.assertRaises(CollectionError):
                validate_snapshot(snapshot)

    def test_reject_oversized_rows_and_timestamp_without_file(self):
        snapshot = self.snapshot()
        snapshot["search_console"]["queries"] *= 251
        with self.assertRaises(CollectionError):
            validate_snapshot(snapshot)
        snapshot = self.snapshot()
        snapshot["collected_at_utc"] = "2000-01-01T00:00:00+00:00"
        with self.assertRaises(CollectionError):
            validate_snapshot(snapshot)

    def test_reject_nonfinite_search_metrics(self):
        for metric in (float("nan"), float("inf"), -1, 2.0):
            snapshot = self.snapshot()
            snapshot["search_console"]["queries"][0]["ctr"] = metric
            with self.subTest(metric=str(metric)), self.assertRaises(CollectionError):
                validate_snapshot(snapshot)


if __name__ == "__main__":
    unittest.main()
