"""Lightweight internal timing metrics for editorial workflows.

Metrics are operational diagnostics only. They are written under the ignored
runtime data directory and never enter article bundles or reader-visible HTML.
"""

from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path

from agents.temporal_validation import KST


_current = ContextVar("editorial_workflow_metrics", default=None)


def _default_path() -> Path:
    override = os.getenv("EDITORIAL_METRICS_FILE")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[1] / "data" / "editorial_runs" / "workflow-metrics.jsonl"


class WorkflowMetrics:
    def __init__(self, action: str):
        self.action = action or "unknown"
        self.started_at = datetime.now(KST).isoformat()
        self.started = time.perf_counter()
        self.timings_ms: dict[str, float] = {}
        self.counters: dict[str, int] = {}
        self.status = "ok"
        self.error_type: str | None = None

    def add_timing(self, name: str, elapsed_seconds: float) -> None:
        self.timings_ms[name] = round(
            self.timings_ms.get(name, 0.0) + elapsed_seconds * 1000,
            2,
        )

    def increment(self, name: str, amount: int = 1) -> None:
        self.counters[name] = self.counters.get(name, 0) + amount

    def finish(self, *, status: str = "ok", error_type: str | None = None) -> dict:
        self.status = status
        self.error_type = error_type
        payload = {
            "started_at": self.started_at,
            "finished_at": datetime.now(KST).isoformat(),
            "action": self.action,
            "status": self.status,
            "error_type": self.error_type,
            "total_ms": round((time.perf_counter() - self.started) * 1000, 2),
            "timings_ms": self.timings_ms,
            "counters": self.counters,
        }
        target = _default_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
        return payload


@contextmanager
def workflow_run(action: str):
    metrics = WorkflowMetrics(action)
    token = _current.set(metrics)
    try:
        yield metrics
    except BaseException as error:
        metrics.finish(status="error", error_type=type(error).__name__)
        raise
    else:
        metrics.finish()
    finally:
        _current.reset(token)


@contextmanager
def timed(name: str):
    metrics = _current.get()
    started = time.perf_counter()
    try:
        yield
    finally:
        if metrics is not None:
            metrics.add_timing(name, time.perf_counter() - started)


def increment(name: str, amount: int = 1) -> None:
    metrics = _current.get()
    if metrics is not None:
        metrics.increment(name, amount)
