"""The refreshed legacy index must fail on stale input and avoid approval claims."""

import importlib.util
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[2] / 'scripts' / 'build_legacy_current_dashboard.py'
SPEC = importlib.util.spec_from_file_location('legacy_current_dashboard', SCRIPT)
dashboard = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = dashboard
SPEC.loader.exec_module(dashboard)
NOW = datetime(2026, 9, 23, 9, tzinfo=timezone(timedelta(hours=9)))


def example():
    return {
        'schema_version': 2, 'site': 'https://lifeinfo24.org',
        'complete': True, 'audited_at': NOW.isoformat(), 'expected_total': 1,
        'changes': {'missing_from_public_snapshot_ids': [77]},
        'posts': [{
            'id': 63, 'title': '<script>unsafe</script>',
            'url': 'https://lifeinfo24.org/post-63/',
            'text_characters': 674, 'flags': ['legacy_layout'],
            'fact_review_status': 'unverified', 'visual_review_status': 'unverified',
            'link_behavior_review_status': 'unverified',
        }],
    }


class CurrentDashboardTests(unittest.TestCase):
    def test_requires_complete_current_site_and_date(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'triage.json'
            for key, value in (('complete', False), ('expected_total', 2),
                               ('site', 'https://other.example'),
                               ('audited_at', '2026-09-22T12:00:00+09:00')):
                data = example()
                data[key] = value
                path.write_text(json.dumps(data), encoding='utf-8')
                with self.subTest(key=key), self.assertRaises(ValueError):
                    dashboard.load_triage(path, NOW)

    def test_independent_review_cannot_be_claimed_from_structure_audit(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'triage.json'
            data = example()
            data['posts'][0]['fact_review_status'] = 'verified'
            path.write_text(json.dumps(data), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'audit_status_is_not_independent_review'):
                dashboard.load_triage(path, NOW)

    def test_public_only_html_escapes_title_and_marks_removed_id_uncertain(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'index.html'
            with patch.object(dashboard, 'candidate', return_value=None):
                content = dashboard.render(example(), output)
            self.assertIn('&lt;script&gt;unsafe&lt;/script&gt;', content)
            self.assertNotIn('<script>unsafe</script>', content)
            self.assertIn('#77', content)
            self.assertIn('공개 REST만으로 알 수 없습니다', content)
            self.assertNotIn('PRIVATE.json', content)
            self.assertNotIn('운영 사이트 변경 0건', content)


if __name__ == '__main__':
    unittest.main()
