"""Contract tests: similarity warns, humans review, SHA/actor/policy stay bound.

Synthetic PASS decisions below test schema behavior ONLY; they do not attest
that the synthetic images were visually approved for Bloguito publication.
"""

import copy
import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PIL import Image, ImageDraw

from agents.featured_image_quality_review import (
    CHECKS, analyze_candidate_diversity, finalize_visual_review,
    prepare_review_template, save_mobile_previews, verify_visual_review_evidence,
)
from agents.featured_image_quality_gate import require_accepted_quality_review


PROJECT = Path(__file__).resolve().parents[2]
PRIOR_SCRATCH = PROJECT.parent / "Bloguito" / "scratch" / "tasks"
REAL_BAD_COVERS = [
    ("draft-cycle-followup-20261011/cover-922-insurance.png", "88c75e5a6fc5c61aaab77ac0beea213171c30131115d37658f152e4c83e1317a"),
    ("draft-cycle-followup-20261011/cover-924-medical.png", "96998a2113b29ad701e781e97ec0e46da171e1464173289315e4299e9f7a86d7"),
    ("disaster-medical-20261011/cover-disaster-medical.png", "06f076c5114f6ce1eb305b34b579eb9efe9e2206fb3c4544507cf22e1e5725c4"),
    ("emergency-safety-20261011/cover-emergency-safety.png", "f2b3f832c34049fbc66dd058a38df45577236cfd92b3dccf915ecb573cbeb98c"),
    ("elder-care-20261011/cover-elder-care.png", "db92eee67d300de829dcbad839f52ae1201e8c68aa9585302df63016e7b29403"),
]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_manifest(directory, images):
    result = {"version": 2, "origin_claim": {"generator_tool": "image_gen.text2im", "save_tool": "cos_core.save_image"},
              "candidates": []}
    for number, path in enumerate(images, 1):
        with Image.open(path) as image:
            fmt, width, height = image.format, image.width, image.height
        result["candidates"].append({"candidate_number": number, "path": str(Path(path).resolve()),
                                     "sha256": sha(path), "format": fmt,
                                     "width": width, "height": height, "bytes": path.stat().st_size})
    manifest = directory / "candidate-manifest.json"
    manifest.write_text(json.dumps(result), encoding="utf-8")
    return manifest


def fake_stage(directory, source, manifest, *, number=1, selection_mode="user"):
    """Fixture-only canonical metadata; this is NOT proof of a generator call."""
    stage = directory / "stage.webp"
    with Image.open(source) as original:
        original.convert("RGB").resize((1200, 675)).save(stage, "WEBP")
    record = {"source_path": str(source.resolve()), "source_sha256": sha(source),
              "output_path": str(stage.resolve()), "output_sha256": sha(stage),
              "candidate_manifest": str(manifest.resolve()),
              "candidate_number": number, "selection_mode": selection_mode,
              "sealed_source_sha256": sha(source), "selection_actor": selection_mode}
    stage.with_suffix(stage.suffix + ".stage.json").write_text(json.dumps(record), encoding="utf-8")
    return stage


def fill_test_observations(template, *, reject=None):
    """Simulated reviewer input for testing validators, never a real review."""
    for candidate in template["candidate_observations"].values():
        candidate.update({"observed_full_size": True,
                          "full_size_observation": "Test-only mock: shape occupies one side of canvas.",
                          "observed_mobile_thumbnail": True,
                          "mobile_observation": "Test-only mock: text remains near the left side."})
        for name in CHECKS:
            result = "REJECT" if reject == name else "PASS"
            candidate["checks"][name] = {"result": result, "evidence": "Test-only evidence for this check; no actual approval."}
    for signal in template["candidate_analysis"]["pair_signals"]:
        if signal["requires_visual_comparison"]:
            template["comparison_decisions"][signal["signal_id"]] = {
                "accepted_distinct": not signal["identical_bytes"],
                "reason": "Test-only explicit pairwise judgment (not observed)."}
    return template


class QualityReviewTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        source = self.root / "one.png"
        Image.new("RGB", (1200, 675), "#18191e").save(source)
        self.source = source
        self.manifest = write_manifest(self.root, [source])
        self.stage = fake_stage(self.root, source, self.manifest)

    def make_receipt(self, template=None, **kwargs):
        values = {"staged_path": self.stage, "selected_candidate": 1,
                  "selection_mode": "user", "task_id": "task-20261012-p2",
                  "review_actor": "user", "review_method": "human_visual",
                  "selection_reason": "Test-only explicit selection reason with inspected details."}
        values.update(kwargs)
        return finalize_visual_review(template or fill_test_observations(prepare_review_template(self.manifest)), **values)

    def test_template_is_pending_and_unobserved_cannot_be_finalized(self):
        template = prepare_review_template(self.manifest)
        self.assertEqual("quality_review_pending", template["status"])
        self.assertEqual("UNVERIFIED", template["candidate_observations"]["1"]["checks"]["topic_scene"]["result"])
        with self.assertRaisesRegex(ValueError, "actual_views_not_documented"):
            self.make_receipt(template)

    def test_mobile_preview_is_review_only_and_not_source(self):
        template = prepare_review_template(self.manifest)
        saved = save_mobile_previews(template, self.root / "previews")
        self.assertEqual(1, len(saved))
        with Image.open(saved[0]) as im:
            self.assertEqual((240, 135), im.size)
        self.assertEqual(sha(self.source), template["candidate_observations"]["1"]["source_sha256"])
        with self.assertRaises(FileExistsError):
            save_mobile_previews(template, self.root / "previews")

    def test_complete_review_builds_p1_compatible_receipt_and_verifies(self):
        receipt = self.make_receipt()
        self.assertEqual("pass", receipt["review_result"])
        self.assertEqual([], receipt["issues"])
        self.assertEqual(6, len(receipt["checks"]))
        self.assertEqual(5, receipt["generator_policy_version"])
        self.assertEqual("pass", verify_visual_review_evidence(
            receipt, manifest_path=self.manifest, staged_path=self.stage)["status"])
        reviewed_path = self.root / "visual-review-receipt.json"
        reviewed_path.write_text(json.dumps(receipt), encoding="utf-8")
        result = require_accepted_quality_review(
            reviewed_path, source_sha256=sha(self.source), staged_sha256=sha(self.stage),
            selected_candidate=1, selection_mode="user", expected_task_id="task-20261012-p2",
            manifest_path=self.manifest, staged_path=self.stage)
        self.assertEqual("pass", result["review_result"])
        # Claiming an altered similarity measurement cannot bypass a fresh
        # comparison against the actual pixels. Freeform review notes are
        # reviewer claims, not cryptographically authenticated signatures.
        receipt["review_evidence"]["similarity_analysis"]["not_a_quality_verdict"] = False
        reviewed_path.write_text(json.dumps(receipt), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "evidence_binding_invalid"):
            require_accepted_quality_review(
                reviewed_path, source_sha256=sha(self.source), staged_sha256=sha(self.stage),
                selected_candidate=1, selection_mode="user", expected_task_id="task-20261012-p2",
                manifest_path=self.manifest, staged_path=self.stage)

    def test_rejected_selected_visual_check_never_passes(self):
        template = fill_test_observations(prepare_review_template(self.manifest), reject="editorial_quality")
        receipt = self.make_receipt(template)
        self.assertEqual("reject", receipt["review_result"])
        self.assertFalse(receipt["checks"]["editorial_quality"])
        self.assertIn("candidate_1:editorial_quality:REJECT", receipt["issues"])

    def test_stage_receipt_or_sha_change_rejected(self):
        self.stage.with_suffix(".webp.stage.json").unlink()
        with self.assertRaisesRegex(ValueError, "stage_receipt_missing"):
            self.make_receipt()
        fake_stage(self.root, self.source, self.manifest)
        receipt = self.make_receipt()
        with Image.open(self.stage) as im:
            Image.new("RGB", im.size, "#e7c770").save(self.stage, "WEBP")
        with self.assertRaisesRegex(ValueError, "stage_receipt_binding_invalid"):
            self.make_receipt()
        with self.assertRaisesRegex(ValueError, "stage_receipt_binding_invalid"):
            verify_visual_review_evidence(receipt, manifest_path=self.manifest, staged_path=self.stage)

    def test_manifest_and_policy_changes_are_rejected(self):
        template = fill_test_observations(prepare_review_template(self.manifest))
        edited = copy.deepcopy(template)
        edited["generator_policy_version"] = -1
        with self.assertRaisesRegex(ValueError, "generator_policy_changed"):
            self.make_receipt(edited)
        new_contents = self.manifest.read_text(encoding="utf-8") + " "
        self.manifest.write_text(new_contents, encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "manifest_changed"):
            self.make_receipt(template)

    def test_unsupported_false_sight_or_missing_dimension_evidence_rejected(self):
        template = fill_test_observations(prepare_review_template(self.manifest))
        template["candidate_observations"]["1"]["observed_mobile_thumbnail"] = False
        with self.assertRaisesRegex(ValueError, "actual_views_not_documented"):
            self.make_receipt(template)
        template["candidate_observations"]["1"]["observed_mobile_thumbnail"] = True
        template["candidate_observations"]["1"]["checks"]["text_accuracy"]["evidence"] = "yes"
        with self.assertRaisesRegex(ValueError, "check_evidence_missing"):
            self.make_receipt(template)

    def test_receipt_extra_flag_or_changed_check_cannot_verify(self):
        receipt = self.make_receipt()
        receipt["checks"]["topic_scene"] = False
        with self.assertRaisesRegex(ValueError, "tampered_or_stale"):
            verify_visual_review_evidence(receipt, manifest_path=self.manifest, staged_path=self.stage)

    def test_recent_cover_change_requires_fresh_comparison(self):
        recent = self.root / "previous.png"
        Image.new("RGB", (1200, 675), "white").save(recent)
        template = fill_test_observations(prepare_review_template(self.manifest, [recent]))
        receipt = self.make_receipt(template)
        self.assertEqual("available", receipt["review_evidence"]["similarity_analysis"]["recent_comparison"])
        Image.new("RGB", (1200, 675), "#777777").save(recent)
        with self.assertRaisesRegex(ValueError, "similarity_evidence_invalid"):
            self.make_receipt(template)

    def test_byte_identical_candidates_cannot_be_called_distinct(self):
        other = self.root / "second.png"
        other.write_bytes(self.source.read_bytes())
        # Existing seal module already rejects byte duplicates; direct signal
        # must nevertheless make the repeated-candidate problem explicit.
        analysis = analyze_candidate_diversity([self.source, other])
        self.assertTrue(analysis["pair_signals"][0]["identical_bytes"])
        self.assertTrue(analysis["review_required"])

    def test_manifest_rejects_same_content_repeated_even_when_sealed_hashes_agree(self):
        duplicate = self.root / "duplicate.png"
        duplicate.write_bytes(self.source.read_bytes())
        manifest = write_manifest(self.root, [self.source, duplicate])
        with self.assertRaisesRegex(ValueError, "visual_review_duplicate_candidate"):
            prepare_review_template(manifest)

    def test_manifest_rejects_byte_distinct_files_with_identical_decoded_pixels(self):
        other = self.root / "second.png"
        with Image.open(self.source) as image:
            image.save(other, "PNG", compress_level=0)
        self.assertNotEqual(sha(self.source), sha(other))
        with self.assertRaisesRegex(ValueError, "visual_review_duplicate_candidate"):
            prepare_review_template(write_manifest(self.root, [self.source, other]))

    def test_expected_candidate_count_matches_sealed_manifest_and_receipt(self):
        from agents.featured_image_quality_review import verify_visual_review_evidence
        receipt = self.make_receipt()
        self.assertEqual("pass", verify_visual_review_evidence(
            receipt, manifest_path=self.manifest, staged_path=self.stage,
            expected_candidate_count=1)["status"])
        with self.assertRaisesRegex(ValueError, "visual_review_candidate_count_mismatch"):
            verify_visual_review_evidence(
                receipt, manifest_path=self.manifest, staged_path=self.stage,
                expected_candidate_count=5)
        receipt["comparison_set"].append({"candidate_number": 2, "source_sha256": "f" * 64})
        with self.assertRaisesRegex(ValueError, "visual_review_candidate_count_mismatch"):
            verify_visual_review_evidence(
                receipt, manifest_path=self.manifest, staged_path=self.stage,
                expected_candidate_count=1)

    def test_two_distinct_candidates_pass_real_gate_when_task_count_matches(self):
        second = self.root / "two.png"
        Image.new("RGB", (1200, 675), "#fefeff").save(second)
        manifest = write_manifest(self.root, [self.source, second])
        template = fill_test_observations(prepare_review_template(manifest))
        created = (datetime.now(timezone.utc) - timedelta(minutes=45)).isoformat()
        receipt = self.make_receipt(template, expected_candidate_count=2,
                                    task_created_at=created)
        review_path = self.root / "quality-review.json"
        review_path.write_text(json.dumps(receipt), encoding="utf-8")
        self.assertEqual("pass", require_accepted_quality_review(
            review_path, source_sha256=sha(self.source), staged_sha256=sha(self.stage),
            selected_candidate=1, selection_mode="user",
            expected_candidate_count=2, task_created_at=created,
            manifest_path=manifest, staged_path=self.stage)["review_result"])
        with self.assertRaisesRegex(ValueError, "visual_review_candidate_count_mismatch"):
            require_accepted_quality_review(
                review_path, source_sha256=sha(self.source), staged_sha256=sha(self.stage),
                selected_candidate=1, selection_mode="user",
                expected_candidate_count=3, task_created_at=created,
                manifest_path=manifest, staged_path=self.stage)

    def test_review_ttl_exact_boundary_and_cross_timezone_order(self):
        from agents.featured_image_quality_review import validate_visual_review_freshness
        now = datetime(2026, 10, 12, 6, 0, tzinfo=timezone.utc)
        validate_visual_review_freshness(
            "2026-10-11T06:00:00Z", now=now)
        # Same instant in KST. Offset-bearing timestamps are compared in UTC.
        validate_visual_review_freshness(
            "2026-10-12T14:00:00+09:00",
            task_created_at="2026-10-12T04:30:00Z", now=now)
        with self.assertRaisesRegex(ValueError, "visual_review_timestamp_expired"):
            validate_visual_review_freshness("2026-10-11T05:59:59Z", now=now)
        with self.assertRaisesRegex(ValueError, "visual_review_timestamp_in_future"):
            validate_visual_review_freshness("2026-10-12T06:00:01Z", now=now)

    def test_finalizer_rejects_old_or_future_review_dates(self):
        for stamp in ("2020-10-12T10:00:00+09:00",
                      (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
                      "2026-10-12T14:00:00"):
            with self.subTest(stamp=stamp), self.assertRaisesRegex(ValueError, "visual_review_timestamp"):
                self.make_receipt(reviewed_at=stamp)

    def test_real_five_bad_covers_trigger_diversity_review_if_available(self):
        sources = [PRIOR_SCRATCH / name for name, _ in REAL_BAD_COVERS]
        if not all(source.is_file() for source in sources):
            self.skipTest("2026-10-11 original PNGs are not checked into Git")
        self.assertEqual([expected for _, expected in REAL_BAD_COVERS], [sha(source) for source in sources])
        analysis = analyze_candidate_diversity(sources)
        # Six pairs share coarse composition despite color and topic changes;
        # the metric flags visual inspection, it cannot pronounce ugly/beautiful.
        self.assertGreaterEqual(len(analysis["review_required"]), 5)
        self.assertTrue(analysis["not_a_quality_verdict"])
        manifest = write_manifest(self.root, sources)
        template = prepare_review_template(manifest)
        self.assertGreaterEqual(len(template["candidate_analysis"]["review_required"]), 5)
        with self.assertRaisesRegex(ValueError, "actual_views_not_documented"):
            self.make_receipt(template)
        stage = fake_stage(self.root, sources[0], manifest)
        simulated_review = fill_test_observations(template)
        # All flagged comparison signals require the reviewer to say WHY two
        # candidates differ; even complete single-image checks are insufficient.
        simulated_review["comparison_decisions"] = {}
        with self.assertRaisesRegex(ValueError, "flagged_pair_unreviewed"):
            self.make_receipt(simulated_review, staged_path=stage)
        fill_test_observations(simulated_review)
        signal = next(s for s in simulated_review["candidate_analysis"]["pair_signals"]
                      if s["requires_visual_comparison"] and s["left"] == "1")
        simulated_review["comparison_decisions"][signal["signal_id"]] = {
            "accepted_distinct": False,
            "reason": "These two layouts repeat the same title/card/icon structure."}
        receipt = self.make_receipt(simulated_review, staged_path=stage)
        self.assertEqual("reject", receipt["review_result"])
        self.assertTrue(any("repeats" in issue for issue in receipt["issues"]))


if __name__ == "__main__":
    unittest.main()
