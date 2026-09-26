import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[2] / 'scripts' / 'editorial_cli_via_ssh.py'


def load_module():
    spec = importlib.util.spec_from_file_location('editorial_cli_via_ssh_tested', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class EditorialCliViaSshTransportTests(unittest.TestCase):
    def test_successful_inventory_uses_direct_ssh_without_tailscale_probe(self):
        module = load_module()
        calls = []

        def fake_run(args, **kwargs):
            calls.append((list(args), dict(kwargs)))
            return subprocess.CompletedProcess(args, 0, stdout='[]', stderr='')

        module._RUN = fake_run
        transport = module.make_transport(
            'revise-draft', {463}, '100.99.177.119',
            ssh_user='ubuntu', wsl_distro='Ubuntu-24.04')
        result = transport(module._WP_PREFIX + module._LIST_ARGS,
                           capture_output=True, text=True, check=True)
        self.assertEqual(0, result.returncode)
        self.assertEqual(1, len(calls))
        self.assertIn('ssh', calls[0][0])
        self.assertNotIn('tailscale', calls[0][0])

    def test_failed_ssh_diagnoses_tailscale_only_once(self):
        module = load_module()
        calls = []
        original = subprocess.CalledProcessError(255, ['ssh'])

        def fake_run(args, **kwargs):
            calls.append((list(args), dict(kwargs)))
            if 'ssh' in args:
                raise original
            return subprocess.CompletedProcess(args, 0, stdout='', stderr='')

        module._RUN = fake_run
        transport = module.make_transport(
            'revise-draft', {463}, '100.99.177.119',
            ssh_user='ubuntu', wsl_distro='Ubuntu-24.04')
        for _ in range(2):
            with self.assertRaises(subprocess.CalledProcessError):
                transport(module._WP_PREFIX + module._LIST_ARGS,
                          capture_output=True, text=True, check=True)
        self.assertEqual(2, len([args for args, _ in calls if 'tailscale' in args]))

    def test_remote_wordpress_error_does_not_trigger_tailscale_diagnostics(self):
        module = load_module()
        calls = []

        def fake_run(args, **kwargs):
            calls.append((list(args), dict(kwargs)))
            return subprocess.CompletedProcess(args, 1, stdout='', stderr='wp error')

        module._RUN = fake_run
        transport = module.make_transport(
            'revise-draft', {463}, '100.99.177.119',
            ssh_user='ubuntu', wsl_distro='Ubuntu-24.04')
        result = transport(module._WP_PREFIX + module._LIST_ARGS,
                           capture_output=True, text=True, check=False)
        self.assertEqual(1, result.returncode)
        self.assertEqual([], [args for args, _ in calls if 'tailscale' in args])

    def test_revise_draft_allows_only_exact_target_and_fields(self):
        module = load_module()
        module._RUN = lambda args, **kwargs: subprocess.CompletedProcess(args, 0, stdout='', stderr='')
        transport = module.make_transport('revise-draft', {463}, 'bloguito')
        transport(module._WP_PREFIX + [
            'post', 'update', '463', '--post_content=reviewed', '--post_excerpt=summary', '--allow-root'])
        with self.assertRaisesRegex(ValueError, 'unexpected_wordpress_update_target'):
            transport(module._WP_PREFIX + [
                'post', 'update', '464', '--post_content=reviewed', '--post_excerpt=summary', '--allow-root'])
        with self.assertRaisesRegex(ValueError, 'unexpected_wordpress_update_flags'):
            transport(module._WP_PREFIX + [
                'post', 'update', '463', '--post_status=publish', '--allow-root'])

    def test_promote_allows_only_publish_status(self):
        module = load_module()
        module._RUN = lambda args, **kwargs: subprocess.CompletedProcess(args, 0, stdout='', stderr='')
        transport = module.make_transport('promote-draft', {463}, 'bloguito')
        transport(module._WP_PREFIX + [
            'post', 'update', '463', '--post_status=publish', '--allow-root'])
        with self.assertRaisesRegex(ValueError, 'unexpected_wordpress_update_flags'):
            transport(module._WP_PREFIX + [
                'post', 'update', '463', '--post_status=draft', '--allow-root'])

    def test_publish_learns_created_id_and_allows_saved_content_read(self):
        module = load_module()
        calls = []

        def fake_run(args, **kwargs):
            calls.append((list(args), dict(kwargs)))
            remote = args[-1]
            if ' wp post create ' in remote:
                return subprocess.CompletedProcess(args, 0, stdout='901\n', stderr='')
            return subprocess.CompletedProcess(args, 0, stdout='', stderr='')

        module._RUN = fake_run
        transport = module.make_transport('publish', set(), 'bloguito')
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'candidate.html'
            source.write_text('<p>reviewed</p>', encoding='utf-8')
            transport(['sudo', 'docker', 'cp', str(source),
                       'wordpress_app:/tmp/editorial_candidate.html'], capture_output=True, check=True)
        transport(module._WP_PREFIX + [
            'post', 'create', '/tmp/editorial_candidate.html', '--post_type=post',
            '--post_status=draft', '--post_title=title', '--post_category=4',
            '--post_excerpt=summary', '--comment_status=closed', '--allow-root', '--porcelain'],
            capture_output=True, text=True, check=True)
        transport(module._WP_PREFIX + [
            'post', 'get', '901', '--fields=post_status,post_content', '--format=json', '--allow-root'],
            capture_output=True, text=True, check=True)
        self.assertEqual(b'<p>reviewed</p>', calls[0][1]['input'])

    def test_rejects_arbitrary_remote_wordpress_command(self):
        module = load_module()
        transport = module.make_transport('revise-draft', {463}, 'bloguito')
        with self.assertRaisesRegex(ValueError, 'unexpected_wordpress_command'):
            transport(module._WP_PREFIX + ['option', 'delete', 'siteurl', '--allow-root'])


if __name__ == '__main__':
    unittest.main()
