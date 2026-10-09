import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from PIL import Image

from agents.featured_image import (
    _FeaturedImageBudget,
    _advance_matching_after_image_checkpoint,
    _read_post_meta,
    hardened_attach_featured_image,
    quick_replace_featured_image,
    reconcile_featured_image_outcome,
    recover_imported_featured_image_outcome,
    replace_featured_image,
    update_featured_image_alt_from_live_baseline,
    validate_featured_image_file,
)


def _wp_args(args):
    if args[:6] == ["sudo", "docker", "exec", "-i", "wordpress_app", "wp"]:
        return args[6:]
    if args[:5] == ["sudo", "docker", "exec", "wordpress_app", "wp"]:
        return args[5:]
    return None


class FeaturedImageReplacementTests(unittest.TestCase):
    def _image(self, folder):
        path = Path(folder) / "cover.jpg"
        Image.new("RGB", (1200, 675), color=(245, 245, 245)).save(path, "JPEG")
        return path

    def test_after_image_checkpoint_cannot_be_completed_by_different_image(self):
        with tempfile.TemporaryDirectory() as folder:
            image_path = self._image(folder)
            checkpoint = {
                "expected_content_sha256": "a" * 64,
                "expected_thumbnail_id": 70,
                "target_image_handle": str(Path(folder) / "selected-candidate.webp"),
            }
            with patch("agents.featured_image.load_after_image_checkpoint", return_value=checkpoint), \
                 patch("agents.featured_image.update_after_image_checkpoint") as advance:
                _advance_matching_after_image_checkpoint(
                    641, expected_content_sha256="a" * 64,
                    expected_thumbnail_id=70, image_path=image_path, result={"attachment_id": 777},
                )
            advance.assert_not_called()

    def test_after_image_checkpoint_advances_only_verified_upload_steps(self):
        with tempfile.TemporaryDirectory() as folder:
            image_path = self._image(folder)
            checkpoint = {
                "expected_content_sha256": "a" * 64,
                "expected_thumbnail_id": 70,
                "target_image_handle": str(image_path),
                "target_image_sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
            }
            result = {"attachment_id": 777, "image": {
                "sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
            }}
            with patch("agents.featured_image.load_after_image_checkpoint", return_value=checkpoint), \
                 patch("agents.featured_image.update_after_image_checkpoint") as advance:
                _advance_matching_after_image_checkpoint(
                    641, expected_content_sha256="a" * 64,
                    expected_thumbnail_id=70, image_path=image_path, result=result,
                )
            steps = advance.call_args.kwargs["completed_steps"]
            self.assertIn("uploaded", steps)
            self.assertIn("readback_verified", steps)
            self.assertNotIn("image_generated", steps)
            self.assertNotIn("image_saved_or_handed_off", steps)

    def test_after_image_checkpoint_rejects_same_path_overwritten_after_seal(self):
        with tempfile.TemporaryDirectory() as folder:
            image_path = self._image(folder)
            old_sha = hashlib.sha256(image_path.read_bytes()).hexdigest()
            checkpoint = {
                "expected_content_sha256": "a" * 64,
                "expected_thumbnail_id": 70,
                "target_image_handle": str(image_path),
                "target_image_sha256": old_sha,
            }
            Image.new("RGB", (1200, 675), "black").save(image_path, "JPEG")
            new_sha = hashlib.sha256(image_path.read_bytes()).hexdigest()
            self.assertNotEqual(old_sha, new_sha)
            with patch("agents.featured_image.load_after_image_checkpoint", return_value=checkpoint), \
                 patch("agents.featured_image.update_after_image_checkpoint") as advance:
                _advance_matching_after_image_checkpoint(
                    641, expected_content_sha256="a" * 64,
                    expected_thumbnail_id=70, image_path=image_path,
                    result={"attachment_id": 777, "image": {"sha256": new_sha}},
                )
            advance.assert_not_called()

    def test_failed_prior_media_import_checkpoint_blocks_direct_image_only_retry(self):
        with tempfile.TemporaryDirectory() as folder:
            image_path = self._image(folder)
            live = {
                "post_status": "draft", "post_title": "title", "post_name": "slug",
                "post_excerpt": "summary", "post_content": "body",
            }
            previous = {
                "status": "failed",
                "checkpoints": {"image_import_attempt": {
                    "started": True,
                    "image_sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
                }},
            }
            with patch("agents.featured_image.acquire_editorial_lock", return_value=object()), \
                 patch("agents.featured_image.release_editorial_lock"), \
                 patch("agents.featured_image.get_post", return_value=live), \
                 patch("agents.featured_image._read_post_meta", return_value="70"), \
                 patch("agents.featured_image.load_task_state", return_value=previous), \
                 patch("agents.featured_image.start_task_state") as start, \
                 patch("agents.featured_image.subprocess.run") as run:
                with self.assertRaisesRegex(ValueError, "featured_image_prior_import_requires_reconcile"):
                    replace_featured_image(
                        641, image_path, hashlib.sha256(b"body").hexdigest(),
                        expected_thumbnail_id=70, alt_text="alt", confirmed=True,
                    )
            start.assert_not_called()
            run.assert_not_called()

    def test_resume_fails_on_remote_lock_busy_before_thumbnail_mutation(self):
        checkpoint = {"attachment_id": 777}
        with patch("agents.featured_image.acquire_featured_image_lock", side_effect=ValueError(
                "featured_image_remote_lock_busy")) as acquire, \
             patch("agents.featured_image.guarded_set_post_thumbnail") as thumbnail:
            with self.assertRaisesRegex(ValueError, "featured_image_remote_lock_busy"):
                reconcile_featured_image_outcome(641, checkpoint, "alt")
        acquire.assert_called_once()
        thumbnail.assert_not_called()

    def test_file_guard_requires_policy_canvas(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "wrong.jpg"
            Image.new("RGB", (800, 450)).save(path, "JPEG")
            with self.assertRaisesRegex(ValueError, "featured_image_canvas_mismatch"):
                validate_featured_image_file(path)

    def test_file_guard_rejects_corrupt_image_with_valid_extension(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "broken.jpg"
            path.write_bytes(b"not-a-jpeg")
            with self.assertRaisesRegex(ValueError, "featured_image_decode_failed"):
                validate_featured_image_file(path)

    def test_local_validation_failure_performs_no_remote_io_or_retry(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "broken.jpg"
            path.write_bytes(b"not-a-jpeg")
            with patch("agents.featured_image.ROOT", Path(folder)), \
                 patch("agents.featured_image.run_wordpress") as remote, \
                 patch("agents.featured_image.acquire_featured_image_lock") as remote_lock:
                with self.assertRaisesRegex(ValueError, "featured_image_decode_failed") as raised:
                    replace_featured_image(
                        641,
                        path,
                        "a" * 64,
                        expected_thumbnail_id=70,
                        alt_text="대체텍스트",
                        confirmed=True,
                    )
            remote.assert_not_called()
            remote_lock.assert_not_called()
            receipt = json.loads(Path(raised.exception.failure_receipt).read_text(encoding="utf-8"))
            self.assertEqual("local_validation", receipt["stage"])
            self.assertFalse(receipt["import_attempted"])
            self.assertFalse(receipt["import_fence_started"])
            self.assertTrue(receipt["automatic_media_reimport_allowed"])

    def test_pipeline_budget_fails_before_starting_an_over_budget_stage(self):
        with patch("agents.featured_image.time.monotonic", side_effect=[100.0, 280.1]):
            budget = _FeaturedImageBudget(180)
            with self.assertRaisesRegex(TimeoutError, "featured_image_pipeline_budget_exhausted:remote_copy"):
                budget.timeout(30, "remote_copy")

    def test_replace_recovers_single_sha_match_after_media_import_ssh_loss_without_reimport(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            image_path = self._image(folder)
            image_sha = hashlib.sha256(image_path.read_bytes()).hexdigest()
            live = {
                "post_status": "draft", "post_title": "검토된 제목", "post_name": "slug",
                "post_content": "body", "post_excerpt": "요약",
            }
            attachment = {
                "ID": 777, "guid": "https://lifeinfo24.org/uploads/cover.jpg",
                "post_title": "검토된 제목", "post_mime_type": "image/jpeg",
            }
            content_sha = hashlib.sha256(b"body").hexdigest()
            media_import_calls = 0

            def run(args, **kwargs):
                nonlocal media_import_calls
                wp = _wp_args(args)
                if wp and wp[:2] == ["post", "get"]:
                    target = wp[2]
                    payload = attachment if target == "777" else live
                    return Mock(stdout=json.dumps(payload), stderr="", returncode=0)
                if wp and wp[:3] == ["post", "meta", "get"]:
                    if wp[3] == "777" and wp[4] == "_wp_attachment_image_alt":
                        return Mock(stdout="대체텍스트\n", stderr="", returncode=0)
                    if wp[4] == "_thumbnail_id":
                        return Mock(stdout="70\n", stderr="", returncode=0)
                if wp and wp[:2] == ["media", "import"]:
                    media_import_calls += 1
                    raise subprocess.CalledProcessError(255, args, output="", stderr="lost response")
                if wp and wp[0] == "eval":
                    payload = json.loads(kwargs["input"])
                    if "sha256" in payload:
                        self.assertEqual(image_sha, payload["sha256"])
                        return Mock(
                            stdout=json.dumps({"status": "ok", "attachment_ids": [777]}),
                            stderr="", returncode=0)
                    if "attachment_id" in payload and "expected" in payload:
                        return Mock(stdout=json.dumps({
                            "status": "ok", "saved": live, "thumbnail_id": "777",
                        }), stderr="", returncode=0)
                if args[:3] == ["sudo", "docker", "cp"]:
                    return Mock(stdout=b"", stderr=b"", returncode=0)
                if args[:5] == ["sudo", "docker", "exec", "wordpress_app", "sha256sum"]:
                    return Mock(stdout=f"{image_sha}  {args[5]}\n", stderr="", returncode=0)
                if args[:5] == ["sudo", "docker", "exec", "wordpress_app", "rm"]:
                    return Mock(stdout=b"", stderr=b"", returncode=0)
                raise AssertionError(args)

            with patch("agents.featured_image.ROOT", root), \
                 patch("agents.featured_image.acquire_editorial_lock", return_value=object()), \
                 patch("agents.featured_image.release_editorial_lock"), \
                 patch("agents.featured_image.acquire_featured_image_lock", return_value={"token": "lock-token-123456", "expires_at": 9999999999}), \
                 patch("agents.featured_image.release_featured_image_lock"), \
                 patch("agents.featured_image.set_featured_image_import_pending") as import_fence, \
                 patch("agents.featured_image.find_attachment_ids_by_sha", side_effect=[[], [777]]), \
                 patch("agents.featured_image.start_task_state"), \
                 patch("agents.featured_image.update_task_state") as update_state, \
                 patch("agents.featured_image.load_task_state", return_value=None), \
                 patch("agents.featured_image.fail_task_state"), \
                 patch("agents.featured_image.subprocess.run", side_effect=run):
                with self.assertRaisesRegex(ValueError, "featured_image_import_process_termination_unknown") as raised:
                    replace_featured_image(
                        641, image_path, content_sha, expected_thumbnail_id=70,
                        alt_text="대체텍스트", confirmed=True)

            self.assertEqual(1, media_import_calls)
            self.assertEqual([True], [c.kwargs["pending"] for c in import_fence.call_args_list])
            receipt = json.loads(Path(raised.exception.failure_receipt).read_text(encoding="utf-8"))
            self.assertEqual("media_import_process_unknown", receipt["stage"])
            self.assertEqual(777, receipt["attachment_id"])
            self.assertFalse(receipt["import_termination_confirmed"])
            self.assertEqual([777], receipt["reconcile_observed_ids"])
            self.assertFalse(receipt["automatic_media_reimport_allowed"])
            self.assertTrue(any(
                call.kwargs.get("checkpoints", {}).get("image_outcome", {}).get("verified") is True
                for call in update_state.call_args_list
            ))

    def test_import_sha_recovery_returns_none_for_zero_matches_and_blocks_multiple(self):
        from agents.featured_image import _find_unique_imported_attachment_by_sha
        with patch("agents.featured_image.find_attachment_ids_by_sha", return_value=[]):
            self.assertIsNone(_find_unique_imported_attachment_by_sha(641, image_sha256="a" * 64))
        with patch("agents.featured_image.find_attachment_ids_by_sha", return_value=[777, 778]):
            with self.assertRaisesRegex(ValueError, "featured_image_import_multiple_sha_matches"):
                _find_unique_imported_attachment_by_sha(641, image_sha256="a" * 64)

    def test_post_meta_read_accepts_utf8_bom(self):
        base = ["sudo", "docker", "exec", "wordpress_app", "wp"]
        with patch("agents.featured_image.subprocess.run", return_value=Mock(
                returncode=0, stdout="\ufeff650\r\n", stderr="")):
            self.assertEqual("650", _read_post_meta(base, 648, "_thumbnail_id"))

    def test_post_meta_read_treats_empty_exit_one_as_missing(self):
        base = ["sudo", "docker", "exec", "wordpress_app", "wp"]
        with patch("agents.featured_image.subprocess.run", return_value=Mock(
                returncode=1, stdout="", stderr="")):
            self.assertIsNone(_read_post_meta(base, 559, "_thumbnail_id"))

    def test_alt_only_preserves_published_post_and_current_thumbnail(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            live = {
                "post_status": "publish", "post_title": "검토된 제목", "post_name": "slug",
                "post_content": "body", "post_excerpt": "요약",
            }
            attachment = {
                "ID": 236, "guid": "https://lifeinfo24.org/uploads/cover.jpg",
                "post_title": "대표 이미지", "post_mime_type": "image/jpeg",
            }
            meta_values = ["236", None, "새 ALT", "236"]
            with patch("agents.featured_image.ROOT", root), \
                 patch("agents.featured_image.acquire_editorial_lock", return_value=object()), \
                 patch("agents.featured_image.release_editorial_lock"), \
                 patch("agents.featured_image.start_task_state") as start_state, \
                 patch("agents.featured_image.update_task_state"), \
                 patch("agents.featured_image.complete_task_state"), \
                 patch("agents.featured_image.fail_task_state"), \
                 patch("agents.featured_image.get_post", side_effect=[live, attachment]), \
                 patch("agents.featured_image._read_post_meta", side_effect=meta_values), \
                 patch("agents.featured_image.guarded_update_featured_image_alt", return_value={
                     "post": live, "thumbnail_id": "236", "attachment_id": 236,
                     "alt_text": "새 ALT",
                 }) as guarded:
                result = update_featured_image_alt_from_live_baseline(
                    235, alt_text="새 ALT", confirmed=True)
            self.assertEqual("publish", result["status"])
            self.assertEqual(236, result["attachment_id"])
            guarded.assert_called_once()
            self.assertIsNone(guarded.call_args.kwargs["expected_alt"])
            self.assertEqual("새 ALT", guarded.call_args.kwargs["alt_text"])
            self.assertEqual("image-metadata-only", start_state.call_args.kwargs["validation_plan"]["profile"])

    def test_replace_preserves_post_and_rank_math_and_verifies_alt(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            image_path = self._image(folder)
            live = {
                "post_status": "draft",
                "post_title": "검토된 제목",
                "post_name": "stable-slug",
                "post_content": "<p>검토된 본문</p>",
                "post_excerpt": "검토된 요약",
            }
            expected_sha = hashlib.sha256(live["post_content"].encode()).hexdigest()
            thumbnail = "642"
            rank = {
                "rank_math_focus_keyword": "키워드",
                "rank_math_title": "SEO 제목",
                "rank_math_description": "SEO 설명",
            }

            def run(args, **kwargs):
                nonlocal thumbnail
                wp = _wp_args(args)
                if wp and wp[:2] == ["post", "get"]:
                    if wp[2] == "777":
                        return Mock(stdout=json.dumps({
                            "ID": 777,
                            "guid": "https://lifeinfo24.org/wp-content/uploads/cover.jpg",
                            "post_title": live["post_title"],
                            "post_mime_type": "image/jpeg",
                        }), returncode=0)
                    return Mock(stdout=json.dumps(live), returncode=0)
                if wp and wp[:3] == ["post", "meta", "get"]:
                    post_id, key = wp[3], wp[4]
                    if post_id == "777" and key == "_wp_attachment_image_alt":
                        return Mock(stdout="대체텍스트\n", stderr="", returncode=0)
                    if key == "_thumbnail_id":
                        return Mock(stdout=thumbnail + "\n", stderr="", returncode=0)
                    return Mock(stdout=rank[key] + "\n", stderr="", returncode=0)
                if wp and wp[:2] == ["media", "import"]:
                    return Mock(stdout="\ufeff777\n", stderr="", returncode=0)
                if wp and wp[0] == "eval":
                    payload = json.loads(kwargs["input"])
                    thumbnail = str(payload["attachment_id"])
                    return Mock(stdout=json.dumps({
                        "status": "ok", "saved": live, "thumbnail_id": thumbnail,
                    }), stderr="", returncode=0)
                if args[:3] == ["sudo", "docker", "cp"]:
                    return Mock(stdout=b"", stderr=b"", returncode=0)
                if args[:5] == ["sudo", "docker", "exec", "wordpress_app", "sha256sum"]:
                    digest = hashlib.sha256(image_path.read_bytes()).hexdigest()
                    return Mock(stdout=f"{digest}  {args[5]}\n", stderr="", returncode=0)
                if args[:5] == ["sudo", "docker", "exec", "wordpress_app", "rm"]:
                    return Mock(stdout=b"", stderr=b"", returncode=0)
                raise AssertionError(args)

            with patch("agents.featured_image.ROOT", root), \
                 patch("agents.featured_image.acquire_featured_image_lock", return_value={"token": "lock-token-123456", "expires_at": 9999999999}), \
                 patch("agents.featured_image.release_featured_image_lock"), \
                 patch("agents.featured_image.set_featured_image_import_pending"), \
                 patch("agents.featured_image.find_attachment_ids_by_sha", return_value=[777]), \
                 patch("agents.featured_image.reviewed_binding_for_post", return_value={
                     "review_digest": "1" * 64,
                     "title_sha256": "2" * 64,
                     "expires_at_gmt": "2026-12-31T00:00:00Z",
                     "requires_live_state": False,
                 }) as reviewed_binding, \
                 patch("agents.featured_image.record_publish_attestation", return_value={
                     "version": 1, "thumbnail_id": 777,
                 }) as record_attestation, \
                 patch("agents.featured_image.start_task_state") as start_state, \
                 patch("agents.featured_image.update_task_state"), \
                 patch("agents.featured_image.fail_task_state"), \
                 patch("agents.featured_image.subprocess.run", side_effect=run):
                result = replace_featured_image(
                    641,
                    image_path,
                    expected_sha,
                    expected_thumbnail_id=642,
                    alt_text="대체텍스트",
                    confirmed=True,
                    approval_kind="manual_user_selected",
                    approval_evidence_sha256="3" * 64,
                )

            self.assertEqual(777, result["attachment_id"])
            self.assertEqual({"version": 1, "thumbnail_id": 777}, result["publish_attestation"])
            reviewed_binding.assert_called_once_with(641, expected_sha, "검토된 제목")
            self.assertEqual("manual_user_selected", record_attestation.call_args.kwargs["approval_kind"])
            self.assertEqual("3" * 64, record_attestation.call_args.kwargs["approval_evidence_sha256"])
            self.assertEqual("draft", result["status"])
            self.assertEqual("stable-slug", live["post_name"])
            self.assertEqual("<p>검토된 본문</p>", live["post_content"])
            self.assertEqual(1, len(list((root / "data" / "editorial_runs").glob("featured-image-edit-641-*.json"))))
            validation_plan = start_state.call_args.kwargs["validation_plan"]
            self.assertEqual("quick-image", validation_plan["profile"])
            self.assertEqual("image-only", validation_plan["binding"]["route"])

    def test_replace_blocks_when_remote_copy_hash_differs_from_validated_source(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            image_path = self._image(folder)
            live = {
                "post_status": "draft", "post_title": "제목", "post_name": "slug",
                "post_content": "body", "post_excerpt": "요약",
            }
            expected_sha = hashlib.sha256(b"body").hexdigest()

            def run(args, **kwargs):
                wp = _wp_args(args)
                if wp and wp[:2] == ["post", "get"]:
                    return Mock(stdout=json.dumps(live), returncode=0)
                if wp and wp[:3] == ["post", "meta", "get"] and wp[4] == "_thumbnail_id":
                    return Mock(stdout="70\n", stderr="", returncode=0)
                if args[:3] == ["sudo", "docker", "cp"]:
                    return Mock(stdout=b"", stderr=b"", returncode=0)
                if args[:5] == ["sudo", "docker", "exec", "wordpress_app", "sha256sum"]:
                    return Mock(stdout=f"{'0' * 64}  {args[5]}\n", stderr="", returncode=0)
                if args[:5] == ["sudo", "docker", "exec", "wordpress_app", "rm"]:
                    return Mock(stdout=b"", stderr=b"", returncode=0)
                raise AssertionError(args)

            with patch("agents.featured_image.ROOT", root), \
                 patch("agents.featured_image.acquire_featured_image_lock", return_value={"token": "lock-token-123456", "expires_at": 9999999999}), \
                 patch("agents.featured_image.release_featured_image_lock"), \
                 patch("agents.featured_image.subprocess.run", side_effect=run), \
                 patch("agents.featured_image.start_task_state"), \
                 patch("agents.featured_image.update_task_state"), \
                 patch("agents.featured_image.fail_task_state"):
                with self.assertRaisesRegex(ValueError, "featured_image_remote_hash_mismatch"):
                    replace_featured_image(
                        641, image_path, expected_sha, expected_thumbnail_id=70,
                        alt_text="대체텍스트", confirmed=True,
                    )

    def test_ambiguous_remote_copy_timeout_cleans_partial_temp_without_import(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            image_path = self._image(folder)
            image_info = validate_featured_image_file(image_path)
            live = {
                "post_status": "draft", "post_title": "제목", "post_name": "slug",
                "post_content": "body", "post_excerpt": "요약",
            }
            attempts = []

            def remote(args, **kwargs):
                attempts.append(args)
                if args[:3] == ["sudo", "docker", "cp"]:
                    raise subprocess.TimeoutExpired(args, kwargs.get("timeout", 30))
                if args[:5] == ["sudo", "docker", "exec", "wordpress_app", "rm"]:
                    return Mock(returncode=0)
                raise AssertionError(args)

            with patch("agents.featured_image.ROOT", root), \
                 patch("agents.featured_image.acquire_featured_image_lock", return_value={"token": "a" * 32}), \
                 patch("agents.featured_image.release_featured_image_lock") as release, \
                 patch("agents.featured_image.get_post", return_value=live), \
                 patch("agents.featured_image._read_post_meta", return_value="70"), \
                 patch("agents.featured_image.run_wordpress", side_effect=remote):
                with self.assertRaises(subprocess.TimeoutExpired) as raised:
                    hardened_attach_featured_image(
                        641, image_path, hashlib.sha256(b"body").hexdigest(),
                        expected_thumbnail_id=70, alt_text="대체텍스트", image_info=image_info,
                    )
            self.assertEqual(1, len([cmd for cmd in attempts if cmd[:3] == ["sudo", "docker", "cp"]]))
            self.assertEqual(1, len([cmd for cmd in attempts if cmd[:5] == ["sudo", "docker", "exec", "wordpress_app", "rm"]]))
            self.assertFalse(any("import" in cmd for cmd in attempts))
            release.assert_called_once()
            receipt = json.loads(Path(raised.exception.failure_receipt).read_text(encoding="utf-8"))
            self.assertEqual("remote_copy", receipt["stage"])
            self.assertEqual("completed", receipt["cleanup_status"])
            self.assertFalse(receipt["import_attempted"])

    def test_hardened_upload_timeout_reconciles_sha_once_without_reimport(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            image_path = self._image(folder)
            image_info = validate_featured_image_file(image_path)
            image_sha = image_info["sha256"]
            live = {
                "post_status": "draft", "post_title": "제목", "post_name": "slug",
                "post_content": "body", "post_excerpt": "요약",
            }
            attachment = {
                "ID": 777, "guid": "https://lifeinfo24.org/uploads/cover.jpg",
                "post_title": "제목", "post_mime_type": "image/jpeg",
            }
            import_calls = 0

            def run(args, **kwargs):
                nonlocal import_calls
                wp = _wp_args(args)
                if wp and wp[:2] == ["media", "import"]:
                    import_calls += 1
                    raise subprocess.TimeoutExpired(args, kwargs.get("timeout", 90))
                if args[:3] == ["sudo", "docker", "cp"]:
                    return Mock(returncode=0, stdout=b"", stderr=b"")
                if args[:5] == ["sudo", "docker", "exec", "wordpress_app", "sha256sum"]:
                    return Mock(returncode=0, stdout=f"{image_sha}  {args[5]}\n", stderr="")
                if args[:5] == ["sudo", "docker", "exec", "wordpress_app", "rm"]:
                    return Mock(returncode=0, stdout=b"", stderr=b"")
                raise AssertionError(args)

            with patch("agents.featured_image.ROOT", root), \
                 patch("agents.featured_image.acquire_featured_image_lock", return_value={"token": "a" * 32}), \
                 patch("agents.featured_image.release_featured_image_lock"), \
                 patch("agents.featured_image.set_featured_image_import_pending") as import_fence, \
                 patch("agents.featured_image.get_post", side_effect=[live, attachment]), \
                 patch("agents.featured_image._read_post_meta", side_effect=["70", "대체텍스트"]), \
                 patch("agents.featured_image.find_attachment_ids_by_sha", side_effect=[[], [777]]) as sha_lookup, \
                 patch("agents.featured_image.guarded_set_post_thumbnail", return_value={
                     "post": live, "thumbnail_id": "777",
                 }), \
                 patch("agents.featured_image.subprocess.run", side_effect=run):
                with self.assertRaisesRegex(ValueError, "featured_image_import_process_termination_unknown") as raised:
                    hardened_attach_featured_image(
                        641, image_path, hashlib.sha256(b"body").hexdigest(),
                        expected_thumbnail_id=70, alt_text="대체텍스트", image_info=image_info,
                    )

            self.assertEqual(1, import_calls)
            self.assertEqual(2, sha_lookup.call_count)
            self.assertEqual([True], [c.kwargs["pending"] for c in import_fence.call_args_list])
            receipt = json.loads(Path(raised.exception.failure_receipt).read_text(encoding="utf-8"))
            self.assertEqual("media_import_process_unknown", receipt["stage"])
            self.assertEqual(777, receipt["attachment_id"])
            self.assertTrue(receipt["sha_reconcile_attempted"])
            self.assertFalse(receipt["import_termination_confirmed"])
            self.assertFalse(receipt["automatic_media_reimport_allowed"])

    def test_timeout_sha_recovered_attachment_remains_fenced_on_resume_without_reimport(self):
        """An attachment SHA match does not prove a timed-out import has terminated."""
        live = {
            "post_status": "draft", "post_title": "제목", "post_name": "slug",
            "post_content": "body", "post_excerpt": "요약",
        }
        image_sha = hashlib.sha256(b"uploaded-image").hexdigest()
        content_sha = hashlib.sha256(b"body").hexdigest()
        with patch("agents.featured_image.find_attachment_ids_by_sha", return_value=[777]) as sha_lookup, \
             patch("agents.featured_image.get_post", return_value=live) as post_read, \
             patch("agents.featured_image.acquire_featured_image_lock") as acquire, \
             patch("agents.featured_image.set_featured_image_import_pending") as import_fence, \
             patch("agents.featured_image.guarded_set_post_thumbnail") as thumbnail, \
             patch("agents.featured_image.subprocess.run") as transport:
            with self.assertRaisesRegex(ValueError, "featured_image_import_process_termination_unknown"):
                recover_imported_featured_image_outcome(
                    641,
                    image_sha256=image_sha,
                    expected_content_sha256=content_sha,
                    expected_thumbnail_id=70,
                    alt_text="대체텍스트",
                    preexisting_attachment_ids=[],
                    lock_token="a" * 32,
                )
        sha_lookup.assert_called_once()
        post_read.assert_called_once()
        acquire.assert_not_called()
        import_fence.assert_not_called()  # Existing import_pending must not be cleared.
        thumbnail.assert_not_called()
        transport.assert_not_called()  # No second wp media import or other transport mutation.

    def test_hardened_upload_ambiguous_timeout_stops_and_writes_resumable_receipt(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            image_path = self._image(folder)
            image_info = validate_featured_image_file(image_path)
            image_sha = image_info["sha256"]
            original_path = root / "candidate-1.png"
            original_path.write_bytes(b"sealed-original")
            stage_receipt = image_path.with_suffix(image_path.suffix + ".stage.json")
            stage_receipt.write_text(json.dumps({
                "source_path": str(original_path.resolve()),
                "source_sha256": hashlib.sha256(original_path.read_bytes()).hexdigest(),
                "output_path": str(image_path.resolve()),
                "output_sha256": image_sha,
            }), encoding="utf-8")
            live = {
                "post_status": "draft", "post_title": "제목", "post_name": "slug",
                "post_content": "body", "post_excerpt": "요약",
            }
            import_calls = 0

            def run(args, **kwargs):
                nonlocal import_calls
                wp = _wp_args(args)
                if wp and wp[:2] == ["media", "import"]:
                    import_calls += 1
                    raise subprocess.TimeoutExpired(args, kwargs.get("timeout", 90))
                if args[:3] == ["sudo", "docker", "cp"]:
                    return Mock(returncode=0, stdout=b"", stderr=b"")
                if args[:5] == ["sudo", "docker", "exec", "wordpress_app", "sha256sum"]:
                    return Mock(returncode=0, stdout=f"{image_sha}  {args[5]}\n", stderr="")
                if args[:5] == ["sudo", "docker", "exec", "wordpress_app", "rm"]:
                    return Mock(returncode=0, stdout=b"", stderr=b"")
                raise AssertionError(args)

            with patch("agents.featured_image.ROOT", root), \
                 patch("agents.featured_image.acquire_featured_image_lock", return_value={"token": "a" * 32}), \
                 patch("agents.featured_image.release_featured_image_lock"), \
                 patch("agents.featured_image.set_featured_image_import_pending") as import_fence, \
                 patch("agents.featured_image.get_post", return_value=live), \
                 patch("agents.featured_image._read_post_meta", return_value="70"), \
                 patch("agents.featured_image.find_attachment_ids_by_sha", side_effect=[[], []]) as sha_lookup, \
                 patch("agents.featured_image.subprocess.run", side_effect=run):
                with self.assertRaisesRegex(ValueError, "featured_image_import_outcome_ambiguous") as raised:
                    hardened_attach_featured_image(
                        641, image_path, hashlib.sha256(b"body").hexdigest(),
                        expected_thumbnail_id=70, alt_text="대체텍스트", image_info=image_info,
                    )

            self.assertEqual(1, import_calls)
            self.assertEqual([True], [c.kwargs["pending"] for c in import_fence.call_args_list])
            self.assertEqual(2, sha_lookup.call_count)
            receipt_path = Path(getattr(raised.exception, "failure_receipt"))
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            self.assertEqual("media_import_sha_reconcile", receipt["stage"])
            self.assertTrue(receipt["import_attempted"])
            self.assertTrue(receipt["sha_reconcile_attempted"])
            self.assertFalse(receipt["resume"]["automatic_media_reimport_allowed"])
            self.assertEqual(image_sha, receipt["image"]["sha256"])
            self.assertEqual(str(image_path.resolve()), receipt["staged_image_path"])
            self.assertEqual(image_sha, receipt["image_sha256"])
            self.assertEqual(str(original_path.resolve()), receipt["original_image_path"])
            self.assertEqual(str(stage_receipt.resolve()), receipt["stage_receipt_path"])
            self.assertFalse(receipt["automatic_media_reimport_allowed"])
            self.assertEqual("completed", receipt["cleanup_status"])
            self.assertEqual("completed", receipt["lock_release_status"])

    def test_remote_post_lock_busy_stops_before_copy_or_import(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            image_path = self._image(folder)
            image_info = validate_featured_image_file(image_path)
            with patch("agents.featured_image.ROOT", root), \
                 patch("agents.featured_image.acquire_featured_image_lock", side_effect=ValueError(
                     "featured_image_remote_lock_busy")), \
                 patch("agents.featured_image.subprocess.run") as run:
                with self.assertRaisesRegex(ValueError, "featured_image_remote_lock_busy") as raised:
                    hardened_attach_featured_image(
                        641, image_path, "a" * 64,
                        expected_thumbnail_id=70, alt_text="대체텍스트", image_info=image_info,
                    )
            run.assert_not_called()
            receipt = json.loads(Path(raised.exception.failure_receipt).read_text(encoding="utf-8"))
            self.assertEqual("remote_lock_acquire", receipt["stage"])
            self.assertFalse(receipt["import_attempted"])

    def test_verified_mutation_is_not_downgraded_by_cleanup_or_release_warning(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            image_path = self._image(folder)
            image_info = validate_featured_image_file(image_path)
            image_sha = image_info["sha256"]
            live = {
                "post_status": "draft", "post_title": "제목", "post_name": "slug",
                "post_content": "body", "post_excerpt": "요약",
            }
            attachment = {
                "ID": 777, "guid": "https://lifeinfo24.org/uploads/cover.jpg",
                "post_title": "제목", "post_mime_type": "image/jpeg",
            }

            def run(args, **kwargs):
                wp = _wp_args(args)
                if wp and wp[:2] == ["media", "import"]:
                    return Mock(returncode=0, stdout="777\n", stderr="")
                if args[:3] == ["sudo", "docker", "cp"]:
                    return Mock(returncode=0, stdout=b"", stderr=b"")
                if args[:5] == ["sudo", "docker", "exec", "wordpress_app", "sha256sum"]:
                    return Mock(returncode=0, stdout=f"{image_sha}  {args[5]}\n", stderr="")
                if args[:5] == ["sudo", "docker", "exec", "wordpress_app", "rm"]:
                    return Mock(returncode=1, stdout=b"", stderr=b"cleanup failed")
                raise AssertionError(args)

            with patch("agents.featured_image.ROOT", root), \
                 patch("agents.featured_image.acquire_featured_image_lock", return_value={"token": "a" * 32}), \
                 patch("agents.featured_image.release_featured_image_lock", side_effect=ValueError("release failed")), \
                 patch("agents.featured_image.set_featured_image_import_pending") as import_fence, \
                 patch("agents.featured_image.get_post", side_effect=[live, attachment]), \
                 patch("agents.featured_image._read_post_meta", side_effect=["70", "대체텍스트"]), \
                 patch("agents.featured_image.find_attachment_ids_by_sha", side_effect=[[], [777]]), \
                 patch("agents.featured_image.guarded_set_post_thumbnail", return_value={
                     "post": live, "thumbnail_id": "777",
                 }), \
                 patch("agents.featured_image.subprocess.run", side_effect=run):
                result = hardened_attach_featured_image(
                    641, image_path, hashlib.sha256(b"body").hexdigest(),
                    expected_thumbnail_id=70, alt_text="대체텍스트", image_info=image_info,
                )

            warnings = result["pipeline"]["warnings"]
            self.assertEqual([True, False], [c.kwargs["pending"] for c in import_fence.call_args_list])
            self.assertTrue(any("cleanup_failed" in warning for warning in warnings))
            self.assertTrue(any("lock_release_failed" in warning for warning in warnings))
            self.assertEqual("expires_by_ttl", result["pipeline"]["remote_lock"])

    def test_thumbnail_cas_mismatch_blocks_before_import(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            image_path = self._image(folder)
            live = {
                "post_status": "draft", "post_title": "t", "post_name": "s",
                "post_content": "body", "post_excerpt": "e",
            }
            sha = hashlib.sha256(b"body").hexdigest()

            def run(args, **kwargs):
                wp = args[5:] if args[:5] == ["sudo", "docker", "exec", "wordpress_app", "wp"] else None
                if wp and wp[:2] == ["post", "get"]:
                    return Mock(stdout=json.dumps(live), returncode=0)
                if wp and wp[:3] == ["post", "meta", "get"] and wp[4] == "_thumbnail_id":
                    return Mock(stdout="999\n", stderr="", returncode=0)
                raise AssertionError(args)

            with patch("agents.featured_image.ROOT", root), \
                 patch("agents.featured_image.subprocess.run", side_effect=run):
                with self.assertRaisesRegex(ValueError, "featured_image_changed_before_replacement"):
                    replace_featured_image(
                        641, image_path, sha, expected_thumbnail_id=642,
                        alt_text="대체텍스트", confirmed=True,
                    )

    def test_resume_reconciles_checkpointed_attachment_without_reimport(self):
        live = {
            "post_status": "draft", "post_title": "제목", "post_name": "slug",
            "post_content": "body", "post_excerpt": "요약",
        }
        rank = {
            "rank_math_focus_keyword": "키워드",
            "rank_math_title": "SEO",
            "rank_math_description": "설명",
        }
        image_sha256 = hashlib.sha256(b"image").hexdigest()
        checkpoint = {
            "attachment_id": 777,
            "content_sha256": hashlib.sha256(b"body").hexdigest(),
            "image_sha256": image_sha256,
            "preserved_post": {
                "post_status": "draft", "post_title": "제목", "post_name": "slug",
                "post_excerpt": "요약",
            },
            "before_rank_math": rank,
            "backup": "backup.json",
        }

        def meta(base, post_id, key, **kwargs):
            if key == "_thumbnail_id":
                return "777"
            if post_id == 777 and key == "_wp_attachment_image_alt":
                return "대체텍스트"
            raise AssertionError((post_id, key))

        attachment = {
            "ID": 777, "guid": "https://lifeinfo24.org/uploads/cover.jpg",
            "post_title": "제목", "post_mime_type": "image/jpeg",
        }
        with patch("agents.featured_image._read_post_meta", side_effect=meta), \
             patch("agents.featured_image.acquire_featured_image_lock", return_value={"token": "a" * 32}), \
             patch("agents.featured_image.release_featured_image_lock"), \
             patch("agents.featured_image._rank_math_meta", return_value=rank), \
             patch("agents.featured_image.find_attachment_ids_by_sha", return_value=[777]), \
             patch("agents.featured_image.get_post", side_effect=[live, attachment]), \
             patch("agents.featured_image.guarded_set_post_thumbnail", return_value={
                 "post": live, "thumbnail_id": "777",
             }) as guarded:
            result = reconcile_featured_image_outcome(641, checkpoint, "대체텍스트")
        guarded.assert_called_once()
        self.assertTrue(result["reconciled"])
        self.assertEqual(777, result["attachment_id"])

    def test_resume_rejects_third_party_thumbnail_after_import_checkpoint(self):
        checkpoint = {"attachment_id": 777}
        with patch("agents.featured_image._read_post_meta", return_value="888"), \
             patch("agents.featured_image.acquire_featured_image_lock", return_value={"token": "a" * 32}), \
             patch("agents.featured_image.release_featured_image_lock"):
            with self.assertRaisesRegex(ValueError, "featured_image_resume_thumbnail_conflict"):
                reconcile_featured_image_outcome(641, checkpoint, "대체텍스트")

    def test_resume_applies_checkpointed_attachment_when_original_thumbnail_is_unchanged(self):
        live = {
            "post_status": "publish", "post_title": "제목", "post_name": "slug",
            "post_content": "body", "post_excerpt": "요약",
        }
        image_sha256 = hashlib.sha256(b"image").hexdigest()
        checkpoint = {
            "attachment_id": 777,
            "expected_thumbnail_id": 70,
            "content_sha256": hashlib.sha256(b"body").hexdigest(),
            "image_sha256": image_sha256,
            "preserved_post": {
                "post_status": "publish", "post_title": "제목", "post_name": "slug",
                "post_excerpt": "요약",
            },
            "backup": "backup.json",
        }
        attachment = {
            "ID": 777, "guid": "https://lifeinfo24.org/uploads/cover.jpg",
            "post_title": "제목", "post_mime_type": "image/jpeg",
        }

        def meta(base, post_id, key, **kwargs):
            if post_id == 641 and key == "_thumbnail_id":
                return "70"
            if post_id == 777 and key == "_wp_attachment_image_alt":
                return "대체텍스트"
            raise AssertionError((post_id, key))

        with patch("agents.featured_image._read_post_meta", side_effect=meta), \
             patch("agents.featured_image.acquire_featured_image_lock", return_value={"token": "a" * 32}), \
             patch("agents.featured_image.release_featured_image_lock"), \
             patch("agents.featured_image.find_attachment_ids_by_sha", return_value=[777]), \
             patch("agents.featured_image.get_post", side_effect=[live, attachment]), \
             patch("agents.featured_image.guarded_set_post_thumbnail", return_value={
                 "post": live, "thumbnail_id": "777",
             }) as guarded:
            result = reconcile_featured_image_outcome(641, checkpoint, "대체텍스트")
        guarded.assert_called_once_with(
            ["sudo", "docker", "exec", "wordpress_app", "wp"],
            641,
            expected={
                "post_status": "publish", "post_title": "제목", "post_name": "slug",
                "post_excerpt": "요약", "content_sha256": hashlib.sha256(b"body").hexdigest(),
            },
            expected_thumbnail_id=70,
            attachment_id=777,
            timeout=30.0,
        )
        self.assertTrue(result["reconciled"])
        self.assertEqual(777, result["attachment_id"])

    def test_quick_replace_reads_its_own_baseline_and_uses_image_only_mutator(self):
        with tempfile.TemporaryDirectory() as folder:
            image_path = self._image(folder)
            live = {
                "post_status": "draft", "post_title": "제목", "post_name": "slug",
                "post_content": "body", "post_excerpt": "요약",
            }
            expected_sha = hashlib.sha256(b"body").hexdigest()
            replacement = {
                "post_id": 641,
                "status": "draft",
                "attachment_id": 777,
                "attachment_url": "https://lifeinfo24.org/uploads/cover.jpg",
                "alt_text": "대체텍스트",
            }
            with patch("agents.featured_image.get_post", return_value=live), \
                 patch("agents.featured_image._read_post_meta", return_value="70"), \
                 patch("agents.featured_image.load_task_state", return_value=None), \
                 patch("agents.featured_image.replace_featured_image", return_value=replacement) as replace, \
                 patch("agents.featured_image.load_after_image_checkpoint", return_value=None):
                result = quick_replace_featured_image(
                    641, image_path, alt_text="대체텍스트", confirmed=True)
        replace.assert_called_once()
        args, kwargs = replace.call_args
        self.assertEqual((641, image_path.resolve(), expected_sha), args[:3])
        self.assertEqual(70, kwargs["expected_thumbnail_id"])
        self.assertEqual("replace-featured-image", kwargs["task_action"])
        self.assertEqual(1, kwargs["task_baseline_extra"]["attempt_number"])
        self.assertEqual(expected_sha, result["baseline_content_sha256"])
        self.assertEqual(70, result["replaced_thumbnail_id"])

    def test_quick_replace_can_set_first_featured_image_without_existing_thumbnail(self):
        with tempfile.TemporaryDirectory() as folder:
            image_path = self._image(folder)
            live = {
                "post_status": "draft", "post_title": "제목", "post_name": "slug",
                "post_content": "body", "post_excerpt": "요약",
            }
            expected_sha = hashlib.sha256(b"body").hexdigest()
            replacement = {
                "post_id": 559,
                "status": "draft",
                "attachment_id": 805,
                "attachment_url": "https://lifeinfo24.org/uploads/cover.jpg",
                "alt_text": "대체텍스트",
            }
            with patch("agents.featured_image.get_post", return_value=live), \
                 patch("agents.featured_image._read_post_meta", return_value=None), \
                 patch("agents.featured_image.load_task_state", return_value=None), \
                 patch("agents.featured_image.replace_featured_image", return_value=replacement) as replace, \
                 patch("agents.featured_image.load_after_image_checkpoint", return_value=None):
                result = quick_replace_featured_image(
                    559, image_path, alt_text="대체텍스트", confirmed=True)
        replace.assert_called_once()
        self.assertIsNone(replace.call_args.kwargs["expected_thumbnail_id"])
        self.assertIsNone(result["replaced_thumbnail_id"])
        self.assertEqual(expected_sha, result["baseline_content_sha256"])

    def test_first_featured_image_resume_preserves_none_original_thumbnail(self):
        with tempfile.TemporaryDirectory() as folder:
            image_path = self._image(folder)
            live = {
                "post_status": "draft", "post_title": "제목", "post_name": "slug",
                "post_content": "body", "post_excerpt": "요약",
            }
            expected_sha = hashlib.sha256(b"body").hexdigest()
            from agents.featured_image import _quick_attempt_key
            attempt_key = _quick_attempt_key(
                559, image_path.resolve(), "대체텍스트", expected_sha)
            previous = {
                "action": "replace-featured-image",
                "status": "failed",
                "baseline": {
                    "attempt_key": attempt_key,
                    "attempt_number": 1,
                    "thumbnail_id": None,
                },
                "checkpoints": {"image_outcome": {
                    "attachment_id": 805,
                    "image_sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
                }},
            }
            reconciled = {
                "post_id": 559, "status": "draft", "attachment_id": 805,
                "attachment_url": "https://lifeinfo24.org/uploads/cover.jpg",
                "alt_text": "대체텍스트", "reconciled": True,
            }
            with patch("agents.featured_image.get_post", return_value=live), \
                 patch("agents.featured_image._read_post_meta", return_value=None), \
                 patch("agents.featured_image.load_task_state", return_value=previous), \
                 patch("agents.featured_image.reconcile_featured_image_outcome", return_value=reconciled), \
                 patch("agents.featured_image.update_task_state"), \
                 patch("agents.featured_image._advance_matching_after_image_checkpoint") as advance:
                result = quick_replace_featured_image(
                    559, image_path, alt_text="대체텍스트", confirmed=True)
        self.assertEqual(805, result["attachment_id"])
        self.assertIsNone(advance.call_args.kwargs["expected_thumbnail_id"])

    def test_quick_replace_blocks_third_identical_attempt(self):
        with tempfile.TemporaryDirectory() as folder:
            image_path = self._image(folder)
            live = {
                "post_status": "draft", "post_title": "제목", "post_name": "slug",
                "post_content": "body", "post_excerpt": "요약",
            }
            from agents.featured_image import _quick_attempt_key
            attempt_key = _quick_attempt_key(
                641, image_path.resolve(), "대체텍스트", hashlib.sha256(b"body").hexdigest())
            failed = {
                "action": "quick-image-replace",
                "status": "failed",
                "baseline": {"attempt_key": attempt_key, "attempt_number": 2, "thumbnail_id": "70"},
                "checkpoints": {},
            }
            with patch("agents.featured_image.get_post", return_value=live), \
                 patch("agents.featured_image._read_post_meta", return_value="70"), \
                 patch("agents.featured_image.load_task_state", return_value=failed):
                with self.assertRaisesRegex(ValueError, "simple_task_retry_budget_exhausted"):
                    quick_replace_featured_image(
                        641, image_path, alt_text="대체텍스트", confirmed=True)

    def test_quick_replace_does_not_reimport_after_ambiguous_media_attempt(self):
        with tempfile.TemporaryDirectory() as folder:
            image_path = self._image(folder)
            live = {
                "post_status": "draft", "post_title": "제목", "post_name": "slug",
                "post_content": "body", "post_excerpt": "요약",
            }
            from agents.featured_image import _quick_attempt_key
            attempt_key = _quick_attempt_key(
                641, image_path.resolve(), "대체텍스트", hashlib.sha256(b"body").hexdigest())
            failed = {
                "action": "quick-image-replace",
                "status": "failed",
                "baseline": {"attempt_key": attempt_key, "attempt_number": 1, "thumbnail_id": "70"},
                "checkpoints": {"image_import_attempt": {"started": True}},
            }
            with patch("agents.featured_image.get_post", return_value=live), \
                 patch("agents.featured_image._read_post_meta", return_value="70"), \
                 patch("agents.featured_image.load_task_state", return_value=failed), \
                 patch("agents.featured_image.replace_featured_image") as replace:
                with self.assertRaisesRegex(ValueError, "featured_image_import_outcome_ambiguous"):
                    quick_replace_featured_image(
                        641, image_path, alt_text="대체텍스트", confirmed=True)
        replace.assert_not_called()

    def test_quick_replace_recovers_ambiguous_import_by_exact_sha_without_reimport(self):
        with tempfile.TemporaryDirectory() as folder:
            image_path = self._image(folder)
            live = {
                "post_status": "draft", "post_title": "제목", "post_name": "slug",
                "post_content": "body", "post_excerpt": "요약",
            }
            expected_content_sha = hashlib.sha256(b"body").hexdigest()
            image_sha = hashlib.sha256(image_path.read_bytes()).hexdigest()
            from agents.featured_image import _quick_attempt_key
            attempt_key = _quick_attempt_key(
                641, image_path.resolve(), "대체텍스트", expected_content_sha)
            failed = {
                "action": "replace-featured-image",
                "status": "failed",
                "baseline": {"attempt_key": attempt_key, "attempt_number": 1, "thumbnail_id": "70"},
                "checkpoints": {"image_import_attempt": {
                    "started": True,
                    "image_sha256": image_sha,
                    "expected_thumbnail_id": 70,
                }},
            }
            recovered = {
                "post_id": 641,
                "status": "draft",
                "attachment_id": 777,
                "attachment_url": "https://lifeinfo24.org/uploads/cover.jpg",
                "alt_text": "대체텍스트",
                "reconciled": True,
            }
            with patch("agents.featured_image.get_post", return_value=live), \
                 patch("agents.featured_image._read_post_meta", return_value="70"), \
                 patch("agents.featured_image.load_task_state", return_value=failed), \
                 patch("agents.featured_image._find_unique_imported_attachment_by_sha", return_value=777), \
                 patch("agents.featured_image.reconcile_featured_image_outcome", return_value=recovered), \
                 patch("agents.featured_image.update_task_state") as update_state, \
                 patch("agents.featured_image.load_after_image_checkpoint", return_value=None), \
                 patch("agents.featured_image.replace_featured_image") as replace:
                result = quick_replace_featured_image(
                    641, image_path, alt_text="대체텍스트", confirmed=True)
        replace.assert_not_called()
        update_state.assert_called_once()
        self.assertEqual(777, result["attachment_id"])
        self.assertEqual(1, result["attempt_number"])


if __name__ == "__main__":
    unittest.main()
