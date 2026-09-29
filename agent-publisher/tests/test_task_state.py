import tempfile
import unittest
from pathlib import Path

from agents.task_state import (
    load_task_state,
    mark_browser_qa_complete,
    start_task_state,
    update_task_state,
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


if __name__ == "__main__":
    unittest.main()
