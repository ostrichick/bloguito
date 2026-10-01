import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import scripts.editorial_cli_via_ssh as ssh_adapter


class ValidationSshIntegrationTests(unittest.TestCase):
    def test_edit_post_repository_regression_runs_before_transport_is_installed(self):
        events = []
        plan = {
            'version': 1,
            'profile': 'full-regression',
            'plan_digest': 'a' * 64,
            'test_groups': ['full-regression'],
        }
        decision = {
            'route': 'fast',
            'reasons': [],
            'target_status': 'draft',
            'validation_plan': plan,
        }

        def validate(received, **_kwargs):
            events.append('validation')
            self.assertIs(plan, received)
            return {
                'profile': 'full-regression', 'tests_run': 10, 'selected_files': ['a.py'],
                'duration_ms': 2.0, 'status': 'passed',
            }

        def make_transport(*_args, **_kwargs):
            events.append('transport')
            return lambda *_a, **_k: None

        with tempfile.TemporaryDirectory() as folder:
            bundle = Path(folder) / 'bundle.json'
            bundle.write_text(json.dumps({}), encoding='utf-8')
            argv = [
                'editorial_cli_via_ssh.py', '--ssh-host', 'bloguito', '--',
                'edit-post', str(bundle), '--post-id', '641',
                '--expected-content-sha256', '0' * 64, '--confirm-update',
                '--edit-intent', '표현만 정리',
            ]
            with patch.object(sys, 'argv', argv), \
                 patch.object(ssh_adapter, 'resolve_transport', return_value=SimpleNamespace(
                     mode='direct', host='bloguito', user=None, wsl_distro=None)), \
                 patch('agents.edit_post.classify_reviewed_post_route', return_value=decision), \
                 patch('agents.validation_runner.require_validation_success', side_effect=validate), \
                 patch.object(ssh_adapter, 'make_transport', side_effect=make_transport), \
                 patch.object(ssh_adapter.editorial_cli, 'main', side_effect=lambda: (
                     self.assertIs(decision, ssh_adapter.editorial_cli._prepared_edit_decision.get()),
                     events.append('cli'),
                 )):
                ssh_adapter.main()

        self.assertEqual(['validation', 'transport', 'cli'], events)

    def test_edit_post_content_plan_skips_python_regression(self):
        events = []
        decision = {
            'route': 'fast',
            'reasons': [],
            'target_status': 'draft',
            'validation_plan': {
                'version': 1,
                'profile': 'quick-text',
                'plan_digest': 'b' * 64,
                'test_groups': [],
            },
        }
        with tempfile.TemporaryDirectory() as folder:
            bundle = Path(folder) / 'bundle.json'
            bundle.write_text(json.dumps({}), encoding='utf-8')
            argv = [
                'editorial_cli_via_ssh.py', '--ssh-host', 'bloguito', '--',
                'edit-post', str(bundle), '--post-id', '641',
                '--expected-content-sha256', '0' * 64, '--confirm-update',
                '--edit-intent', '표현만 정리',
            ]
            with patch.object(sys, 'argv', argv), \
                 patch.object(ssh_adapter, 'resolve_transport', return_value=SimpleNamespace(
                     mode='direct', host='bloguito', user=None, wsl_distro=None)), \
                 patch('agents.edit_post.classify_reviewed_post_route', return_value=decision), \
                 patch('agents.validation_runner.require_validation_success') as validate, \
                 patch.object(ssh_adapter, 'make_transport', side_effect=lambda *_a, **_k: (
                     events.append('transport') or (lambda *_x, **_y: None))), \
                 patch.object(ssh_adapter.editorial_cli, 'main', side_effect=lambda: events.append('cli')):
                ssh_adapter.main()
        validate.assert_not_called()
        self.assertEqual(['transport', 'cli'], events)


if __name__ == '__main__':
    unittest.main()
