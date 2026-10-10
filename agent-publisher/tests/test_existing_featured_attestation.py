import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agents import featured_image


class ExistingFeaturedAttestationTests(unittest.TestCase):
    def setUp(self):
        self.original = {
            "post_status": "draft",
            "post_title": "Reviewed title",
            "post_name": "",
            "post_content": "<p>Reviewed body</p>",
            "post_excerpt": "Summary",
        }
        self.sha = featured_image.content_sha256(self.original["post_content"])
        self.image_info = {
            "path": "C:/tmp/current-cover.jpg",
            "width": 1200,
            "height": 675,
            "format": "JPEG",
            "sha256": "a" * 64,
        }
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        self.root = Path(self._dir.name)
        self.patches = [
            patch.object(featured_image, "ROOT", self.root),
            patch.object(featured_image, "validate_featured_image_file", return_value=self.image_info),
            patch.object(featured_image, "get_post", side_effect=lambda base, id, **kw:
                         self.original if id == 592 else
                         {"ID": 608, "guid": "https://example.org/cover.jpg",
                          "post_title": "Current cover", "post_mime_type": "image/jpeg"}),
            patch.object(featured_image, "_read_post_meta", side_effect=lambda base, id, key:
                         "608" if key == "_thumbnail_id" else
                         "카드포인트 통합조회, 남은 포인트 계좌입금 안내"),
            patch.object(featured_image, "reviewed_binding_for_post", return_value={
                "review_digest": "b" * 64, "title_sha256": "c" * 64,
                "expires_at_gmt": "2026-10-11T12:00:00Z", "requires_live_state": True,
            }),
            patch.object(featured_image, "backup_json", return_value=self.root / "original.json"),
            patch.object(featured_image, "record_publish_attestation",
                         return_value={"version":1, "thumbnail_id":608}),
            patch("agents.publish_gate.validate_publish_attestation",
                  return_value={"version":1, "thumbnail_id":608}),
        ]
        self.mocks = [p.start() for p in self.patches]
        self.addCleanup(lambda: [p.stop() for p in reversed(self.patches)])

    def run_attestation(self, **kwargs):
        return featured_image.attest_current_featured_image(
            592, "C:/tmp/current-cover.jpg", self.sha, 608,
            alt_text="카드포인트 통합조회, 남은 포인트 계좌입금 안내",
            approval_evidence_sha256="d" * 64, confirmed=True, **kwargs)

    def test_existing_image_produces_gate_only_without_reimport_or_change(self):
        from agents.post_manifest_store import acquire_editorial_lock
        result = self.run_attestation()
        self.assertTrue(result["readback_verified"])
        self.assertTrue(result["image_unchanged"])
        self.assertEqual(608, result["thumbnail_id"])
        record = self.mocks[6]
        self.assertEqual("automated_visual_review", record.call_args.kwargs["approval_kind"])
        self.assertEqual(self.sha, record.call_args.kwargs["content_sha256"])
        self.assertFalse((self.root / "data" / ".editorial-publish.lock").exists())

    def test_stale_body_refuses_gate(self):
        with patch.object(featured_image, "record_publish_attestation") as record:
            with self.assertRaisesRegex(ValueError, "post_baseline_mismatch"):
                featured_image.attest_current_featured_image(
                    592, "C:/tmp/current-cover.jpg", "e" * 64, 608,
                    alt_text="카드포인트 통합조회, 남은 포인트 계좌입금 안내",
                    approval_evidence_sha256="d" * 64, confirmed=True)
            record.assert_not_called()

    def test_stale_thumbnail_refuses_gate(self):
        with patch.object(featured_image, "record_publish_attestation") as record:
            with self.assertRaisesRegex(ValueError, "thumbnail_changed"):
                featured_image.attest_current_featured_image(
                    592, "C:/tmp/current-cover.jpg", self.sha, 609,
                    alt_text="카드포인트 통합조회, 남은 포인트 계좌입금 안내",
                    approval_evidence_sha256="d" * 64, confirmed=True)
            record.assert_not_called()

    def test_remote_sha_mismatch_fails_closed(self):
        with patch.object(featured_image, "record_publish_attestation",
                          side_effect=ValueError("publish_attestation_write_failed:binding_mismatch")):
            with self.assertRaisesRegex(ValueError, "binding_mismatch"):
                self.run_attestation()


if __name__ == "__main__":
    unittest.main()
