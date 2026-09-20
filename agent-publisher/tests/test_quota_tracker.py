import unittest
from agents.quota_tracker import (
    get_quota_date,
    record_usage,
    get_model_status,
    get_all_status,
    format_quota_summary,
    get_model_cascade,
    MODEL_CASCADE,
)


class TestQuotaTracker(unittest.TestCase):
    def test_get_quota_date(self):
        d = get_quota_date()
        self.assertRegex(d, r"^\d{4}-\d{2}-\d{2}$")

    def test_model_cascade(self):
        cascade = get_model_cascade("gemini-3.6-flash")
        self.assertEqual(cascade[0], "gemini-3.6-flash")
        self.assertIn("gemini-3.5-flash-lite", cascade)

    def test_record_and_get_status(self):
        st = record_usage("gemini-3.5-flash-lite", count=1)
        self.assertGreaterEqual(st["used"], 1)
        self.assertLessEqual(st["remaining"], st["limit"])

    def test_format_summary(self):
        summary = format_quota_summary()
        self.assertIn("gemini-3.6-flash", summary)
        self.assertIn("gemini-3.5-flash-lite", summary)


if __name__ == "__main__":
    unittest.main()
