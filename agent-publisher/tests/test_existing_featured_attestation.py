import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import editorial_cli

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
            patch.object(featured_image, "read_post_thumbnail_snapshot",
                         side_effect=lambda base, post_id: (self.original.copy(), "608")),
        ]
        self.mocks = [p.start() for p in self.patches]
        self.addCleanup(lambda: [p.stop() for p in reversed(self.patches)])

    def run_attestation(self, **kwargs):
        return featured_image.attest_current_featured_image(
            592, "C:/tmp/current-cover.jpg", self.sha, 608,
            alt_text="카드포인트 통합조회, 남은 포인트 계좌입금 안내",
            approval_evidence_sha256="d" * 64, confirmed=True, **kwargs)

    def test_existing_image_produces_gate_only_without_reimport_or_change(self):
        # Integrity check cannot issue automated_visual_review for an existing
        # cover without a separately authenticated human/reviewer event.
        with self.assertRaisesRegex(ValueError, 'independent_visual_approval_required'):
            self.run_attestation()
        self.mocks[6].assert_not_called()
        self.assertFalse((self.root / "data" / ".editorial-publish.lock").exists())
        self.mocks[8].assert_not_called()

    def test_cli_existing_image_integrity_cannot_self_issue_visual_review_attestation(self):
        import sys
        argv = ['editorial_cli.py', 'replace-featured-image',
                '--post-id', '592', '--attest-existing',
                '--image-path', 'C:/tmp/current-cover.jpg',
                '--alt-text', '기존 이미지 검증', '--confirm-update',
                '--expected-thumbnail-id', '608',
                '--expected-content-sha256', self.sha]
        with (patch.object(sys, 'argv', argv),
              patch.object(featured_image, 'attest_current_featured_image') as attestation,
              patch.object(featured_image, 'record_publish_attestation') as writer):
            with self.assertRaisesRegex(ValueError, 'independent_visual_approval_required'):
                editorial_cli._main()
            attestation.assert_not_called()
            writer.assert_not_called()

    def test_stale_body_refuses_gate(self):
        with patch.object(featured_image, "record_publish_attestation") as record:
            with self.assertRaisesRegex(ValueError, "independent_visual_approval_required"):
                featured_image.attest_current_featured_image(
                    592, "C:/tmp/current-cover.jpg", "e" * 64, 608,
                    alt_text="카드포인트 통합조회, 남은 포인트 계좌입금 안내",
                    approval_evidence_sha256="d" * 64, confirmed=True)
            record.assert_not_called()

    def test_stale_thumbnail_refuses_gate(self):
        with patch.object(featured_image, "record_publish_attestation") as record:
            with self.assertRaisesRegex(ValueError, "independent_visual_approval_required"):
                featured_image.attest_current_featured_image(
                    592, "C:/tmp/current-cover.jpg", self.sha, 609,
                    alt_text="카드포인트 통합조회, 남은 포인트 계좌입금 안내",
                    approval_evidence_sha256="d" * 64, confirmed=True)
            record.assert_not_called()

    def test_remote_sha_mismatch_fails_closed(self):
        with patch.object(featured_image, "record_publish_attestation",
                          side_effect=ValueError("publish_attestation_write_failed:binding_mismatch")):
            with self.assertRaisesRegex(ValueError, "independent_visual_approval_required"):
                self.run_attestation()

    def test_untrusted_attestation_does_not_read_or_write_even_if_server_could_drift(self):
        for changed in [({**self.original, 'post_title': 'changed'}, '608'),
                        (self.original, '999')]:
            with self.subTest(changed=changed):
                observed = iter([(self.original.copy(), '608'), changed])
                with patch.object(featured_image, 'read_post_thumbnail_snapshot',
                                  side_effect=lambda *a: next(observed)) as snapshot:
                    with self.assertRaisesRegex(ValueError, 'independent_visual_approval_required'):
                        self.run_attestation()
                snapshot.assert_not_called()
                self.mocks[6].assert_not_called()


if __name__ == "__main__":
    unittest.main()
