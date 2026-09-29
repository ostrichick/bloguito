"""Run the regression-test subset selected by :mod:`validation_router`."""

from __future__ import annotations

import importlib
import io
import json
import os
import sys
import time
import unittest
from pathlib import Path

from agents.validation_router import validate_validation_plan
from agents.workflow_metrics import WorkflowMetrics


ROOT = Path(__file__).resolve().parents[2]
TESTS_DIR = ROOT / "agent-publisher" / "tests"
MANIFEST_FILE = TESTS_DIR / "test_groups.json"
_ACTIVE_ENV = "BLOGUITO_VALIDATION_TEST_ACTIVE"


def load_test_manifest(path: Path = MANIFEST_FILE) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("version") != 1:
        raise ValueError("invalid_validation_test_manifest")
    validate_test_manifest(payload)
    return payload


def validate_test_manifest(manifest: dict) -> None:
    groups = manifest.get("groups")
    full_only = manifest.get("full_only")
    post_selectors = manifest.get("post_selectors", {})
    if not isinstance(groups, dict) or not isinstance(full_only, list) or not isinstance(post_selectors, dict):
        raise ValueError("invalid_validation_test_manifest")

    existing = {path.name for path in TESTS_DIR.glob("test_*.py")}
    grouped = set()
    for name, files in groups.items():
        if not isinstance(name, str) or not isinstance(files, list) or not files:
            raise ValueError("invalid_validation_test_group:" + str(name))
        for filename in files:
            if not isinstance(filename, str) or filename not in existing:
                raise ValueError("unknown_validation_test_file:" + str(filename))
            grouped.add(filename)
    full_only_set = set(full_only)
    if not full_only_set.issubset(existing):
        missing = sorted(full_only_set - existing)
        raise ValueError("unknown_full_only_test_file:" + ",".join(missing))
    overlap = grouped & full_only_set
    if overlap:
        raise ValueError("validation_test_manifest_overlap:" + ",".join(sorted(overlap)))
    covered = grouped | full_only_set
    if covered != existing:
        missing = sorted(existing - covered)
        extra = sorted(covered - existing)
        raise ValueError(
            "validation_test_manifest_coverage:" + json.dumps(
                {"missing": missing, "extra": extra}, ensure_ascii=False, sort_keys=True))
    for post_id, files in post_selectors.items():
        if not str(post_id).isdigit() or not isinstance(files, list) or not files:
            raise ValueError("invalid_validation_post_selector:" + str(post_id))
        unknown = set(files) - existing
        if unknown:
            raise ValueError("unknown_validation_post_selector_file:" + ",".join(sorted(unknown)))


def selected_test_files(plan: dict, manifest: dict | None = None) -> list[str]:
    validate_validation_plan(plan)
    manifest = manifest or load_test_manifest()
    if plan.get("full_regression_required") or "full-regression" in plan.get("test_groups", []):
        return sorted(path.name for path in TESTS_DIR.glob("test_*.py"))
    groups = manifest["groups"]
    selected = set()
    for group in plan.get("test_groups", []):
        if group not in groups:
            raise ValueError("unknown_validation_test_group:" + str(group))
        selected.update(groups[group])
    post_id = (plan.get("binding") or {}).get("post_id")
    if post_id is not None:
        selected.update(manifest.get("post_selectors", {}).get(str(post_id), []))
    return sorted(selected)


def _load_suite(files: list[str]) -> unittest.TestSuite:
    agent_root = str(ROOT / "agent-publisher")
    tests_root = str(TESTS_DIR)
    for path in (agent_root, tests_root):
        if path not in sys.path:
            sys.path.insert(0, path)
    suite = unittest.TestSuite()
    for filename in files:
        module_name = Path(filename).stem
        module = importlib.import_module(module_name)
        suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(module))
    return suite


def run_validation_plan(plan: dict, *, stream=None, verbosity: int = 1) -> dict:
    """Run only the regression files selected by a validation plan.

    The environment marker prevents CLI subprocesses created by unit tests from
    recursively launching another validation suite.
    """
    validate_validation_plan(plan)
    files = selected_test_files(plan)
    if not files:
        return {
            "status": "passed",
            "profile": plan.get("profile"),
            "plan_digest": plan.get("plan_digest"),
            "test_groups": list(plan.get("test_groups", [])),
            "selected_files": [],
            "tests_run": 0,
            "failures": 0,
            "errors": 0,
            "skipped": 0,
            "duration_ms": 0.0,
        }

    suite = _load_suite(files)
    started = time.perf_counter()
    metrics = WorkflowMetrics("run-validation")
    metrics.increment("validation_test_files", len(files))
    metrics.increment("validation_test_groups", len(plan.get("test_groups", [])))
    metrics.increment("validation_profile_" + str(plan.get("profile", "unknown")).replace("-", "_"))
    previous = os.environ.get(_ACTIVE_ENV)
    os.environ[_ACTIVE_ENV] = "1"
    try:
        result = unittest.TextTestRunner(
            stream=stream or sys.stderr,
            verbosity=verbosity,
        ).run(suite)
    finally:
        if previous is None:
            os.environ.pop(_ACTIVE_ENV, None)
        else:
            os.environ[_ACTIVE_ENV] = previous
    receipt = {
        "status": "passed" if result.wasSuccessful() else "failed",
        "profile": plan.get("profile"),
        "plan_digest": plan.get("plan_digest"),
        "test_groups": list(plan.get("test_groups", [])),
        "selected_files": files,
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(getattr(result, "skipped", [])),
        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
    }
    metrics.add_timing("validation_tests", receipt["duration_ms"] / 1000)
    metrics.increment("validation_tests", result.testsRun)
    metrics.increment("validation_failures", len(result.failures) + len(result.errors))
    metrics.finish(
        status="ok" if result.wasSuccessful() else "error",
        error_type=None if result.wasSuccessful() else "ValidationTestFailure",
    )
    return receipt


def require_validation_success(plan: dict, *, stream=None, verbosity: int = 1) -> dict:
    receipt = run_validation_plan(plan, stream=stream, verbosity=verbosity)
    if receipt["status"] != "passed":
        raise RuntimeError(
            "selected_validation_tests_failed:" + json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return receipt


def validation_tests_active() -> bool:
    return os.getenv(_ACTIVE_ENV) == "1"
