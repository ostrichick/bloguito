import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from agents.image_generation_policy import (
    load_image_generator_policy,
    new_image_generation_task,
    unavailable_diagnosis,
    validate_image_task_policy,
    validate_image_task_selection,
)


class ImageGenerationPolicyTests(unittest.TestCase):
    def test_default_and_one_candidate_are_task_scoped(self):
        default = new_image_generation_task(brief_id="new-health-brief")
        self.assertEqual(5, default["candidate_count"])
        self.assertEqual("default", default["candidate_count_source"])
        one = new_image_generation_task(post_id=922, candidate_count=1)
        self.assertEqual(1, one["candidate_count"])
        self.assertEqual("user_requested", one["candidate_count_source"])
        self.assertNotEqual(default["task_id"], one["task_id"])
        self.assertEqual("awaiting_image_gen", one["status"])
        self.assertTrue(one["image_pending"])
        self.assertEqual("chatgpt_image_gen", one["generator"])

    def test_selection_delegation_cannot_be_inferred(self):
        with self.assertRaisesRegex(ValueError, "explicit_delegation_required"):
            new_image_generation_task(post_id=922, selection_mode="agent-delegated")
        delegated = new_image_generation_task(
            post_id=922, selection_mode="agent-delegated", explicitly_delegated=True)
        self.assertTrue(delegated["explicit_delegation"])
        pending = new_image_generation_task(post_id=922, candidate_count=1)
        with self.assertRaisesRegex(ValueError, "agent_delegation_not_authorized"):
            validate_image_task_selection(pending, selected_candidate=1,
                                          selection_mode="agent-delegated")
        validate_image_task_selection(pending, selected_candidate=1,
                                      selection_mode="user")
        validate_image_task_selection(delegated, selected_candidate=1,
                                      selection_mode="agent-delegated")
        with self.assertRaisesRegex(ValueError, "candidate_outside_authorized_count"):
            validate_image_task_selection(delegated, selected_candidate=6,
                                          selection_mode="agent-delegated")

    def test_old_grant_cannot_be_used_for_new_post_task_or_after_expiry(self):
        now = datetime(2026, 10, 12, 0, 0, tzinfo=timezone.utc)
        record = {
            "task_id": "task-922-current", "target": {"post_id": 922},
            "kind": "one_task_generation_request",
            "approval_evidence_sha256": "a" * 64,
            "approved_at": (now - timedelta(minutes=1)).isoformat(),
            "expires_at": (now + timedelta(minutes=10)).isoformat(),
        }
        current = new_image_generation_task(
            post_id=922, task_id="task-922-current", now=now, task_exception=record)
        self.assertEqual("task_scoped_claim_only", current["task_exception"]["evidence_level"])
        self.assertFalse(current["task_exception"]["generator_override_allowed"])
        validate_image_task_policy(current, now=now)
        with self.assertRaisesRegex(ValueError, "wrong_task_or_target"):
            new_image_generation_task(
                post_id=930, task_id="task-930-new", now=now, task_exception=record)
        with self.assertRaisesRegex(ValueError, "not_current"):
            validate_image_task_policy(current, now=now + timedelta(minutes=11))
        record["approval_evidence_sha256"] = "from an earlier chat"
        with self.assertRaisesRegex(ValueError, "approval_reference_required"):
            new_image_generation_task(
                post_id=922, task_id="task-922-current", now=now, task_exception=record)

    def test_policy_tampering_changes_digest_and_invalidates_task(self):
        task = new_image_generation_task(post_id=922)
        self.assertEqual(load_image_generator_policy()["sha256"], task["generator_policy_sha256"])
        from agents.image_generation_policy import POLICY_FILE
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "editorial_policy.json"
            data = json.loads(POLICY_FILE.read_text(encoding="utf-8"))
            data["featured_image_policy"]["manual_generation"]["candidate_count"] = 3
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "generator_policy_changed"):
                validate_image_task_policy(task, policy_path=path)
            data["featured_image_policy"]["manual_generation"]["local_generation_allowed"] = True
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unavailable_or_incompatible"):
                load_image_generator_policy(path)

    def test_cos_catalog_absence_is_not_host_failure(self):
        diagnosis = unavailable_diagnosis("cos_catalog_only")
        self.assertEqual("awaiting_image_gen", diagnosis["status"])
        self.assertEqual("cos_catalog_does_not_prove_host_unavailable", diagnosis["reason"])
        self.assertEqual("awaiting_image_gen",
                         unavailable_diagnosis("chatgpt_host_current_turn")["status"])
        held = unavailable_diagnosis("chatgpt_host_current_turn",
                                     host_call_result_observed=True)
        self.assertEqual("held_image_generation_unavailable", held["status"])
        self.assertEqual("caller_report_only", held["evidence_level"])
        self.assertEqual("held_image_generation_unavailable",
                         unavailable_diagnosis("unattended_scheduler")["status"])


if __name__ == "__main__":
    unittest.main()
