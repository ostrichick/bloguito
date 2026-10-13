import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import editorial_cli
from agents.image_generation_policy import new_image_generation_task
from test_editorial_system import sample


READY = {"status": "ready", "reasons": [], "details": []}


class PrepareDraftFastPathTests(unittest.TestCase):
    def test_prepare_draft_rejects_self_issued_image_task_without_trusted_registration(self):
        bundle = sample()
        expected_review = bundle.pop("review")

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            bundle_path = root / "bundle.json"
            image_path = root / "cover.jpg"
            receipt_path = root / "receipt.json"
            visual_review_path = root / "visual-review.json"
            image_task_record_path = root / "image-task-record.json"
            image_task_id = "prepare-draft-fast-path-fixture"
            bundle_path.write_text(json.dumps(bundle, ensure_ascii=False), encoding="utf-8")
            image_path.write_bytes(b"reviewed-image")
            image_task = new_image_generation_task(
                brief_id=bundle["brief"]["id"], task_id=image_task_id,
                candidate_count=1, selection_mode="user",
            )
            image_task_record_path.write_text(
                json.dumps(image_task, ensure_ascii=False), encoding="utf-8")

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
                "--visual-review-receipt", str(visual_review_path),
                "--image-task-id", image_task_id,
                "--image-task-record", str(image_task_record_path),
                "--output",
                str(receipt_path),
            ]
            with patch("sys.argv", argv), \
                    patch("editorial_cli.validate_bundle", return_value=READY) as validate, \
                    patch("editorial_cli.load_inventory") as load_inventory, \
                    patch("editorial_cli.EditorialWriterAgent.review", return_value=expected_review) as review, \
                    patch("agents.featured_image.verify_manual_image_upload_lineage", return_value={
                        "candidate_number": 1, "selection_mode": "user",
                        "selection_actor": "user",
                        "source_sha256": "a" * 64,
                        "staged_sha256": "b" * 64,
                    }) as lineage, \
                    patch("agents.featured_image_quality_gate.require_accepted_quality_review", return_value={
                        "review_result": "pass", "task_id": image_task_id,
                        "review_actor": "user", "review_method": "human_visual",
                    }) as quality_review, \
                    patch("agents.designer.cleanup_generated_cover") as cleanup, \
                    patch("agents.publisher.PublisherAgent.publish", return_value=901) as publish, \
                    patch("agents.featured_image.replace_featured_image_from_live_baseline", return_value={
                        "post_id": 901,
                        "attachment_id": 777,
                        "publish_attestation": {"version": 1},
                    }) as replace:
                with self.assertRaisesRegex(ValueError, "prepare_draft_image_trusted_task_registration_unavailable"):
                    editorial_cli.main()

        load_inventory.assert_not_called()
        review.assert_not_called()
        publish.assert_not_called()
        replace.assert_not_called()
        lineage.assert_called_once()
        quality_review.assert_not_called()
        cleanup.assert_not_called()
        validate.assert_not_called()

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

    def test_image_bearing_draft_without_trusted_task_registration_never_creates_draft(self):
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
                        "candidate_number": 1, "selection_mode": "user",
                        "selection_actor": "user", "source_sha256": "a" * 64,
                    }), \
                    patch("agents.publisher.PublisherAgent.publish", return_value=903) as publish, \
                    patch("agents.featured_image.replace_featured_image_from_live_baseline",
                          side_effect=RuntimeError("remote import pending")) as replace:
                with self.assertRaises(SystemExit) as blocked:
                    editorial_cli.main()
            self.assertEqual(2, blocked.exception.code)
            self.assertFalse(receipt_path.exists())
            publish.assert_not_called()
            replace.assert_not_called()

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
