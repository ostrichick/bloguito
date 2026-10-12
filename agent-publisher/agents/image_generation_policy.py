"""Task-bound image generation policy for the ChatGPT/CoS handoff.

This module validates local records. It cannot inspect or attest to native
ChatGPT image_gen calls, and a recorded user instruction does not prove one.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path


POLICY_FILE = Path(__file__).resolve().parents[1] / "editorial_policy.json"
NATIVE_PROVIDER = "chatgpt_image_gen"
TASK_CONTRACT_VERSION = 1
_SHA = re.compile(r"[0-9a-f]{64}\Z")


def load_image_generator_policy(path: Path | None = None) -> dict:
    """Read the versioned execution policy and fail closed if it has drifted."""
    try:
        payload = json.loads(Path(path or POLICY_FILE).read_text(encoding="utf-8"))
        policy = payload["featured_image_policy"]
        manual = policy["manual_generation"]
        if (type(policy["version"]) is not int or policy["version"] <= 0
                or manual["provider"] != NATIVE_PROVIDER
                or manual["local_generation_allowed"] is not False
                or manual["gemini_generation_allowed"] is not False
                or type(manual["candidate_count"]) is not int
                or manual["candidate_count"] <= 0
                or manual["agent_selection_requires_delegation"] is not True):
            raise ValueError("image_generator_policy_invalid")
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise ValueError("image_generator_policy_unavailable_or_incompatible") from exc
    encoded = json.dumps(policy, sort_keys=True, ensure_ascii=False,
                         separators=(",", ":")).encode("utf-8")
    return {
        "version": policy["version"],
        "sha256": hashlib.sha256(encoded).hexdigest(),
        "provider": NATIVE_PROVIDER,
        "default_candidate_count": manual["candidate_count"],
    }


def _timestamp(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("image_exception_timestamp_required")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("image_exception_timestamp_invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("image_exception_timezone_required")
    return parsed.astimezone(timezone.utc)


def validate_task_exception(record: dict, *, task_id: str, target: dict,
                            now: datetime | None = None) -> dict:
    """Accept only a fresh grant scoped to this exact task and target.

    The returned metadata is an *authorization claim*, not permission to
    substitute a local generator through the normal image upload pipeline.
    """
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("image_exception_evaluation_timezone_required")
    if (not isinstance(record, dict) or record.get("task_id") != task_id
            or record.get("target") != target):
        raise ValueError("image_exception_wrong_task_or_target")
    if record.get("kind") != "one_task_generation_request":
        raise ValueError("image_exception_kind_invalid")
    evidence = record.get("approval_evidence_sha256")
    if not isinstance(evidence, str) or not _SHA.fullmatch(evidence):
        raise ValueError("image_exception_approval_reference_required")
    granted = _timestamp(record.get("approved_at"))
    expiry = _timestamp(record.get("expires_at"))
    evaluated = now.astimezone(timezone.utc)
    if expiry <= granted or evaluated < granted or evaluated >= expiry:
        raise ValueError("image_exception_not_current")
    return {
        "task_id": task_id,
        "target": dict(target),
        "kind": "one_task_generation_request",
        "approval_evidence_sha256": evidence,
        "approved_at": granted.isoformat(),
        "expires_at": expiry.isoformat(),
        "evidence_level": "task_scoped_claim_only",
        "generator_override_allowed": False,
    }


def new_image_generation_task(*, post_id: int | None = None,
                              brief_id: str | None = None,
                              task_id: str | None = None,
                              candidate_count: int | None = None,
                              selection_mode: str = "pending",
                              explicitly_delegated: bool = False,
                              task_exception: dict | None = None,
                              now: datetime | None = None,
                              policy_path: Path | None = None) -> dict:
    """Make a fresh record for one image request, never inheriting old grants."""
    if (post_id is None) == (brief_id is None):
        raise ValueError("image_task_one_target_required")
    if post_id is not None and (type(post_id) is not int or post_id <= 0):
        raise ValueError("image_task_post_id_invalid")
    if brief_id is not None and (not isinstance(brief_id, str)
                                 or not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", brief_id)):
        raise ValueError("image_task_brief_id_invalid")
    target = {"post_id": post_id} if post_id is not None else {"brief_id": brief_id}
    task_id = task_id or uuid.uuid4().hex
    if not isinstance(task_id, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{8,128}", task_id):
        raise ValueError("image_task_id_invalid")
    policy = load_image_generator_policy(policy_path)
    count = policy["default_candidate_count"] if candidate_count is None else candidate_count
    if type(count) is not int or not 1 <= count <= 20:
        raise ValueError("image_task_candidate_count_invalid")
    if selection_mode not in {"pending", "user", "agent-delegated"}:
        raise ValueError("image_task_selection_mode_invalid")
    if selection_mode == "agent-delegated" and explicitly_delegated is not True:
        raise ValueError("image_task_explicit_delegation_required")
    if explicitly_delegated is True and selection_mode != "agent-delegated":
        raise ValueError("image_task_delegation_scope_conflict")
    exception = (validate_task_exception(task_exception, task_id=task_id,
                                         target=target, now=now)
                 if task_exception is not None else None)
    return {
        "schema_version": TASK_CONTRACT_VERSION,
        "task_id": task_id,
        "target": target,
        "generator_policy_version": policy["version"],
        "generator_policy_sha256": policy["sha256"],
        "generator": policy["provider"],
        "candidate_count": count,
        "candidate_count_source": "default" if candidate_count is None else "user_requested",
        "selection_mode": selection_mode,
        "explicit_delegation": bool(explicitly_delegated),
        "task_exception": exception,
        "status": "awaiting_image_gen",
        "image_pending": True,
    }


def validate_image_task_policy(task: dict, *, policy_path: Path | None = None,
                               now: datetime | None = None) -> None:
    """Check policy drift and that a grant cannot outlive this task's attempt."""
    policy = load_image_generator_policy(policy_path)
    if (not isinstance(task, dict)
            or task.get("generator_policy_version") != policy["version"]
            or task.get("generator_policy_sha256") != policy["sha256"]
            or task.get("generator") != policy["provider"]):
        raise ValueError("image_task_generator_policy_changed")
    if task.get("task_exception") is not None:
        validate_task_exception(task["task_exception"],
                                task_id=task.get("task_id"),
                                target=task.get("target"), now=now)


def unavailable_diagnosis(scope: str, *, host_call_result_observed: bool = False) -> dict:
    """Record only what the caller reports observing; no fake host attestation."""
    if scope not in {"cos_catalog_only", "chatgpt_host_current_turn", "unattended_scheduler"}:
        raise ValueError("image_tool_observation_scope_invalid")
    if scope == "cos_catalog_only":
        return {"status": "awaiting_image_gen", "image_pending": True,
                "observation_scope": scope, "evidence_level": "caller_report_only",
                "reason": "cos_catalog_does_not_prove_host_unavailable"}
    if host_call_result_observed is not True and scope == "chatgpt_host_current_turn":
        return {"status": "awaiting_image_gen", "image_pending": True,
                "observation_scope": scope, "evidence_level": "caller_report_only",
                "reason": "host_call_outcome_not_observed"}
    return {"status": "held_image_generation_unavailable", "image_pending": True,
            "observation_scope": scope, "evidence_level": "caller_report_only",
            "reason": "current_host_route_unavailable" if scope == "chatgpt_host_current_turn"
            else "unattended_server_has_no_native_image_gen_route"}
