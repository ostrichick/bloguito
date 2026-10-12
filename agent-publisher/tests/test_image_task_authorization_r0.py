"""R0 regression: claims from the caller are not authorization evidence."""

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import editorial_cli
from agents.image_generation_policy import new_image_generation_task
from agents.task_state import (
    validate_current_image_task, write_after_image_checkpoint,
    load_after_image_checkpoint, claim_image_import_attempt)


class ImageTaskAuthorizationR0Tests(unittest.TestCase):
    def make_args(self, action="replace-featured-image", *, task_id=None, file=None, task_record=None):
        return SimpleNamespace(action=action, post_id=922, image_task_id=task_id,
                               file=file, image_task_record=task_record)

    def test_complete_and_held_checkpoints_cannot_be_used_for_new_upload(self):
        for status in ("complete", "held_image_generation_unavailable", "cancelled", "awaiting_image_gen"):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                task = new_image_generation_task(post_id=922, candidate_count=1,
                                                 selection_mode="agent-delegated", explicitly_delegated=True)
                write_after_image_checkpoint(
                    922, remaining_steps=["upload"], expected_content_sha256="a" * 64,
                    expected_thumbnail_id=924, target_image_handle="native:pending",
                    completion_requirements=["uploaded"], image_task=task, root=root)
                state = load_after_image_checkpoint(922, root)
                state["status"] = status
                checkpoint = root / "data/editorial_runs/task-state/post-922/after-image.json"
                checkpoint.write_text(json.dumps(state), encoding="utf-8")
                with self.assertRaises(ValueError):
                    validate_current_image_task(922, root)
                args = self.make_args(task_id=task["task_id"])
                with (patch("agents.task_state.load_after_image_checkpoint", return_value=state),
                      patch("agents.task_state.validate_current_image_task", side_effect=ValueError("not_active"))):
                    with self.assertRaises(ValueError):
                        editorial_cli._require_current_image_task(args, {
                            "candidate_number": 1, "selection_mode": "agent-delegated"})

    def test_caller_created_task_json_not_enough_even_when_policy_metadata_valid(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            task = new_image_generation_task(post_id=922, candidate_count=1,
                                             selection_mode="agent-delegated", explicitly_delegated=True)
            task_file = root / "invented-authority.json"
            task_file.write_text(json.dumps(task), encoding="utf-8")
            args = self.make_args(task_id=task["task_id"], task_record=task_file)
            with patch("agents.task_state.load_after_image_checkpoint", return_value=None):
                with self.assertRaises(ValueError):
                    editorial_cli._require_current_image_task(args, {
                        "candidate_number": 1, "selection_mode": "agent-delegated"})

    def test_new_draft_self_authored_user_choice_is_not_permission_to_import(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            task = new_image_generation_task(brief_id="brief-922", candidate_count=1,
                                             selection_mode="user")
            task_file = root / "invented-draft-task.json"
            task_file.write_text(json.dumps(task), encoding="utf-8")
            bundle = root / "bundle.json"
            bundle.write_text(json.dumps({"brief": {"id": "brief-922"}}), encoding="utf-8")
            args = self.make_args("prepare-draft", task_id=task["task_id"],
                                  task_record=task_file, file=bundle)
            with self.assertRaises(ValueError):
                editorial_cli._require_current_image_task(args, {
                    "candidate_number": 1, "selection_mode": "user"})

    def test_active_checkpoint_and_exact_existing_post_can_continue(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            task = new_image_generation_task(post_id=922, candidate_count=1,
                                             selection_mode="agent-delegated", explicitly_delegated=True)
            write_after_image_checkpoint(
                922, remaining_steps=["upload"], expected_content_sha256="a" * 64,
                expected_thumbnail_id=924, target_image_handle="native:pending",
                completion_requirements=["uploaded"], image_task=task, root=root)
            state = load_after_image_checkpoint(922, root)
            args = self.make_args(task_id=task["task_id"])
            with (patch("agents.task_state.load_after_image_checkpoint", return_value=state),
                  patch("agents.task_state.validate_current_image_task", return_value=task)):
                accepted = editorial_cli._require_current_image_task(args, {
                    "candidate_number": 1, "selection_mode": "agent-delegated"})
            self.assertEqual(task["task_id"], accepted["task_id"])

    def test_started_import_and_completed_upload_are_fenced(self):
        for variant in ("upload_attempt_started", "uploaded", "task_completed"):
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                task = new_image_generation_task(post_id=922, candidate_count=1,
                                                 selection_mode="user")
                write_after_image_checkpoint(
                    922, remaining_steps=["image upload"],
                    expected_content_sha256="a" * 64,
                    expected_thumbnail_id=924, target_image_handle="native:pending",
                    completion_requirements=["uploaded"], image_task=task, root=root)
                path = root / "data/editorial_runs/task-state/post-922/after-image.json"
                state = json.loads(path.read_text(encoding="utf-8"))
                if variant == "upload_attempt_started":
                    state["result"]["upload_attempt_started"] = True
                elif variant == "uploaded":
                    state["completed"]["uploaded"] = True
                else:
                    state["image_task"]["status"] = "completed"
                    state["image_task"]["image_pending"] = False
                path.write_text(json.dumps(state), encoding="utf-8")
                with self.assertRaises(ValueError):
                    validate_current_image_task(922, root)

    def test_canonical_first_claim_succeeds_once_and_recovery_does_not_retry(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            task = new_image_generation_task(post_id=922, candidate_count=1,
                                             selection_mode="user")
            write_after_image_checkpoint(
                922, remaining_steps=["image upload"],
                expected_content_sha256="a" * 64,
                expected_thumbnail_id=924, target_image_handle="native:pending",
                completion_requirements=["uploaded"], image_task=task, root=root)
            self.assertEqual(task["task_id"], validate_current_image_task(922, root)["task_id"])
            with self.assertRaisesRegex(ValueError, "identity_mismatch"):
                claim_image_import_attempt(922, "wrong-task", root)
            self.assertFalse(load_after_image_checkpoint(922, root)["result"].get("upload_attempt_started"))
            claim = claim_image_import_attempt(922, task["task_id"], root)
            self.assertTrue(claim["result"]["upload_attempt_started"])
            with self.assertRaisesRegex(ValueError, "import_started_or_completed"):
                claim_image_import_attempt(922, task["task_id"], root)
            self.assertFalse((root / "data/.editorial-publish.lock").exists())

    def test_canonical_cli_claim_precedes_image_mutation(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "staged.webp"
            path.write_bytes(b"stub")
            task = new_image_generation_task(post_id=922, candidate_count=1,
                                             selection_mode="user")
            state = {"status": "in_progress", "image_task": task,
                     "image_task_id": task["task_id"], "created_at": "2026-10-12T15:00:00+09:00"}
            argv = ["editorial_cli.py", "replace-featured-image", "--post-id", "922",
                    "--image-path", str(path), "--alt-text", "실제 원본 이미지 설명",
                    "--confirm-update", "--confirm-image-selection",
                    "--candidate-manifest", str(Path(folder) / "manifest.json"),
                    "--selected-candidate", "1", "--selection-mode", "user",
                    "--visual-review-receipt", str(Path(folder) / "quality.json"),
                    "--image-task-id", task["task_id"]]
            calls = []
            def claim(*args):
                calls.append("claim")
            def upload(*args, **kwargs):
                calls.append("upload")
                return {"status": "draft", "post_id": 922}
            with (patch("sys.argv", argv),
                  patch("agents.task_state.load_after_image_checkpoint", return_value=state),
                  patch("agents.task_state.validate_current_image_task", return_value=task),
                  patch("agents.task_state.claim_image_import_attempt", side_effect=claim),
                  patch("agents.featured_image.verify_manual_image_upload_lineage", return_value={
                      "source_sha256": "a" * 64, "staged_sha256": "b" * 64,
                      "candidate_number": 1, "selection_mode": "user"}),
                  patch("agents.featured_image_quality_gate.require_accepted_quality_review",
                        return_value={"review_result": "pass"}),
                  patch("agents.featured_image.replace_featured_image_from_live_baseline",
                        side_effect=upload)):
                editorial_cli._main()
            self.assertEqual(["claim", "upload"], calls)


if __name__ == "__main__":
    unittest.main()
