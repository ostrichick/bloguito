"""Run repository regression tests only when a validation plan requires them."""

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
_ACTIVE_ENV = "BLOGUITO_VALIDATION_TEST_ACTIVE"


def selected_test_files(plan: dict) -> list[str]:
    validate_validation_plan(plan)
    if not plan.get("full_regression_required"):
        return []
    return sorted(path.name for path in TESTS_DIR.glob("test_*.py"))


def _load_suite(files: list[str]) -> unittest.TestSuite:
    repo_root = str(ROOT)
    agent_root = str(ROOT / "agent-publisher")
    tests_root = str(TESTS_DIR)
    for path in (repo_root, agent_root, tests_root):
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
