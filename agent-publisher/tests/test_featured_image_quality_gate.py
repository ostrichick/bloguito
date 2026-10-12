import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from agents.featured_image_quality_gate import require_accepted_quality_review
import editorial_cli


SOURCE = "a" * 64
STAGED = "b" * 64
POLICY_VERSION = json.loads((Path(__file__).resolve().parents[1] / "editorial_policy.json").read_text(
    encoding="utf-8"))["featured_image_policy"]["version"]


def valid_receipt():
    return {
        "schema_version": 1,
        "task_id": "post-932-20261012",
        "generator_policy_version": POLICY_VERSION,
        "source_sha256": SOURCE,
        "staged_sha256": STAGED,
        "selected_candidate": 1,
        "selection_mode": "agent-delegated",
        "review_actor": "agent-delegated",
        "review_method": "direct_agent_visual",
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "review_result": "pass",
        "issues": [],
        "checks": {
            "topic_scene": True,
            "editorial_quality": True,
            "candidate_diversity": True,
            "recent_cover_comparison": True,
            "text_accuracy": True,
            "mobile_readability": True,
        },
        "comparison_set": [{"candidate_number": 1, "source_sha256": SOURCE}],
        "selection_reason": "Actual original reviewed, clear subject and sufficient contrast",
        "review_evidence": {
            "candidate_observations": {"1": {
                "source_sha256": SOURCE, "observed_full_size": True,
                "full_size_observation": "Checked actual full image at its native size",
                "observed_mobile_thumbnail": True,
                "mobile_observation": "Read message in mobile 240x135 rendition",
                "checks": {key: {"result": "PASS", "evidence": "Observed acceptable original visual content"}
                           for key in ("topic_scene", "editorial_quality", "candidate_diversity",
                                       "recent_cover_comparison", "text_accuracy", "mobile_readability")},
            }},
        },
    }


class QualityGateTests(unittest.TestCase):
    def evaluate(self, receipt, *, source=SOURCE, staged=STAGED, candidate=1,
                 mode="agent-delegated", **kwargs):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "quality.json"
            path.write_text(json.dumps(receipt), encoding="utf-8")
            return require_accepted_quality_review(
                path, source_sha256=source, staged_sha256=staged,
                selected_candidate=candidate, selection_mode=mode, **kwargs)

    def test_quality_review_age_uses_strict_timezone_and_24h_ttl(self):
        now = datetime.now(timezone.utc)
        expired = ["2020-10-12T10:00:00+09:00",
                   (now - timedelta(hours=25)).isoformat(),
                   (now + timedelta(days=1)).isoformat(),
                   "2026-10-12T15:00:00", "2026-10-12", "2026/10/12T15:00:00Z",
                   "2026-10-12 15:00:00+09:00"]
        for stamp in expired:
            record = valid_receipt()
            record["reviewed_at"] = stamp
            with self.subTest(stamp=stamp), self.assertRaisesRegex(ValueError, "visual_review_timestamp"):
                self.evaluate(record)

    def test_quality_review_must_follow_task_creation_and_expire_with_task(self):
        now = datetime.now(timezone.utc)
        fresh_review = valid_receipt()
        fresh_review["reviewed_at"] = (now - timedelta(minutes=5)).isoformat()
        created = (now - timedelta(hours=1)).isoformat()
        self.assertEqual("pass", self.evaluate(fresh_review, task_created_at=created)["review_result"])
        for creation in ((now + timedelta(minutes=1)).isoformat(),
                         (now - timedelta(hours=25)).isoformat(),
                         "2026-10-12T10:00:00"):
            with self.subTest(created=creation), self.assertRaisesRegex(ValueError, "visual_review_timestamp"):
                self.evaluate(fresh_review, task_created_at=creation)

    def test_declared_candidate_count_requires_manifest_revalidation(self):
        with self.assertRaisesRegex(ValueError, "visual_review_candidate_inventory_required"):
            self.evaluate(valid_receipt(), expected_candidate_count=5)
        with self.assertRaisesRegex(ValueError, "visual_review_candidate_count_invalid"):
            self.evaluate(valid_receipt(), expected_candidate_count=True)

    def test_comparison_set_cannot_claim_repeated_or_nonsequential_candidates(self):
        for items in (
            [{"candidate_number": 1, "source_sha256": SOURCE}] * 2,
            [{"candidate_number": 1, "source_sha256": SOURCE},
             {"candidate_number": 2, "source_sha256": SOURCE}],
            [{"candidate_number": 3, "source_sha256": SOURCE}],
        ):
            record = valid_receipt()
            record["comparison_set"] = items
            with self.subTest(items=items), self.assertRaisesRegex(ValueError, "visual_review_comparison"):
                self.evaluate(record)

    def test_valid_record_is_bound_to_exact_candidate_bytes(self):
        record = self.evaluate(valid_receipt())
        self.assertEqual("pass", record["review_result"])
        self.assertEqual("post-932-20261012", record["task_id"])

    def test_changed_original_or_stage_cannot_reuse_review(self):
        for kwargs in ({"source": "c" * 64}, {"staged": "c" * 64},
                       {"candidate": 2}, {"mode": "user"}):
            with self.subTest(kwargs=kwargs), self.assertRaisesRegex(
                    ValueError, "visual_review_receipt_candidate_or_sha_mismatch"):
                self.evaluate(valid_receipt(), **kwargs)

    def test_rejection_and_missing_visual_checks_never_count_as_pass(self):
        for change in ("reject", "issues", "false_check", "unverified_check"):
            receipt = valid_receipt()
            if change == "reject":
                receipt["review_result"] = "reject"
            if change == "issues":
                receipt["issues"] = ["low quality clipart"]
            if change == "false_check":
                receipt["checks"]["editorial_quality"] = False
            if change == "unverified_check":
                receipt["checks"].pop("candidate_diversity")
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.evaluate(receipt)

    def test_quality_claim_lacking_actual_reviewer_metadata_is_rejected(self):
        for missing in ("review_actor", "review_method", "reviewed_at", "comparison_set",
                        "selection_reason", "task_id"):
            receipt = valid_receipt()
            receipt.pop(missing)
            with self.subTest(missing=missing), self.assertRaises(ValueError):
                self.evaluate(receipt)

    def test_vision_method_requires_model_result_reference(self):
        receipt = valid_receipt()
        receipt["review_method"] = "vision_model"
        with self.assertRaisesRegex(ValueError, "visual_review_model_evidence_missing"):
            self.evaluate(receipt)
        receipt["model_result_ref"] = "review-log-20261012.json"
        self.assertEqual("pass", self.evaluate(receipt)["review_result"])

    def test_missing_review_file_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "visual_review_receipt_missing_or_invalid"):
            require_accepted_quality_review(
                Path("/not-a-real-quality-receipt.json"), source_sha256=SOURCE,
                staged_sha256=STAGED, selected_candidate=1,
                selection_mode="agent-delegated")

    def test_old_policy_and_forged_boolean_without_per_image_observation_rejected(self):
        for variant in ("old_policy", "no_observation", "unreviewed_detail"):
            record = valid_receipt()
            if variant == "old_policy":
                record["generator_policy_version"] = POLICY_VERSION - 1
            elif variant == "no_observation":
                record.pop("review_evidence")
            else:
                record["review_evidence"]["candidate_observations"]["1"]["checks"]["topic_scene"]["result"] = "UNVERIFIED"
            with self.subTest(variant=variant), self.assertRaises(ValueError):
                self.evaluate(record)

    def test_all_three_normal_content_commands_require_review_before_write(self):
        for action in ("prepare-draft", "edit-post", "replace-featured-image"):
            with self.subTest(action=action), tempfile.TemporaryDirectory() as temp:
                cover = Path(temp) / "staged.webp"
                cover.write_bytes(b"placeholder-for-stubbed-lineage")
                with (patch("sys.argv", ["editorial_cli.py", action, "--post-id", "932",
                                         "--image-path", str(cover),
                                         "--candidate-manifest", str(Path(temp) / "candidate.json"),
                                         "--selected-candidate", "1", "--selection-mode", "user"]),
                      patch("agents.featured_image.verify_manual_image_upload_lineage",
                            return_value={"source_sha256": SOURCE, "staged_sha256": STAGED,
                                          "candidate_number": 1, "selection_mode": "user"}),
                      patch("agents.publisher.PublisherAgent.publish") as publish):
                    with self.assertRaises(SystemExit):
                        editorial_cli._main()
                    publish.assert_not_called()

    def test_direct_cli_fake_task_id_cannot_authorize_image_write(self):
        with tempfile.TemporaryDirectory() as temp:
            cover = Path(temp) / "stage.webp"
            cover.write_bytes(b"stub")
            with (patch("sys.argv", ["editorial_cli.py", "replace-featured-image",
                                     "--post-id", "932", "--image-path", str(cover),
                                     "--candidate-manifest", str(Path(temp) / "manifest.json"),
                                     "--selected-candidate", "1", "--selection-mode", "agent-delegated",
                                     "--image-task-id", "caller-chosen-task-932",
                                     "--visual-review-receipt", str(Path(temp) / "review.json")]),
                  patch("agents.featured_image.verify_manual_image_upload_lineage", return_value={
                      "source_sha256": SOURCE, "staged_sha256": STAGED,
                      "candidate_number": 1, "selection_mode": "agent-delegated"}),
                  patch("agents.task_state.load_after_image_checkpoint", return_value=None),
                  patch("agents.featured_image_quality_gate.require_accepted_quality_review") as review,
                  patch("agents.featured_image.replace_featured_image_from_live_baseline") as upload):
                with self.assertRaisesRegex(ValueError, "current_image_task_checkpoint_required"):
                    editorial_cli._main()
                review.assert_not_called()
                upload.assert_not_called()


if __name__ == "__main__":
    unittest.main()
