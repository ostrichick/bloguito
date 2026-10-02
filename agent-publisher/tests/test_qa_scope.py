import copy
import hashlib
import tempfile
import unittest
from pathlib import Path

from agents.change_classifier import classify_change
from agents.task_state import mark_browser_qa_complete, start_task_state, update_task_state
from test_editorial_system import sample


class QaScopeTests(unittest.TestCase):
    def test_content_table_and_image_public_scopes_are_derived(self):
        old = sample()
        new = copy.deepcopy(old)
        new['plan']['sections'][0]['table'] = {
            'caption': '비교', 'headers': ['항목', '내용'],
            'rows': [{'cells': ['A', 'B'], 'evidence': []}],
        }
        scopes = classify_change(
            old, new, image_changed=True, target_status='publish')['qa_scopes']
        self.assertIn('content-mobile-desktop', scopes)
        self.assertIn('layout-accessibility', scopes)
        self.assertNotIn('featured-image', scopes)
        self.assertNotIn('public-page', scopes)

    def test_text_and_image_only_edits_skip_browser_qa(self):
        old = sample()
        text = copy.deepcopy(old)
        text['plan']['sections'][0]['heading'] = '더 짧은 안내'
        self.assertEqual([], classify_change(old, text, target_status='publish')['qa_scopes'])
        self.assertEqual([], classify_change(
            None, None, image_changed=True, target_status='publish')['qa_scopes'])

    def test_qa_completion_requires_all_scopes_and_matching_thumbnail(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            sha = hashlib.sha256(b'body').hexdigest()
            start_task_state(
                641, action='edit-post', edit_intent='이미지 포함 문구 수정',
                baseline={'desired_content_sha256': sha},
                qa_requirements=['content-mobile-desktop', 'featured-image'], root=root)
            update_task_state(
                641, status='saved_pending_qa', completed=['wordpress_saved'],
                result={'desired_content_sha256': sha, 'image_phase': {'attachment_id': 777}},
                root=root)
            with self.assertRaisesRegex(ValueError, 'browser_qa_scope_incomplete'):
                mark_browser_qa_complete(
                    641, sha, completed_scopes=['content-mobile-desktop'], root=root)
            with self.assertRaisesRegex(ValueError, 'browser_qa_thumbnail_mismatch'):
                mark_browser_qa_complete(
                    641, sha,
                    completed_scopes=['content-mobile-desktop', 'featured-image'],
                    observed_thumbnail_id=778, root=root)
            state = mark_browser_qa_complete(
                641, sha,
                completed_scopes=['content-mobile-desktop', 'featured-image'],
                observed_thumbnail_id=777, root=root)
        self.assertEqual('complete', state['status'])


if __name__ == '__main__':
    unittest.main()
