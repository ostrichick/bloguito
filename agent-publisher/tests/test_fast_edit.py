import copy
import hashlib
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

from agents.editorial import render
from agents.fast_edit import (
    FULL_REVIEW_REQUIRED,
    classify_fast_edit,
    fast_revise_reviewed_draft,
)
from test_editorial_system import NOW, sample


class FastEditTests(unittest.TestCase):
    def _pair(self):
        old = sample()
        new = copy.deepcopy(old)
        new['plan']['sections'][0]['heading'] = '더 간단한 소제목'
        return old, new

    def test_classifier_allows_scoped_wording_edit_with_same_evidence(self):
        old, new = self._pair()
        result = classify_fast_edit(old, new)
        self.assertEqual('candidate', result['status'])

    def test_classifier_rejects_new_number(self):
        old, new = self._pair()
        new['plan']['lead']['text'] += ' 999원'
        result = classify_fast_edit(old, new)
        self.assertEqual(FULL_REVIEW_REQUIRED, result['status'])
        self.assertTrue(any(reason.startswith('new_fact_tokens:') for reason in result['reasons']))

    def test_classifier_rejects_source_or_action_change(self):
        old, new = self._pair()
        new['sources'][0]['url'] = 'https://example.org/changed'
        result = classify_fast_edit(old, new)
        self.assertEqual(FULL_REVIEW_REQUIRED, result['status'])
        self.assertIn('sources_or_actions_changed', result['reasons'])

    def test_fast_revision_uses_only_target_get_update_get(self):
        old, new = self._pair()
        old_body = render(old['plan'], old['sources'])
        new_body = render(new['plan'], new['sources'])
        live = {
            'ID': 393,
            'post_title': old['plan']['title'],
            'post_status': 'draft',
            'post_name': 'stable-slug',
            'post_content': old_body,
            'post_excerpt': old['plan']['lead']['text'],
        }
        # The test fixture lead can be short enough that excerpt normalization
        # differs; use the production helper's exact value.
        from agents.editorial import excerpt_from_lead
        live['post_excerpt'] = excerpt_from_lead(old['plan']['lead'])

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            data = root / 'data'
            data.mkdir()
            index = data / 'draft_posts.json'
            index.write_text(json.dumps([{
                'id': 393,
                'fact_manifest': {'editorial_bundle': old},
            }]), encoding='utf-8')
            calls = []

            def run(args, **kwargs):
                calls.append(args)
                if args[5:7] == ['post', 'get']:
                    return Mock(stdout=json.dumps(live))
                if args[5:7] == ['post', 'update']:
                    live['post_content'] = next(x.split('=', 1)[1] for x in args if x.startswith('--post_content='))
                    live['post_excerpt'] = next(x.split('=', 1)[1] for x in args if x.startswith('--post_excerpt='))
                    return Mock(stdout='Success')
                raise AssertionError(args)

            delta = {
                'mode': 'delta',
                'base_review_digest': old['review']['digest'],
                'base_policy_digest': old['review']['policy_digest'],
                'delta_digest': 'x',
                'checks': {
                    'meaning_preserved': True,
                    'evidence_still_supports': True,
                    'conditions_preserved': True,
                    'no_new_claims': True,
                    'reader_task_preserved': True,
                },
                'issues': [],
                'checked_at': datetime.now().astimezone().isoformat(),
            }
            with patch('agents.fast_edit.ROOT', root), \
                 patch('agents.fast_edit.DRAFTS_INDEX_FILE', index), \
                 patch('agents.fast_edit.validate_fast_edit', return_value={
                     'status': 'candidate', 'reasons': [], 'changed_blocks': {'removed': [], 'added': []}}), \
                 patch('agents.fast_edit._review_delta', return_value=delta), \
                 patch('agents.fast_edit.subprocess.run', side_effect=run):
                result = fast_revise_reviewed_draft(
                    393, new, hashlib.sha256(old_body.encode()).hexdigest(), confirmed=True)

            self.assertEqual(393, result)
            self.assertEqual(new_body, live['post_content'])
            self.assertEqual(3, len(calls))
            self.assertFalse(any(args[5:7] == ['post', 'list'] for args in calls))
            saved = json.loads(index.read_text(encoding='utf-8'))[0]['fact_manifest']['editorial_bundle']
            self.assertIn('fast_edit_review', saved)
            self.assertEqual(old['review'], saved['review'])


if __name__ == '__main__':
    unittest.main()
