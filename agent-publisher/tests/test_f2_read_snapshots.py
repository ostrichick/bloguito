"""F2 read consolidation: same-state preimport snapshot, never cached write CAS."""

import importlib.util
import hashlib
import json
import subprocess
import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

PUBLISHER_ROOT = Path(__file__).resolve().parents[1]
if str(PUBLISHER_ROOT) not in sys.path:
    sys.path.insert(0, str(PUBLISHER_ROOT))

from agents.wordpress_mutation import (
    POST_THUMBNAIL_SNAPSHOT_SCRIPT, guarded_set_post_thumbnail,
    read_post_thumbnail_snapshot,
)

ROOT = Path(__file__).resolve().parents[2]
WP = ['sudo', 'docker', 'exec', 'wordpress_app', 'wp']
POST = {
    'post_status': 'draft', 'post_title': '제목', 'post_name': 'slug',
    'post_content': 'body', 'post_excerpt': 'excerpt',
}


def load_adapter():
    spec = importlib.util.spec_from_file_location(
        'f2_transport_under_test', ROOT / 'scripts' / 'editorial_cli_via_ssh.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CombinedSnapshotTests(unittest.TestCase):
    def test_single_fresh_read_has_exact_output_and_one_roundtrip(self):
        seen = []
        def runner(command, **kwargs):
            seen.append((command, kwargs))
            return Mock(stdout=json.dumps({'post': POST, 'thumbnail_id': '70'}))
        with patch('agents.wordpress_mutation.run_wordpress', side_effect=runner), \
             patch('agents.wordpress_mutation.increment') as increment:
            pair = read_post_thumbnail_snapshot(WP, 641, timeout=10)
        self.assertEqual((POST, '70'), pair)
        self.assertEqual(1, len(seen), 'two separate post and meta reads used to require two calls')
        self.assertEqual(WP + ['eval', POST_THUMBNAIL_SNAPSHOT_SCRIPT, '--allow-root'],
                         seen[0][0])
        self.assertEqual({'post_id': 641}, json.loads(seen[0][1]['input']))
        self.assertTrue(seen[0][1]['check'])
        self.assertEqual(10, seen[0][1]['timeout'])
        increment.assert_called_once_with('wp_roundtrips')

    def test_no_cache_second_call_observes_editor_race(self):
        observations = iter([
            {'post': POST, 'thumbnail_id': '70'},
            {'post': {**POST, 'post_title': 'other editor'}, 'thumbnail_id': '999'},
        ])
        with patch('agents.wordpress_mutation.run_wordpress',
                   side_effect=lambda *a, **k: Mock(stdout=json.dumps(next(observations)))) as run:
            first = read_post_thumbnail_snapshot(WP, 641)
            second = read_post_thumbnail_snapshot(WP, 641)
        self.assertEqual(2, run.call_count, 'fresh prewrite snapshot must never be cached')
        self.assertNotEqual(first, second)

    def test_invalid_or_partial_snapshot_fails_closed_no_fallback(self):
        invalid = [
            {'status': 'missing'},
            {'post': POST},
            {'post': POST, 'thumbnail_id': '0'},
            {'post': POST, 'thumbnail_id': -3},
            {'post': {**POST, 'post_content': None}, 'thumbnail_id': '70'},
            {'post': {**POST, 'unexpected': 'x'}, 'thumbnail_id': '70'},
        ]
        for value in invalid:
            with self.subTest(value=value), patch(
                    'agents.wordpress_mutation.run_wordpress',
                    return_value=Mock(stdout=json.dumps(value))) as run:
                with self.assertRaisesRegex(ValueError, 'invalid_post_thumbnail_snapshot_readback'):
                    read_post_thumbnail_snapshot(WP, 641)
                run.assert_called_once()
        with patch('agents.wordpress_mutation.run_wordpress') as run:
            with self.assertRaisesRegex(ValueError, 'invalid_post_thumbnail_snapshot_target'):
                read_post_thumbnail_snapshot(WP, True)
            run.assert_not_called()

    def test_remote_response_loss_propagates_no_stale_read_retry_here(self):
        with patch('agents.wordpress_mutation.run_wordpress',
                   side_effect=subprocess.TimeoutExpired('wp', 10)) as run:
            with self.assertRaises(subprocess.TimeoutExpired):
                read_post_thumbnail_snapshot(WP, 641, timeout=10)
        run.assert_called_once()

    def test_parallel_editor_change_between_read_and_guarded_cas_still_blocks(self):
        # This test simulates a separate editor committing immediately after
        # the combined read and before the guarded server-side mutation.
        changed = threading.Event()
        world = {'title': POST['post_title'], 'thumb': '70', 'mutations': 0}
        requests = []
        def server(command, **kwargs):
            requests.append(command)
            if command[6] == POST_THUMBNAIL_SNAPSHOT_SCRIPT:
                return Mock(stdout=json.dumps({
                    'post': dict(POST), 'thumbnail_id': world['thumb']}))
            if not changed.is_set():
                raise AssertionError('concurrent change was not injected')
            expected = json.loads(kwargs['input'])['expected']
            self.assertNotEqual(expected['post_title'], world['title'])
            return Mock(stdout=json.dumps({'status': 'cas_mismatch'}))
        def editor():
            world['title'] = 'edited by another process'
            world['thumb'] = '999'
            changed.set()
        with patch('agents.wordpress_mutation.run_wordpress', side_effect=server):
            baseline, thumb = read_post_thumbnail_snapshot(WP, 641)
            worker = threading.Thread(target=editor)
            worker.start()
            worker.join(timeout=3)
            self.assertTrue(changed.is_set())
            with self.assertRaisesRegex(ValueError, 'wordpress_guarded_cas_mismatch'):
                guarded_set_post_thumbnail(
                    WP, 641, expected={
                        'post_status': baseline['post_status'],
                        'post_title': baseline['post_title'],
                        'post_name': baseline['post_name'],
                        'post_excerpt': baseline['post_excerpt'],
                        'content_sha256': hashlib.sha256(
                            baseline['post_content'].encode()).hexdigest(),
                    }, expected_thumbnail_id=int(thumb), attachment_id=777)
        self.assertEqual(2, len(requests), 'one snapshot and one independent mutation CAS')
        self.assertEqual(0, world['mutations'])

    def test_adapter_readonly_allowlist_and_exact_target_are_unchanged(self):
        adapter = load_adapter()
        calls = []
        def remote(args, **kwargs):
            calls.append((args, kwargs))
            return subprocess.CompletedProcess(
                args, 0, stdout=json.dumps({'post': POST, 'thumbnail_id': '70'}), stderr='')
        adapter._RUN = remote
        command = WP + ['eval', POST_THUMBNAIL_SNAPSHOT_SCRIPT, '--allow-root']
        payload = json.dumps({'post_id': 641})
        invoke = adapter.make_transport('replace-featured-image', {641}, 'bloguito')
        outcome = invoke(command, input=payload, capture_output=True, text=True, check=True)
        self.assertEqual(0, outcome.returncode)
        self.assertEqual(1, len(calls))
        self.assertIn('sudo docker exec -i wordpress_app wp eval', calls[0][0][-1])
        self.assertEqual(payload, calls[0][1]['input'])
        self.assertTrue(calls[0][1]['check'])
        for bad in ({'post_id': 642}, {'post_id': True},
                    {'post_id': 641, 'other': 'x'}, {'post_id': '641'}):
            with self.subTest(bad=bad), self.assertRaisesRegex(
                    ValueError, 'invalid_image_snapshot_request'):
                invoke(command, input=json.dumps(bad), capture_output=True, text=True)
        self.assertEqual(1, len(calls), 'rejected payload must not open an SSH call')
        narrow = adapter.make_transport('public-standard', {641}, 'bloguito')
        with self.assertRaisesRegex(ValueError, 'unexpected_wordpress_command'):
            narrow(command, input=payload, capture_output=True, text=True)
        self.assertEqual(1, len(calls))


if __name__ == '__main__':
    unittest.main()
