import unittest
from unittest.mock import patch

from agents.editorial_legacy_draft import upgrade_legacy_draft


class EvergreenLegacyDraftGuardTests(unittest.TestCase):
    def test_explicit_existing_evergreen_draft_passes_initial_scope_guard(self):
        bundle = {
            'brief': {
                'content_type': 'evergreen',
                'useful_until': None,
                'existing_post_id': 227,
            }
        }
        with patch('agents.editorial_legacy_draft.sync_inventory',
                   side_effect=RuntimeError('guard_passed')):
            with self.assertRaisesRegex(RuntimeError, 'guard_passed'):
                upgrade_legacy_draft(227, bundle, '0' * 64, confirmed=True)

    def test_new_or_dated_nonexception_draft_is_still_rejected(self):
        evergreen_new = {
            'brief': {
                'content_type': 'evergreen',
                'useful_until': None,
                'existing_post_id': 228,
            }
        }
        dated = {
            'brief': {
                'content_type': 'seasonal',
                'useful_until': '2026-09-30',
                'existing_post_id': 227,
            }
        }
        with self.assertRaisesRegex(
                ValueError, 'specific_legacy_draft_upgrade_confirmation_required'):
            upgrade_legacy_draft(227, evergreen_new, '0' * 64, confirmed=True)
        with self.assertRaisesRegex(
                ValueError, 'specific_legacy_draft_upgrade_confirmation_required'):
            upgrade_legacy_draft(227, dated, '0' * 64, confirmed=True)


if __name__ == '__main__':
    unittest.main()
