import hashlib
import unittest
from pathlib import Path
from unittest.mock import patch
import sys

PUBLISHER = Path(__file__).resolve().parents[1]
if str(PUBLISHER) not in sys.path:
    sys.path.insert(0, str(PUBLISHER))

from agents.task_reconciliation import compare_live_snapshot, read_live_task_reconciliation


class TaskReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.body = '<p>current checked content</p>'
        self.sha = hashlib.sha256(self.body.encode()).hexdigest()
        self.post = {'post_status': 'draft', 'post_content': self.body,
                     'post_title': 'Title', 'post_name': 'title', 'post_excerpt': 'Excerpt'}
        self.state = {'post_id': 641, 'baseline': {'expected_content_sha256': 'a' * 64},
                      'result': {'desired_content_sha256': self.sha, 'target_status': 'draft',
                                 'image_phase': {'attachment_id': 723}}}

    def test_exact_live_read_is_scoped_and_never_authorizes_writes(self):
        with patch('agents.wordpress_mutation.read_post_thumbnail_snapshot',
                   return_value=(self.post, '723')) as read:
            result = read_live_task_reconciliation(641, self.state)
        self.assertEqual('matched_post_snapshot', result['status'])
        self.assertEqual({'content_sha256': True, 'post_status': True, 'thumbnail_id': True},
                         result['comparisons'])
        self.assertFalse(result['metadata_verified'])
        self.assertFalse(result['attachment_bytes_verified'])
        self.assertFalse(result['write_authorized'])
        read.assert_called_once()

    def test_external_body_thumbnail_and_status_changes_block_resume(self):
        for post, thumb in [({**self.post, 'post_content': 'other'}, '723'),
                            (self.post, '724'),
                            ({**self.post, 'post_status': 'publish'}, '723')]:
            with self.subTest(post=post, thumb=thumb):
                result = compare_live_snapshot(641, self.state, post, thumb)
                self.assertEqual('live_state_drift', result['status'])
                self.assertFalse(result['write_authorized'])

    def test_missing_record_wrong_target_and_no_sha_never_claim_safe_write(self):
        for state in [None, {'post_id': 642},
                      {'post_id': 641, 'result': {}, 'baseline': {}}]:
            with self.subTest(state=state):
                result = compare_live_snapshot(641, state, self.post, '723')
                self.assertEqual('unverified', result['status'])
                self.assertFalse(result['write_authorized'])
        with patch('agents.wordpress_mutation.read_post_thumbnail_snapshot') as read:
            self.assertEqual('unverified', read_live_task_reconciliation(641, None)['status'])
            read.assert_not_called()

    def test_live_remote_read_errors_propagate_instead_of_becoming_false_success(self):
        with patch('agents.wordpress_mutation.read_post_thumbnail_snapshot',
                   side_effect=RuntimeError('WordPress read failed')):
            with self.assertRaisesRegex(RuntimeError, 'WordPress read failed'):
                read_live_task_reconciliation(641, self.state)
