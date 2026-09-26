import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[2] / 'scripts' / 'sync_editorial_state_via_ssh.py'


def load_module():
    spec = importlib.util.spec_from_file_location('sync_editorial_state_via_ssh_tested', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SyncEditorialStateViaSshTests(unittest.TestCase):
    def test_imports_both_indexes_without_tailscale_preflight(self):
        module = load_module()
        calls = []
        payloads = [
            json.dumps([{'id': 463, 'fact_manifest': {'editorial_bundle': {}}}]),
            json.dumps([{'id': 55, 'status': 'publish'}]),
        ]

        def fake_run(args, **kwargs):
            calls.append(list(args))
            return subprocess.CompletedProcess(args, 0, stdout=payloads.pop(0), stderr='')

        module._RUN = fake_run
        with tempfile.TemporaryDirectory() as folder:
            draft = Path(folder) / 'draft_posts.json'
            published = Path(folder) / 'published_posts.json'
            module._FILES = {'draft_posts.json': draft, 'published_posts.json': published}
            result = module.sync_state(
                '100.99.177.119', ssh_user='ubuntu', wsl_distro='Ubuntu-24.04')
            self.assertEqual({'draft_posts.json': 1, 'published_posts.json': 1}, result)
            self.assertEqual(463, json.loads(draft.read_text(encoding='utf-8'))[0]['id'])
        self.assertEqual(2, len(calls))
        self.assertTrue(all('ssh' in call for call in calls))
        self.assertTrue(all('tailscale' not in call for call in calls))

    def test_refuses_to_overwrite_local_canonical_state_before_ssh(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as folder:
            draft = Path(folder) / 'draft_posts.json'
            published = Path(folder) / 'published_posts.json'
            draft.write_text('[]', encoding='utf-8')
            module._FILES = {'draft_posts.json': draft, 'published_posts.json': published}
            calls = []
            module._RUN = lambda args, **kwargs: calls.append(args)
            with self.assertRaisesRegex(FileExistsError, 'local_editorial_state_already_exists'):
                module.sync_state('bloguito')
            self.assertEqual([], calls)

    def test_invalid_remote_index_is_not_written(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as folder:
            draft = Path(folder) / 'draft_posts.json'
            published = Path(folder) / 'published_posts.json'
            module._FILES = {'draft_posts.json': draft, 'published_posts.json': published}
            module._RUN = lambda args, **kwargs: subprocess.CompletedProcess(
                args, 0, stdout='{"not":"a list"}', stderr='')
            with self.assertRaisesRegex(ValueError, 'invalid_remote_draft_posts.json'):
                module.sync_state('bloguito')
            self.assertFalse(draft.exists())
            self.assertFalse(published.exists())


if __name__ == '__main__':
    unittest.main()
