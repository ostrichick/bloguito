import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from agents.wordpress_mutation import (
    GUARDED_ATTACHMENT_ALT_MUTATION_SCRIPT,
    GUARDED_CATEGORY_MUTATION_SCRIPT,
    GUARDED_POST_MUTATION_SCRIPT,
    GUARDED_THUMBNAIL_MUTATION_SCRIPT,
    backup_json,
    content_sha256,
    get_post,
    guarded_set_post_category,
    guarded_set_post_thumbnail,
    guarded_update_featured_image_alt,
    guarded_update_post,
    verify_cas,
    verify_saved_fields,
)


class WordPressMutationPrimitiveTests(unittest.TestCase):
    def test_guarded_scripts_use_database_row_locks_and_transactions(self):
        for script in (
                GUARDED_POST_MUTATION_SCRIPT,
                GUARDED_CATEGORY_MUTATION_SCRIPT,
                GUARDED_THUMBNAIL_MUTATION_SCRIPT,
                GUARDED_ATTACHMENT_ALT_MUTATION_SCRIPT):
            self.assertIn('START TRANSACTION', script)
            self.assertIn('FOR UPDATE', script)
            self.assertIn('ROLLBACK', script)
            self.assertIn('COMMIT', script)
        self.assertIn('$wpdb->posts', GUARDED_POST_MUTATION_SCRIPT)
        self.assertIn('$wpdb->term_relationships', GUARDED_CATEGORY_MUTATION_SCRIPT)
        self.assertIn('wp_attachment_is_image', GUARDED_THUMBNAIL_MUTATION_SCRIPT)
        self.assertIn('$wpdb->postmeta', GUARDED_THUMBNAIL_MUTATION_SCRIPT)
        self.assertIn('_wp_attachment_image_alt', GUARDED_ATTACHMENT_ALT_MUTATION_SCRIPT)
        self.assertIn('wp_attachment_is_image', GUARDED_ATTACHMENT_ALT_MUTATION_SCRIPT)

    def test_get_builds_expected_wp_cli_command(self):
        base = ['sudo', 'docker', 'exec', 'wordpress_app', 'wp']
        calls = []

        def run(args, **kwargs):
            calls.append(args)
            if args[5:7] == ['post', 'get']:
                return Mock(stdout=json.dumps({'ID': 7, 'post_content': 'old'}))
            return Mock(stdout='Success')

        with patch('agents.wordpress_mutation.subprocess.run', side_effect=run):
            row = get_post(base, 7)
        self.assertEqual(7, row['ID'])
        self.assertEqual(['post', 'get'], calls[0][5:7])

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
        self.assertEqual(
            ['sudo', 'docker', 'exec', '-i', 'wordpress_app', 'wp'],
            seen['args'][:6],
        )
        self.assertEqual(['eval', GUARDED_POST_MUTATION_SCRIPT, '--allow-root'], seen['args'][6:])
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

    def test_guarded_update_keeps_invalid_payload_fail_closed(self):
        base = ['sudo', 'docker', 'exec', 'wordpress_app', 'wp']
        with patch('agents.wordpress_mutation.subprocess.run', return_value=Mock(
                stdout=json.dumps({'status': 'invalid_payload'}))):
            with self.assertRaisesRegex(ValueError, 'wordpress_guarded_protocol_rejected'):
                guarded_update_post(
                    base,
                    7,
                    expected={
                        'post_status': 'draft', 'post_title': 'title', 'post_name': 'slug',
                        'post_excerpt': 'old excerpt', 'content_sha256': content_sha256('old'),
                    },
                    updates={'post_content': 'new', 'post_excerpt': 'new excerpt'},
                )

    def test_guarded_update_can_atomically_promote_status(self):
        base = ['sudo', 'docker', 'exec', 'wordpress_app', 'wp']
        saved = {
            'post_status': 'publish', 'post_title': 'title', 'post_name': 'slug',
            'post_content': 'old', 'post_excerpt': 'old excerpt',
        }
        with patch('agents.wordpress_mutation.subprocess.run', return_value=Mock(
                stdout=json.dumps({'status': 'ok', 'saved': saved}))) as run:
            result = guarded_update_post(
                base, 7,
                expected={
                    'post_status': 'draft', 'post_title': 'title', 'post_name': 'slug',
                    'post_excerpt': 'old excerpt', 'content_sha256': content_sha256('old'),
                },
                updates={'post_status': 'publish'},
            )
        self.assertEqual('publish', result['post_status'])
        payload = json.loads(run.call_args.kwargs['input'])
        self.assertEqual({'post_status': 'publish'}, payload['updates'])

    def test_guarded_update_can_bind_canonical_category_to_content_cas(self):
        base = ['sudo', 'docker', 'exec', 'wordpress_app', 'wp']
        saved = {
            'post_status': 'publish', 'post_title': 'title', 'post_name': 'slug',
            'post_content': 'new', 'post_excerpt': 'old excerpt',
        }
        with patch('agents.wordpress_mutation.subprocess.run', return_value=Mock(
                stdout=json.dumps({'status': 'ok', 'saved': saved, 'category_ids': [278]}))) as run:
            guarded_update_post(
                base, 7,
                expected={
                    'post_status': 'publish', 'post_title': 'title', 'post_name': 'slug',
                    'post_excerpt': 'old excerpt', 'content_sha256': content_sha256('old'),
                    'category_ids': [278],
                },
                updates={'post_content': 'new'},
            )
        payload = json.loads(run.call_args.kwargs['input'])
        self.assertEqual([278], payload['expected']['category_ids'])

    def test_guarded_update_rejects_category_readback_drift(self):
        base = ['sudo', 'docker', 'exec', 'wordpress_app', 'wp']
        saved = {
            'post_status': 'publish', 'post_title': 'title', 'post_name': 'slug',
            'post_content': 'new', 'post_excerpt': 'old excerpt',
        }
        with patch('agents.wordpress_mutation.subprocess.run', return_value=Mock(
                stdout=json.dumps({'status': 'ok', 'saved': saved, 'category_ids': [277]}))):
            with self.assertRaisesRegex(ValueError, 'wordpress_guarded_readback_failed'):
                guarded_update_post(
                    base, 7,
                    expected={
                        'post_status': 'publish', 'post_title': 'title', 'post_name': 'slug',
                        'post_excerpt': 'old excerpt', 'content_sha256': content_sha256('old'),
                        'category_ids': [278],
                    },
                    updates={'post_content': 'new'},
                )

    def test_guarded_update_binds_reviewed_meta_to_same_transaction(self):
        base = ['sudo', 'docker', 'exec', 'wordpress_app', 'wp']
        saved = {
            'post_status': 'publish', 'post_title': 'title', 'post_name': 'slug',
            'post_content': 'new', 'post_excerpt': 'old excerpt',
        }
        expected_meta = {
            'rank_math_focus_keyword': 'old key',
            'rank_math_title': None,
            'rank_math_description': 'old description',
        }
        updates_meta = {
            'rank_math_focus_keyword': 'new key',
            'rank_math_title': 'new title',
            'rank_math_description': 'new description',
        }
        with patch('agents.wordpress_mutation.subprocess.run', return_value=Mock(
                stdout=json.dumps({
                    'status': 'ok', 'saved': saved, 'saved_meta': updates_meta,
                }))) as run:
            result = guarded_update_post(
                base, 7,
                expected={
                    'post_status': 'publish', 'post_title': 'title', 'post_name': 'slug',
                    'post_excerpt': 'old excerpt', 'content_sha256': content_sha256('old'),
                },
                updates={'post_content': 'new'},
                expected_meta=expected_meta,
                updates_meta=updates_meta,
            )
        self.assertEqual(saved, result)
        payload = json.loads(run.call_args.kwargs['input'])
        self.assertEqual(expected_meta, payload['expected_meta'])
        self.assertEqual(updates_meta, payload['updates_meta'])
        self.assertIn('$wpdb->postmeta', GUARDED_POST_MUTATION_SCRIPT)

    def test_guarded_category_mutation_uses_same_stdin_contract(self):
        base = ['sudo', 'docker', 'exec', 'wordpress_app', 'wp']
        saved = {
            'post_status': 'draft', 'post_title': 'title', 'post_name': 'slug',
            'post_content': 'old', 'post_excerpt': 'old excerpt',
        }
        with patch('agents.wordpress_mutation.subprocess.run', return_value=Mock(
                stdout=json.dumps({'status': 'ok', 'saved': saved, 'category_ids': [274]}))) as run:
            result = guarded_set_post_category(
                base, 7,
                expected={
                    'post_status': 'draft', 'post_title': 'title', 'post_name': 'slug',
                    'post_excerpt': 'old excerpt', 'content_sha256': content_sha256('old'),
                    'category_ids': [4],
                },
                target_category_id=274,
            )
        self.assertEqual([274], result['category_ids'])
        self.assertEqual(['sudo', 'docker', 'exec', '-i', 'wordpress_app', 'wp'],
                         run.call_args.args[0][:6])
        self.assertEqual(['eval', GUARDED_CATEGORY_MUTATION_SCRIPT, '--allow-root'],
                         run.call_args.args[0][6:])
        payload = json.loads(run.call_args.kwargs['input'])
        self.assertEqual(1, payload['protocol'])
        self.assertEqual(7, payload['post_id'])
        self.assertEqual([4], payload['expected']['category_ids'])
        self.assertEqual(274, payload['target_category_id'])

    def test_guarded_publish_allows_wordpress_to_generate_slug_from_empty_draft_name(self):
        base = ['sudo', 'docker', 'exec', 'wordpress_app', 'wp']
        saved = {
            'post_status': 'publish',
            'post_title': '검토된 제목',
            'post_name': 'wordpress-generated-slug',
            'post_content': 'reviewed body',
            'post_excerpt': 'summary',
        }
        with patch('agents.wordpress_mutation.run_wordpress', return_value=Mock(
                stdout=json.dumps({'status': 'ok', 'saved': saved}))) as run:
            result = guarded_update_post(
                base,
                885,
                expected={
                    'post_status': 'draft',
                    'post_title': '검토된 제목',
                    'post_name': '',
                    'post_excerpt': 'summary',
                    'content_sha256': content_sha256('reviewed body'),
                },
                updates={'post_status': 'publish'},
            )
        self.assertEqual('publish', result['post_status'])
        self.assertEqual('wordpress-generated-slug', result['post_name'])
        self.assertIn('$allow_auto_slug=', GUARDED_POST_MUTATION_SCRIPT)
        payload = json.loads(run.call_args.kwargs['input'])
        self.assertEqual('', payload['expected']['post_name'])
        self.assertEqual('publish', payload['updates']['post_status'])

    def test_guarded_thumbnail_mutation_uses_exact_post_and_thumbnail_cas(self):
        base = ['sudo', 'docker', 'exec', 'wordpress_app', 'wp']
        saved = {
            'post_status': 'draft', 'post_title': 'title', 'post_name': 'slug',
            'post_content': 'old', 'post_excerpt': 'old excerpt',
        }
        with patch('agents.wordpress_mutation.subprocess.run', return_value=Mock(
                stdout=json.dumps({
                    'status': 'ok', 'saved': saved, 'thumbnail_id': '777',
                }))) as run:
            result = guarded_set_post_thumbnail(
                base, 7,
                expected={
                    'post_status': 'draft', 'post_title': 'title', 'post_name': 'slug',
                    'post_excerpt': 'old excerpt', 'content_sha256': content_sha256('old'),
                },
                expected_thumbnail_id=642,
                attachment_id=777,
            )
        self.assertEqual('777', result['thumbnail_id'])
        self.assertEqual(['sudo', 'docker', 'exec', '-i', 'wordpress_app', 'wp'],
                         run.call_args.args[0][:6])
        payload = json.loads(run.call_args.kwargs['input'])
        self.assertEqual(642, payload['expected_thumbnail_id'])
        self.assertEqual(777, payload['attachment_id'])

    def test_guarded_attachment_alt_mutation_uses_exact_post_thumbnail_and_alt_cas(self):
        base = ['sudo', 'docker', 'exec', 'wordpress_app', 'wp']
        saved = {
            'post_status': 'publish', 'post_title': 'title', 'post_name': 'slug',
            'post_content': 'old', 'post_excerpt': 'old excerpt',
        }
        with patch('agents.wordpress_mutation.subprocess.run', return_value=Mock(
                stdout=json.dumps({
                    'status': 'ok', 'saved': saved, 'thumbnail_id': '236',
                    'attachment_id': 236, 'alt_text': '새 대체텍스트',
                }))) as run:
            result = guarded_update_featured_image_alt(
                base, 235,
                expected={
                    'post_status': 'publish', 'post_title': 'title', 'post_name': 'slug',
                    'post_excerpt': 'old excerpt', 'content_sha256': content_sha256('old'),
                },
                attachment_id=236,
                expected_alt=None,
                alt_text='새 대체텍스트',
            )
        self.assertEqual('236', result['thumbnail_id'])
        self.assertEqual('새 대체텍스트', result['alt_text'])
        self.assertEqual(['sudo', 'docker', 'exec', '-i', 'wordpress_app', 'wp'],
                         run.call_args.args[0][:6])
        self.assertEqual(['eval', GUARDED_ATTACHMENT_ALT_MUTATION_SCRIPT, '--allow-root'],
                         run.call_args.args[0][6:])
        payload = json.loads(run.call_args.kwargs['input'])
        self.assertEqual(235, payload['post_id'])
        self.assertEqual(236, payload['attachment_id'])
        self.assertIsNone(payload['expected_alt'])
        self.assertEqual('새 대체텍스트', payload['alt_text'])


if __name__ == '__main__':
    unittest.main()
