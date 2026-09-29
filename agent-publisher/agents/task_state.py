"""Small resumable state records for long-running editorial mutations.

The state file intentionally stores hashes, IDs and phase names only. Article/source
content stays in the reviewed bundle and WordPress backups instead of being copied
into another runtime file.
"""

from __future__ import annotations

import json
import os
import re
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from agents.editorial import ROOT
from agents.temporal_validation import KST


STATE_VERSION = 1
_PHASES = (
    "baseline_read",
    "route_selected",
    "source_validation",
    "content_review",
    "image_validated",
    "wordpress_saved",
    "browser_qa",
)


def _now() -> str:
    return datetime.now(KST).isoformat()


def task_state_path(post_id: int, root: Path | None = None) -> Path:
    if not isinstance(post_id, int) or post_id <= 0:
        raise ValueError("valid_post_id_required")
    root = Path(root or ROOT)
    return root / "data" / "editorial_runs" / "task-state" / f"post-{post_id}.json"


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
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("version") != STATE_VERSION:
        raise ValueError("invalid_task_state")
    return payload


def start_task_state(
    post_id: int,
    *,
    action: str,
    edit_intent: str,
    baseline: dict[str, Any] | None = None,
    reuse: dict[str, Any] | None = None,
    artifacts: dict[str, str] | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    if not isinstance(action, str) or not action.strip():
        raise ValueError("task_action_required")
    if not isinstance(edit_intent, str) or not edit_intent.strip():
        raise ValueError("task_edit_intent_required")
    existing = load_task_state(post_id, root)
    if existing and existing.get("status") in {"in_progress", "saved_pending_qa"}:
        raise ValueError("active_task_state_exists: resume or complete the existing task first")
    now = _now()
    payload = {
        "version": STATE_VERSION,
        "task_id": f"{now.replace(':', '').replace('-', '')}-{post_id}",
        "post_id": post_id,
        "action": action.strip(),
        "edit_intent": edit_intent.strip(),
        "status": "in_progress",
        "started_at": now,
        "updated_at": now,
        "baseline": deepcopy(baseline or {}),
        "reuse": deepcopy(reuse or {}),
        "route": None,
        "route_reasons": [],
        "completed": {phase: False for phase in _PHASES},
        "pending": list(_PHASES),
        "artifacts": dict(artifacts or {}),
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
    artifacts: dict[str, str] | None = None,
    result: dict[str, Any] | None = None,
    status: str | None = None,
    error: str | None = None,
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
        payload["artifacts"].update(dict(artifacts))
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
    return update_task_state(post_id, status="complete", result=result, root=root)


def mark_browser_qa_complete(
    post_id: int,
    expected_content_sha256: str,
    *,
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
    return update_task_state(
        post_id,
        completed=["browser_qa"],
        status="complete",
        root=root,
    )


def fail_task_state(
    post_id: int,
    error: BaseException | str,
    *,
    blocked: bool = False,
    root: Path | None = None,
) -> dict[str, Any]:
    message = str(error)
    if len(message) > 1000:
        message = message[:997] + "..."
    return update_task_state(
        post_id,
        status="blocked" if blocked else "failed",
        error=message,
        root=root,
    )
