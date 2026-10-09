"""Boundary tests for the post-image continuation, without WordPress writes."""
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "featured_image_followthrough.py"
spec = importlib.util.spec_from_file_location("featured_image_followthrough", SCRIPT)
follow = importlib.util.module_from_spec(spec)
spec.loader.exec_module(follow)


class FeaturedImageFollowthroughTests(unittest.TestCase):
    def setUp(self):
        self.baseline = {
            "post_id": 856, "content_sha256": "a" * 64,
            "thumbnail_id": 857, "status": "draft",
            "title": "노인장기요양보험", "slug": "", "excerpt": "기존 발췌문",
        }

    def test_begin_requires_a_real_wordpress_read_before_checkpoint(self):
        with (patch.object(follow, "read_wordpress", return_value=self.baseline) as live,
              patch.object(follow, "load_after_image_checkpoint", return_value=None),
              patch.object(follow, "write_after_image_checkpoint") as write,
              patch.object(follow, "update_after_image_checkpoint") as update):
            result = follow.begin(856)
        live.assert_called_once_with(856, "bloguito")
        self.assertEqual("awaiting_image_gen", result["status"])
        self.assertEqual("a" * 64, write.call_args.kwargs["expected_content_sha256"])
        self.assertEqual(857, write.call_args.kwargs["expected_thumbnail_id"])
        self.assertEqual(set(follow.REQUIRED), set(write.call_args.kwargs["completion_requirements"]))
        self.assertEqual("draft", update.call_args.kwargs["result"]["initial_status"])

    def test_connection_failure_cannot_create_a_false_preflight(self):
        with (patch.object(follow, "read_wordpress", side_effect=RuntimeError("ssh_failed")),
              patch.object(follow, "load_after_image_checkpoint", return_value=None),
              patch.object(follow, "write_after_image_checkpoint") as write):
            with self.assertRaisesRegex(RuntimeError, "ssh_failed"):
                follow.begin(856)
        write.assert_not_called()

    def test_begin_accepts_draft_without_existing_thumbnail(self):
        no_cover = {**self.baseline, "thumbnail_id": None}
        with (patch.object(follow, "read_wordpress", return_value=no_cover),
              patch.object(follow, "load_after_image_checkpoint", return_value=None),
              patch.object(follow, "write_after_image_checkpoint") as write,
              patch.object(follow, "update_after_image_checkpoint")):
            follow.begin(856)
        self.assertIsNone(write.call_args.kwargs["expected_thumbnail_id"])

    def test_active_checkpoint_cannot_be_replaced(self):
        with (patch.object(follow, "load_after_image_checkpoint",
                           return_value={"status": "in_progress"}),
              patch.object(follow, "read_wordpress") as live):
            with self.assertRaisesRegex(ValueError, "active_after_image_checkpoint_exists"):
                follow.begin(856)
        live.assert_not_called()

    def test_status_is_incomplete_until_upload_and_readback_verified(self):
        incomplete = {
            "status": "in_progress",
            "completed": {"image_generated": True, "image_saved_or_handed_off": True},
            "completion_requirements": list(follow.REQUIRED),
            "result": {},
        }
        with (patch.object(follow, "load_after_image_checkpoint", return_value=incomplete),
              patch.object(follow, "read_wordpress") as live):
            state = follow.inspect(856)
        self.assertIn("uploaded", state["missing_requirements"])
        self.assertNotIn("wordpress_verified", state)
        live.assert_not_called()

    def test_complete_status_rechecks_attachment_and_unchanged_post(self):
        complete = {
            "status": "complete", "completed": {s: True for s in follow.REQUIRED},
            "completion_requirements": list(follow.REQUIRED),
            "expected_content_sha256": "a" * 64,
            "result": {
                "attachment_id": 904, "attachment_url": "https://example.org/904.webp",
                "initial_status": "draft", "initial_title": "노인장기요양보험",
                "initial_slug": "", "initial_excerpt": "기존 발췌문",
            },
        }
        with (patch.object(follow, "load_after_image_checkpoint", return_value=complete),
              patch.object(follow, "read_wordpress", return_value={**self.baseline, "thumbnail_id": 904})):
            self.assertTrue(follow.inspect(856)["wordpress_verified"])
        with (patch.object(follow, "load_after_image_checkpoint", return_value=complete),
              patch.object(follow, "read_wordpress", return_value={**self.baseline, "thumbnail_id": 905})):
            self.assertFalse(follow.inspect(856)["wordpress_verified"])

    def test_stale_wordpress_baseline_prevents_any_image_import(self):
        checkpoint = {
            "status": "in_progress", "expected_content_sha256": "a" * 64,
            "expected_thumbnail_id": 857, "completed": {},
            "result": {"initial_status": self.baseline["status"],
                       "initial_title": self.baseline["title"],
                       "initial_slug": self.baseline["slug"],
                       "initial_excerpt": self.baseline["excerpt"]},
        }
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "candidate-1.png"
            source.write_bytes(b"saved-original")
            with (patch.object(follow, "load_after_image_checkpoint", return_value=checkpoint),
                  patch.object(follow, "read_wordpress",
                               return_value={**self.baseline, "thumbnail_id": 858}),
                  patch.object(follow, "_run") as run):
                with self.assertRaisesRegex(ValueError, "wordpress_changed_since_image"):
                    follow.continue_upload(
                        856, source, "설명",
                        selected_candidate=1, selection_mode="agent-delegated")
            run.assert_not_called()

    def test_existing_staging_prevents_blind_second_import(self):
        checkpoint = {
            "status": "in_progress", "expected_content_sha256": "a" * 64,
            "expected_thumbnail_id": 857, "completed": {},
            "result": {"initial_status": self.baseline["status"],
                       "initial_title": self.baseline["title"],
                       "initial_slug": self.baseline["slug"],
                       "initial_excerpt": self.baseline["excerpt"]},
        }
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "candidate-1.png"
            source.write_bytes(b"saved-original")
            source.with_name("candidate-manifest.json").write_text("{}", encoding="utf-8")
            with (patch.object(follow, "load_after_image_checkpoint", return_value=checkpoint),
                  patch.object(follow, "read_wordpress", return_value=self.baseline),
                  patch.object(follow, "_run") as run):
                with self.assertRaisesRegex(ValueError, "existing_staging_requires_explicit_resume|candidate_not_sealed"):
                    # An already created manifest is not treated as proof that
                    # an importer may safely retry.
                    source.with_name("candidate-1-upload.webp").write_bytes(b"old")
                    follow.continue_upload(
                        856, source, "설명",
                        selected_candidate=1, selection_mode="agent-delegated")
            run.assert_not_called()

    def test_one_call_continues_from_saved_image_through_verified_upload(self):
        checkpoint = {
            "status": "in_progress", "expected_content_sha256": "a" * 64,
            "expected_thumbnail_id": 857, "completed": {},
        }
        fake_upload = {"post_id": 856, "attachment_id": 904,
                       "attachment_url": "https://example.org/904.webp"}
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "candidate-1.png"
            Image.new("RGB", (1672, 941), "white").save(source, "PNG")
            real_run = follow._run

            def transport_only_mock(argv, **kwargs):
                if "editorial_cli_via_ssh.py" in " ".join(str(item) for item in argv):
                    return "[Validation] image-only: PASS\n" + json.dumps(fake_upload)
                return real_run(argv, **kwargs)

            initial = {
                "initial_status": self.baseline["status"],
                "initial_title": self.baseline["title"],
                "initial_slug": self.baseline["slug"],
                "initial_excerpt": self.baseline["excerpt"],
            }
            checkpoint["result"] = initial
            with (patch.object(follow, "load_after_image_checkpoint", return_value=checkpoint),
                  patch.object(follow, "read_wordpress", return_value=self.baseline),
                  patch.object(follow, "_run", side_effect=transport_only_mock) as run,
                  patch.object(follow, "update_after_image_checkpoint") as update,
                  patch.object(follow, "assert_after_image_complete") as guard,
                  patch.object(follow, "inspect", return_value={
                      "wordpress_verified": True, "missing_requirements": [],
                  })):
                result = follow.continue_upload(
                    856, source, "장기요양보험 신청 안내",
                    selected_candidate=1, selection_mode="agent-delegated")
            self.assertEqual(3, run.call_count)
            self.assertIn("replace-featured-image", run.call_args.args[0])
            self.assertIn("--confirm-image-selection", run.call_args.args[0])
            self.assertEqual("completed", result["status"])
            self.assertEqual(["image_generated", "image_saved_or_handed_off"],
                             update.call_args_list[0].kwargs["completed_steps"])
            self.assertTrue(update.call_args.kwargs["result"]["upload_attempt_started"])
            self.assertTrue(source.with_name("candidate-1-upload.webp").is_file())
            guard.assert_called_once()

    def test_previous_ambiguous_import_must_not_be_retried(self):
        checkpoint = {
            "status": "in_progress", "expected_content_sha256": "a" * 64,
            "expected_thumbnail_id": 857, "completed": {},
            "result": {"upload_attempt_started": True},
        }
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "candidate-1.png"
            source.write_bytes(b"saved-original")
            with (patch.object(follow, "load_after_image_checkpoint", return_value=checkpoint),
                  patch.object(follow, "read_wordpress") as live,
                  patch.object(follow, "_run") as run):
                with self.assertRaisesRegex(ValueError, "ambiguous_previous_upload_attempt"):
                    follow.continue_upload(
                        856, source, "ALT", selected_candidate=1,
                        selection_mode="agent-delegated", resume=True)
            live.assert_not_called()
            run.assert_not_called()

    def test_missing_explicit_selection_cannot_start_import(self):
        with (patch.object(follow, "load_after_image_checkpoint", return_value={
                  "status": "in_progress", "completed": {}, "result": {},
              }), patch.object(follow, "_run") as run):
            with self.assertRaisesRegex(ValueError, "explicit_selected_candidate_required"):
                follow.continue_upload(856, Path("missing.png"), "ALT")
        run.assert_not_called()

    def test_console_output_with_progress_has_exactly_one_receipt(self):
        receipt = {"post_id": 856, "attachment_id": 904}
        result = follow._parse_upload_receipt(
            "[Edit Route] image-only\n" + json.dumps(receipt) + "\n[Complete]", 856)
        self.assertEqual(receipt, result)
        with self.assertRaisesRegex(RuntimeError, "upload_receipt_missing_or_ambiguous"):
            follow._parse_upload_receipt(json.dumps(receipt) * 2, 856)

    def test_sealed_third_user_choice_survives_local_stage_and_upload(self):
        initial = {"initial_status": self.baseline["status"],
                   "initial_title": self.baseline["title"],
                   "initial_slug": self.baseline["slug"],
                   "initial_excerpt": self.baseline["excerpt"]}
        checkpoint = {
            "status": "in_progress", "expected_content_sha256": "a" * 64,
            "expected_thumbnail_id": 857, "completed": {}, "result": initial,
        }
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            originals = []
            for number, color in enumerate(("red", "green", "blue"), start=1):
                candidate = root / f"candidate-{number}.png"
                Image.new("RGB", (1600, 900), color).save(candidate, "PNG")
                originals.append(candidate)
            manifest = root / "candidate-manifest.json"
            real_run = follow._run
            real_run([str(follow.sys.executable),
                      str(follow.ROOT / "scripts/seal_featured_image_candidates.py"),
                      *map(str, originals), "--output", str(manifest)])
            fake_upload = {"post_id": 856, "attachment_id": 904}
            def transport_mock(argv, **kwargs):
                if "editorial_cli_via_ssh.py" in " ".join(str(item) for item in argv):
                    return json.dumps(fake_upload)
                return real_run(argv, **kwargs)

            with (patch.object(follow, "load_after_image_checkpoint", return_value=checkpoint),
                  patch.object(follow, "read_wordpress", return_value=self.baseline),
                  patch.object(follow, "_run", side_effect=transport_mock) as run,
                  patch.object(follow, "update_after_image_checkpoint"),
                  patch.object(follow, "assert_after_image_complete"),
                  patch.object(follow, "inspect", return_value={"wordpress_verified": True})):
                result = follow.continue_upload(
                    856, originals[2], "Third candidate",
                    candidate_manifest=manifest, selected_candidate=3, selection_mode="user")
            self.assertEqual("completed", result["status"])
            self.assertEqual(2, run.call_count)  # stage + canonical upload, no new seal
            argv = run.call_args.args[0]
            self.assertEqual("3", argv[argv.index("--selected-candidate") + 1])
            self.assertEqual("user", argv[argv.index("--selection-mode") + 1])

    def test_verified_local_stage_resumes_without_another_import_attempt(self):
        initial = {"initial_status": self.baseline["status"],
                   "initial_title": self.baseline["title"],
                   "initial_slug": self.baseline["slug"],
                   "initial_excerpt": self.baseline["excerpt"]}
        checkpoint = {
            "status": "in_progress", "expected_content_sha256": "a" * 64,
            "expected_thumbnail_id": 857, "completed": {}, "result": initial,
        }
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "candidate-1.png"
            Image.new("RGB", (1600, 900), "white").save(source, "PNG")
            manifest = root / "candidate-manifest.json"
            output = root / "candidate-1-upload.webp"
            follow._run([str(follow.sys.executable),
                         str(follow.ROOT / "scripts/seal_featured_image_candidates.py"),
                         str(source), "--output", str(manifest)])
            follow._run([str(follow.sys.executable),
                         str(follow.ROOT / "scripts/stage_featured_image.py"),
                         str(source), str(output), "--candidate-manifest", str(manifest),
                         "--selected-candidate", "1", "--selection-mode", "user"])
            fake_upload = {"post_id": 856, "attachment_id": 904}
            with (patch.object(follow, "load_after_image_checkpoint", return_value=checkpoint),
                  patch.object(follow, "read_wordpress", return_value=self.baseline),
                  patch.object(follow, "_run", return_value=json.dumps(fake_upload)) as run,
                  patch.object(follow, "update_after_image_checkpoint"),
                  patch.object(follow, "assert_after_image_complete"),
                  patch.object(follow, "inspect", return_value={"wordpress_verified": True})):
                with self.assertRaisesRegex(ValueError, "existing_staging_requires_explicit_resume"):
                    follow.continue_upload(
                        856, source, "ALT", candidate_manifest=manifest,
                        selected_candidate=1, selection_mode="user")
                result = follow.continue_upload(
                    856, source, "ALT", candidate_manifest=manifest,
                    selected_candidate=1, selection_mode="user", resume=True)
            self.assertEqual("completed", result["status"])
            self.assertEqual(1, run.call_count)
            self.assertIn("editorial_cli_via_ssh.py", " ".join(run.call_args.args[0]))

    def test_read_wordpress_treats_missing_thumbnail_meta_as_none(self):
        post = {
            "ID": 856, "post_content": "text", "post_title": "Title",
            "post_status": "draft", "post_name": "slug", "post_excerpt": "",
        }
        with patch.object(follow, "_wp", side_effect=[
                json.dumps(post),
                RuntimeError("command_exit_1:Error: Could not find the specified post meta field."),
        ]):
            self.assertIsNone(follow.read_wordpress(856)["thumbnail_id"])


if __name__ == "__main__":
    unittest.main()
