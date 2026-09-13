import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agents.temporal_validation import KST, extract_evidence, validate_availability
from agents.copywriter import CopywriterAgent
from agents.publisher import PublisherAgent

NOW = datetime(2026, 9, 13, 12, tzinfo=KST)


class TemporalTests(unittest.TestCase):
    def check(self, text, requires_sale=False, now=NOW):
        return validate_availability({"evidence": extract_evidence(text, "https://example.com/notice"), "requires_sale": requires_sale, "sale_source_url": "https://example.com/notice"}, now)

    def test_application_active(self):
        self.assertEqual(self.check("신청기간: 2026년 9월 1일 ~ 9월 30일")["status"], "active")

    def test_closed_deadline(self):
        self.assertEqual(self.check("신청마감: 2026.09.12")["status"], "closed")

    def test_date_only_includes_full_day(self):
        self.assertEqual(self.check("신청마감: 2026.09.13", now=NOW.replace(hour=23, minute=59))["status"], "active")
        self.assertEqual(self.check("신청마감: 2026.09.13", now=NOW + timedelta(days=1))["status"], "closed")

    def test_explicit_hour(self):
        self.assertEqual(self.check("접수마감: 2026년 9월 13일 오전 11시")["status"], "closed")
        self.assertEqual(self.check("접수마감: 2026년 9월 13일 오후 1시")["status"], "active")

    def test_not_open(self):
        self.assertIn("not_open_yet", self.check("접수기간: 2026.09.14 ~ 09.30")["reasons"])

    def test_invalid_unknown_ambiguous(self):
        for text in ["접수마감: 9월 30일", "접수마감: 2026.02.30", "접수기간: 2026.09.30 ~ 09.01", "접수기간: 2026.09.30", "접수마감: 추후 공지", "상시 신청 가능"]:
            with self.subTest(text=text):
                self.assertEqual(self.check(text)["status"], "needs_review")

    def test_sale_requires_status_and_window(self):
        text = "공연일시: 2026.12.25\n예매기간: 2026.09.01 ~ 12.24"
        self.assertEqual(self.check(text, True)["status"], "needs_review")
        self.assertEqual(self.check(text + "\n판매상태: 판매중", True)["status"], "active")
        self.assertEqual(self.check(text + "\n판매상태: 매진", True)["status"], "closed")

    def test_future_open_overrides_filter(self):
        text = "공연일시: 2026.12.25\n예매오픈: 2026.09.15 오후 1시\n판매상태: 판매중"
        self.assertIn("not_open_yet", self.check(text, True)["reasons"])

    def test_sale_must_be_from_selected_product(self):
        source = {"requires_sale": True, "sale_source_url": "https://nol.yanolja.com/ticket/products/1", "evidence": extract_evidence("공연일시: 2026.12.25\n예매기간: 2026.09.01 ~ 12.24\n판매상태: 판매중", "https://example.com/news")}
        self.assertIn("sale_evidence_not_from_verified_product", validate_availability(source, NOW)["reasons"])

    def test_event_future_application_closed(self):
        self.assertEqual(self.check("행사일시: 2026.12.25\n신청마감: 2026.09.12")["status"], "closed")

    def test_conflicting_sources(self):
        self.assertIn("conflicting_dates", self.check("접수마감: 2026.09.20\n접수마감: 2026.09.30")["reasons"])
        self.assertIn("conflicting_status", self.check("접수마감: 2026.09.30\n접수상태: 접수중\n접수상태: 접수마감")["reasons"])

    def test_unrelated_date_not_availability(self):
        self.assertEqual(self.check("보도일: 2026.09.13; 생일: 2026.12.25")["status"], "needs_review")

    def test_utc_uses_korean_day(self):
        self.assertEqual(self.check("신청마감: 2026.09.13", now=(NOW.replace(hour=23)).astimezone(__import__('datetime').timezone.utc))["status"], "active")

    def test_writer_cannot_trust_gemini_active(self):
        writer = object.__new__(CopywriterAgent)
        writer.client = True
        writer._generate_with_gemini = Mock(return_value={"is_valid_and_active": True})
        item = {"title": "마감 공고", "temporal_source": {"evidence": extract_evidence("신청마감: 2020.09.12", "https://example.com")}}
        self.assertIsNone(writer.write_article(item))
        writer._generate_with_gemini.assert_not_called()

    @patch("agents.publisher.subprocess.run")
    def test_publisher_rechecks_before_side_effects(self, run):
        with self.assertRaises(ValueError):
            PublisherAgent().publish({"temporal_source": {"evidence": extract_evidence("신청마감: 2020.09.12", "https://example.com")}})
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
