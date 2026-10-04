"""Offline growth analyzer tests; no Google, WordPress, or network calls."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from agents.growth_analysis import analyze_growth, load_policy, save_opportunities


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "growth_policy.json"


def post(post_id, published, permalink, **extra):
    return {
        "ID": post_id,
        "post_title": extra.pop("title", f"Post {post_id}"),
        "post_status": "publish",
        "post_name": extra.pop("post_name", f"post-{post_id}"),
        "permalink": permalink,
        "post_date": published,
        "category_slugs": extra.pop("category_slugs", ["life-admin"]),
        "categories": extra.pop("categories", ["행정/생활서비스"]),
        **extra,
    }


def snapshot(page_rows, ga_rows=None):
    return {
        "schema_version": 2,
        "period": {"start": "2026-09-02", "end": "2026-09-29",
                   "timezone": "Google-property-specific"},
        "search_console": {
            "pages": page_rows,
            "queries": [{"query": "테스트 검색", "clicks": 1, "impressions": 5,
                         "ctr": 0.2, "position": 4.0}],
            "daily": [],
        },
        "ga4": {"pages": ga_rows or [], "channels": [], "daily": [], "traffic_identity": []},
    }


class GrowthAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.policy = load_policy(POLICY)

    def test_classifies_winner_quick_win_growth_candidate_and_too_early(self):
        posts = [
            post(217, "2026-09-01 09:00:00", "https://lifeinfo24.org/ktx/"),
            post(345, "2026-09-01 09:00:00", "https://lifeinfo24.org/bus/"),
            post(400, "2026-09-01 09:00:00", "https://lifeinfo24.org/grow/"),
            post(500, "2026-09-25 09:00:00", "https://lifeinfo24.org/new/"),
        ]
        rows = [
            {"page": "https://lifeinfo24.org/ktx/", "clicks": 13, "impressions": 173,
             "ctr": 13 / 173, "position": 8.42},
            {"page": "https://lifeinfo24.org/bus/", "clicks": 1, "impressions": 53,
             "ctr": 1 / 53, "position": 7.11},
            {"page": "https://lifeinfo24.org/grow/", "clicks": 0, "impressions": 20,
             "ctr": 0.0, "position": 18.0},
        ]
        report = analyze_growth(snapshot(rows), posts, self.policy)
        self.assertEqual(1, report["provenance_contract_version"])
        classes = {row["post_id"]: row["classification"] for row in report["pages"]}
        self.assertEqual("winner", classes[217])
        self.assertEqual("quick_win", classes[345])
        self.assertEqual("growth_candidate", classes[400])
        self.assertEqual("too_early", classes[500])
        self.assertTrue(all(
            row["editorial_provenance"]["auto_adoptable"] is False
            for row in report["pages"]
        ))

    def test_provenance_map_is_bound_into_page_for_planner(self):
        posts = [post(609, "2026-09-01 09:00:00", "https://lifeinfo24.org/minimum/")]
        provenance = {
            609: {
                "classification": "reviewed_exact",
                "auto_adoptable": True,
                "live_status": "publish",
                "live_content_sha256": "a" * 64,
                "review_digest": "b" * 64,
                "bundle_digest": "c" * 64,
                "provenance_variant": "current",
                "canonical_category_key": "finance",
            },
        }
        report = analyze_growth(snapshot([]), posts, self.policy, provenance_by_id=provenance)
        self.assertEqual(provenance[609], report["pages"][0]["editorial_provenance"])

    def test_strong_search_signal_overrides_fresh_age_but_future_post_does_not(self):
        posts = [
            post(217, "2026-09-18 20:46:34", "https://lifeinfo24.org/ktx/"),
            post(345, "2026-09-24 14:31:37", "https://lifeinfo24.org/bus/"),
            post(900, "2026-10-02 09:00:00", "https://lifeinfo24.org/future/"),
        ]
        rows = [
            {"page": "https://lifeinfo24.org/ktx/", "clicks": 13, "impressions": 173,
             "ctr": 13 / 173, "position": 8.42},
            {"page": "https://lifeinfo24.org/bus/", "clicks": 1, "impressions": 53,
             "ctr": 1 / 53, "position": 7.11},
            {"page": "https://lifeinfo24.org/future/", "clicks": 8, "impressions": 100,
             "ctr": 0.08, "position": 4.0},
        ]
        report = analyze_growth(snapshot(rows), posts, self.policy)
        by_id = {row["post_id"]: row for row in report["pages"]}
        self.assertEqual("winner", by_id[217]["classification"])
        self.assertIn("fresh_post_but_signal_threshold_reached", by_id[217]["reasons"])
        self.assertEqual("quick_win", by_id[345]["classification"])
        self.assertEqual("too_early", by_id[900]["classification"])
        self.assertEqual(["published_after_reporting_period"], by_id[900]["reasons"])

    def test_explicit_expiry_is_seasonal_decay_and_low_samples_are_not_overclaimed(self):
        posts = [
            post(229, "2026-08-01 09:00:00", "https://lifeinfo24.org/chuseok/",
                 expires_at="2026-09-28"),
            post(121, "2026-09-01 09:00:00", "https://lifeinfo24.org/resident/"),
        ]
        rows = [{"page": "https://lifeinfo24.org/resident/", "clicks": 0, "impressions": 10,
                 "ctr": 0.0, "position": 6.1}]
        report = analyze_growth(snapshot(rows), posts, self.policy)
        by_id = {row["post_id"]: row for row in report["pages"]}
        self.assertEqual("seasonal_decay", by_id[229]["classification"])
        self.assertEqual("observed", by_id[121]["classification"])
        self.assertEqual("low", by_id[121]["confidence"])
        self.assertIn("sample_too_small_for_strong_action", by_id[121]["reasons"])

    def test_matches_permalink_post_id_and_ga4_path_but_reports_unknown_urls(self):
        posts = [post(349, "2026-09-01 09:00:00", "https://lifeinfo24.org/concert/")]
        rows = [
            {"page": "https://lifeinfo24.org/?p=349", "clicks": 3, "impressions": 30,
             "ctr": 0.1, "position": 8.2},
            {"page": "https://lifeinfo24.org/legacy-deleted/", "clicks": 1, "impressions": 2,
             "ctr": 0.5, "position": 5.0},
        ]
        ga4 = [
            {"pagePath": "/concert/", "screenPageViews": "4", "activeUsers": "2"},
            {"pagePath": "/preview470.html", "screenPageViews": "3", "activeUsers": "1"},
        ]
        report = analyze_growth(snapshot(rows, ga4), posts, self.policy)
        self.assertEqual(1, report["summary"]["mapped_gsc_pages"])
        self.assertEqual(1, report["summary"]["unmatched_gsc_pages"])
        page = report["pages"][0]
        self.assertEqual(4, page["ga4_all_channels"]["screenPageViews"])
        self.assertEqual("winner", page["classification"])
        self.assertEqual("/preview470.html", report["unmatched_ga4_paths"][0]["pagePath"])

    def test_private_report_save_is_round_trippable(self):
        report = analyze_growth(snapshot([]), [], self.policy)
        with tempfile.TemporaryDirectory() as root:
            target = save_opportunities(report, Path(root) / "growth")
            self.assertEqual("latest-opportunities.json", target.name)
            self.assertEqual(report, json.loads(target.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
