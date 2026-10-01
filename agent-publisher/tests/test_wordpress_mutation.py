import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from agents.wordpress_mutation import (
    GUARDED_POST_MUTATION_SCRIPT,
    META_BATCH_SCRIPT,
    backup_json,
    content_sha256,
    get_post,
    guarded_update_post,
    read_post_meta_batch,
    set_post_meta_batch,
    update_post,
    verify_cas,
    verify_saved_fields,
)


class WordPressMutationPrimitiveTests(unittest.TestCase):
    def test_get_and_update_build_expected_wp_cli_commands(self):
        base = ['sudo', 'docker', 'exec', 'wordpress_app', 'wp']
        calls = []

        def run(args, **kwargs):
            calls.append(args)
            if args[5:7] == ['post', 'get']:
                return Mock(stdout=json.dumps({'ID': 7, 'post_content': 'old'}))
            return Mock(stdout='Success')

        with patch('agents.wordpress_mutation.subprocess.run', side_effect=run):
            row = get_post(base, 7)
            update_post(base, 7, {'post_content': 'new'})
        self.assertEqual(7, row['ID'])
        self.assertEqual(['post', 'get'], calls[0][5:7])
        self.assertIn('--post_content=new', calls[1])

    def test_get_post_accepts_utf8_bom_from_remote_wp_cli(self):
        base = ['sudo', 'docker', 'exec', 'wordpress_app', 'wp']
        payload = '\ufeff' + json.dumps({'ID': 648, 'post_status': 'draft'})
        with patch('agents.wordpress_mutation.subprocess.run', return_value=Mock(stdout=payload)):
            row = get_post(base, 648)
        self.assertEqual(648, row['ID'])
        self.assertEqual('draft', row['post_status'])

    def test_cas_and_saved_field_helpers(self):
        post = {'post_status': 'draft', 'post_title': 't', 'post_content': 'body', 'post_name': 'slug'}
        digest = content_sha256('body')
        self.assertTrue(verify_cas(post, status='draft', title='t', content_sha=digest))
        self.assertFalse(verify_cas(post, status='publish', content_sha=digest))
        self.assertTrue(verify_saved_fields(
            post,
            expected={'post_status': 'draft'},
            preserved={'post_name': 'slug'},
        ))

    def test_backup_is_private_json_under_editorial_runs(self):
        with tempfile.TemporaryDirectory() as folder:
            path = backup_json(Path(folder), 'test', 9, {'ID': 9})
            self.assertEqual({'ID': 9}, json.loads(path.read_text(encoding='utf-8')))
            self.assertEqual('editorial_runs', path.parent.name)

    def test_guarded_update_sends_fixed_eval_program_and_returns_readback(self):
        base = ['sudo', 'docker', 'exec', 'wordpress_app', 'wp']
        saved = {
            'post_status': 'draft', 'post_title': 'title', 'post_name': 'slug',
            'post_content': 'new', 'post_excerpt': 'new excerpt',
        }
        seen = {}

        def run(args, **kwargs):
            seen['args'] = args
            seen['payload'] = json.loads(kwargs['input'])
            return Mock(stdout=json.dumps({'status': 'ok', 'saved': saved}))

        with patch('agents.wordpress_mutation.subprocess.run', side_effect=run):
            result = guarded_update_post(
                base,
                7,
                expected={
                    'post_status': 'draft', 'post_title': 'title', 'post_name': 'slug',
                    'post_excerpt': 'old excerpt', 'content_sha256': content_sha256('old'),
                },
                updates={'post_content': 'new', 'post_excerpt': 'new excerpt'},
            )
        self.assertEqual(saved, result)
        self.assertEqual(['eval', GUARDED_POST_MUTATION_SCRIPT, '--allow-root'], seen['args'][5:])
        self.assertEqual(7, seen['payload']['post_id'])

    def test_guarded_update_recovers_exact_already_applied_state_after_retry(self):
        base = ['sudo', 'docker', 'exec', 'wordpress_app', 'wp']
        current = {
            'post_status': 'draft', 'post_title': 'title', 'post_name': 'slug',
            'post_content': 'new', 'post_excerpt': 'new excerpt',
        }
        with patch('agents.wordpress_mutation.subprocess.run', return_value=Mock(
                stdout='warning\n' + json.dumps({'status': 'cas_mismatch', 'current': current}))):
            result = guarded_update_post(
                base,
                7,
                expected={
                    'post_status': 'draft', 'post_title': 'title', 'post_name': 'slug',
                    'post_excerpt': 'old excerpt', 'content_sha256': content_sha256('old'),
                },
                updates={'post_content': 'new', 'post_excerpt': 'new excerpt'},
            )
        self.assertEqual(current, result)

    def test_guarded_update_rejects_real_cas_conflict(self):
        base = ['sudo', 'docker', 'exec', 'wordpress_app', 'wp']
        current = {
            'post_status': 'draft', 'post_title': 'title', 'post_name': 'slug',
            'post_content': 'other editor', 'post_excerpt': 'old excerpt',
        }
        with patch('agents.wordpress_mutation.subprocess.run', return_value=Mock(
                stdout=json.dumps({'status': 'cas_mismatch', 'current': current}))):
            with self.assertRaisesRegex(ValueError, 'wordpress_guarded_cas_mismatch'):
                guarded_update_post(
                    base,
                    7,
                    expected={
                        'post_status': 'draft', 'post_title': 'title', 'post_name': 'slug',
                        'post_excerpt': 'old excerpt', 'content_sha256': content_sha256('old'),
                    },
                    updates={'post_content': 'new', 'post_excerpt': 'new excerpt'},
                )

    def test_meta_batch_reads_multiple_keys_in_one_wp_process(self):
        base = ['sudo', 'docker', 'exec', 'wordpress_app', 'wp']
        seen = {}

        def run(args, **kwargs):
            seen['args'] = args
            seen['payload'] = json.loads(kwargs['input'])
            return Mock(stdout='\ufeff' + json.dumps({
                'status': 'ok',
                'meta': {'a': 'one', 'b': None},
            }))

        with patch('agents.wordpress_mutation.subprocess.run', side_effect=run):
            result = read_post_meta_batch(base, 7, ['a', 'b'])
        self.assertEqual({'a': 'one', 'b': None}, result)
        self.assertEqual(['eval', META_BATCH_SCRIPT, '--allow-root'], seen['args'][5:])
        self.assertEqual(['a', 'b'], seen['payload']['keys'])

    def test_meta_batch_write_returns_verified_readback_in_one_process(self):
        base = ['sudo', 'docker', 'exec', 'wordpress_app', 'wp']
        calls = []

        def run(args, **kwargs):
            calls.append(args)
            payload = json.loads(kwargs['input'])
            return Mock(stdout=json.dumps({'status': 'ok', 'meta': payload['updates']}))

        with patch('agents.wordpress_mutation.subprocess.run', side_effect=run):
            result = set_post_meta_batch(base, 7, {'rank_math_title': 'title', 'rank_math_description': 'desc'})
        self.assertEqual({'rank_math_title': 'title', 'rank_math_description': 'desc'}, result)
        self.assertEqual(1, len(calls))


if __name__ == '__main__':
    unittest.main()
