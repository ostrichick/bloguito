import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from agents.wordpress_mutation import (
    backup_json,
    content_sha256,
    get_post,
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


if __name__ == '__main__':
    unittest.main()
