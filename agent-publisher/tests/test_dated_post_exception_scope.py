"""Table-driven guards for narrowly scoped dated-post exceptions."""

import unittest
from datetime import date, timedelta

from agents.editorial import dated_post_exception, topic_reasons
from agents.policy_exceptions import load_policy_exceptions


CASE_IDS = (
    "2026-chuseok-toll-post-145-refresh",
    "2026-chuseok-rail-post-217-refresh",
    "2026-chuseok-ev-post-219-refresh",
    "2026-chuseok-bank-post-225",
    "2026-chuseok-seoul-waste-post-229-publish",
    "2026-chuseok-free-parking-post-237-publish",
)


def _required_urls(record):
    if record.get("official_urls"):
        return list(record["official_urls"])
    urls = [record["official_url"]]
    if record.get("required_attachment_url"):
        urls.append(record["required_attachment_url"])
    return urls


def _brief(exception_id, record):
    return {
        "id": exception_id,
        "existing_post_id": record["existing_post_id"],
        "content_type": "dated",
        "useful_until": record["useful_until"],
        "official_urls": _required_urls(record),
        "approved": True,
        "reviewed_at": record["approved_on"],
        "review_until": record["useful_until"],
        "category_key": "transport",
        "entity": exception_id,
        "primary_keyword": exception_id,
        "question": "reader question",
        "angle": "official source summary",
        "required_title_terms": ["2026"],
        "reader_questions": [{"id": "q1", "question": "reader question"}],
    }


class DatedPostExceptionScopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = load_policy_exceptions("dated_post")

    def test_exception_requires_exact_post_window_and_source_set(self):
        for exception_id in CASE_IDS:
            with self.subTest(exception_id=exception_id):
                record = self.records[exception_id]
                brief = _brief(exception_id, record)
                approved_on = date.fromisoformat(record["approved_on"])
                expires_on = date.fromisoformat(record["useful_until"])

                self.assertTrue(dated_post_exception(brief, approved_on))
                self.assertFalse(dated_post_exception(
                    {**brief, "existing_post_id": record["existing_post_id"] + 1}, approved_on))
                self.assertFalse(dated_post_exception(
                    {**brief, "useful_until": (expires_on + timedelta(days=1)).isoformat()}, approved_on))
                self.assertFalse(dated_post_exception(
                    {**brief, "official_urls": brief["official_urls"][:-1]}, approved_on))
                self.assertFalse(dated_post_exception(brief, expires_on + timedelta(days=1)))

    def test_exception_does_not_weaken_minimum_lifetime_for_other_posts(self):
        for exception_id in CASE_IDS:
            with self.subTest(exception_id=exception_id):
                record = self.records[exception_id]
                brief = _brief(exception_id, record)
                approved_on = date.fromisoformat(record["approved_on"])

                self.assertNotIn("insufficient_useful_lifetime", topic_reasons(brief, approved_on))
                other = {**brief, "existing_post_id": record["existing_post_id"] + 1}
                self.assertIn("insufficient_useful_lifetime", topic_reasons(other, approved_on))


if __name__ == "__main__":
    unittest.main()