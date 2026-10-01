import tempfile
import unittest
from pathlib import Path

from agents.task_state import (
    STATE_VERSION,
    complete_task_state,
    intent_sha256,
    load_after_image_checkpoint,
    load_task_state,
    mark_browser_qa_complete,
    start_task_state,
    task_state_path,
    update_after_image_checkpoint,
    update_task_state,
    write_after_image_checkpoint,
)


class TaskStateTests(unittest.TestCase):
    def test_state_is_resumable_and_tracks_pending_phases(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            start_task_state(
                641,
                action="edit-draft",
                edit_intent="문구 정리",
                baseline={"expected_content_sha256": "a" * 64},
                root=root,
            )
            state = update_task_state(
                641,
                completed=["route_selected", "content_review", "wordpress_saved"],
                route="fast",
                status="saved_pending_qa",
                result={"post_id": 641},
                root=root,
            )
            reread = load_task_state(641, root)
        self.assertEqual(state, reread)
        self.assertEqual("saved_pending_qa", reread["status"])
        self.assertEqual("fast", reread["route"])
        self.assertNotIn("wordpress_saved", reread["pending"])
        self.assertIn("browser_qa", reread["pending"])
        self.assertNotIn("post_content", str(reread))
        self.assertNotIn("edit_intent", reread)
        self.assertEqual(intent_sha256("문구 정리"), reread["edit_intent_sha256"])
        self.assertEqual(STATE_VERSION, reread["version"])

    def test_validation_plan_is_persisted_without_article_content(self):
        plan = {
            "version": 1,
            "profile": "quick-text",
            "plan_digest": "a" * 64,
            "full_regression_required": False,
        }
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            start_task_state(
                641, action="edit-draft", edit_intent="문구 정리",
                validation_plan=plan, root=root)
            state = load_task_state(641, root)
        self.assertEqual(plan, state["validation_plan"])
        self.assertNotIn("post_content", str(state["validation_plan"]))

    def test_unknown_phase_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            start_task_state(641, action="x", edit_intent="y", root=root)
            with self.assertRaisesRegex(ValueError, "unknown_task_phase"):
                update_task_state(641, completed=["made_up"], root=root)

    def test_active_state_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            start_task_state(641, action="edit-draft", edit_intent="첫 작업", root=root)
            with self.assertRaisesRegex(ValueError, "active_task_state_exists"):
                start_task_state(641, action="edit-draft", edit_intent="두 번째 작업", root=root)

    def test_saved_pending_qa_state_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            start_task_state(641, action="edit-draft", edit_intent="첫 작업", root=root)
            update_task_state(641, status="saved_pending_qa", root=root)
            with self.assertRaisesRegex(ValueError, "active_task_state_exists"):
                start_task_state(641, action="edit-draft", edit_intent="두 번째 작업", root=root)

    def test_browser_qa_completion_closes_saved_task_with_matching_sha(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            sha = "a" * 64
            start_task_state(
                641,
                action="edit-draft",
                edit_intent="문구 정리",
                baseline={"expected_content_sha256": "b" * 64},
                root=root,
            )
            update_task_state(
                641,
                completed=["wordpress_saved"],
                status="saved_pending_qa",
                result={"desired_content_sha256": sha},
                root=root,
            )
            completed = mark_browser_qa_complete(641, sha, root=root)
        self.assertEqual("complete", completed["status"])
        self.assertTrue(completed["completed"]["browser_qa"])
        self.assertNotIn("browser_qa", completed["pending"])

    def test_browser_qa_completion_rejects_wrong_sha(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            start_task_state(
                641,
                action="replace-featured-image",
                edit_intent="이미지 교체",
                baseline={"expected_content_sha256": "a" * 64},
                root=root,
            )
            update_task_state(
                641,
                completed=["wordpress_saved"],
                status="saved_pending_qa",
                root=root,
            )
            with self.assertRaisesRegex(ValueError, "browser_qa_content_sha_mismatch"):
                mark_browser_qa_complete(641, "b" * 64, root=root)

    def test_completion_guard_rejects_missing_required_phase(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            sha = "a" * 64
            start_task_state(
                641,
                action="quick-image-replace",
                edit_intent="이미지 교체",
                baseline={"expected_content_sha256": sha},
                completion_requirements=["image_saved", "wordpress_saved", "browser_qa"],
                root=root,
            )
            update_task_state(
                641,
                completed=["wordpress_saved"],
                status="saved_pending_qa",
                root=root,
            )
            with self.assertRaisesRegex(ValueError, "task_completion_guard_incomplete:image_saved"):
                mark_browser_qa_complete(641, sha, root=root)
            with self.assertRaisesRegex(ValueError, "task_completion_guard_incomplete"):
                complete_task_state(641, root=root)

    def test_after_image_checkpoint_survives_turn_and_requires_all_steps(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            checkpoint = write_after_image_checkpoint(
                641,
                remaining_steps=["새 이미지 업로드", "대표이미지 지정", "본문 수정"],
                expected_content_sha256="a" * 64,
                expected_thumbnail_id=70,
                target_image_handle="chatgpt-native:pending",
                completion_requirements=[
                    "image_generated", "image_saved_or_handed_off", "uploaded",
                    "featured_image_set", "requested_content_or_meta_edits_done",
                    "readback_verified",
                ],
                root=root,
            )
            self.assertEqual("in_progress", checkpoint["status"])
            state = update_after_image_checkpoint(
                641,
                completed_steps=[
                    "image_generated", "image_saved_or_handed_off", "uploaded",
                    "featured_image_set", "readback_verified",
                ],
                target_image_handle="scratch/tasks/641/cover.jpg",
                root=root,
            )
            self.assertEqual("in_progress", state["status"])
            self.assertFalse(state["completed"]["requested_content_or_meta_edits_done"])
            final = update_after_image_checkpoint(
                641,
                completed_steps=["requested_content_or_meta_edits_done"],
                root=root,
            )
            reread = load_after_image_checkpoint(641, root)
        self.assertEqual("complete", final["status"])
        self.assertEqual(final, reread)

    def test_terminal_state_is_archived_before_next_task(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            first = start_task_state(641, action="edit-draft", edit_intent="첫 작업", root=root)
            update_task_state(641, status="complete", root=root)
            second = start_task_state(641, action="edit-draft", edit_intent="두 번째 작업", root=root)
            archive = task_state_path(641, root).parent / "archive"
            archived = list(archive.glob("*.json"))
        self.assertEqual(1, len(archived))
        self.assertNotEqual(first["task_id"], second["task_id"])

    def test_legacy_v1_state_loads_without_raw_intent(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            legacy = root / "data" / "editorial_runs" / "task-state" / "post-641.json"
            legacy.parent.mkdir(parents=True)
            legacy.write_text(
                '{"version":1,"task_id":"legacy","post_id":641,"action":"edit-draft",'
                '"edit_intent":"문구 정리","status":"failed","started_at":"x","updated_at":"x",'
                '"baseline":{},"reuse":{},"route":null,"route_reasons":[],"completed":{},'
                '"pending":[],"artifacts":{},"result":{},"error":null}',
                encoding="utf-8",
            )
            state = load_task_state(641, root)
        self.assertEqual(STATE_VERSION, state["version"])
        self.assertNotIn("edit_intent", state)
        self.assertEqual(intent_sha256("문구 정리"), state["edit_intent_sha256"])


if __name__ == "__main__":
    unittest.main()
