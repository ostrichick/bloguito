import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import scripts.editorial_cli_via_ssh as ssh_adapter


class ValidationSshIntegrationTests(unittest.TestCase):
    def test_edit_post_validation_runs_before_transport_is_installed(self):
        events = []
        plan = {
            'version': 1,
            'profile': 'quick-text',
            'plan_digest': 'a' * 64,
            'test_groups': ['core-safe-edit', 'fast-edit'],
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
                'profile': 'quick-text', 'tests_run': 36, 'selected_files': ['a.py'],
                'duration_ms': 12.5, 'status': 'passed',
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
                 patch.object(ssh_adapter.editorial_cli, 'main', side_effect=lambda: events.append('cli')):
                ssh_adapter.main()

        self.assertEqual(['validation', 'transport', 'cli'], events)


if __name__ == '__main__':
    unittest.main()
