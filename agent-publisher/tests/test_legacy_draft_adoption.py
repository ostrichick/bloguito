import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agents import legacy_draft_adoption as adoption
from agents.post_manifest_store import load_record
from test_editorial_system import sample


class LegacyDraftAdoptionTests(unittest.TestCase):
    def setUp(self):
        self.bundle = sample()
        self.bundle["brief"]["existing_post_id"] = 858
        self.bundle["plan"]["title"] = "새로 검수한 국민연금 실버론 안내"
        self.before = {
            "post_status": "draft", "post_title": "기존 실버론 임시글",
            "post_name": "", "post_excerpt": "수동으로 작성한 요약은 보존합니다.",
            "post_content": "<p>기존 글입니다.</p>",
        }
        self.initial_sha = hashlib.sha256(self.before["post_content"].encode()).hexdigest()
        self.context = tempfile.TemporaryDirectory()
        self.addCleanup(self.context.cleanup)
        self.root = Path(self.context.name)
        data = self.root / "data"
        data.mkdir()
        self.draft = data / "draft_posts.json"
        self.public = data / "published_posts.json"
        self.draft.write_text("[]", encoding="utf-8")
        self.public.write_text("[]", encoding="utf-8")
        self.inventory = {"checked_on": "2026-10-10", "posts": [{
            "ID": 858, "post_status": "draft", "post_title": self.before["post_title"],
            "content_sha256": self.initial_sha,
        }]}
        self.patches = [
            patch.object(adoption, "ROOT", self.root),
            patch.object(adoption, "DRAFTS_INDEX_FILE", self.draft),
            patch.object(adoption, "POSTS_INDEX_FILE", self.public),
            patch.object(adoption, "sync_inventory"),
            patch.object(adoption, "load_inventory", return_value=self.inventory),
            patch.object(adoption, "inventory_content_sha", return_value=self.initial_sha),
            patch.object(adoption, "get_post", return_value=self.before),
            patch.object(adoption, "_adoption_category_ids", return_value=[3]),
            patch.object(adoption, "_read_permalink", return_value="https://lifeinfo24.org/p/858/"),
            patch.object(adoption, "render", return_value="<p>새로 검수한 본문.</p>"),
            patch.object(adoption, "missing_internal_post_ids", return_value=[]),
            patch.object(adoption, "verify_sources_unchanged", return_value={
                "all_unchanged": True, "refetched_source_ids": ["s1"]}),
            patch.object(adoption, "validate_bundle", return_value={"status": "ready", "reasons": []}),
            patch.object(adoption, "hydrate_duplicate_candidates", side_effect=lambda b, inv, **k: inv),
            patch.object(adoption, "rank_math_meta_from_brief", return_value=None),
            patch.object(adoption, "excerpt_from_lead", return_value="검수 후 새 요약"),
            patch.object(adoption, "resolve_category", return_value={
                "id": 3, "name": "복지/지원금"}),
            patch.object(adoption, "save_report"),
            patch.object(adoption, "invalidate_inventory"),
        ]
        self.started = [entry.start() for entry in self.patches]
        self.addCleanup(lambda: [entry.stop() for entry in reversed(self.patches)])

    def test_success_requires_guarded_readback_before_new_reviewed_record(self):
        verified = []

        def guarded(*args, **kwargs):
            self.assertEqual(self.initial_sha, kwargs["expected"]["content_sha256"])
            self.assertEqual([3], kwargs["expected"]["category_ids"])
            self.assertEqual("draft", kwargs["expected"]["post_status"])
            self.assertEqual("기존 실버론 임시글", kwargs["expected"]["post_title"])
            self.assertEqual("수동으로 작성한 요약은 보존합니다.",
                             kwargs["expected"]["post_excerpt"])
            self.assertNotIn("post_excerpt", kwargs["updates"])
            self.assertIsNone(load_record(self.draft, 858))
            return {**self.before, **kwargs["updates"]}

        def check(*args, **kwargs):
            self.assertIsNone(load_record(self.draft, 858))
            verified.append(True)
            return True

        with patch.object(adoption, "guarded_update_post", side_effect=guarded), \
             patch.object(adoption, "verify_saved_fields", side_effect=check), \
             patch.object(adoption, "backup_json", return_value=self.root / "backup.json"):
            result = adoption.adopt_reviewed_legacy_draft(
                858, self.bundle, self.initial_sha,
                confirmed=True, confirm_title_change=True)
        self.assertTrue(verified)
        self.assertEqual("standard-legacy-draft", result["route"])
        self.assertTrue(result["readback_verified"])
        stored = load_record(self.draft, 858)
        self.assertIsNotNone(stored)
        self.assertEqual(self.bundle, stored.record["fact_manifest"]["editorial_bundle"])
        self.assertEqual("draft", stored.record["status"])
        self.assertEqual("https://lifeinfo24.org/p/858/", stored.record["url"])

    def test_source_recheck_mismatch_does_not_call_wordpress_mutator(self):
        with patch.object(adoption, "verify_sources_unchanged",
                          side_effect=ValueError("official_sources_changed_since_review")), \
             patch.object(adoption, "guarded_update_post") as mutate:
            with self.assertRaisesRegex(ValueError, "official_sources_changed"):
                adoption.adopt_reviewed_legacy_draft(
                    858, self.bundle, self.initial_sha, confirmed=True,
                    confirm_title_change=True)
            mutate.assert_not_called()
        self.assertIsNone(load_record(self.draft, 858))

    def test_full_review_rejection_never_creates_provenance(self):
        with patch.object(adoption, "validate_bundle", return_value={
                     "status": "hold", "reasons": ["semantic_review_invalid"]}), \
             patch.object(adoption, "guarded_update_post") as mutate:
            with self.assertRaisesRegex(ValueError, "full_review_required"):
                adoption.adopt_reviewed_legacy_draft(
                    858, self.bundle, self.initial_sha, confirmed=True,
                    confirm_title_change=True)
            mutate.assert_not_called()
        self.assertIsNone(load_record(self.draft, 858))

    def test_cannot_adopt_other_id_or_non_draft(self):
        with patch.object(adoption, "guarded_update_post") as mutate:
            with self.assertRaisesRegex(ValueError, "explicit_post_id_binding"):
                adoption.adopt_reviewed_legacy_draft(
                    859, self.bundle, self.initial_sha, confirmed=True,
                    confirm_title_change=True)
            with patch.object(adoption, "get_post",
                              return_value={**self.before, "post_status": "publish"}):
                with self.assertRaisesRegex(ValueError, "live_baseline_mismatch"):
                    adoption.adopt_reviewed_legacy_draft(
                        858, self.bundle, self.initial_sha, confirmed=True,
                        confirm_title_change=True)
            mutate.assert_not_called()
        self.assertIsNone(load_record(self.draft, 858))


if __name__ == "__main__":
    unittest.main()
