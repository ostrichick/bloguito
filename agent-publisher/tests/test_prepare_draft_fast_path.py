import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import editorial_cli
from test_editorial_system import sample


READY = {"status": "ready", "reasons": [], "details": []}


class PrepareDraftFastPathTests(unittest.TestCase):
    def test_prepare_draft_delegated_choice_is_not_recorded_as_user_selected(self):
        bundle = sample()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            bundle_path = root / "bundle.json"
            image_path = root / "cover.webp"
            bundle_path.write_text(json.dumps(bundle, ensure_ascii=False), encoding="utf-8")
            image_path.write_bytes(b"verified-cover")
            argv = [
                "editorial_cli.py", "prepare-draft", str(bundle_path),
                "--image-path", str(image_path), "--alt-text", "복지 이미지",
                "--confirm-image-selection", "--candidate-manifest", str(root / "manifest.json"),
                "--selected-candidate", "1", "--selection-mode", "agent-delegated",
            ]
            with patch("sys.argv", argv), \
                    patch("editorial_cli.validate_bundle", return_value=READY), \
                    patch("agents.featured_image.verify_manual_image_upload_lineage", return_value={
                        "candidate_number": 1, "selection_mode": "agent-delegated",
                        "source_sha256": "a" * 64,
                    }), \
                    patch("agents.publisher.PublisherAgent.publish", return_value=903), \
                    patch("agents.featured_image.replace_featured_image_from_live_baseline",
                          return_value={"post_id": 903, "attachment_id": 904}) as replace:
                editorial_cli.main()
            self.assertEqual("manual_agent_delegated",
                             replace.call_args.kwargs["approval_kind"])

    def test_replace_featured_image_cli_passes_pinned_initial_baseline(self):
        with tempfile.TemporaryDirectory() as folder:
            image = Path(folder) / "selected.webp"
            image.write_bytes(b"candidate-bytes")
            fingerprint = "b" * 64
            argv = [
                "editorial_cli.py", "replace-featured-image", "--post-id", "641",
                "--image-path", str(image), "--candidate-manifest", str(Path(folder) / "manifest.json"),
                "--selected-candidate", "1", "--selection-mode", "agent-delegated",
                "--alt-text", "Reviewed ALT", "--confirm-update", "--confirm-image-selection",
                "--expected-initial-image-baseline-sha256", fingerprint,
            ]
            with patch("sys.argv", argv), \
                 patch("agents.featured_image.verify_manual_image_upload_lineage", return_value={
                     "candidate_number": 1, "selection_mode": "agent-delegated",
                     "source_sha256": "a" * 64,
                 }), \
                 patch("agents.featured_image.replace_featured_image_from_live_baseline", return_value={
                     "post_id": 641, "attachment_id": 777,
                 }) as replace:
                editorial_cli.main()
        self.assertEqual(fingerprint, replace.call_args.kwargs["expected_initial_baseline_sha256"])

    def test_replace_featured_image_cli_rejects_pinned_baseline_for_alt_only(self):
        argv = ["editorial_cli.py", "replace-featured-image", "--post-id", "641",
                "--alt-only", "--alt-text", "Reviewed ALT", "--confirm-update",
                "--expected-initial-image-baseline-sha256", "b" * 64]
        with patch("sys.argv", argv), \
             patch("agents.featured_image.update_featured_image_alt_from_live_baseline") as alt:
            with self.assertRaises(SystemExit):
                editorial_cli.main()
        alt.assert_not_called()

    def test_prepare_draft_reviews_once_without_cli_inventory_and_uses_provided_image(self):
        bundle = sample()
        expected_review = bundle.pop("review")

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            bundle_path = root / "bundle.json"
            image_path = root / "cover.jpg"
            receipt_path = root / "receipt.json"
            bundle_path.write_text(json.dumps(bundle, ensure_ascii=False), encoding="utf-8")
            image_path.write_bytes(b"reviewed-image")

            argv = [
                "editorial_cli.py",
                "prepare-draft",
                str(bundle_path),
                "--author-model",
                "GPT-5.6 Sol",
                "--image-path",
                str(image_path),
                "--alt-text",
                "선풍기 배출 안내 대표 이미지",
                "--confirm-image-selection",
                "--candidate-manifest", str(root / "candidate-manifest.json"),
                "--selected-candidate", "1",
                "--selection-mode", "user",
                "--output",
                str(receipt_path),
            ]
            with patch("sys.argv", argv), \
                    patch("editorial_cli.validate_bundle", return_value=READY) as validate, \
                    patch("editorial_cli.load_inventory") as load_inventory, \
                    patch("editorial_cli.EditorialWriterAgent.review", return_value=expected_review) as review, \
                    patch("agents.featured_image.verify_manual_image_upload_lineage", return_value={
                        "candidate_number": 1, "selection_mode": "user",
                        "source_sha256": "a" * 64,
                    }) as lineage, \
                    patch("agents.designer.cleanup_generated_cover") as cleanup, \
                    patch("agents.publisher.PublisherAgent.publish", return_value=901) as publish, \
                    patch("agents.featured_image.replace_featured_image_from_live_baseline", return_value={
                        "post_id": 901,
                        "attachment_id": 777,
                        "publish_attestation": {"version": 1},
                    }) as replace:
                editorial_cli.main()

            saved = json.loads(bundle_path.read_text(encoding="utf-8"))
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            self.assertTrue(image_path.exists())

        load_inventory.assert_not_called()
        review.assert_called_once()
        publish.assert_called_once()
        self.assertNotIn("image_path", publish.call_args.kwargs)
        replace.assert_called_once()
        lineage.assert_called_once()
        self.assertEqual(901, replace.call_args.args[0])
        self.assertEqual(image_path, replace.call_args.args[1])
        self.assertEqual("manual_user_selected", replace.call_args.kwargs["approval_kind"])
        self.assertEqual("GPT-5.6 Sol", saved["authoring"]["model"])
        self.assertEqual(expected_review, saved["review"])
        self.assertEqual(901, receipt["post_id"])
        self.assertEqual("draft", receipt["status"])
        self.assertEqual("created", receipt["semantic_review"])
        self.assertTrue(receipt["featured_image_attached"])
        self.assertEqual({"version": 1}, receipt["publish_attestation"])
        cleanup.assert_not_called()
        self.assertGreaterEqual(validate.call_count, 2)

    def test_prepare_draft_reuses_current_review_and_allows_image_to_be_deferred(self):
        bundle = sample()

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            bundle_path = root / "bundle.json"
            bundle_path.write_text(json.dumps(bundle, ensure_ascii=False), encoding="utf-8")

            argv = ["editorial_cli.py", "prepare-draft", str(bundle_path)]
            with patch("sys.argv", argv), \
                    patch("editorial_cli.validate_bundle", return_value=READY), \
                    patch("editorial_cli.EditorialWriterAgent.review") as review, \
                    patch("agents.designer.DesignerAgent.generate_image") as generate, \
                    patch("agents.publisher.PublisherAgent.publish", return_value=902) as publish:
                editorial_cli.main()

        review.assert_not_called()
        generate.assert_not_called()
        publish.assert_called_once()

    def test_failed_image_upload_keeps_committed_draft_id_receipt(self):
        bundle = sample()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            bundle_path = root / "bundle.json"
            image_path = root / "cover.jpg"
            receipt_path = root / "receipt.json"
            bundle_path.write_text(json.dumps(bundle, ensure_ascii=False), encoding="utf-8")
            image_path.write_bytes(b"sealed-test")
            argv = [
                "editorial_cli.py", "prepare-draft", str(bundle_path),
                "--image-path", str(image_path), "--alt-text", "안내 이미지",
                "--confirm-image-selection", "--candidate-manifest", str(root / "manifest.json"),
                "--selected-candidate", "1", "--selection-mode", "user",
                "--output", str(receipt_path),
            ]
            with patch("sys.argv", argv), \
                    patch("editorial_cli.validate_bundle", return_value=READY), \
                    patch("agents.featured_image.verify_manual_image_upload_lineage", return_value={
                        "candidate_number": 1, "selection_mode": "user", "source_sha256": "a" * 64,
                    }), \
                    patch("agents.publisher.PublisherAgent.publish", return_value=903) as publish, \
                    patch("agents.featured_image.replace_featured_image_from_live_baseline",
                          side_effect=RuntimeError("remote import pending")):
                with self.assertRaisesRegex(RuntimeError, "remote import pending"):
                    editorial_cli.main()
            pending = json.loads(receipt_path.read_text(encoding="utf-8"))
            self.assertEqual(903, pending["post_id"])
            self.assertEqual("draft_saved_pending_image", pending["completion"])
            self.assertFalse(pending["featured_image_attached"])
            publish.assert_called_once()

    def test_prepare_draft_blocks_before_review_image_or_wordpress_when_local_preflight_fails(self):
        bundle = sample()
        bundle.pop("review")
        blocked = {"status": "needs_review", "reasons": ["number_without_evidence"], "details": []}

        with tempfile.TemporaryDirectory() as folder:
            bundle_path = Path(folder) / "bundle.json"
            bundle_path.write_text(json.dumps(bundle, ensure_ascii=False), encoding="utf-8")
            argv = [
                "editorial_cli.py",
                "prepare-draft",
                str(bundle_path),
                "--author-model",
                "GPT-5.6 Sol",
            ]
            with patch("sys.argv", argv), \
                    patch("editorial_cli.validate_bundle", return_value=blocked), \
                    patch("editorial_cli.EditorialWriterAgent.review") as review, \
                    patch("agents.designer.DesignerAgent.generate_image") as generate, \
                    patch("agents.publisher.PublisherAgent.publish") as publish:
                with self.assertRaises(SystemExit) as error:
                    editorial_cli.main()

        self.assertEqual(2, error.exception.code)
        review.assert_not_called()
        generate.assert_not_called()
        publish.assert_not_called()


if __name__ == "__main__":
    unittest.main()
