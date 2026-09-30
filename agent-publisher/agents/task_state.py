"""Small resumable state records for long-running editorial mutations.

The state file intentionally stores hashes, IDs and phase names only. Article/source
content stays in the reviewed bundle and WordPress backups instead of being copied
into another runtime file.
"""

from __future__ import annotations

import json
import os
import re
import hashlib
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from agents.editorial import ROOT
from agents.temporal_validation import KST


STATE_VERSION = 4
LEGACY_STATE_VERSIONS = {1, 2, 3}
_PHASES = (
    "baseline_read",
    "route_selected",
    "source_validation",
    "content_review",
    "image_validated",
    "content_saved",
    "image_saved",
    "wordpress_saved",
    "browser_qa",
)

_AFTER_IMAGE_STEPS = (
    "image_generated",
    "image_saved_or_handed_off",
    "uploaded",
    "featured_image_set",
    "requested_content_or_meta_edits_done",
    "readback_verified",
    "content_sha_preserved",
)


def _now() -> str:
    return datetime.now(KST).isoformat()


def intent_sha256(edit_intent: str) -> str:
    if not isinstance(edit_intent, str) or not edit_intent.strip():
        raise ValueError("task_edit_intent_required")
    return hashlib.sha256(edit_intent.strip().encode("utf-8")).hexdigest()


def task_state_dir(post_id: int, root: Path | None = None) -> Path:
    if not isinstance(post_id, int) or post_id <= 0:
        raise ValueError("valid_post_id_required")
    root = Path(root or ROOT)
    return root / "data" / "editorial_runs" / "task-state" / f"post-{post_id}"


def task_state_path(post_id: int, root: Path | None = None) -> Path:
    return task_state_dir(post_id, root) / "current.json"


def after_image_checkpoint_path(post_id: int, root: Path | None = None) -> Path:
    return task_state_dir(post_id, root) / "after-image.json"


def _legacy_task_state_path(post_id: int, root: Path | None = None) -> Path:
    root = Path(root or ROOT)
    return root / "data" / "editorial_runs" / "task-state" / f"post-{post_id}.json"


def _file_sha256(path: Path) -> str | None:
    try:
        if path.is_file():
            return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        pass
    return None


def _normalize_artifacts(artifacts: dict[str, Any] | None) -> dict[str, Any]:
    result = {}
    for key, value in (artifacts or {}).items():
        if isinstance(value, str):
            path = Path(value)
            result[key] = {"path": value, "sha256": _file_sha256(path)}
        elif isinstance(value, dict):
            result[key] = deepcopy(value)
        else:
            raise ValueError("invalid_task_artifact")
    return result


def _migrate_state(payload: dict[str, Any]) -> dict[str, Any]:
    version = payload.get("version")
    if version == STATE_VERSION:
        return payload
    if version not in LEGACY_STATE_VERSIONS:
        raise ValueError("invalid_task_state")
    migrated = deepcopy(payload)
    migrated["version"] = STATE_VERSION
    if version == 1:
        raw_intent = migrated.pop("edit_intent", None)
        if raw_intent:
            migrated["edit_intent_sha256"] = intent_sha256(raw_intent)
    migrated.setdefault("edit_intent_sha256", None)
    migrated.setdefault("checkpoints", {})
    migrated["artifacts"] = _normalize_artifacts(migrated.get("artifacts", {}))
    completed = migrated.setdefault("completed", {})
    for phase in _PHASES:
        completed.setdefault(phase, False)
    if completed.get("wordpress_saved"):
        completed["content_saved"] = True
        # v1/v2 had no explicit image phase. A terminal WordPress save therefore
        # means that phase was either completed or intentionally skipped.
        completed["image_saved"] = True
    migrated.setdefault("qa_requirements", [])
    migrated.setdefault("validation_plan", {})
    migrated.setdefault("completion_requirements", [])
    migrated["pending"] = [phase for phase in _PHASES if not completed[phase]]
    return migrated


def completion_requirements_for_task(
    *,
    image_changed: bool,
    qa_requirements: list[str] | tuple[str, ...] | None,
) -> list[str]:
    """Return the phases that must finish before a user-facing task can close."""
    required = [
        "baseline_read",
        "route_selected",
        "source_validation",
        "content_review",
        "content_saved",
        "image_saved",
        "wordpress_saved",
    ]
    if image_changed:
        required.append("image_validated")
    if qa_requirements:
        required.append("browser_qa")
    return required


def _validate_completion_requirements(requirements) -> list[str]:
    values = list(requirements or [])
    unknown = [phase for phase in values if phase not in _PHASES]
    if unknown:
        raise ValueError("unknown_completion_requirement:" + ",".join(unknown))
    return list(dict.fromkeys(values))


def _missing_completion_requirements(payload: dict[str, Any], *, assume: set[str] | None = None) -> list[str]:
    assume = set(assume or set())
    completed = payload.get("completed", {})
    required = _validate_completion_requirements(payload.get("completion_requirements", []))
    return [phase for phase in required if not completed.get(phase) and phase not in assume]


def _validate_after_image_steps(values) -> list[str]:
    steps = list(values or [])
    unknown = [step for step in steps if step not in _AFTER_IMAGE_STEPS]
    if unknown:
        raise ValueError("unknown_after_image_step:" + ",".join(unknown))
    return list(dict.fromkeys(steps))


def load_after_image_checkpoint(post_id: int, root: Path | None = None) -> dict[str, Any] | None:
    path = after_image_checkpoint_path(post_id, root)
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("post_id") != post_id:
        raise ValueError("invalid_after_image_checkpoint")
    return payload


def write_after_image_checkpoint(
    post_id: int,
    *,
    remaining_steps: list[str] | tuple[str, ...],
    expected_content_sha256: str,
    expected_thumbnail_id: int,
    target_image_handle: str,
    completion_requirements: list[str] | tuple[str, ...],
    root: Path | None = None,
) -> dict[str, Any]:
    if not re.fullmatch(r"[0-9a-f]{64}", expected_content_sha256 or ""):
        raise ValueError("expected_content_sha256_required")
    if type(expected_thumbnail_id) is not int or expected_thumbnail_id <= 0:
        raise ValueError("expected_thumbnail_id_required")
    remaining_steps = [str(step).strip() for step in remaining_steps if str(step).strip()]
    if not remaining_steps:
        raise ValueError("after_image_remaining_steps_required")
    target_image_handle = str(target_image_handle or "").strip()
    if not target_image_handle or "\x00" in target_image_handle:
        raise ValueError("after_image_target_handle_required")
    completion_requirements = _validate_after_image_steps(completion_requirements)
    if not completion_requirements:
        raise ValueError("after_image_completion_requirements_required")
    existing = load_after_image_checkpoint(post_id, root)
    if existing and existing.get("status") == "in_progress":
        raise ValueError("active_after_image_checkpoint_exists")
    now = _now()
    payload = {
        "version": 1,
        "post_id": post_id,
        "status": "in_progress",
        "created_at": now,
        "updated_at": now,
        "expected_content_sha256": expected_content_sha256,
        "expected_thumbnail_id": expected_thumbnail_id,
        "target_image_handle": target_image_handle,
        "remaining_steps": remaining_steps,
        "completion_requirements": completion_requirements,
        "completed": {step: False for step in _AFTER_IMAGE_STEPS},
        "result": {},
    }
    return _write(after_image_checkpoint_path(post_id, root), payload)


def update_after_image_checkpoint(
    post_id: int,
    *,
    completed_steps: list[str] | tuple[str, ...] | None = None,
    target_image_handle: str | None = None,
    result: dict[str, Any] | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    path = after_image_checkpoint_path(post_id, root)
    payload = load_after_image_checkpoint(post_id, root)
    if payload is None:
        raise ValueError("after_image_checkpoint_missing")
    for step in _validate_after_image_steps(completed_steps):
        payload["completed"][step] = True
    if target_image_handle is not None:
        target_image_handle = str(target_image_handle).strip()
        if not target_image_handle or "\x00" in target_image_handle:
            raise ValueError("after_image_target_handle_required")
        payload["target_image_handle"] = target_image_handle
    if result:
        payload["result"].update(deepcopy(result))
    missing = [
        step for step in payload.get("completion_requirements", [])
        if not payload.get("completed", {}).get(step)
    ]
    payload["status"] = "complete" if not missing else "in_progress"
    payload["updated_at"] = _now()
    return _write(path, payload)


def assert_after_image_complete(
    post_id: int,
    root: Path | None = None,
    *,
    expected_content_sha256: str | None = None,
) -> None:
    payload = load_after_image_checkpoint(post_id, root)
    if not payload or payload.get("status") == "complete":
        return
    if (expected_content_sha256 is not None
            and payload.get("expected_content_sha256") != expected_content_sha256):
        return
    missing = [
        step for step in payload.get("completion_requirements", [])
        if not payload.get("completed", {}).get(step)
    ]
    raise ValueError("after_image_steps_incomplete:" + ",".join(missing))


def _write(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.chmod(temporary, 0o600)
    temporary.replace(path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return payload


def load_task_state(post_id: int, root: Path | None = None) -> dict[str, Any] | None:
    path = task_state_path(post_id, root)
    legacy = _legacy_task_state_path(post_id, root)
    source = path if path.is_file() else legacy
    if not source.is_file():
        return None
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("invalid_task_state")
    return _migrate_state(payload)


def _archive_state(post_id: int, payload: dict[str, Any], root: Path | None = None) -> Path:
    directory = task_state_dir(post_id, root) / "archive"
    directory.mkdir(parents=True, exist_ok=True)
    task_id = re.sub(r"[^A-Za-z0-9_.-]", "_", str(payload.get("task_id") or _now()))
    target = directory / f"{task_id}.json"
    if target.exists():
        suffix = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()[:8]
        target = directory / f"{task_id}-{suffix}.json"
    _write(target, payload)
    return target


def start_task_state(
    post_id: int,
    *,
    action: str,
    edit_intent: str,
    baseline: dict[str, Any] | None = None,
    reuse: dict[str, Any] | None = None,
    artifacts: dict[str, Any] | None = None,
    qa_requirements: list[str] | tuple[str, ...] | None = None,
    validation_plan: dict[str, Any] | None = None,
    completion_requirements: list[str] | tuple[str, ...] | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    if not isinstance(action, str) or not action.strip():
        raise ValueError("task_action_required")
    edit_intent_digest = intent_sha256(edit_intent)
    existing = load_task_state(post_id, root)
    if existing and existing.get("status") in {"in_progress", "saved_pending_qa"}:
        raise ValueError("active_task_state_exists: resume or complete the existing task first")
    if existing:
        _archive_state(post_id, existing, root)
    now = _now()
    payload = {
        "version": STATE_VERSION,
        "task_id": f"{now.replace(':', '').replace('-', '')}-{post_id}",
        "post_id": post_id,
        "action": action.strip(),
        "edit_intent_sha256": edit_intent_digest,
        "status": "in_progress",
        "started_at": now,
        "updated_at": now,
        "baseline": deepcopy(baseline or {}),
        "reuse": deepcopy(reuse or {}),
        "route": None,
        "route_reasons": [],
        "completed": {phase: False for phase in _PHASES},
        "pending": list(_PHASES),
        "artifacts": _normalize_artifacts(artifacts),
        "qa_requirements": sorted(set(qa_requirements or [])),
        "validation_plan": deepcopy(validation_plan or {}),
        "completion_requirements": _validate_completion_requirements(completion_requirements),
        "checkpoints": {},
        "result": {},
        "error": None,
    }
    payload["pending"] = [phase for phase in _PHASES if not payload["completed"][phase]]
    return _write(task_state_path(post_id, root), payload)


def update_task_state(
    post_id: int,
    *,
    completed: list[str] | tuple[str, ...] | None = None,
    route: str | None = None,
    route_reasons: list[str] | None = None,
    reuse: dict[str, Any] | None = None,
    artifacts: dict[str, Any] | None = None,
    qa_requirements: list[str] | tuple[str, ...] | None = None,
    validation_plan: dict[str, Any] | None = None,
    completion_requirements: list[str] | tuple[str, ...] | None = None,
    checkpoints: dict[str, Any] | None = None,
    result: dict[str, Any] | None = None,
    status: str | None = None,
    error: str | dict[str, Any] | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    path = task_state_path(post_id, root)
    payload = load_task_state(post_id, root)
    if payload is None:
        raise ValueError("task_state_missing")
    if completed:
        unknown = [phase for phase in completed if phase not in payload["completed"]]
        if unknown:
            raise ValueError("unknown_task_phase:" + ",".join(unknown))
        for phase in completed:
            payload["completed"][phase] = True
    if route is not None:
        payload["route"] = route
    if route_reasons is not None:
        payload["route_reasons"] = list(route_reasons)
    if reuse:
        payload["reuse"].update(deepcopy(reuse))
    if artifacts:
        payload["artifacts"].update(_normalize_artifacts(artifacts))
    if qa_requirements is not None:
        payload["qa_requirements"] = sorted(set(qa_requirements))
    if validation_plan is not None:
        payload["validation_plan"] = deepcopy(validation_plan)
    if completion_requirements is not None:
        payload["completion_requirements"] = _validate_completion_requirements(completion_requirements)
    if checkpoints:
        payload.setdefault("checkpoints", {}).update(deepcopy(checkpoints))
    if result:
        payload["result"].update(deepcopy(result))
    if status is not None:
        if status not in {"in_progress", "saved_pending_qa", "complete", "blocked", "failed"}:
            raise ValueError("invalid_task_status")
        payload["status"] = status
    if error is not None:
        payload["error"] = error
    payload["pending"] = [phase for phase in _PHASES if not payload["completed"][phase]]
    payload["updated_at"] = _now()
    return _write(path, payload)


def complete_task_state(
    post_id: int,
    *,
    result: dict[str, Any] | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    state = load_task_state(post_id, root)
    if state is None:
        raise ValueError("task_state_missing")
    missing = _missing_completion_requirements(state)
    if missing:
        raise ValueError("task_completion_guard_incomplete:" + ",".join(missing))
    expected_sha = (
        state.get("result", {}).get("desired_content_sha256")
        or state.get("baseline", {}).get("expected_content_sha256")
    )
    assert_after_image_complete(post_id, root, expected_content_sha256=expected_sha)
    return update_task_state(post_id, status="complete", result=result, root=root)


def mark_browser_qa_complete(
    post_id: int,
    expected_content_sha256: str,
    *,
    completed_scopes: list[str] | tuple[str, ...] | None = None,
    observed_thumbnail_id: int | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    """Close a saved task only after the caller has completed browser QA."""
    if not re.fullmatch(r"[0-9a-f]{64}", expected_content_sha256 or ""):
        raise ValueError("expected_content_sha256_required")
    state = load_task_state(post_id, root)
    if not state or state.get("status") != "saved_pending_qa":
        raise ValueError("saved_pending_qa_task_required")
    if not state.get("completed", {}).get("wordpress_saved"):
        raise ValueError("wordpress_save_not_completed")
    expected = (
        state.get("result", {}).get("desired_content_sha256")
        or state.get("baseline", {}).get("expected_content_sha256")
    )
    if expected != expected_content_sha256:
        raise ValueError("browser_qa_content_sha_mismatch")
    from agents.qa_scope import validate_qa_scopes
    completed_scopes = validate_qa_scopes(completed_scopes)
    required = set(state.get("qa_requirements", []))
    if required - set(completed_scopes):
        raise ValueError("browser_qa_scope_incomplete:" + ",".join(sorted(required - set(completed_scopes))))
    if "featured-image" in required:
        expected_thumbnail = (
            state.get("result", {}).get("attachment_id")
            or (state.get("result", {}).get("image_phase") or {}).get("attachment_id")
            or (state.get("checkpoints", {}).get("image_outcome") or {}).get("attachment_id")
        )
        if (type(observed_thumbnail_id) is not int or type(expected_thumbnail) is not int
                or observed_thumbnail_id != expected_thumbnail):
            raise ValueError("browser_qa_thumbnail_mismatch")
    missing = _missing_completion_requirements(state, assume={"browser_qa"})
    if missing:
        raise ValueError("task_completion_guard_incomplete:" + ",".join(missing))
    assert_after_image_complete(
        post_id, root, expected_content_sha256=expected_content_sha256)
    return update_task_state(
        post_id,
        completed=["browser_qa"],
        status="complete",
        result={
            "qa_completed_scopes": completed_scopes,
            "qa_observed_thumbnail_id": observed_thumbnail_id,
        },
        root=root,
    )


def fail_task_state(
    post_id: int,
    error: BaseException | str,
    *,
    blocked: bool = False,
    root: Path | None = None,
) -> dict[str, Any]:
    error_type = type(error).__name__ if isinstance(error, BaseException) else "TaskError"
    message = str(error)
    code = re.sub(r"[^a-zA-Z0-9_.:-]+", "_", message.strip())[:160] or "unknown_error"
    return update_task_state(
        post_id,
        status="blocked" if blocked else "failed",
        error={"type": error_type, "code": code},
        root=root,
    )
