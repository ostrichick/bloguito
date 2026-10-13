"""Q3/R1 pure recovery classification: candidates are NEVER ownership."""
import unittest

from agents.media_recovery_contract import (
    assess_pending_import, classify_sha_candidates, hold_pending_import,
)


class MediaRecoveryContractTests(unittest.TestCase):
    def test_sha_candidate_categories_are_never_write_authorization(self):
        for ids, prior, expected, candidates in [
            ([], [], "no_sha_matching_attachment_outcome_unknown", []),
            ([303], [], "single_sha_matching_attachment_unconfirmed", [303]),
            ([303, 404], [303], "single_sha_matching_attachment_unconfirmed", [404]),
            ([303, 404], None, "multiple_sha_matching_attachments_ambiguous", [303, 404]),
        ]:
            with self.subTest(ids=ids, prior=prior):
                result = classify_sha_candidates(ids, preexisting_ids=prior)
                self.assertEqual(expected, result["status"])
                self.assertEqual(candidates, result["candidate_attachment_ids"])
                self.assertFalse(result["write_authorized"])
                self.assertFalse(result["ownership_verified"])
                self.assertFalse(result["import_termination_verified"])
                self.assertFalse(result["automatic_retry"])

    def test_invalid_prior_or_observed_ids_fail_closed(self):
        for observed, prior in [([0], []), ([303, 303], []), ([303], [303, 303]),
                                (["303"], []), ([303], [True])]:
            with self.subTest(observed=observed, prior=prior):
                with self.assertRaisesRegex(ValueError, "invalid_featured_image_"):
                    classify_sha_candidates(observed, preexisting_ids=prior)

    def test_pending_receipt_never_becomes_owned_from_sha_or_lock_token(self):
        attempt = {"started": True, "image_sha256": "a" * 64,
                   "expected_thumbnail_id": 12, "preexisting_attachment_ids": [],
                   "attachment_id": 777, "import_termination_confirmed": True}
        # The attempt itself is not the post-import result receipt, even when
        # manually annotated. Keep automatic write disabled in all cases.
        self.assertFalse(assess_pending_import(
            attempt, image_sha256="a" * 64,
            expected_thumbnail_id=12)["write_authorized"])
        with self.assertRaisesRegex(ValueError, "ownership_unverified"):
            hold_pending_import(attempt, image_sha256="a" * 64, expected_thumbnail_id=12)
        attempt["lock_token"] = "token-is-not-liveness"
        with self.assertRaisesRegex(ValueError, "process_termination_unknown"):
            hold_pending_import(attempt, image_sha256="a" * 64, expected_thumbnail_id=12)

    def test_wrong_image_or_thumbnail_refuses_before_candidate_lookup(self):
        attempt = {"started": True, "image_sha256": "a" * 64,
                   "expected_thumbnail_id": None}
        for sha, thumb in [("b" * 64, None), ("a" * 64, 13)]:
            with self.subTest(sha=sha, thumb=thumb):
                with self.assertRaisesRegex(ValueError, "resume_image_import_artifact_conflict"):
                    hold_pending_import(attempt, image_sha256=sha,
                                        expected_thumbnail_id=thumb)


if __name__ == "__main__":
    unittest.main()
