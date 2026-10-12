"""Pre-import binding of a real visual decision to a sealed cover candidate.

The receipt is a recorded reviewer decision, not a cryptographic proof that
the image-generation host or a vision model was called. Verify the actual
review evidence separately; a JSON claim alone cannot prove observation.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


REQUIRED_VISUAL_CHECKS = frozenset({
    "topic_scene", "editorial_quality", "candidate_diversity",
    "recent_cover_comparison", "text_accuracy", "mobile_readability",
})


def require_accepted_quality_review(
    receipt_path: Path | str,
    *, source_sha256: str, staged_sha256: str,
    selected_candidate: int, selection_mode: str,
) -> dict:
    """Reject absent, malformed, non-current or unreviewed image decisions.

    The caller must validate candidate provenance independently. The reviewer
    is responsible for *actually seeing* the image; do not auto-create a PASS.
    """
    if not receipt_path:
        raise ValueError("visual_review_receipt_required_before_media_import")
    try:
        path = Path(receipt_path).resolve(strict=True)
        raw = path.read_bytes()
        review = json.loads(raw.decode("utf-8"))
    except (OSError, ValueError, UnicodeError) as exc:
        raise ValueError("visual_review_receipt_missing_or_invalid") from exc
    if not isinstance(review, dict) or review.get("schema_version") != 1:
        raise ValueError("visual_review_receipt_schema_invalid")
    policy_path = Path(__file__).resolve().parents[1] / "editorial_policy.json"
    try:
        current_policy = json.loads(policy_path.read_text(encoding="utf-8"))["featured_image_policy"]["version"]
    except (OSError, UnicodeError, ValueError, KeyError, TypeError) as exc:
        raise ValueError("visual_review_current_policy_unavailable") from exc
    if review.get("generator_policy_version") != current_policy:
        raise ValueError("visual_review_policy_version_stale_or_missing")
    sha_pattern = re.compile(r"[0-9a-f]{64}")
    if (any(not isinstance(v, str) or not sha_pattern.fullmatch(v)
            for v in (source_sha256, staged_sha256))
            or review.get("source_sha256") != source_sha256
            or review.get("staged_sha256") != staged_sha256
            or type(selected_candidate) is not int
            or review.get("selected_candidate") != selected_candidate
            or review.get("selection_mode") != selection_mode):
        raise ValueError("visual_review_receipt_candidate_or_sha_mismatch")
    task_id = review.get("task_id")
    if not isinstance(task_id, str) or not re.fullmatch(r"[a-zA-Z0-9_.-]{4,120}", task_id):
        raise ValueError("visual_review_task_identity_invalid")
    if review.get("review_result") != "pass" or review.get("issues") != []:
        raise ValueError("visual_review_not_accepted")
    if (review.get("review_actor") not in {"user", "agent-delegated", "independent-reviewer"}
            or review.get("review_method") not in {"human_visual", "vision_model", "direct_agent_visual"}):
        raise ValueError("visual_review_actor_or_method_invalid")
    if (review.get("review_method") == "vision_model"
            and not isinstance(review.get("model_result_ref"), str)):
        raise ValueError("visual_review_model_evidence_missing")
    if (review.get("selection_mode") == "user"
            and review.get("review_actor") == "agent-delegated"):
        raise ValueError("visual_review_actor_selection_conflict")
    check_results = review.get("checks")
    if (not isinstance(check_results, dict)
            or not REQUIRED_VISUAL_CHECKS.issubset(check_results)
            or any(check_results[k] is not True for k in REQUIRED_VISUAL_CHECKS)):
        raise ValueError("visual_review_checks_incomplete_or_failed")
    if not isinstance(review.get("reviewed_at"), str) or not review["reviewed_at"].strip():
        raise ValueError("visual_review_time_missing")
    if (not isinstance(review.get("comparison_set"), list)
            or not review["comparison_set"]
            or not isinstance(review.get("selection_reason"), str)
            or len(review["selection_reason"].strip()) < 12):
        raise ValueError("visual_review_comparison_or_reason_missing")
    comparison = review["comparison_set"]
    if (any(not isinstance(item, dict) or type(item.get("candidate_number")) is not int
            or not isinstance(item.get("source_sha256"), str)
            or not sha_pattern.fullmatch(item["source_sha256"]) for item in comparison)
            or not any(item["candidate_number"] == selected_candidate
                       and item["source_sha256"] == source_sha256 for item in comparison)):
        raise ValueError("visual_review_comparison_candidate_mismatch")
    evidence = review.get("review_evidence")
    if not isinstance(evidence, dict) or not isinstance(evidence.get("candidate_observations"), dict):
        raise ValueError("visual_review_observations_missing")
    for item in comparison:
        observation = evidence["candidate_observations"].get(str(item["candidate_number"]))
        if (not isinstance(observation, dict)
                or observation.get("source_sha256") != item["source_sha256"]
                or observation.get("observed_full_size") is not True
                or observation.get("observed_mobile_thumbnail") is not True
                or not isinstance(observation.get("full_size_observation"), str)
                or len(observation["full_size_observation"].strip()) < 12
                or not isinstance(observation.get("mobile_observation"), str)
                or len(observation["mobile_observation"].strip()) < 12):
            raise ValueError("visual_review_actual_observation_evidence_missing")
    selected = evidence["candidate_observations"][str(selected_candidate)]
    checks = selected.get("checks")
    if (not isinstance(checks, dict) or not REQUIRED_VISUAL_CHECKS.issubset(checks)
            or any(not isinstance(checks[name], dict) or checks[name].get("result") != "PASS"
                   or not isinstance(checks[name].get("evidence"), str)
                   or len(checks[name]["evidence"].strip()) < 12
                   for name in REQUIRED_VISUAL_CHECKS)):
        raise ValueError("visual_review_selected_evidence_incomplete")
    return {
        "review_result": "pass", "review_actor": review["review_actor"],
        "review_method": review["review_method"],
        "receipt_sha256": hashlib.sha256(raw).hexdigest(),
        "task_id": task_id,
    }
