import copy
import unittest

from agents.editorial import (
    validate_bundle,
    validate_content,
    validate_review_binding,
    validate_site_context,
    validate_sources,
)
from test_editorial_system import NOW, sample


class ValidationScopeTests(unittest.TestCase):
    def test_full_validation_still_matches_combined_scopes(self):
        bundle = sample()
        inventory = {'checked_on': NOW.date().isoformat(), 'posts': []}
        full = validate_bundle(bundle, inventory, now=NOW)
        combined = validate_bundle(
            bundle,
            inventory,
            now=NOW,
            scopes={'content', 'source', 'site', 'review'},
        )
        self.assertEqual(full, combined)

    def test_content_scope_does_not_require_inventory(self):
        bundle = sample()
        result = validate_content(bundle, now=NOW)
        self.assertNotIn('fresh_inventory_required', result['reasons'])

    def test_source_scope_detects_hash_mismatch_without_content_review(self):
        bundle = sample()
        broken = copy.deepcopy(bundle)
        broken['sources'][0]['sha256'] = '0' * 64
        result = validate_sources(broken, now=NOW)
        self.assertIn('source_hash_mismatch', result['reasons'])
        self.assertNotIn('review_not_bound_to_current_content', result['reasons'])

    def test_site_scope_requires_fresh_inventory_but_not_review(self):
        bundle = sample()
        result = validate_site_context(bundle, {'checked_on': '2000-01-01', 'posts': []}, now=NOW)
        self.assertEqual(['fresh_inventory_required'], result['reasons'])

    def test_review_scope_detects_changed_plan_only_as_binding_problem(self):
        bundle = sample()
        changed = copy.deepcopy(bundle)
        changed['plan']['lead']['text'] += ' 변경'
        result = validate_review_binding(changed, now=NOW)
        self.assertIn('review_not_bound_to_current_content', result['reasons'])
        self.assertNotIn('number_without_evidence', result['reasons'])


if __name__ == '__main__':
    unittest.main()
