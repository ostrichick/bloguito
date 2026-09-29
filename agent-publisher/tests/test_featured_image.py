import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from PIL import Image

from agents.featured_image import replace_featured_image, validate_featured_image_file


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
                wp = args[5:] if args[:5] == ["sudo", "docker", "exec", "wordpress_app", "wp"] else None
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
                    thumbnail = "777"
                    return Mock(stdout="777\n", stderr="", returncode=0)
                if args[:3] == ["sudo", "docker", "cp"]:
                    return Mock(stdout=b"", stderr=b"", returncode=0)
                if args[:5] == ["sudo", "docker", "exec", "wordpress_app", "rm"]:
                    return Mock(stdout=b"", stderr=b"", returncode=0)
                raise AssertionError(args)

            with patch("agents.featured_image.ROOT", root), \
                 patch("agents.featured_image.start_task_state"), \
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


if __name__ == "__main__":
    unittest.main()
