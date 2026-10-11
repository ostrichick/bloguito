"""Operator diagnostics never adopt an unknown post or change the journal."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from agents.draft_create_journal import DraftCreateJournal, workflow_key
from agents.draft_create_reconciliation import reconcile_draft_create
from agents.editorial import render, excerpt_from_lead
from test_editorial_system import sample


class DraftReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)
        self.bundle = sample()
        self.content = render(self.bundle['plan'], self.bundle['sources'])
        self.title = self.bundle['plan']['title']
        self.excerpt = excerpt_from_lead(self.bundle['plan']['lead'])
        self.journal = DraftCreateJournal(workflow_key(self.bundle, content=self.content,
                 title=self.title, excerpt=self.excerpt), directory=self.dir)
        self.wp = Mock(return_value={'post_status': 'draft', 'post_title': self.title,
                  'post_name': 'title', 'post_content': self.content,
                  'post_excerpt': self.excerpt})

    def check(self, candidate=None):
        return reconcile_draft_create(self.bundle, candidate_post_id=candidate,
                                      journal_directory=self.dir, wordpress_reader=self.wp)

    def test_missing_journal_cannot_adopt_even_exact_candidate(self):
        report = self.check(509)
        self.assertEqual('missing', report['journal_state'])
        self.assertFalse(report['write_authorized'])
        self.assertFalse(report['automatic_create_retry'])
        self.wp.assert_not_called()

    def test_creating_unknown_never_retries_or_mutates_journal(self):
        self.journal.begin()
        original = self.journal.path.read_bytes()
        report = self.check()
        self.assertIn('do_not_retry', report['next_action'])
        self.wp.assert_not_called()
        candidate = self.check(509)
        self.assertTrue(candidate['live_post_match'])
        self.assertIn('operator_prove_original_post_id_receipt', candidate['next_action'])
        self.assertEqual(original, self.journal.path.read_bytes())

    def test_known_id_live_match_allows_only_canonical_resume(self):
        self.journal.created(509)
        report = self.check()
        self.assertEqual(509, report['inspected_post_id'])
        self.assertTrue(report['live_post_match'])
        self.assertIn('rerun_canonical_prepare_draft', report['next_action'])
        self.assertFalse(report['write_authorized'])

    def test_conflicting_id_and_body_drift_fail_closed(self):
        self.journal.created(509)
        report = self.check(508)
        self.assertIn('conflicts', report['next_action'])
        self.wp.assert_not_called()
        self.wp.return_value = {**self.wp.return_value, 'post_content': '<p>changed</p>'}
        report = self.check(509)
        self.assertFalse(report['live_post_match'])
        self.assertIn('stop_draft_drift', report['next_action'])


if __name__ == '__main__':
    unittest.main()
