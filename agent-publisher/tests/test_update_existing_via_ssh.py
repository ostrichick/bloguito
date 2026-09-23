"""Transport restrictions for the opt-in editorial SSH bridge."""
import importlib.util
import pathlib
import subprocess
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('reviewed_ssh_bridge', ROOT / 'scripts/update_existing_via_ssh.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class RemoteReviewBridgeTests(unittest.TestCase):
    def setUp(self):
        self.run = MODULE.make_transport('bloguito', 137, '<p>한국어 & test</p>')
        self.base = ['sudo', 'docker', 'exec', 'wordpress_app', 'wp']

    def test_list_get_read_only(self):
        with patch.object(MODULE, '_RUN') as host:
            self.run(self.base + MODULE._LIST_ARGS, check=True, capture_output=True, text=True)
            command = host.call_args.args[0]
            self.assertEqual(command[:6], ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10', 'bloguito'])
            self.assertIn('post list', command[6])
            self.assertEqual(host.call_args.kwargs['encoding'], 'utf-8')
            self.run(self.base + ['post', 'get', '137', '--format=json', '--allow-root'])
            self.assertIn('post get 137', host.call_args.args[0][6])

    def test_only_matching_rendered_post_update_allowed(self):
        with patch.object(MODULE, '_RUN') as host:
            self.run(self.base + ['post', 'update', '137', '--post_content=<p>한국어 & test</p>',
                                  '--post_excerpt=본문', '--allow-root'])
            self.assertIn("'--post_content=<p>한국어 & test</p>'", host.call_args.args[0][6])
            self.assertIn("'--post_excerpt=본문'", host.call_args.args[0][6])
            for command in (
                ['post', 'update', '138', '--post_content=<p>한국어 & test</p>', '--allow-root'],
                ['post', 'update', '137', '--post_content=FORGED', '--allow-root'],
                ['post', 'delete', '137', '--force', '--allow-root'],
                ['post', 'update', '137', '--post_content=<p>한국어 & test</p>', '--post_status=draft', '--allow-root'],
            ):
                with self.assertRaises(ValueError):
                    self.run(self.base + command)
            self.assertEqual(host.call_count, 1)

    def test_rejects_non_wordpress_command_and_unsafe_hosts(self):
        with self.assertRaises(ValueError):
            MODULE.make_transport('bloguito; rm -rf /', 137, 'x')
        with self.assertRaises(ValueError):
            self.run(['bash', '-c', 'true'])
        with self.assertRaises(ValueError):
            self.run(self.base + ['post', 'get', '138', '--format=json', '--allow-root'])


if __name__ == '__main__':
    unittest.main()
