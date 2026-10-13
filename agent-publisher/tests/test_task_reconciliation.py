import hashlib
import unittest
from pathlib import Path
from unittest.mock import patch
import sys

PUBLISHER = Path(__file__).resolve().parents[1]
if str(PUBLISHER) not in sys.path:
    sys.path.insert(0, str(PUBLISHER))

from agents.task_reconciliation import (
    compare_live_snapshot, read_live_task_reconciliation, inspect_uncertain_image_import,
)


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

    def test_ambiguous_image_import_sha_candidates_never_authorize_retry(self):
        interrupted = {'post_id': 641,
                       'checkpoints': {'image_import_attempt': {
                           'started': True, 'image_sha256': 'b' * 64}}}
        for found, phase in [([], 'no_sha_matching_attachment_outcome_unknown'),
                             ([303], 'single_sha_matching_attachment_unconfirmed'),
                             ([303, 404], 'multiple_sha_matching_attachments_ambiguous')]:
            with self.subTest(found=found), patch(
                    'agents.wordpress_mutation.find_attachment_ids_by_sha', return_value=found) as lookup:
                result = inspect_uncertain_image_import(641, interrupted, 'b' * 64)
                self.assertEqual(phase, result['status'])
                self.assertFalse(result['automatic_retry'])
                self.assertFalse(result['write_authorized'])
                lookup.assert_called_once()

    def test_image_reconciliation_refuses_unbound_or_completed_journal(self):
        with patch('agents.wordpress_mutation.find_attachment_ids_by_sha') as lookup:
            for state in [None, {'post_id': 642},
                          {'post_id': 641, 'checkpoints': {}},
                          {'post_id': 641, 'checkpoints': {'image_import_attempt': {'started': True},
                                                           'image_outcome': {'attachment_id': 90}}}]:
                result = inspect_uncertain_image_import(641, state, 'b' * 64)
                self.assertFalse(result['write_authorized'])
            lookup.assert_not_called()
        with self.assertRaisesRegex(ValueError, 'valid_staged'):
            inspect_uncertain_image_import(641, {'post_id': 641}, 'invalid')

    def test_uncertain_import_lookup_read_failure_propagates(self):
        interrupted = {'post_id': 641,
                       'checkpoints': {'image_import_attempt': {
                           'started': True, 'image_sha256': 'b' * 64}}}
        with patch('agents.wordpress_mutation.find_attachment_ids_by_sha',
                   side_effect=RuntimeError('remote WP unavailable')):
            with self.assertRaisesRegex(RuntimeError, 'remote WP unavailable'):
                inspect_uncertain_image_import(641, interrupted, 'b' * 64)

    def test_operator_sha_probe_must_match_original_import_attempt(self):
        attempt = {'post_id': 641, 'checkpoints': {'image_import_attempt': {
            'started': True, 'image_sha256': 'a' * 64,
            'preexisting_attachment_ids': [303],
        }}}
        with patch('agents.wordpress_mutation.find_attachment_ids_by_sha',
                   return_value=[303, 404]) as lookup:
            mismatch = inspect_uncertain_image_import(641, attempt, 'b' * 64)
        self.assertEqual('unverified', mismatch['status'])
        self.assertEqual('original_attempt_sha_mismatch', mismatch['reason'])
        self.assertFalse(mismatch['write_authorized'])
        lookup.assert_not_called()

        with patch('agents.wordpress_mutation.find_attachment_ids_by_sha',
                   return_value=[303, 404]) as lookup:
            result = inspect_uncertain_image_import(641, attempt, 'a' * 64)
        self.assertEqual('single_sha_matching_attachment_unconfirmed', result['status'])
        self.assertEqual([404], result['candidate_attachment_ids'])
        self.assertFalse(result['ownership_verified'])
        self.assertFalse(result['import_termination_verified'])
        lookup.assert_called_once()
