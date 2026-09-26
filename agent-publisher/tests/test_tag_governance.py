import unittest
import importlib.util
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from agents.publisher import PublisherAgent
from agents.editorial_writer import article_from_bundle
from test_editorial_system import sample


ROOT = Path(__file__).resolve().parents[2]
AUDIT_SPEC = importlib.util.spec_from_file_location(
    "audit_tag_governance",
    ROOT / "scripts" / "audit_tag_governance.py",
)
audit_tag_governance = importlib.util.module_from_spec(AUDIT_SPEC)
assert AUDIT_SPEC.loader is not None
AUDIT_SPEC.loader.exec_module(audit_tag_governance)


class TagGovernanceTests(unittest.TestCase):
    def test_editorial_article_has_no_tags(self):
        article = article_from_bundle(sample())
        self.assertEqual(article["tags"], [])

    def test_nonempty_tags_fail_before_wordpress_io(self):
        article = article_from_bundle(sample())
        article["tags"] = ["일회성태그"]
        with patch("sync_wordpress_inventory.sync_inventory") as sync, \
             patch("agents.publisher.subprocess.run") as run:
            with self.assertRaisesRegex(ValueError, "editorial_tags_disabled"):
                PublisherAgent()._publish_editorial(article)
        sync.assert_not_called()
        run.assert_not_called()

    def test_audit_classification_preserves_inventory_and_policy_precedence(self):
        tags = [
            {"term_id": "1", "name": "기초연금 신청방법", "slug": "spaced", "count": "1"},
            {"term_id": "2", "name": "기초연금신청방법", "slug": "compact", "count": "1"},
            {"term_id": "3", "name": "2026 추석", "slug": "dated", "count": "2"},
            {"term_id": "4", "name": "재사용", "slug": "reused", "count": "2"},
            {"term_id": "5", "name": "미사용", "slug": "unused", "count": "0"},
        ]
        original = deepcopy(tags)

        rows = audit_tag_governance.classify(tags)
        by_id = {row["term_id"]: row for row in rows}

        self.assertEqual(tags, original)
        self.assertEqual(by_id[1]["classification"], audit_tag_governance.MERGE)
        self.assertEqual(by_id[1]["merge_into"], "기초연금신청방법")
        self.assertEqual(by_id[2]["classification"], audit_tag_governance.STOP)
        self.assertEqual(by_id[3]["classification"], audit_tag_governance.STOP)
        self.assertEqual(by_id[4]["classification"], audit_tag_governance.KEEP)
        self.assertEqual(by_id[5]["classification"], audit_tag_governance.DELETE)
        self.assertEqual(
            audit_tag_governance.summary(rows),
            {
                audit_tag_governance.KEEP: 1,
                audit_tag_governance.MERGE: 1,
                audit_tag_governance.STOP: 2,
                audit_tag_governance.DELETE: 1,
            },
        )


if __name__ == "__main__":
    unittest.main()
