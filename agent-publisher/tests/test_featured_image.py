import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from PIL import Image

from agents.featured_image import (
    _read_post_meta,
    quick_replace_featured_image,
    reconcile_featured_image_outcome,
    replace_featured_image,
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

    def test_file_guard_requires_policy_canvas(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "wrong.jpg"
            Image.new("RGB", (800, 450)).save(path, "JPEG")
            with self.assertRaisesRegex(ValueError, "featured_image_canvas_mismatch"):
                validate_featured_image_file(path)

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
                if args[:5] == ["sudo", "docker", "exec", "wordpress_app", "rm"]:
                    return Mock(stdout=b"", stderr=b"", returncode=0)
                raise AssertionError(args)

            with patch("agents.featured_image.ROOT", root), \
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
                )

            self.assertEqual(777, result["attachment_id"])
            self.assertEqual("draft", result["status"])
            self.assertEqual("stable-slug", live["post_name"])
            self.assertEqual("<p>검토된 본문</p>", live["post_content"])
            self.assertEqual(1, len(list((root / "data" / "editorial_runs").glob("featured-image-edit-641-*.json"))))
            validation_plan = start_state.call_args.kwargs["validation_plan"]
            self.assertEqual("quick-image", validation_plan["profile"])
            self.assertEqual("image-only", validation_plan["binding"]["route"])

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
        checkpoint = {
            "attachment_id": 777,
            "content_sha256": hashlib.sha256(b"body").hexdigest(),
            "preserved_post": {
                "post_status": "draft", "post_title": "제목", "post_name": "slug",
                "post_excerpt": "요약",
            },
            "before_rank_math": rank,
            "backup": "backup.json",
        }

        def meta(base, post_id, key):
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
             patch("agents.featured_image._rank_math_meta", return_value=rank), \
             patch("agents.featured_image.get_post", side_effect=[live, attachment]):
            result = reconcile_featured_image_outcome(641, checkpoint, "대체텍스트")
        self.assertTrue(result["reconciled"])
        self.assertEqual(777, result["attachment_id"])

    def test_resume_rejects_third_party_thumbnail_after_import_checkpoint(self):
        checkpoint = {"attachment_id": 777}
        with patch("agents.featured_image._read_post_meta", return_value="888"):
            with self.assertRaisesRegex(ValueError, "featured_image_resume_thumbnail_conflict"):
                reconcile_featured_image_outcome(641, checkpoint, "대체텍스트")

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


if __name__ == "__main__":
    unittest.main()
