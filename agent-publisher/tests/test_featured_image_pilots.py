"""R5 readiness contract: simulations can never be counted as real pilots."""

from __future__ import annotations

import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "verify_featured_image_pilots.py"
spec = importlib.util.spec_from_file_location("verify_featured_image_pilots", SCRIPT)
pilots = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pilots)


class FeaturedImagePilotReadinessTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.plan = self.root / "pilots.json"
        self.rows = []
        for index, topic in enumerate((
                "전기요금 지원 신청", "대중교통 환승 할인", "주택 임대차 계약"), start=1):
            image = self.root / f"source-{index}.png"
            staged = self.root / f"staged-{index}.webp"
            image.write_bytes(f"dummy bytes {index}".encode())
            staged.write_bytes(f"staged bytes {index}".encode())
            manifest = self.root / f"candidate-{index}.json"
            manifest.write_text("{}", encoding="utf-8")
            review = self.root / f"review-{index}.json"
            review.write_text("{}", encoding="utf-8")
            self.rows.append({
                "topic": topic,
                "post_id": 900 + index,
                "task": {"task_id": f"r5-task-{index}",
                         "target": {"post_id": 900 + index},
                         "candidate_count": 1,
                         "generator_policy_sha256": "f" * 64},
                "task_created_at": "2026-10-12T10:00:00+00:00",
                "manifest_path": manifest.name,
                "review_path": review.name,
                "source_path": image.name,
                "staged_path": staged.name,
                "selected_candidate": 1,
                "selection_mode": "user",
                "wordpress_expectation": {
                    "content_sha256": hashlib.sha256(topic.encode()).hexdigest(),
                    "previous_thumbnail_id": None,
                    "attachment_id": 1000 + index,
                    "alt_text": f"대표이미지 {index}",
                    "attachment_url": f"https://example.invalid/cover-{index}.webp",
                    "post_status": "draft", "post_title": topic,
                    "post_slug": f"article-{index}", "post_excerpt": "요약",
                },
            })
        self.write_plan()

    def write_plan(self, rows=None):
        self.plan.write_text(json.dumps({"version": 1, "pilots":
                                         self.rows if rows is None else rows},
                                        ensure_ascii=False), encoding="utf-8")

    @staticmethod
    def _verified(**kwargs):
        return {"status": "host_verified_and_review_authorized",
                "task_id": kwargs["task"]["task_id"]}

    def test_missing_plan_is_no_go(self):
        report = pilots.evaluate(self.root / "absent.json")
        self.assertEqual("NO-GO", report["status"])
        self.assertIn("pilot_manifest_missing_or_invalid", report["blockers"])

    def test_must_have_exactly_three_entries(self):
        for count in (0, 1, 2, 4):
            with self.subTest(count=count):
                self.write_plan([*self.rows] * (count // 3) + self.rows[:count % 3])
                with patch.object(pilots, "verify_image_upload_trust") as verify:
                    report = pilots.evaluate(self.plan)
                self.assertIn("exactly_three_pilots_required", report["blockers"])
                verify.assert_not_called()

    def test_duplicate_topic_and_post_or_task_cannot_qualify(self):
        original_rows = copy.deepcopy(self.rows)
        for field in ("topic", "post_id", "task_id"):
            with self.subTest(field=field):
                self.rows = copy.deepcopy(original_rows)
                if field == "task_id":
                    self.rows[1]["task"]["task_id"] = self.rows[0]["task"]["task_id"]
                else:
                    self.rows[1][field] = self.rows[0][field]
                    if field == "post_id":
                        self.rows[1]["task"]["target"]["post_id"] = self.rows[0][field]
                self.write_plan()
                with (patch.object(pilots, "_production_root_supported", return_value=True),
                      patch.object(pilots, "verify_image_upload_trust", side_effect=self._verified)):
                    report = pilots.evaluate(self.plan)
                self.assertIn("pilots_not_three_distinct_topics_posts_and_tasks",
                              report["blockers"])
                self.assertEqual("NO-GO", report["status"])

    def test_topic_placeholder_cannot_pass_as_real_topic(self):
        for topic in ("Test 1", "주제 2", "  ", "Pilot #3"):
            with self.subTest(topic=topic):
                old = self.rows[0]["topic"]
                self.rows[0]["topic"] = topic
                self.write_plan()
                with patch.object(pilots, "verify_image_upload_trust") as verify:
                    report = pilots.evaluate(self.plan)
                self.assertIn("pilot_topic_missing_or_placeholder", report["blockers"])
                self.rows[0]["topic"] = old

    def test_missing_real_image_bytes_fails_before_signature_checker(self):
        self.rows[0]["source_path"] = "absent.png"
        self.write_plan()
        with (patch.object(pilots, "_production_root_supported", return_value=True),
              patch.object(pilots, "verify_image_upload_trust", side_effect=self._verified) as verify):
            report = pilots.evaluate(self.plan)
        self.assertFalse(report["pilots"][0]["provenance_verified"])
        self.assertEqual(2, verify.call_count)
        self.assertIn("pilot_required_evidence_unavailable", report["blockers"])

    def test_unsigned_self_reports_and_fake_wordpress_snapshot_stay_no_go(self):
        # Real trust verification receives missing proof files; no keys generated.
        report = pilots.evaluate(self.plan)
        self.assertEqual(0, report["trusted_provenance_count"])
        self.assertEqual(0, report["wordpress_verified_count"])
        self.assertEqual("NO-GO", report["status"])
        self.assertIn("independent_wordpress_cas_alt_readback_unavailable", report["blockers"])
        self.rows[0]["wordpress_verified"] = True  # caller-invented bypass marker
        self.write_plan()
        with patch.object(pilots, "verify_image_upload_trust") as verify:
            report = pilots.evaluate(self.plan)
        self.assertIn("pilot_record_schema_invalid", report["blockers"])
        self.assertEqual("NO-GO", report["status"])
        self.assertEqual(0, report["wordpress_verified_count"])
        self.assertFalse(verify.called and report["status"] == "GO")

    def test_production_trust_root_is_never_overridden_even_in_readiness(self):
        with (patch.object(pilots, "_production_root_supported", return_value=True),
              patch.object(pilots, "verify_image_upload_trust", side_effect=self._verified) as verifier):
            report = pilots.evaluate(self.plan)
        self.assertEqual(3, verifier.call_count)
        self.assertEqual(3, report["trusted_provenance_count"])
        for index, call in enumerate(verifier.call_args_list):
            self.assertNotIn("trust_root", call.kwargs)
            self.assertNotIn("now", call.kwargs)
            self.assertEqual(hashlib.sha256(
                (self.root / self.rows[index]["source_path"]).read_bytes()).hexdigest(),
                call.kwargs["source_sha256"])
            self.assertEqual(hashlib.sha256(
                (self.root / self.rows[index]["staged_path"]).read_bytes()).hexdigest(),
                call.kwargs["staged_sha256"])
        self.assertEqual("NO-GO", report["status"])
        self.assertEqual(0, report["wordpress_verified_count"])
        self.assertEqual(0, report["checker_wordpress_mutations"])
        self.assertEqual(0, report["verified_pilot_count"])

    def test_no_go_when_signed_provenance_claim_succeeds_but_wp_unavailable(self):
        # This mock only reaches the WP boundary; it is not signed pilot proof.
        with (patch.object(pilots, "_production_root_supported", return_value=True),
              patch.object(pilots, "verify_image_upload_trust", side_effect=self._verified)):
            report = pilots.evaluate(self.plan)
        self.assertEqual([True, True, True],
                         [row["provenance_verified"] for row in report["pilots"]])
        self.assertTrue(all(not row["wordpress_verified"] for row in report["pilots"]))
        self.assertEqual(["independent_wordpress_cas_alt_readback_unavailable"],
                         report["blockers"])

    def test_unsupported_host_platform_never_marks_fake_production_root_trusted(self):
        with (patch.object(pilots, "_production_root_supported", return_value=False),
              patch.object(pilots, "verify_image_upload_trust") as verifier):
            report = pilots.evaluate(self.plan)
        verifier.assert_not_called()
        self.assertEqual(0, report["trusted_provenance_count"])
        self.assertIn("held_provenance_unverifiable:protected_production_trust_root_unavailable",
                      report["blockers"])

    def test_upload_plan_cannot_claim_published_or_forge_cas_fields(self):
        self.rows[0]["wordpress_expectation"]["post_status"] = "publish"
        self.write_plan()
        report = pilots.evaluate(self.plan)
        self.assertIn("pilot_wordpress_expectation_invalid", report["blockers"])

    def test_main_reports_json_and_nonzero_without_network_or_wp_calls(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exit_code = pilots.main(["--manifest", str(self.plan)])
        self.assertEqual(2, exit_code)
        self.assertEqual("NO-GO", json.loads(output.getvalue())["status"])
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            pilots.main(["--manifest", str(self.plan), "--trust-root", str(self.root)])
        self.assertEqual(2, raised.exception.code)


if __name__ == "__main__":
    unittest.main()
