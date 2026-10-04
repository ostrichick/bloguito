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
    def test_image_snapshot_batches_only_the_immediately_following_thumbnail_read(self):
        module = load_module()
        calls = []
        post = {'post_status': 'publish', 'post_title': 'title', 'post_name': 'slug',
                'post_content': 'body', 'post_excerpt': 'summary'}

        def fake_run(args, **kwargs):
            calls.append(list(args))
            remote = args[-1]
            data = json.dumps({'post': post, 'thumbnail_id': '700'}) if ' wp eval ' in remote else '701'
            return subprocess.CompletedProcess(args, 0, stdout=data, stderr='')

        module._RUN = fake_run
        transport = module.make_transport('replace-featured-image', {463}, 'bloguito')
        get = module._WP_PREFIX + ['post', 'get', '463',
            '--fields=post_status,post_title,post_name,post_content,post_excerpt', '--format=json', '--allow-root']
        meta = module._WP_PREFIX + ['post', 'meta', 'get', '463', '_thumbnail_id', '--allow-root']
        result = transport(get, capture_output=True, text=True, check=True)
        self.assertEqual(post, json.loads(result.stdout))
        self.assertEqual('700', transport(meta, capture_output=True, text=True).stdout)
        self.assertEqual(1, len(calls))
        self.assertEqual('701', transport(meta, capture_output=True, text=True).stdout)
        self.assertEqual(2, len(calls))
        transport(get, capture_output=True, text=True)
        transport(module._WP_PREFIX + ['post', 'meta', 'get', '463', 'rank_math_title', '--allow-root'],
                  capture_output=True, text=True)
        self.assertEqual('701', transport(meta, capture_output=True, text=True).stdout)
        self.assertEqual(5, len(calls))
        with self.assertRaisesRegex(ValueError, 'unexpected_wordpress_get_target'):
            transport(module._WP_PREFIX + ['post', 'get', '999', *get[8:]], text=True)

    def test_section_image_import_allows_non_featured_media_only_for_target(self):
        module = load_module()
        calls = []

        def fake_run(args, **kwargs):
            calls.append(list(args))
            return subprocess.CompletedProcess(args, 0, stdout='777\n', stderr='')

        module._RUN = fake_run
        transport = module.make_transport('import-section-image', {648}, 'bloguito')
        remote = '/tmp/editorial_section_648_0123456789ab.webp'
        result = transport(module._WP_PREFIX + [
            'media', 'import', remote, '--post_id=648', '--title=행사 이미지', '--alt=행사 장면',
            '--porcelain', '--allow-root'], capture_output=True, text=True, check=True)
        self.assertEqual(0, result.returncode)
        transport(module._WP_PREFIX + [
            'post', 'get', '777', '--fields=ID,guid,post_title,post_mime_type',
            '--format=json', '--allow-root'], capture_output=True, text=True, check=True)
        with self.assertRaisesRegex(ValueError, 'unexpected_wordpress_command'):
            transport(module._WP_PREFIX + [
                'media', 'import', remote, '--post_id=649', '--title=행사 이미지', '--alt=행사 장면',
                '--porcelain', '--allow-root'])

    def test_section_image_snapshot_allows_target_and_learned_attachment_only(self):
        module = load_module()

        def fake_run(args, **kwargs):
            remote = args[-1] if args else ''
            if ' wp media import ' in remote:
                return subprocess.CompletedProcess(args, 0, stdout='777\n', stderr='')
            return subprocess.CompletedProcess(args, 0, stdout='{}', stderr='')

        module._RUN = fake_run
        transport = module.make_transport('import-section-image', {648}, 'bloguito')
        snapshot = module._WP_PREFIX + [
            'eval', module.SECTION_IMAGE_SNAPSHOT_SCRIPT, '--allow-root']
        transport(snapshot, input=json.dumps({
            'protocol': 1, 'post_id': 648, 'attachment_id': None,
        }), capture_output=True, text=True, check=True)
        with self.assertRaisesRegex(ValueError, 'unexpected_wordpress_get_target'):
            transport(snapshot, input=json.dumps({
                'protocol': 1, 'post_id': 649, 'attachment_id': None,
            }), text=True)
        with self.assertRaisesRegex(ValueError, 'unexpected_wordpress_get_target'):
            transport(snapshot, input=json.dumps({
                'protocol': 1, 'post_id': 648, 'attachment_id': 777,
            }), text=True)

        remote = '/tmp/editorial_section_648_0123456789ab.webp'
        transport(module._WP_PREFIX + [
            'media', 'import', remote, '--post_id=648', '--title=title', '--alt=alt',
            '--porcelain', '--allow-root'], capture_output=True, text=True, check=True)
        transport(snapshot, input=json.dumps({
            'protocol': 1, 'post_id': 648, 'attachment_id': 777,
        }), capture_output=True, text=True, check=True)

    def test_section_image_snapshot_255_retries_but_media_import_does_not(self):
        module = load_module()
        snapshot_attempts = 0

        def snapshot_run(args, **kwargs):
            nonlocal snapshot_attempts
            if 'ssh' in args:
                snapshot_attempts += 1
                if snapshot_attempts == 1:
                    return subprocess.CompletedProcess(args, 255, stdout='', stderr='lost')
                return subprocess.CompletedProcess(args, 0, stdout='{}', stderr='')
            return subprocess.CompletedProcess(args, 0, stdout='', stderr='')

        module._RUN = snapshot_run
        transport = module.make_transport('import-section-image', {648}, 'bloguito')
        result = transport(module._WP_PREFIX + [
            'eval', module.SECTION_IMAGE_SNAPSHOT_SCRIPT, '--allow-root'],
            input=json.dumps({'protocol': 1, 'post_id': 648, 'attachment_id': None}),
            capture_output=True, text=True, check=False)
        self.assertEqual(0, result.returncode)
        self.assertEqual(2, snapshot_attempts)

        media_attempts = 0
        def media_run(args, **kwargs):
            nonlocal media_attempts
            if 'ssh' in args:
                media_attempts += 1
                return subprocess.CompletedProcess(args, 255, stdout='', stderr='lost')
            return subprocess.CompletedProcess(args, 0, stdout='', stderr='')
        module._RUN = media_run
        transport = module.make_transport('import-section-image', {648}, 'bloguito')
        media_result = transport(module._WP_PREFIX + [
            'media', 'import', '/tmp/editorial_section_648_0123456789ab.webp',
            '--post_id=648', '--title=title', '--alt=alt', '--porcelain', '--allow-root'],
            capture_output=True, text=True, check=False)
        self.assertEqual(255, media_result.returncode)
        self.assertEqual(1, media_attempts)

    def test_successful_inventory_uses_direct_ssh_without_tailscale_probe(self):
        module = load_module()
        calls = []

        def fake_run(args, **kwargs):
            calls.append((list(args), dict(kwargs)))
            return subprocess.CompletedProcess(args, 0, stdout='[]', stderr='')

        module._RUN = fake_run
        transport = module.make_transport(
            'draft-standard', {463}, '100.99.177.119',
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
            'draft-standard', {463}, '100.99.177.119',
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
            'draft-standard', {463}, '100.99.177.119',
            ssh_user='ubuntu', wsl_distro='Ubuntu-24.04')
        result = transport(module._WP_PREFIX + module._LIST_ARGS,
                           capture_output=True, text=True, check=False)
        self.assertEqual(0, result.returncode)
        self.assertEqual(2, ssh_attempts)
        self.assertEqual(2, len([args for args in calls if 'tailscale' in args]))

    def test_prepare_draft_create_255_is_not_retried(self):
        module = load_module()
        calls = []

        def fake_run(args, **kwargs):
            calls.append(list(args))
            if 'ssh' in args:
                return subprocess.CompletedProcess(args, 255, stdout='', stderr='lost response')
            return subprocess.CompletedProcess(args, 0, stdout='', stderr='')

        module._RUN = fake_run
        transport = module.make_transport(
            'prepare-draft', set(), '100.99.177.119', ssh_user='ubuntu', wsl_distro='Ubuntu-24.04')
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
        transport = module.make_transport('draft-fast', {463}, 'bloguito')
        transport(module._WP_PREFIX + [
            'post', 'get', '463',
            '--fields=post_status,post_title,post_name,post_content,post_excerpt',
            '--format=json', '--allow-root'])

    def test_fast_revise_guarded_mutation_retries_255_once(self):
        module = load_module()
        ssh_attempts = 0

        def fake_run(args, **kwargs):
            nonlocal ssh_attempts
            if 'ssh' in args:
                ssh_attempts += 1
                if ssh_attempts == 1:
                    return subprocess.CompletedProcess(args, 255, stdout='', stderr='timeout')
                return subprocess.CompletedProcess(args, 0, stdout='Success', stderr='')
            return subprocess.CompletedProcess(args, 0, stdout='', stderr='')

        module._RUN = fake_run
        transport = module.make_transport('draft-fast', {463}, 'bloguito')
        payload = json.dumps({
            'protocol': 1, 'post_id': 463,
            'expected': {
                'post_status': 'draft', 'post_title': 'title', 'post_name': 'slug',
                'post_excerpt': 'old', 'content_sha256': '0' * 64,
            },
            'updates': {'post_content': '<p>reviewed</p>', 'post_excerpt': 'summary'},
        })
        result = transport(module._WP_PREFIX + [
            'eval', module.GUARDED_POST_MUTATION_SCRIPT, '--allow-root'],
            input=payload, capture_output=True, text=True, check=False)
        self.assertEqual(0, result.returncode)
        self.assertEqual(2, ssh_attempts)

    def test_remote_wordpress_error_does_not_trigger_tailscale_diagnostics(self):
        module = load_module()
        calls = []

        def fake_run(args, **kwargs):
            calls.append((list(args), dict(kwargs)))
            return subprocess.CompletedProcess(args, 1, stdout='', stderr='wp error')

        module._RUN = fake_run
        transport = module.make_transport(
            'draft-standard', {463}, '100.99.177.119',
            ssh_user='ubuntu', wsl_distro='Ubuntu-24.04')
        result = transport(module._WP_PREFIX + module._LIST_ARGS,
                           capture_output=True, text=True, check=False)
        self.assertEqual(1, result.returncode)
        self.assertEqual([], [args for args, _ in calls if 'tailscale' in args])

    def test_explicit_tailscale_profile_uses_tailscale_transport(self):
        module = load_module()
        calls = []

        def fake_run(args, **kwargs):
            calls.append(list(args))
            return subprocess.CompletedProcess(args, 0, stdout='[]', stderr='')

        module._RUN = fake_run
        transport = module.make_transport(
            'draft-standard', {463}, '100.99.177.119', ssh_user='ubuntu',
            wsl_distro='Ubuntu-24.04', use_tailscale=True)
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
            'draft-standard', {463}, '100.99.177.119',
            ssh_user='ubuntu', wsl_distro='Ubuntu-24.04')
        transport(module._WP_PREFIX + module._LIST_ARGS,
                  capture_output=True, text=True, check=True)
        self.assertEqual('--exec', calls[0][3])
        self.assertNotIn('--', calls[0][:4])
        self.assertIn('ControlMaster=auto', calls[0])
        self.assertIn('ControlPersist=30', calls[0])
        self.assertTrue(any(item.startswith('ControlPath=/tmp/bloguito-editorial-') for item in calls[0]))

    def test_native_direct_ssh_does_not_use_controlmaster(self):
        module = load_module()
        calls = []
        module._RUN = lambda args, **kwargs: (
            calls.append(list(args)) or subprocess.CompletedProcess(args, 0, stdout='[]', stderr=''))
        transport = module.make_transport('draft-standard', {463}, 'bloguito')
        transport(module._WP_PREFIX + module._LIST_ARGS,
                  capture_output=True, text=True, check=True)
        self.assertNotIn('ControlMaster=auto', calls[0])
        self.assertFalse(any(item.startswith('ControlPath=') for item in calls[0]))

    def test_revise_draft_allows_only_exact_guarded_target_and_fields(self):
        module = load_module()
        module._RUN = lambda args, **kwargs: subprocess.CompletedProcess(args, 0, stdout='', stderr='')
        transport = module.make_transport('draft-standard', {463}, 'bloguito')
        expected = {
            'post_status': 'draft', 'post_title': 'title', 'post_name': 'slug',
            'post_excerpt': 'old', 'content_sha256': '0' * 64,
        }
        transport(module._WP_PREFIX + ['eval', module.GUARDED_POST_MUTATION_SCRIPT, '--allow-root'],
                  input=json.dumps({'protocol': 1, 'post_id': 463, 'expected': expected,
                                    'updates': {'post_content': 'reviewed', 'post_excerpt': 'summary'}}),
                  text=True)
        with self.assertRaisesRegex(ValueError, 'unexpected_wordpress_update_target'):
            transport(module._WP_PREFIX + ['eval', module.GUARDED_POST_MUTATION_SCRIPT, '--allow-root'],
                      input=json.dumps({'protocol': 1, 'post_id': 464, 'expected': expected,
                                        'updates': {'post_content': 'reviewed', 'post_excerpt': 'summary'}}),
                      text=True)
        with self.assertRaisesRegex(ValueError, 'unexpected_wordpress_update_flags'):
            transport(module._WP_PREFIX + ['eval', module.GUARDED_POST_MUTATION_SCRIPT, '--allow-root'],
                      input=json.dumps({'protocol': 1, 'post_id': 463, 'expected': expected,
                                        'updates': {'post_content': 'reviewed'}}), text=True)
        with self.assertRaisesRegex(ValueError, 'unexpected_wordpress_command'):
            transport(module._WP_PREFIX + [
                'post', 'update', '463', '--post_content=reviewed', '--post_excerpt=summary', '--allow-root'])

    def test_revise_draft_streams_guarded_payload_over_stdin(self):
        module = load_module()
        calls = []

        def fake_run(args, **kwargs):
            calls.append((list(args), dict(kwargs)))
            return subprocess.CompletedProcess(args, 0, stdout='Success', stderr='')

        module._RUN = fake_run
        transport = module.make_transport('draft-standard', {463}, 'bloguito')
        reviewed = '<div>' + ('검토된 긴 본문' * 10000) + '</div>'
        payload = json.dumps({
            'protocol': 1, 'post_id': 463,
            'expected': {
                'post_status': 'draft', 'post_title': 'title', 'post_name': 'slug',
                'post_excerpt': 'old', 'content_sha256': '0' * 64,
            },
            'updates': {'post_content': reviewed, 'post_excerpt': '검토된 요약'},
        }, ensure_ascii=False)
        transport(module._WP_PREFIX + ['eval', module.GUARDED_POST_MUTATION_SCRIPT, '--allow-root'],
                  input=payload, capture_output=True, text=True, check=True)

        self.assertEqual(1, len(calls))
        argv, kwargs = calls[0]
        remote = argv[-1]
        self.assertIn('docker exec -i wordpress_app wp eval', remote)
        self.assertNotIn('검토된 긴 본문', remote)
        self.assertEqual(reviewed, json.loads(kwargs['input'])['updates']['post_content'])

    def test_revise_draft_guarded_title_change_requires_explicit_transport_permission(self):
        module = load_module()
        module._RUN = lambda args, **kwargs: subprocess.CompletedProcess(args, 0, stdout='', stderr='')
        command = module._WP_PREFIX + ['eval', module.GUARDED_POST_MUTATION_SCRIPT, '--allow-root']
        payload = json.dumps({
            'protocol': 1, 'post_id': 463,
            'expected': {
                'post_status': 'draft', 'post_title': 'old title', 'post_name': 'slug',
                'post_excerpt': 'old', 'content_sha256': '0' * 64,
            },
            'updates': {'post_content': 'reviewed', 'post_excerpt': 'summary',
                        'post_title': 'reviewed title'},
        })
        with self.assertRaisesRegex(ValueError, 'unexpected_wordpress_update_flags'):
            module.make_transport('draft-standard', {463}, 'bloguito')(command, input=payload, text=True)
        module.make_transport(
            'draft-standard', {463}, 'bloguito', allow_title_change=True)(command, input=payload, text=True)

    def test_revise_draft_never_allows_plain_title_update_even_when_title_change_confirmed(self):
        module = load_module()
        module._RUN = lambda args, **kwargs: subprocess.CompletedProcess(args, 0, stdout='', stderr='')
        transport = module.make_transport(
            'draft-standard', {463}, 'bloguito', allow_title_change=True)
        with self.assertRaisesRegex(ValueError, 'unexpected_wordpress_command'):
            transport(module._WP_PREFIX + [
                'post', 'update', '463', '--post_title=reviewed title', '--allow-root'])

    def test_edit_post_transport_must_be_preclassified(self):
        module = load_module()
        with self.assertRaisesRegex(ValueError, 'edit_post_requires_preclassified_transport'):
            module.make_transport('edit-post', {463}, 'bloguito')

    def test_internal_public_transport_profiles_are_not_user_cli_actions(self):
        module = load_module()
        self.assertIn('draft-fast', module._TRANSPORT_PROFILES)
        self.assertIn('draft-standard', module._TRANSPORT_PROFILES)
        self.assertIn('public-fast', module._TRANSPORT_PROFILES)
        self.assertIn('public-standard', module._TRANSPORT_PROFILES)
        self.assertNotIn('draft-fast', module._CLI_ACTIONS)
        self.assertNotIn('draft-standard', module._CLI_ACTIONS)
        self.assertNotIn('public-fast', module._CLI_ACTIONS)
        self.assertNotIn('public-standard', module._CLI_ACTIONS)

    def test_cli_action_metadata_is_single_source_for_user_action_sets(self):
        module = load_module()
        self.assertEqual(set(module._CLI_ACTION_METADATA), module._CLI_ACTIONS)
        self.assertEqual(
            {'prepare-draft', 'edit-post', 'replace-featured-image'},
            module._PRIMARY_CLI_ACTIONS,
        )
        self.assertEqual({'promote-draft'}, module._PUBLICATION_CLI_ACTIONS)
        self.assertEqual(
            {'reformat', 'fix-excerpt', 'repair-draft-category', 'import-section-image'},
            module._MAINTENANCE_CLI_ACTIONS,
        )
        self.assertEqual({'prepare-draft'}, module._CREATE_ACTIONS)
        self.assertEqual(
            {'prepare-draft', 'promote-draft', 'reformat', 'repair-draft-category'},
            module._PERMALINK_ACTIONS,
        )
        self.assertEqual({
            'repair-draft-category': {'post_category'},
            'promote-draft': {'post_status'},
            'reformat': {'post_content'},
            'fix-excerpt': {'post_excerpt'},
        }, module._UPDATE_FIELDS)

    def test_parse_cli_request_normalizes_edit_post_inputs(self):
        module = load_module()
        expected_sha = 'a' * 64
        request = module._parse_cli_request([
            'edit-post', 'bundle.json', '--post-id', '648',
            '--expected-content-sha256', expected_sha,
            '--image-path', 'cover.webp', '--confirm-title-change', '--resume',
            '--output', 'receipt.json',
        ])

        self.assertEqual('edit-post', request.action)
        self.assertEqual(frozenset({648}), request.target_ids)
        self.assertEqual(Path('bundle.json'), request.bundle_path)
        self.assertEqual(Path('cover.webp'), request.image_path)
        self.assertTrue(request.image_path_supplied)
        self.assertEqual(expected_sha, request.expected_content_sha256)
        self.assertTrue(request.confirm_title_change)
        self.assertTrue(request.resume)
        self.assertEqual(Path('receipt.json'), request.output_path)

    def test_parse_cli_request_preserves_promote_and_reformat_target_shapes(self):
        module = load_module()
        promote = module._parse_cli_request([
            'promote-draft', '101,125', '--ids', '130', '131', '--confirm-publish',
        ])
        reformat = module._parse_cli_request(['reformat', '463'])

        self.assertEqual(frozenset({101, 125, 130, 131}), promote.target_ids)
        self.assertEqual(frozenset({463}), reformat.target_ids)

    def test_parse_cli_request_keeps_existing_first_value_and_target_semantics(self):
        module = load_module()
        request = module._parse_cli_request([
            'edit-post', 'bundle.json',
            '--post-id', '648', '--post-id', '649',
            '--expected-content-sha256', 'a' * 64,
            '--expected-content-sha256', 'b' * 64,
        ])
        promote = module._parse_cli_request([
            'promote-draft', '--ids', '101', '--ids', '202',
        ])

        self.assertEqual(frozenset({648, 649}), request.target_ids)
        self.assertEqual('a' * 64, request.expected_content_sha256)
        self.assertEqual(frozenset({101}), promote.target_ids)

    def test_legacy_edit_actions_are_not_user_cli_actions(self):
        module = load_module()
        for action in {
            'publish', 'edit-draft', 'revise-draft', 'fast-revise-draft',
            'update-existing', 'update-draft', 'quick-image-replace',
            'replace-legacy-draft',
        }:
            self.assertNotIn(action, module._CLI_ACTIONS)

    def test_edit_post_standard_wrapper_passes_reviewed_rank_math_meta(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as folder:
            bundle = Path(folder) / 'bundle.json'
            bundle.write_text(json.dumps({
                'brief': {
                    'primary_keyword': '2026 부산 10월 축제',
                    'seo': {
                        'title': '2026 부산 10월 축제 일정',
                        'description': '2026 부산 10월 축제 일정과 주요 프로그램을 확인합니다.',
                    },
                },
            }, ensure_ascii=False), encoding='utf-8')
            argv = [
                'editorial_cli_via_ssh.py', '--ssh-host', 'bloguito', '--',
                'edit-post', str(bundle), '--post-id', '648',
                '--expected-content-sha256', '0' * 64, '--confirm-update',
                '--edit-intent', '행사 정보 보완',
            ]
            with patch('sys.argv', argv), \
                 patch.object(module, 'resolve_transport', return_value=SimpleNamespace(
                     mode='direct', host='bloguito', user=None, wsl_distro=None)), \
                 patch('agents.edit_post.classify_reviewed_post_route', return_value={
                     'route': 'standard', 'reasons': [], 'target_status': 'draft',
                     'validation_plan': {},
                 }), \
                 patch('agents.validation_runner.require_validation_success', return_value={
                     'profile': 'standard-event', 'tests_run': 1, 'selected_files': ['test.py'],
                     'duration_ms': 1.0,
                 }), \
                 patch.object(module, 'make_transport', return_value=lambda *args, **kwargs: None) as make, \
                 patch.object(module.editorial_cli, 'main'):
                module.main()

        self.assertEqual('draft-standard', make.call_args.args[0])
        self.assertEqual({
            'rank_math_focus_keyword': '2026 부산 10월 축제',
            'rank_math_title': '2026 부산 10월 축제 일정',
            'rank_math_description': '2026 부산 10월 축제 일정과 주요 프로그램을 확인합니다.',
        }, make.call_args.kwargs['expected_rank_math_meta'])

    def test_promote_allows_only_publish_status(self):
        module = load_module()
        module._RUN = lambda args, **kwargs: subprocess.CompletedProcess(args, 0, stdout='', stderr='')
        transport = module.make_transport('promote-draft', {463}, 'bloguito')
        expected = {
            'post_status': 'draft', 'post_title': 'title', 'post_name': 'slug',
            'post_excerpt': 'old', 'content_sha256': '0' * 64,
        }
        transport(module._WP_PREFIX + ['eval', module.GUARDED_POST_MUTATION_SCRIPT, '--allow-root'],
                  input=json.dumps({'protocol': 1, 'post_id': 463, 'expected': expected,
                                    'updates': {'post_status': 'publish'}}), text=True)
        with self.assertRaisesRegex(ValueError, 'unexpected_wordpress_update_flags'):
            transport(module._WP_PREFIX + ['eval', module.GUARDED_POST_MUTATION_SCRIPT, '--allow-root'],
                      input=json.dumps({'protocol': 1, 'post_id': 463, 'expected': expected,
                                        'updates': {'post_status': 'draft'}}), text=True)
        with self.assertRaisesRegex(ValueError, 'unexpected_wordpress_command'):
            transport(module._WP_PREFIX + [
                'post', 'update', '463', '--post_status=publish', '--allow-root'])

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
        transport = module.make_transport('prepare-draft', set(), 'bloguito')
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
        transport(module._WP_PREFIX + [
            'post', 'meta', 'set', '901', '_bloguito_permalink_scheme', 'post-id-v1', '--allow-root'])
        self.assertEqual(b'<p>reviewed</p>', calls[0][1]['input'])

    def test_publish_allows_only_supported_rank_math_meta(self):
        module = load_module()
        module._RUN = lambda args, **kwargs: subprocess.CompletedProcess(args, 0, stdout='', stderr='')
        transport = module.make_transport('prepare-draft', {901}, 'bloguito')
        for key in ('rank_math_focus_keyword', 'rank_math_title', 'rank_math_description'):
            transport(module._WP_PREFIX + [
                'post', 'meta', 'set', '901', key, 'reviewed value', '--allow-root'])
        with self.assertRaisesRegex(ValueError, 'unexpected_wordpress_command'):
            transport(module._WP_PREFIX + [
                'post', 'meta', 'set', '901', 'rank_math_robots', 'noindex', '--allow-root'])
        transport(module._WP_PREFIX + [
            'post', 'meta', 'set', '901', '_bloguito_permalink_scheme', 'post-id-v1', '--allow-root'])
        with self.assertRaisesRegex(ValueError, 'unexpected_wordpress_command'):
            transport(module._WP_PREFIX + [
                'post', 'meta', 'set', '901', '_bloguito_permalink_scheme', 'legacy', '--allow-root'])

    def test_revise_draft_allows_only_reviewed_rank_math_meta(self):
        module = load_module()
        module._RUN = lambda args, **kwargs: subprocess.CompletedProcess(args, 0, stdout='reviewed value\n', stderr='')
        expected = {
            'rank_math_focus_keyword': '10월 대전 행사',
            'rank_math_title': '10월 대전 행사 2026',
            'rank_math_description': '10월 대전 행사 설명',
        }
        transport = module.make_transport(
            'draft-standard', {641}, 'bloguito', expected_rank_math_meta=expected)
        for key, value in expected.items():
            transport(module._WP_PREFIX + [
                'post', 'meta', 'get', '641', key, '--allow-root'])
        with self.assertRaisesRegex(ValueError, 'unexpected_wordpress_command'):
            transport(module._WP_PREFIX + [
                'post', 'meta', 'set', '641', 'rank_math_title', expected['rank_math_title'], '--allow-root'])
        payload = {
            'protocol': 1,
            'post_id': 641,
            'expected': {
                'post_status': 'draft', 'post_title': 'title', 'post_name': 'slug',
                'post_excerpt': 'old', 'content_sha256': '0' * 64,
            },
            'updates': {'post_content': 'new', 'post_excerpt': 'summary'},
            'expected_meta': {key: 'old ' + key for key in expected},
            'updates_meta': expected,
        }
        transport(
            module._WP_PREFIX + ['eval', module.GUARDED_POST_MUTATION_SCRIPT, '--allow-root'],
            input=json.dumps(payload), text=True)
        payload['updates_meta'] = {**expected, 'rank_math_title': 'unreviewed title'}
        with self.assertRaisesRegex(ValueError, 'invalid_guarded_wordpress_meta_expectation'):
            transport(
                module._WP_PREFIX + ['eval', module.GUARDED_POST_MUTATION_SCRIPT, '--allow-root'],
                input=json.dumps(payload), text=True)

    def test_repair_draft_category_allows_only_target_category_update(self):
        module = load_module()
        module._RUN = lambda args, **kwargs: subprocess.CompletedProcess(args, 0, stdout='[]\n', stderr='')
        transport = module.make_transport('repair-draft-category', {648}, 'bloguito')
        transport(module._WP_PREFIX + [
            'post', 'term', 'list', '648', 'category',
            '--fields=term_id,name,slug', '--format=json', '--allow-root'])
        payload = json.dumps({
            'protocol': 1, 'post_id': 648,
            'expected': {
                'post_status': 'draft', 'post_title': 'title', 'post_name': 'slug',
                'post_excerpt': '', 'content_sha256': '0' * 64, 'category_ids': [4],
            },
            'target_category_id': 274,
        })
        transport(module._WP_PREFIX + [
            'eval', module.GUARDED_CATEGORY_MUTATION_SCRIPT, '--allow-root'],
            input=payload, text=True)
        transport(module._WP_PREFIX + [
            'eval', 'echo get_permalink(648);', '--allow-root'])
        with self.assertRaisesRegex(ValueError, 'unexpected_wordpress_command'):
            transport(module._WP_PREFIX + [
                'post', 'update', '648', '--post_category=274', '--allow-root'])
        with self.assertRaisesRegex(ValueError, 'unexpected_wordpress_command'):
            transport(module._WP_PREFIX + [
                'post', 'term', 'list', '649', 'category',
                '--fields=term_id,name,slug', '--format=json', '--allow-root'])

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

    def test_create_rejects_manual_post_name(self):
        module = load_module()
        module._RUN = lambda args, **kwargs: subprocess.CompletedProcess(args, 0, stdout='901\n', stderr='')
        transport = module.make_transport('prepare-draft', set(), 'bloguito')
        base = [
            'post', 'create', '/tmp/editorial_candidate.html', '--post_type=post',
            '--post_status=draft', '--post_title=title', '--post_category=4',
            '--post_excerpt=summary', '--comment_status=closed', '--allow-root', '--porcelain']
        transport(module._WP_PREFIX + base)
        command = list(base)
        command.insert(5, '--post_name=manual-slug')
        with self.assertRaisesRegex(ValueError, 'unexpected_wordpress_draft_create'):
            transport(module._WP_PREFIX + command)

    def test_replace_featured_image_allows_only_targeted_import_and_readback(self):
        module = load_module()
        calls = []

        def fake_run(args, **kwargs):
            calls.append((list(args), dict(kwargs)))
            remote = args[-1] if args else ''
            if ' wp media import ' in remote:
                return subprocess.CompletedProcess(args, 0, stdout='777\n', stderr='')
            if ' wp post get 777 ' in remote:
                return subprocess.CompletedProcess(args, 0, stdout='{}', stderr='')
            return subprocess.CompletedProcess(args, 0, stdout='', stderr='')

        module._RUN = fake_run
        transport = module.make_transport('replace-featured-image', {463}, 'bloguito')
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'cover.jpg'
            source.write_bytes(b'image')
            transport([
                'sudo', 'docker', 'cp', str(source),
                'wordpress_app:/tmp/editorial_cover_463.jpg'], capture_output=True, check=True)
        transport(module._WP_PREFIX + [
            'media', 'import', '/tmp/editorial_cover_463.jpg', '--post_id=463',
            '--title=검토된 제목', '--alt=검토된 대체텍스트',
            '--porcelain', '--allow-root'], capture_output=True, text=True, check=True)
        expected = {
            'post_status': 'draft', 'post_title': '검토된 제목', 'post_name': 'slug',
            'post_excerpt': 'summary', 'content_sha256': '0' * 64,
        }
        transport(
            module._WP_PREFIX + ['eval', module.GUARDED_THUMBNAIL_MUTATION_SCRIPT, '--allow-root'],
            input=json.dumps({
                'protocol': 1, 'post_id': 463, 'expected': expected,
                'expected_thumbnail_id': 642, 'attachment_id': 777,
            }), text=True)
        transport(module._WP_PREFIX + [
            'post', 'get', '777', '--fields=ID,guid,post_title,post_mime_type',
            '--format=json', '--allow-root'], capture_output=True, text=True, check=True)
        transport(module._WP_PREFIX + [
            'post', 'meta', 'get', '777', '_wp_attachment_image_alt', '--allow-root'],
            capture_output=True, text=True, check=False)
        with self.assertRaisesRegex(ValueError, 'unexpected_wordpress_command'):
            transport(module._WP_PREFIX + [
                'post', 'update', '463', '--post_content=x', '--allow-root'])
        with self.assertRaisesRegex(ValueError, 'unexpected_wordpress_command'):
            transport(module._WP_PREFIX + [
                'media', 'import', '/tmp/editorial_cover_463.jpg', '--post_id=463',
                '--featured_image', '--title=검토된 제목', '--alt=검토된 대체텍스트',
                '--porcelain', '--allow-root'])

    def test_replace_featured_image_media_import_255_is_not_retried(self):
        module = load_module()
        ssh_attempts = 0

        def fake_run(args, **kwargs):
            nonlocal ssh_attempts
            if 'ssh' in args:
                ssh_attempts += 1
                return subprocess.CompletedProcess(args, 255, stdout='', stderr='lost response')
            return subprocess.CompletedProcess(args, 0, stdout='', stderr='')

        module._RUN = fake_run
        transport = module.make_transport('replace-featured-image', {463}, 'bloguito')
        result = transport(module._WP_PREFIX + [
            'media', 'import', '/tmp/editorial_cover_463.jpg', '--post_id=463',
            '--title=검토된 제목', '--alt=대체텍스트',
            '--porcelain', '--allow-root'], capture_output=True, text=True, check=False)
        self.assertEqual(255, result.returncode)
        self.assertEqual(1, ssh_attempts)

    def test_featured_image_import_accepts_utf8_bom_media_id(self):
        module = load_module()

        def fake_run(args, **kwargs):
            remote = args[-1] if args else ''
            if ' wp media import ' in remote:
                return subprocess.CompletedProcess(args, 0, stdout='\ufeff703\n', stderr='')
            return subprocess.CompletedProcess(args, 0, stdout='', stderr='')

        module._RUN = fake_run
        transport = module.make_transport('replace-featured-image', {648}, 'bloguito')
        result = transport(module._WP_PREFIX + [
            'media', 'import', '/tmp/editorial_cover_648.webp', '--post_id=648',
            '--title=검토된 제목', '--alt=대체텍스트',
            '--porcelain', '--allow-root'], capture_output=True, text=True, check=True)
        self.assertEqual(0, result.returncode)

    def test_quick_image_replace_alias_is_removed_from_user_cli(self):
        module = load_module()
        self.assertNotIn('quick-image-replace', module._CLI_ACTIONS)

    def test_primary_replace_featured_image_uses_restricted_image_transport(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as folder:
            image = Path(folder) / 'cover.jpg'
            image.write_bytes(b'image')
            argv = [
                'editorial_cli_via_ssh.py', '--ssh-host', 'bloguito', '--',
                'replace-featured-image', '--post-id', '724', '--image-path', str(image),
                '--alt-text', '국민연금 수령 시기 안내', '--confirm-update',
            ]
            with patch('sys.argv', argv), \
                    patch.object(module, 'resolve_transport', return_value=SimpleNamespace(
                        mode='direct', host='bloguito', user=None, wsl_distro=None)), \
                    patch.object(module, 'make_transport', return_value=lambda *args, **kwargs: None) as make, \
                    patch.object(module.editorial_cli, 'main') as cli_main:
                module.main()
        cli_main.assert_called_once()
        self.assertEqual('replace-featured-image', make.call_args.args[0])
        self.assertEqual({724}, make.call_args.args[1])

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
        transport = module.make_transport('draft-standard', {463}, 'bloguito')
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
        transport = module.make_transport('draft-standard', {463}, 'bloguito')
        transport(module._WP_PREFIX + module._LIGHT_INVENTORY_ARGS,
                  capture_output=True, text=True, check=True)
        remote_commands = [args[-1] for args, _ in calls if args]
        self.assertTrue(any(' wp eval ' in remote for remote in remote_commands))
        self.assertTrue(any('$q' in remote for remote in remote_commands))
        transport(module._WP_PREFIX + [
            'post', 'get', '700', '--format=json', '--allow-root'],
            capture_output=True, text=True, check=True)
        with self.assertRaisesRegex(ValueError, 'unexpected_wordpress_command'):
            transport(module._WP_PREFIX + [
                'post', 'update', '700', '--post_content=x', '--post_excerpt=y', '--allow-root'])


if __name__ == '__main__':
    unittest.main()
