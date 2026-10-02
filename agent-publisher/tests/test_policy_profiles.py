"""Semantic policy binding should invalidate only posts affected by a policy change."""

import copy
import unittest
from unittest.mock import patch

from agents import editorial
from tests.test_editorial_system import sample


class PolicyProfileTests(unittest.TestCase):
    def setUp(self):
        self.docs = {
            'EDITORIAL_SYSTEM.md': 'common-v1',
            'GENERAL_POST_STANDARD.md': 'general-v1',
            'EVENT_POST_STANDARD.md': 'event-v1',
        }

    def event_bundle(self):
        bundle = sample()
        bundle['brief']['event_post_standard_version'] = 1
        bundle['temporal_source']['multi_event_schedule'] = True
        return bundle

    def test_general_fingerprint_ignores_event_document_changes(self):
        bundle = sample()
        with patch('agents.editorial._policy_document_text', side_effect=lambda name: self.docs[name]):
            before = editorial.policy_fingerprint(bundle)
            self.docs['EVENT_POST_STANDARD.md'] = 'event-v2'
            after = editorial.policy_fingerprint(bundle)
        self.assertEqual(before, after)

    def test_event_fingerprint_changes_with_event_document(self):
        bundle = self.event_bundle()
        with patch('agents.editorial._policy_document_text', side_effect=lambda name: self.docs[name]):
            before = editorial.policy_fingerprint(bundle)
            self.docs['EVENT_POST_STANDARD.md'] = 'event-v2'
            after = editorial.policy_fingerprint(bundle)
        self.assertNotEqual(before, after)

    def test_general_fingerprint_changes_with_general_document(self):
        bundle = sample()
        with patch('agents.editorial._policy_document_text', side_effect=lambda name: self.docs[name]):
            before = editorial.policy_fingerprint(bundle)
            self.docs['GENERAL_POST_STANDARD.md'] = 'general-v2'
            after = editorial.policy_fingerprint(bundle)
        self.assertNotEqual(before, after)

    def test_featured_image_settings_do_not_invalidate_text_review(self):
        bundle = sample()
        rules = editorial.policy()
        changed = copy.deepcopy(rules)
        changed['featured_image_policy']['version'] += 1
        with patch('agents.editorial._policy_document_text', side_effect=lambda name: self.docs[name]), \
             patch('agents.editorial.policy', return_value=rules):
            before = editorial.policy_fingerprint(bundle)
        with patch('agents.editorial._policy_document_text', side_effect=lambda name: self.docs[name]), \
             patch('agents.editorial.policy', return_value=changed):
            after = editorial.policy_fingerprint(bundle)
        self.assertEqual(before, after)

    def test_only_matching_post_exception_is_bound(self):
        bundle = sample()
        bundle['brief']['id'] = 'target'
        target = {
            'id': 'target', 'status': 'active', 'existing_post_id': 1,
            'useful_until': '2026-12-01', 'expires_on': '2026-12-01',
            'approved_on': '2026-10-02', 'reason': 'target only',
        }
        def lookup(kind, exception_id, **kwargs):
            return copy.deepcopy(target) if kind == 'dated_post' and exception_id == 'target' else None
        with patch('agents.editorial._policy_document_text', side_effect=lambda name: self.docs[name]), \
             patch('agents.editorial.get_policy_exception', side_effect=lookup):
            before = editorial.policy_fingerprint(bundle)
        unrelated_changed = {'id': 'other', 'useful_until': '2026-12-03'}
        self.assertNotEqual(target['id'], unrelated_changed['id'])
        with patch('agents.editorial._policy_document_text', side_effect=lambda name: self.docs[name]), \
             patch('agents.editorial.get_policy_exception', side_effect=lookup):
            after = editorial.policy_fingerprint(bundle)
        self.assertEqual(before, after)


if __name__ == '__main__':
    unittest.main()
