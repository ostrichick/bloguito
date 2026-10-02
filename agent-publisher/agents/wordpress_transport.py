"""Explicit, context-scoped execution for WordPress/container operations."""

from contextlib import contextmanager
from contextvars import ContextVar
import subprocess

_runner = ContextVar('wordpress_command_runner', default=None)


def run_wordpress(command, *args, **kwargs):
    runner = _runner.get()
    return (runner or subprocess.run)(command, *args, **kwargs)


@contextmanager
def wordpress_transport(runner):
    if not callable(runner):
        raise TypeError('wordpress_transport_runner_required')
    token = _runner.set(runner)
    try:
        yield
    finally:
        _runner.reset(token)
