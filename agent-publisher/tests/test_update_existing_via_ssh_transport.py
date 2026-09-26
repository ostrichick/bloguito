import importlib.util
import json
import subprocess
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[2] / 'scripts' / 'update_existing_via_ssh.py'


def load_module():
    spec = importlib.util.spec_from_file_location('update_existing_via_ssh_tested', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class UpdateExistingViaSshTransportTests(unittest.TestCase):
    def test_wsl_route_attempts_ssh_directly_without_pre_ping(self):
        module = load_module()
        calls = []

        def fake_run(args, **kwargs):
            calls.append((list(args), dict(kwargs)))
            return subprocess.CompletedProcess(args, 0, stdout='[]', stderr='')

        module._RUN = fake_run
        run = module.make_transport(
            '100.99.177.119',
            139,
            'rendered',
            wsl_distro='Ubuntu-24.04',
            ssh_user='ubuntu',
        )
        result = run(module._PREFIX + module._LIST_ARGS,
                     capture_output=True, text=True, check=True)

        self.assertEqual(0, result.returncode)
        self.assertEqual(
            ['wsl.exe', '-d', 'Ubuntu-24.04', '--', 'ssh',
             '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10',
             'ubuntu@100.99.177.119'],
            calls[0][0][:-1],
        )
        self.assertTrue(calls[0][0][-1].startswith(
            'sudo docker exec wordpress_app wp post list '))
        self.assertEqual(1, len(calls))

    def test_wsl_route_diagnoses_only_after_ssh_failure_and_preserves_exception(self):
        module = load_module()
        calls = []
        original = subprocess.CalledProcessError(255, ['ssh'])

        def fake_run(args, **kwargs):
            calls.append((list(args), dict(kwargs)))
            if len(calls) == 1:
                raise original
            return subprocess.CompletedProcess(args, 0, stdout='', stderr='')

        module._RUN = fake_run
        run = module.make_transport(
            '100.99.177.119',
            139,
            'rendered',
            wsl_distro='Ubuntu-24.04',
            ssh_user='ubuntu',
        )

        with self.assertRaises(subprocess.CalledProcessError) as raised:
            run(module._PREFIX + module._LIST_ARGS,
                capture_output=True, text=True, check=True)

        self.assertIs(original, raised.exception)
        self.assertEqual('ssh', calls[0][0][4])
        self.assertEqual(
            ['wsl.exe', '-d', 'Ubuntu-24.04', '--', 'tailscale', 'status'],
            calls[1][0],
        )
        self.assertEqual(
            ['wsl.exe', '-d', 'Ubuntu-24.04', '--', 'tailscale', 'ping', '-c', '1',
             '100.99.177.119'],
            calls[2][0],
        )

    def test_wsl_route_does_not_repeat_diagnostics_after_connectivity_recovers(self):
        module = load_module()
        calls = []
        ssh_attempts = 0

        def fake_run(args, **kwargs):
            nonlocal ssh_attempts
            calls.append((list(args), dict(kwargs)))
            if 'ssh' in args:
                ssh_attempts += 1
                if ssh_attempts in (1, 3):
                    raise subprocess.CalledProcessError(255, args)
            return subprocess.CompletedProcess(args, 0, stdout='[]', stderr='')

        module._RUN = fake_run
        run = module.make_transport(
            '100.99.177.119',
            139,
            'rendered',
            wsl_distro='Ubuntu-24.04',
            ssh_user='ubuntu',
        )

        with self.assertRaises(subprocess.CalledProcessError):
            run(module._PREFIX + module._LIST_ARGS,
                capture_output=True, text=True, check=True)
        run(module._PREFIX + module._LIST_ARGS,
            capture_output=True, text=True, check=True)
        with self.assertRaises(subprocess.CalledProcessError):
            run(module._PREFIX + module._LIST_ARGS,
                capture_output=True, text=True, check=True)

        diagnostic_calls = [args for args, _ in calls if 'tailscale' in args]
        self.assertEqual(2, len(diagnostic_calls))

    def test_remote_wordpress_error_does_not_trigger_tailscale_diagnostics(self):
        module = load_module()
        calls = []

        def fake_run(args, **kwargs):
            calls.append((list(args), dict(kwargs)))
            return subprocess.CompletedProcess(args, 1, stdout='', stderr='wp error')

        module._RUN = fake_run
        run = module.make_transport(
            '100.99.177.119',
            139,
            'rendered',
            wsl_distro='Ubuntu-24.04',
            ssh_user='ubuntu',
        )
        result = run(module._PREFIX + module._LIST_ARGS,
                     capture_output=True, text=True, check=False)

        self.assertEqual(1, result.returncode)
        self.assertEqual([], [args for args, _ in calls if 'tailscale' in args])

    def test_rejects_unsafe_wsl_transport_identifiers(self):
        module = load_module()
        with self.assertRaisesRegex(ValueError, 'invalid_ssh_user'):
            module.make_transport('100.99.177.119', 139, 'x', ssh_user='ubuntu;id')
        with self.assertRaisesRegex(ValueError, 'invalid_wsl_distro'):
            module.make_transport('100.99.177.119', 139, 'x', wsl_distro='Ubuntu 24.04')

    def test_lightweight_inventory_allows_candidate_read_but_not_write(self):
        module = load_module()
        inventory = [{
            'ID': 700,
            'post_title': 'candidate',
            'post_status': 'publish',
            'content_sha256': '0' * 64,
            'content_urls': ['https://example.org/a'],
        }]

        def fake_run(args, **kwargs):
            remote = args[-1]
            if ' wp eval ' in remote:
                return subprocess.CompletedProcess(args, 0, stdout=json.dumps(inventory), stderr='')
            return subprocess.CompletedProcess(args, 0, stdout='{}', stderr='')

        module._RUN = fake_run
        run = module.make_transport('bloguito', 139, 'rendered')
        run(module._PREFIX + module._LIGHT_INVENTORY_ARGS,
            capture_output=True, text=True, check=True)
        run(module._PREFIX + ['post', 'get', '700', '--format=json', '--allow-root'],
            capture_output=True, text=True, check=True)
        with self.assertRaisesRegex(ValueError, 'unexpected_wordpress_write_arguments'):
            run(module._PREFIX + ['post', 'update', '700', '--post_content=x', '--allow-root'])


if __name__ == '__main__':
    unittest.main()
