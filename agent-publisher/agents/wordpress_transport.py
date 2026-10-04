"""Explicit, context-scoped execution for WordPress/container operations."""

from contextlib import contextmanager
from contextvars import ContextVar
import subprocess

_runner = ContextVar('wordpress_command_runner', default=None)


def _with_docker_stdin(command):
    """Keep stdin attached for direct ``docker exec`` calls that receive input.

    Docker does not forward the parent process stdin into an exec'd container
    unless ``-i`` is present.  Remote/editorial transports already choose their
    own safe stdin forwarding strategy, so this normalization is intentionally
    limited to the direct subprocess path.
    """
    if not isinstance(command, (list, tuple)):
        return command
    argv = list(command)
    if argv[:3] == ['sudo', 'docker', 'exec'] and (len(argv) < 4 or argv[3] != '-i'):
        argv.insert(3, '-i')
    return argv


def run_wordpress(command, *args, **kwargs):
    runner = _runner.get()
    if runner is not None:
        return runner(command, *args, **kwargs)
    if kwargs.get('input') is not None:
        command = _with_docker_stdin(command)
    return subprocess.run(command, *args, **kwargs)


@contextmanager
def wordpress_transport(runner):
    if not callable(runner):
        raise TypeError('wordpress_transport_runner_required')
    token = _runner.set(runner)
    try:
        yield
    finally:
        _runner.reset(token)
