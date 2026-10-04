import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agents.edit_router import classify_edit_route, edit_reviewed_draft
from agents.editorial import render
from agents.task_state import intent_sha256
from agents.validation_reuse import assess_validation_reuse
from test_editorial_system import sample


class EditRouterTests(unittest.TestCase):
    def _tracked(self, root, bundle):
        data = root / "data"
        data.mkdir(parents=True)
        index = data / "draft_posts.json"
        index.write_text(json.dumps([{
            "id": 393,
            "fact_manifest": {"editorial_bundle": bundle},
        }]), encoding="utf-8")
        return index

    def test_wording_only_routes_fast_without_full_reviewer(self):
        old = sample()
        new = copy.deepcopy(old)
        new["plan"]["sections"][0]["heading"] = "더 간단한 소제목"
        with tempfile.TemporaryDirectory() as folder:
            index = self._tracked(Path(folder), old)
            with patch("agents.edit_router.DRAFTS_INDEX_FILE", index), \
                 patch("agents.edit_router.validate_fast_edit", return_value={
                     "status": "candidate", "reasons": [], "changed_blocks": {"removed": [], "added": []}
                 }):
                decision = classify_edit_route(393, new)
        self.assertEqual("fast", decision["route"])
        self.assertTrue(decision["reuse"]["reuse_sources"])

    def test_new_fact_routes_standard(self):
        old = sample()
        new = copy.deepcopy(old)
        new["plan"]["lead"]["text"] += " 999원"
        with tempfile.TemporaryDirectory() as folder:
            index = self._tracked(Path(folder), old)
            with patch("agents.edit_router.DRAFTS_INDEX_FILE", index):
                decision = classify_edit_route(393, new)
        self.assertEqual("standard", decision["route"])
        self.assertTrue(any(reason.startswith("new_fact_tokens:") for reason in decision["reasons"]))

    def test_fast_route_calls_only_fast_mutator_without_long_task_state(self):
        old = sample()
        new = copy.deepcopy(old)
        new["plan"]["sections"][0]["heading"] = "더 간단한 소제목"
        body_sha = hashlib.sha256(render(old["plan"], old["sources"]).encode()).hexdigest()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            index = self._tracked(root, old)
            prepared = {
                "mode": "delta",
                "base_review_digest": old["review"]["digest"],
                "base_policy_digest": old["review"]["policy_digest"],
                "delta_digest": "prepared",
                "checks": {
                    "meaning_preserved": True,
                    "evidence_still_supports": True,
                    "conditions_preserved": True,
                    "no_new_claims": True,
                    "reader_task_preserved": True,
                },
                "issues": [],
                "edit_intent": "표현만 간결하게",
            }
            with patch("agents.edit_router.DRAFTS_INDEX_FILE", index), \
                 patch("agents.edit_router.validate_fast_edit", return_value={
                     "status": "candidate", "reasons": [], "changed_blocks": {"removed": [], "added": []}
                 }), \
                 patch("agents.edit_router.start_task_state") as start_state, \
                 patch("agents.edit_router.update_task_state"), \
                 patch("agents.edit_router.prepare_fast_delta_review", return_value=prepared), \
                 patch("agents.edit_router.fast_revise_reviewed_draft", return_value=393) as fast, \
                 patch("agents.edit_router.revise_reviewed_draft") as standard:
                result = edit_reviewed_draft(
                    393, new, body_sha, confirmed=True, edit_intent="표현만 간결하게"
                )
        self.assertEqual("fast", result["route"])
        fast.assert_called_once()
        self.assertEqual(prepared, fast.call_args.kwargs["prepared_delta_review"])
        standard.assert_not_called()
        start_state.assert_not_called()

    def test_resume_after_saved_content_skips_mutation_when_manifest_matches(self):
        old = sample()
        new = copy.deepcopy(old)
        new["plan"]["sections"][0]["heading"] = "더 간단한 소제목"
        old_body = render(old["plan"], old["sources"])
        new_body = render(new["plan"], new["sources"])
        old_sha = hashlib.sha256(old_body.encode()).hexdigest()
        new_sha = hashlib.sha256(new_body.encode()).hexdigest()
        reuse = assess_validation_reuse(old, new)
        state = {
            "action": "edit-draft",
            "status": "saved_pending_qa",
            "edit_intent_sha256": intent_sha256("표현만 간결하게"),
            "route": "fast",
            "route_reasons": [],
            "reuse": reuse,
            "baseline": {
                "expected_content_sha256": old_sha,
                "desired_content_sha256": new_sha,
                "candidate_content_digest": reuse["fingerprint_after"]["content_digest"],
            },
            "result": {},
        }
        live = {
            "post_status": "draft",
            "post_title": new["plan"]["title"],
            "post_name": "stable",
            "post_content": new_body,
            "post_excerpt": "x",
        }
        with patch("agents.edit_router.classify_edit_route", return_value={
                 "route": "standard", "reasons": ["base_review_not_current"],
                 "fast_report": {"status": "FULL_REVIEW_REQUIRED", "reasons": ["base_review_not_current"]},
                 "reuse": assess_validation_reuse(new, new),
             }), \
             patch("agents.edit_router.load_task_state", return_value=state), \
             patch("agents.edit_router.get_post", return_value=live), \
             patch("agents.edit_router._load_tracked_bundle", return_value=new), \
             patch("agents.edit_router.update_task_state") as update, \
             patch("agents.edit_router.fast_revise_reviewed_draft") as fast, \
             patch("agents.edit_router.revise_reviewed_draft") as standard:
            result = edit_reviewed_draft(
                393, new, old_sha, confirmed=True, edit_intent="표현만 간결하게", resume=True
            )
        self.assertTrue(result["resumed"])
        self.assertTrue(result["wordpress_saved"])
        fast.assert_not_called()
        standard.assert_not_called()
        self.assertEqual(2, update.call_count)
        self.assertTrue(any(
            call.kwargs.get("status") == "saved_pending_qa"
            for call in update.call_args_list
        ))

    def test_resume_blocks_when_live_sha_is_neither_old_nor_desired(self):
        old = sample()
        new = copy.deepcopy(old)
        new["plan"]["sections"][0]["heading"] = "더 간단한 소제목"
        old_body = render(old["plan"], old["sources"])
        new_body = render(new["plan"], new["sources"])
        old_sha = hashlib.sha256(old_body.encode()).hexdigest()
        new_sha = hashlib.sha256(new_body.encode()).hexdigest()
        reuse = assess_validation_reuse(old, new)
        state = {
            "action": "edit-draft", "status": "in_progress",
            "edit_intent_sha256": intent_sha256("표현만 간결하게"), "route": "fast",
            "route_reasons": [], "reuse": reuse,
            "baseline": {
                "expected_content_sha256": old_sha,
                "desired_content_sha256": new_sha,
                "candidate_content_digest": reuse["fingerprint_after"]["content_digest"],
            },
            "result": {},
        }
        live = {
            "post_status": "draft", "post_title": old["plan"]["title"],
            "post_name": "stable", "post_content": "third-party edit", "post_excerpt": "x",
        }
        with patch("agents.edit_router.classify_edit_route", return_value={
                 "route": "fast", "reasons": [],
                 "fast_report": {"status": "candidate", "reasons": [], "changed_blocks": {"removed": [], "added": []}},
                 "reuse": reuse,
             }), \
             patch("agents.edit_router.load_task_state", return_value=state), \
             patch("agents.edit_router.get_post", return_value=live), \
             patch("agents.edit_router.fail_task_state") as fail:
            with self.assertRaisesRegex(ValueError, "resume_state_conflict"):
                edit_reviewed_draft(
                    393, new, old_sha, confirmed=True, edit_intent="표현만 간결하게", resume=True
                )
        fail.assert_called_once()

    def test_resume_blocks_when_live_status_is_publish_even_if_desired_sha_matches(self):
        old = sample()
        new = copy.deepcopy(old)
        new["plan"]["sections"][0]["heading"] = "더 간단한 소제목"
        old_body = render(old["plan"], old["sources"])
        new_body = render(new["plan"], new["sources"])
        old_sha = hashlib.sha256(old_body.encode()).hexdigest()
        new_sha = hashlib.sha256(new_body.encode()).hexdigest()
        reuse = assess_validation_reuse(old, new)
        state = {
            "action": "edit-draft", "status": "in_progress",
            "edit_intent_sha256": intent_sha256("표현만 간결하게"), "route": "fast",
            "route_reasons": [], "reuse": reuse,
            "baseline": {
                "expected_content_sha256": old_sha,
                "desired_content_sha256": new_sha,
                "candidate_content_digest": reuse["fingerprint_after"]["content_digest"],
            },
            "result": {},
        }
        live = {
            "post_status": "publish", "post_title": new["plan"]["title"],
            "post_name": "stable", "post_content": new_body, "post_excerpt": "x",
        }
        with patch("agents.edit_router.classify_edit_route", return_value={
                 "route": "fast", "reasons": [],
                 "fast_report": {"status": "candidate", "reasons": [], "changed_blocks": {}},
                 "reuse": reuse,
             }), \
             patch("agents.edit_router.load_task_state", return_value=state), \
             patch("agents.edit_router.get_post", return_value=live), \
             patch("agents.edit_router.fail_task_state") as fail:
            with self.assertRaisesRegex(ValueError, "resume_state_conflict"):
                edit_reviewed_draft(
                    393, new, old_sha, confirmed=True, edit_intent="표현만 간결하게", resume=True
                )
        fail.assert_called_once_with(393, "resume_state_conflict", blocked=True)

    def test_standard_route_records_preflight_checkpoint_from_reviser(self):
        old = sample()
        new = copy.deepcopy(old)
        new["plan"]["lead"]["text"] += " 999원"
        body_sha = hashlib.sha256(render(old["plan"], old["sources"]).encode()).hexdigest()
        decision = {
            "route": "standard",
            "reasons": ["new_fact_tokens:999원"],
            "fast_report": {"status": "FULL_REVIEW_REQUIRED", "reasons": ["new_fact_tokens:999원"]},
            "reuse": assess_validation_reuse(old, new),
        }

        def standard_side_effect(*args, **kwargs):
            kwargs["checkpoint_callback"]({
                "inventory_checked_on": "2026-09-29",
                "source_validation": {"all_unchanged": True},
                "review_digest": "review",
            })
            return 393

        with patch("agents.edit_router.classify_edit_route", return_value=decision), \
             patch("agents.edit_router.start_task_state"), \
             patch("agents.edit_router.update_task_state") as update, \
             patch("agents.edit_router.revise_reviewed_draft", side_effect=standard_side_effect) as standard, \
             patch("agents.edit_router.fast_revise_reviewed_draft") as fast:
            result = edit_reviewed_draft(
                393, new, body_sha, confirmed=True, edit_intent="새 가격 정보 반영"
            )
        self.assertEqual("standard", result["route"])
        standard.assert_called_once()
        fast.assert_not_called()
        self.assertTrue(any(
            call.kwargs.get("checkpoints", {}).get("standard_preflight", {}).get("source_validation")
            == {"all_unchanged": True}
            for call in update.call_args_list
        ))

    def test_content_save_is_checkpointed_before_image_failure(self):
        old = sample()
        new = copy.deepcopy(old)
        new["plan"]["sections"][0]["heading"] = "짧은 소제목"
        old_sha = hashlib.sha256(render(old["plan"], old["sources"]).encode()).hexdigest()
        decision = {
            "route": "fast", "reasons": [],
            "fast_report": {"status": "candidate", "reasons": [], "changed_blocks": {}},
            "reuse": assess_validation_reuse(old, new),
            "qa_requirements": ["content-mobile-desktop", "featured-image"],
        }
        with tempfile.TemporaryDirectory() as folder:
            image = Path(folder) / "cover.jpg"
            image.write_bytes(b"image")
            with patch("agents.edit_router.classify_edit_route", return_value=decision), \
                 patch("agents.edit_router._load_tracked_bundle", return_value=old), \
                 patch("agents.edit_router.start_task_state"), \
                 patch("agents.edit_router.update_task_state") as update, \
                 patch("agents.edit_router.prepare_fast_delta_review", return_value={"prepared": True}), \
                 patch("agents.edit_router.fast_revise_reviewed_draft", return_value=393), \
                 patch("agents.edit_router.replace_featured_image", side_effect=ValueError("image failed")), \
                 patch("agents.edit_router.fail_task_state") as fail:
                with self.assertRaisesRegex(ValueError, "image failed"):
                    edit_reviewed_draft(
                        393, new, old_sha, confirmed=True, edit_intent="표현과 이미지 수정",
                        image_path=image, expected_thumbnail_id=70, alt_text="검토된 이미지")
        self.assertTrue(any(
            "content_saved" in call.kwargs.get("completed", [])
            for call in update.call_args_list
        ))
        self.assertFalse(any(
            "wordpress_saved" in call.kwargs.get("completed", [])
            for call in update.call_args_list
        ))
        fail.assert_called_once()

    def test_resume_after_content_save_runs_only_image_phase(self):
        old = sample()
        new = copy.deepcopy(old)
        new["plan"]["sections"][0]["heading"] = "짧은 소제목"
        old_body = render(old["plan"], old["sources"])
        new_body = render(new["plan"], new["sources"])
        old_sha = hashlib.sha256(old_body.encode()).hexdigest()
        new_sha = hashlib.sha256(new_body.encode()).hexdigest()
        reuse = assess_validation_reuse(old, new)
        with tempfile.TemporaryDirectory() as folder:
            image = Path(folder) / "cover.jpg"
            image.write_bytes(b"image")
            state = {
                "action": "edit-draft", "status": "failed",
                "edit_intent_sha256": intent_sha256("표현과 이미지 수정"),
                "route": "fast", "route_reasons": [], "reuse": reuse,
                "baseline": {
                    "expected_content_sha256": old_sha,
                    "desired_content_sha256": new_sha,
                    "candidate_content_digest": reuse["fingerprint_after"]["content_digest"],
                    "expected_thumbnail_id": 70,
                    "alt_text_sha256": hashlib.sha256("검토된 이미지".encode()).hexdigest(),
                },
                "artifacts": {"image_path": {
                    "path": str(image), "sha256": hashlib.sha256(b"image").hexdigest(),
                }},
                "completed": {"content_saved": True, "image_saved": False},
                "checkpoints": {}, "result": {},
            }
            live = {
                "post_status": "draft", "post_title": new["plan"]["title"],
                "post_name": "slug", "post_content": new_body, "post_excerpt": "x",
            }
            with patch("agents.edit_router.classify_edit_route", return_value={
                     "route": "fast", "reasons": [],
                     "fast_report": {"status": "candidate", "reasons": [], "changed_blocks": {}},
                     "reuse": reuse, "qa_requirements": ["featured-image"],
                 }), \
                 patch("agents.edit_router.load_task_state", return_value=state), \
                 patch("agents.edit_router.get_post", return_value=live), \
                 patch("agents.edit_router._load_tracked_bundle", return_value=new), \
                 patch("agents.edit_router.update_task_state"), \
                 patch("agents.edit_router.fast_revise_reviewed_draft") as fast, \
                 patch("agents.edit_router.revise_reviewed_draft") as standard, \
                 patch("agents.edit_router.replace_featured_image", return_value={
                     "attachment_id": 88, "attachment_url": "https://example/image.jpg",
                 }) as image_edit:
                result = edit_reviewed_draft(
                    393, new, old_sha, confirmed=True, edit_intent="표현과 이미지 수정",
                    image_path=image, expected_thumbnail_id=70, alt_text="검토된 이미지",
                    resume=True)
        fast.assert_not_called()
        standard.assert_not_called()
        image_edit.assert_called_once()
        self.assertEqual(88, result["image"]["attachment_id"])


if __name__ == "__main__":
    unittest.main()
