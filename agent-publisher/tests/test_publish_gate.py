import hashlib
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

from agents.editorial import render
from agents.publish_gate import (
    approval_evidence_digest,
    record_publish_attestation,
    reviewed_binding_for_post,
    validate_publish_attestation,
)
from agents.temporal_validation import KST
from test_editorial_system import sample, sign


class PublishGateTests(unittest.TestCase):
    def _current_bundle(self):
        bundle = sample()
        now = datetime.now(KST)
        bundle["sources"][0]["fetched_at"] = now.isoformat()
        sign(bundle)
        bundle["review"]["checked_at"] = now.isoformat()
        return bundle

    def test_reviewed_binding_requires_exact_reviewed_body_and_title(self):
        bundle = self._current_bundle()
        content = render(bundle["plan"], bundle["sources"])
        content_sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            drafts = root / "drafts.json"
            published = root / "published.json"
            drafts.write_text(json.dumps([{
                "id": 901,
                "fact_manifest": {"editorial_bundle": bundle},
            }], ensure_ascii=False), encoding="utf-8")
            with patch("config.DRAFTS_INDEX_FILE", drafts), patch("config.POSTS_INDEX_FILE", published):
                binding = reviewed_binding_for_post(901, content_sha, bundle["plan"]["title"])
                with self.assertRaisesRegex(ValueError, "reviewed_publish_title_mismatch"):
                    reviewed_binding_for_post(901, content_sha, "changed title")
                with self.assertRaisesRegex(ValueError, "reviewed_publish_content_mismatch"):
                    reviewed_binding_for_post(901, "0" * 64, bundle["plan"]["title"])
                stale = json.loads(json.dumps(bundle))
                stale["review"]["policy_digest"] = "0" * 64
                drafts.write_text(json.dumps([{
                    "id": 901,
                    "fact_manifest": {"editorial_bundle": stale},
                }], ensure_ascii=False), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "reviewed_publish_review_not_current"):
                    reviewed_binding_for_post(901, content_sha, stale["plan"]["title"])

        self.assertEqual(bundle["review"]["digest"], binding["review_digest"])
        self.assertEqual(
            hashlib.sha256(bundle["plan"]["title"].encode("utf-8")).hexdigest(),
            binding["title_sha256"],
        )
        self.assertTrue(binding["expires_at_gmt"].endswith("Z"))
        self.assertIs(binding["requires_live_state"], False)

    def test_manual_approval_evidence_is_deterministic_and_kind_bound(self):
        evidence = {"post_id": 901, "image_sha256": "a" * 64, "selection_confirmed": True}
        first = approval_evidence_digest("manual_user_selected", evidence)
        second = approval_evidence_digest("manual_user_selected", dict(evidence))
        self.assertEqual(first, second)
        self.assertRegex(first, r"^[0-9a-f]{64}$")
        with self.assertRaisesRegex(ValueError, "image_approval_evidence_required"):
            approval_evidence_digest("unknown", evidence)

    def test_record_attestation_sends_exact_image_and_review_binding(self):
        with tempfile.TemporaryDirectory() as folder:
            image = Path(folder) / "cover.jpg"
            image.write_bytes(b"approved image bytes")
            observed = {"version": 1, "post_id": 901}
            with patch("agents.publish_gate.run_wordpress", return_value=Mock(
                    stdout=json.dumps({"status": "ok", "attestation": observed}))) as run:
                result = record_publish_attestation(
                    ["wp"], 901,
                    content_sha256="0" * 64,
                    review_digest="1" * 64,
                    title_sha256="2" * 64,
                    thumbnail_id=777,
                    image_path=image,
                    alt_text="검토된 대체텍스트",
                    approval_kind="manual_user_selected",
                    approval_evidence_sha256="3" * 64,
                    expires_at_gmt="2099-01-01T00:00:00Z",
                    requires_live_state=False,
                )
        payload = json.loads(run.call_args.kwargs["input"])
        self.assertEqual(901, payload["post_id"])
        self.assertEqual(777, payload["thumbnail_id"])
        self.assertEqual(hashlib.sha256(b"approved image bytes").hexdigest(), payload["image_sha256"])
        self.assertIs(payload["requires_live_state"], False)
        self.assertEqual(
            hashlib.sha256("검토된 대체텍스트".encode("utf-8")).hexdigest(),
            payload["alt_text_sha256"],
        )
        self.assertEqual(observed, result)

    def test_validate_attestation_fails_closed_with_wordpress_reason(self):
        with patch("agents.publish_gate.run_wordpress", return_value=Mock(stdout=json.dumps({
            "status": "blocked", "reason": "featured_image_changed_after_approval",
        }))):
            with self.assertRaisesRegex(
                    ValueError, "publication_gate_blocked:featured_image_changed_after_approval"):
                validate_publish_attestation(["wp"], 901, expected_review_digest="a" * 64)


if __name__ == "__main__":
    unittest.main()
