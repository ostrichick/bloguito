import copy
import unittest

from agents.content_clusters import (
    ContentClusterError,
    apply_cluster_related_posts,
    cluster_link_report,
    related_post_candidates,
    validate_clusters,
)


CLUSTERS = {
    "schema_version": 1,
    "clusters": {
        "docs": {"name": "서류", "posts": [10, 20, 30]},
    },
}


def inventory(*, with_urls=True):
    rows = [
        {"ID": 10, "post_title": "주민등록등본 인터넷 발급 안내", "post_status": "publish"},
        {"ID": 20, "post_title": "건강진단결과서 인터넷 발급 안내", "post_status": "publish"},
        {"ID": 30, "post_title": "건축물대장 무료발급 안내", "post_status": "draft"},
        {"ID": 40, "post_title": "다른 글", "post_status": "publish"},
    ]
    if with_urls:
        for row in rows:
            row["content_urls"] = []
    return {"schema_version": 2, "checked_on": "2026-10-03", "posts": rows}


class ContentClusterTests(unittest.TestCase):
    def test_candidates_are_curated_published_and_exclude_current_post(self):
        brief = {"cluster_id": "docs", "existing_post_id": 10}
        self.assertEqual([20], [row["post_id"] for row in
                               related_post_candidates(brief, inventory(), CLUSTERS)])

    def test_cluster_binding_replaces_model_invented_related_posts_before_review(self):
        brief = {"cluster_id": "docs"}
        plan = {"title": "테스트", "related_posts": [
            {"post_id": 999, "label": "모델이 만든 링크", "url": "https://lifeinfo24.org/?p=999"}
        ]}
        bound = apply_cluster_related_posts(plan, brief, inventory(), CLUSTERS)
        self.assertEqual([10, 20], [row["post_id"] for row in bound["related_posts"]])
        self.assertNotEqual(plan, bound)

    def test_unknown_cluster_fails_closed(self):
        with self.assertRaisesRegex(ContentClusterError, "unknown_brief_cluster_id"):
            related_post_candidates({"cluster_id": "missing"}, inventory(), CLUSTERS)

    def test_cluster_posts_cannot_overlap(self):
        bad = copy.deepcopy(CLUSTERS)
        bad["clusters"]["other"] = {"name": "중복", "posts": [20]}
        with self.assertRaisesRegex(ContentClusterError, "content_cluster_post_overlap"):
            validate_clusters(bad)

    def test_orphan_detector_uses_only_complete_explicit_link_state(self):
        data = inventory()
        data["posts"][0]["content_urls"] = ["https://lifeinfo24.org/?p=20"]
        report = cluster_link_report(data, CLUSTERS)
        by_id = {row["post_id"]: row for row in report["posts"]}
        self.assertTrue(report["link_state_complete"])
        self.assertEqual(1, by_id[10]["outgoing_cluster_links"])
        self.assertEqual(1, by_id[20]["incoming_explicit_links"])
        self.assertFalse(by_id[10]["orphan_candidate"])
        self.assertFalse(by_id[20]["orphan_candidate"])

    def test_missing_content_urls_never_claims_orphan(self):
        report = cluster_link_report(inventory(with_urls=False), CLUSTERS)
        self.assertFalse(report["link_state_complete"])
        self.assertEqual(0, report["orphan_candidates"])
        self.assertTrue(all(row["incoming_explicit_links"] is None for row in report["posts"]))


if __name__ == "__main__":
    unittest.main()
