"""Lightweight internal timing metrics for editorial workflows.

Metrics are operational diagnostics only. They are written under the ignored
runtime data directory and never enter article bundles or reader-visible HTML.
"""

from __future__ import annotations

import json
import os
import sys
import time
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path

from agents.temporal_validation import KST


_current = ContextVar("editorial_workflow_metrics", default=None)

TIMING_CATEGORIES = frozenset({
    "validation",
    "source",
    "review",
    "wp",
    "browser",
    "image",
    "other",
})


def timing_category(name: str) -> str:
    """Map a stage name to a stable coarse workflow category.

    Existing callers can keep using ``timed('source_fetch')``; the mapping is
    deliberately name-based so category aggregation adds negligible overhead and
    does not require every orchestration path to change at once.
    """
    normalized = str(name or "").strip().lower().replace("-", "_")
    if normalized.startswith(("validation", "regression")):
        return "validation"
    if normalized.startswith("source") or normalized in {"fetch", "fetch_sources"}:
        return "source"
    if "review" in normalized:
        return "review"
    if normalized.startswith(("wp_", "wordpress")):
        return "wp"
    if normalized.startswith(("browser", "qa_")) or "browser_qa" in normalized:
        return "browser"
    if normalized.startswith(("image", "featured_image", "section_image", "designer")):
        return "image"
    return "other"


def summarize_timing_categories(rows) -> dict:
    """Aggregate category elapsed time across metrics rows, including old rows."""
    totals: dict[str, float] = {}
    run_count = 0
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        run_count += 1
        categories = row.get("timing_categories_ms")
        if not isinstance(categories, dict):
            categories = {}
            for name, value in (row.get("timings_ms") or {}).items():
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    category = timing_category(name)
                    categories[category] = categories.get(category, 0.0) + float(value)
        for category, value in categories.items():
            if category not in TIMING_CATEGORIES:
                continue
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                totals[category] = totals.get(category, 0.0) + float(value)
    totals = {key: round(value, 2) for key, value in sorted(totals.items())}
    means = {
        key: round(value / run_count, 2)
        for key, value in totals.items()
    } if run_count else {}
    return {
        "runs": run_count,
        "category_totals_ms": totals,
        "category_mean_per_run_ms": means,
    }


def _run_context() -> str:
    override = os.getenv("EDITORIAL_METRICS_CONTEXT")
    if override:
        return override.strip().lower()
    if any(name.startswith("test_") or ".test_" in name for name in sys.modules):
        return "test"
    return "live"


def _default_path(context: str | None = None) -> Path:
    override = os.getenv("EDITORIAL_METRICS_FILE")
    if override:
        return Path(override)
    filename = "workflow-metrics-test.jsonl" if (context or _run_context()) == "test" else "workflow-metrics.jsonl"
    return Path(__file__).resolve().parents[1] / "data" / "editorial_runs" / filename


class WorkflowMetrics:
    def __init__(self, action: str):
        self.action = action or "unknown"
        self.run_context = _run_context()
        self.started_at = datetime.now(KST).isoformat()
        self.started = time.perf_counter()
        self.timings_ms: dict[str, float] = {}
        self.timing_categories_ms: dict[str, float] = {}
        self.counters: dict[str, int] = {}
        self.status = "ok"
        self.error_type: str | None = None

    def add_timing(self, name: str, elapsed_seconds: float, *, category: str | None = None) -> None:
        category = category or timing_category(name)
        if category not in TIMING_CATEGORIES:
            raise ValueError("unknown_workflow_timing_category:" + str(category))
        elapsed_ms = elapsed_seconds * 1000
        self.timings_ms[name] = round(
            self.timings_ms.get(name, 0.0) + elapsed_ms,
            2,
        )
        self.timing_categories_ms[category] = round(
            self.timing_categories_ms.get(category, 0.0) + elapsed_ms,
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
            "run_context": self.run_context,
            "status": self.status,
            "error_type": self.error_type,
            "total_ms": round((time.perf_counter() - self.started) * 1000, 2),
            "timings_ms": self.timings_ms,
            "timing_categories_ms": self.timing_categories_ms,
            "counters": self.counters,
        }
        target = _default_path(self.run_context)
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
def timed(name: str, *, category: str | None = None):
    metrics = _current.get()
    started = time.perf_counter()
    try:
        yield
    finally:
        if metrics is not None:
            metrics.add_timing(name, time.perf_counter() - started, category=category)


def increment(name: str, amount: int = 1) -> None:
    metrics = _current.get()
    if metrics is not None:
        metrics.increment(name, amount)
