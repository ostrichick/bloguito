import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from agents.policy_exceptions import get_policy_exception, load_policy_exceptions


class PolicyExceptionRegistryTests(unittest.TestCase):
    def test_dated_exception_preserves_historical_scope_but_expires_currently(self):
        key = '2026-chuseok-rail-post-217-refresh'
        historical = get_policy_exception('dated_post', key, on_date=date(2026, 9, 24))
        current = get_policy_exception('dated_post', key, on_date=date(2026, 10, 2))
        self.assertEqual(217, historical['existing_post_id'])
        self.assertEqual('expired', historical['status'])
        self.assertEqual('2026-09-27', historical['expires_on'])
        self.assertIsNone(current)

    def test_current_gwangju_exception_is_still_active_until_its_end_date(self):
        record = get_policy_exception(
            'dated_post', 'gwangju-october-festivals-2026', on_date=date(2026, 10, 2))
        self.assertEqual('active', record['status'])
        self.assertEqual(666, record['existing_post_id'])
        self.assertEqual('2026-10-25', record['expires_on'])

    def test_legacy_procedure_is_exact_id_and_active(self):
        record = get_policy_exception(
            'legacy_procedure', 'legacy-85-timeless-navigation-full-20260923')
        self.assertEqual(85, record['existing_post_id'])
        self.assertEqual('active', record['status'])
        self.assertIsNone(get_policy_exception('legacy_procedure', 'another-post'))

    def test_malformed_registry_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'dated-posts.json').write_text(json.dumps({
                'schema_version': 1,
                'kind': 'dated_post',
                'exceptions': {'bad': {'id': 'bad', 'status': 'active'}},
            }), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'invalid_policy_exception_post_id'):
                load_policy_exceptions('dated_post', root=root)


if __name__ == '__main__':
    unittest.main()
