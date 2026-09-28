import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


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
        self.assertEqual(4, len([args for args, _ in calls if 'ssh' in args]))

    def test_transient_255_is_retried_once_after_diagnosis(self):
        module = load_module()
        calls = []
        ssh_attempts = 0

        def fake_run(args, **kwargs):
            nonlocal ssh_attempts
            calls.append(list(args))
            if 'ssh' in args:
                ssh_attempts += 1
                if ssh_attempts == 1:
                    return subprocess.CompletedProcess(args, 255, stdout='', stderr='timeout')
                return subprocess.CompletedProcess(args, 0, stdout='[]', stderr='')
            return subprocess.CompletedProcess(args, 0, stdout='', stderr='')

        module._RUN = fake_run
        transport = module.make_transport(
            'revise-draft', {463}, '100.99.177.119',
            ssh_user='ubuntu', wsl_distro='Ubuntu-24.04')
        result = transport(module._WP_PREFIX + module._LIST_ARGS,
                           capture_output=True, text=True, check=False)
        self.assertEqual(0, result.returncode)
        self.assertEqual(2, ssh_attempts)
        self.assertEqual(2, len([args for args in calls if 'tailscale' in args]))

    def test_publish_create_255_is_not_retried(self):
        module = load_module()
        calls = []

        def fake_run(args, **kwargs):
            calls.append(list(args))
            if 'ssh' in args:
                return subprocess.CompletedProcess(args, 255, stdout='', stderr='lost response')
            return subprocess.CompletedProcess(args, 0, stdout='', stderr='')

        module._RUN = fake_run
        transport = module.make_transport(
            'publish', set(), '100.99.177.119', ssh_user='ubuntu', wsl_distro='Ubuntu-24.04')
        result = transport(module._WP_PREFIX + [
            'post', 'create', '/tmp/editorial_candidate.html', '--post_type=post',
            '--post_status=draft', '--post_title=title', '--post_category=4',
            '--post_excerpt=summary', '--comment_status=closed', '--allow-root', '--porcelain'],
            capture_output=True, text=True, check=False)
        self.assertEqual(255, result.returncode)
        self.assertEqual(1, len([args for args in calls if 'ssh' in args]))
        self.assertEqual(2, len([args for args in calls if 'tailscale' in args]))

    def test_fast_revise_allows_minimal_target_post_fields(self):
        module = load_module()
        module._RUN = lambda args, **kwargs: subprocess.CompletedProcess(
            args, 0, stdout='{}', stderr='')
        transport = module.make_transport('fast-revise-draft', {463}, 'bloguito')
        transport(module._WP_PREFIX + [
            'post', 'get', '463',
            '--fields=post_status,post_title,post_name,post_content,post_excerpt',
            '--format=json', '--allow-root'])

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

    def test_explicit_tailscale_ssh_uses_tailscale_transport(self):
        module = load_module()
        calls = []

        def fake_run(args, **kwargs):
            calls.append(list(args))
            return subprocess.CompletedProcess(args, 0, stdout='[]', stderr='')

        module._RUN = fake_run
        transport = module.make_transport(
            'revise-draft', {463}, '100.99.177.119', ssh_user='ubuntu',
            wsl_distro='Ubuntu-24.04', tailscale_ssh=True)
        transport(module._WP_PREFIX + module._LIST_ARGS,
                  capture_output=True, text=True, check=True)
        self.assertEqual(
            ['wsl.exe', '-d', 'Ubuntu-24.04', '--exec', 'tailscale', 'ssh',
             'ubuntu@100.99.177.119'],
            calls[0][:7],
        )

    def test_wsl_ssh_uses_exec_mode_without_intermediate_shell(self):
        module = load_module()
        calls = []

        def fake_run(args, **kwargs):
            calls.append(list(args))
            return subprocess.CompletedProcess(args, 0, stdout='[]', stderr='')

        module._RUN = fake_run
        transport = module.make_transport(
            'revise-draft', {463}, '100.99.177.119',
            ssh_user='ubuntu', wsl_distro='Ubuntu-24.04')
        transport(module._WP_PREFIX + module._LIST_ARGS,
                  capture_output=True, text=True, check=True)
        self.assertEqual('--exec', calls[0][3])
        self.assertNotIn('--', calls[0][:4])

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

    def test_revise_draft_streams_reviewed_content_over_stdin(self):
        module = load_module()
        calls = []

        def fake_run(args, **kwargs):
            calls.append((list(args), dict(kwargs)))
            return subprocess.CompletedProcess(args, 0, stdout='Success', stderr='')

        module._RUN = fake_run
        transport = module.make_transport('revise-draft', {463}, 'bloguito')
        reviewed = '<div>' + ('검토된 긴 본문' * 10000) + '</div>'
        transport(module._WP_PREFIX + [
            'post', 'update', '463', f'--post_content={reviewed}',
            '--post_excerpt=검토된 요약', '--allow-root'],
            capture_output=True, text=True, check=True)

        self.assertEqual(1, len(calls))
        argv, kwargs = calls[0]
        remote = argv[-1]
        self.assertIn('docker exec -i wordpress_app wp post update 463 -', remote)
        self.assertIn('--post_excerpt=', remote)
        self.assertNotIn('검토된 긴 본문', remote)
        self.assertEqual(reviewed, kwargs['input'])

    def test_revise_draft_title_change_requires_explicit_transport_permission(self):
        module = load_module()
        module._RUN = lambda args, **kwargs: subprocess.CompletedProcess(args, 0, stdout='', stderr='')
        command = module._WP_PREFIX + [
            'post', 'update', '463', '--post_content=reviewed', '--post_excerpt=summary',
            '--post_title=reviewed title', '--allow-root']
        with self.assertRaisesRegex(ValueError, 'unexpected_wordpress_update_flags'):
            module.make_transport('revise-draft', {463}, 'bloguito')(command)
        module.make_transport(
            'revise-draft', {463}, 'bloguito', allow_title_change=True)(command)

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

    def test_publish_allows_only_supported_rank_math_meta(self):
        module = load_module()
        module._RUN = lambda args, **kwargs: subprocess.CompletedProcess(args, 0, stdout='', stderr='')
        transport = module.make_transport('publish', {901}, 'bloguito')
        for key in ('rank_math_focus_keyword', 'rank_math_title', 'rank_math_description'):
            transport(module._WP_PREFIX + [
                'post', 'meta', 'set', '901', key, 'reviewed value', '--allow-root'])
        with self.assertRaisesRegex(ValueError, 'unexpected_wordpress_command'):
            transport(module._WP_PREFIX + [
                'post', 'meta', 'set', '901', 'rank_math_robots', 'noindex', '--allow-root'])

    def test_prepare_draft_can_create_and_attach_only_its_generated_image(self):
        module = load_module()
        calls = []

        def fake_run(args, **kwargs):
            calls.append((list(args), dict(kwargs)))
            remote = args[-1]
            if ' wp post create ' in remote:
                return subprocess.CompletedProcess(args, 0, stdout='901\n', stderr='')
            return subprocess.CompletedProcess(args, 0, stdout='', stderr='')

        module._RUN = fake_run
        transport = module.make_transport('prepare-draft', set(), 'bloguito')
        transport(module._WP_PREFIX + [
            'post', 'create', '/tmp/editorial_candidate.html', '--post_type=post',
            '--post_status=draft', '--post_title=title', '--post_category=4',
            '--post_excerpt=summary', '--comment_status=closed', '--allow-root', '--porcelain'],
            capture_output=True, text=True, check=True)

        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'cover.jpg'
            source.write_bytes(b'image')
            transport([
                'sudo', 'docker', 'cp', str(source),
                'wordpress_app:/tmp/editorial_cover_901.jpg'],
                capture_output=True, check=True)

        transport(module._WP_PREFIX + [
            'media', 'import', '/tmp/editorial_cover_901.jpg', '--post_id=901',
            '--featured_image', '--allow-root'], capture_output=True, check=True)

        with self.assertRaisesRegex(ValueError, 'unexpected_wordpress_command'):
            transport(module._WP_PREFIX + [
                'media', 'import', '/tmp/editorial_cover_902.jpg', '--post_id=902',
                '--featured_image', '--allow-root'], capture_output=True, check=True)

        self.assertTrue(any(b'image' == kwargs.get('input') for _, kwargs in calls))

    def test_prepare_draft_wrapper_syncs_catalog_after_successful_editorial_command(self):
        module = load_module()
        calls = []

        def fake_run(args, **kwargs):
            calls.append((list(args), dict(kwargs)))
            return subprocess.CompletedProcess(args, 0, stdout='catalog synced\n', stderr='')

        module._RUN = fake_run
        with tempfile.TemporaryDirectory() as folder:
            receipt_path = Path(folder) / 'receipt.json'
            receipt_path.write_text(json.dumps({'action': 'prepare-draft'}), encoding='utf-8')
            argv = [
                'editorial_cli_via_ssh.py', '--ssh-host', 'bloguito', '--',
                'prepare-draft', 'bundle.json', '--author-model', 'GPT-5.6 Sol',
                '--output', str(receipt_path),
            ]
            with patch('sys.argv', argv), \
                    patch.object(module, 'resolve_transport', return_value=SimpleNamespace(
                        mode='direct', host='bloguito', user=None, wsl_distro=None)), \
                    patch.object(module, 'make_transport', return_value=lambda *args, **kwargs: None), \
                    patch.object(module.editorial_cli, 'main') as cli_main:
                module.main()
            receipt = json.loads(receipt_path.read_text(encoding='utf-8'))

        cli_main.assert_called_once()
        catalog_calls = [args for args, _ in calls if args and args[-1].endswith('sync_post_catalog.py')]
        self.assertEqual(1, len(catalog_calls))
        self.assertEqual('passed', receipt['catalog_sync'])
        self.assertEqual(1, receipt['catalog_sync_attempts'])

    def test_prepare_draft_catalog_failure_retries_sync_only_without_replaying_create(self):
        module = load_module()
        calls = []

        def fake_run(args, **kwargs):
            calls.append((list(args), dict(kwargs)))
            return subprocess.CompletedProcess(args, 1, stdout='', stderr='offline')

        module._RUN = fake_run
        argv = [
            'editorial_cli_via_ssh.py', '--ssh-host', 'bloguito', '--',
            'prepare-draft', 'bundle.json', '--author-model', 'GPT-5.6 Sol',
        ]
        with patch('sys.argv', argv), \
                patch.object(module, 'resolve_transport', return_value=SimpleNamespace(
                    mode='direct', host='bloguito', user=None, wsl_distro=None)), \
                patch.object(module, 'make_transport', return_value=lambda *args, **kwargs: None), \
                patch.object(module.editorial_cli, 'main') as cli_main:
            module.main()

        cli_main.assert_called_once()
        catalog_calls = [args for args, _ in calls if args and args[-1].endswith('sync_post_catalog.py')]
        self.assertEqual(2, len(catalog_calls))

    def test_rejects_arbitrary_remote_wordpress_command(self):
        module = load_module()
        transport = module.make_transport('revise-draft', {463}, 'bloguito')
        with self.assertRaisesRegex(ValueError, 'unexpected_wordpress_command'):
            transport(module._WP_PREFIX + ['option', 'delete', 'siteurl', '--allow-root'])

    def test_lightweight_inventory_grants_read_only_candidate_get(self):
        module = load_module()
        inventory = [{
            'ID': 700,
            'post_title': 'candidate',
            'post_status': 'publish',
            'content_sha256': '0' * 64,
            'content_urls': ['https://example.org/a'],
        }]
        calls = []

        def fake_run(args, **kwargs):
            calls.append((list(args), dict(kwargs)))
            remote = args[-1]
            if ' wp eval ' in remote:
                return subprocess.CompletedProcess(args, 0, stdout=json.dumps(inventory), stderr='')
            return subprocess.CompletedProcess(args, 0, stdout='{}', stderr='')

        module._RUN = fake_run
        transport = module.make_transport('revise-draft', {463}, 'bloguito')
        transport(module._WP_PREFIX + module._LIGHT_INVENTORY_ARGS,
                  capture_output=True, text=True, check=True)
        remote_commands = [args[-1] for args, _ in calls if args]
        self.assertTrue(any(' wp eval ' in remote for remote in remote_commands))
        self.assertTrue(any('$q' in remote for remote in remote_commands))
        transport(module._WP_PREFIX + [
            'post', 'get', '700', '--format=json', '--allow-root'],
            capture_output=True, text=True, check=True)
        with self.assertRaisesRegex(ValueError, 'unexpected_wordpress_update_target'):
            transport(module._WP_PREFIX + [
                'post', 'update', '700', '--post_content=x', '--post_excerpt=y', '--allow-root'])


if __name__ == '__main__':
    unittest.main()
