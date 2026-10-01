import copy
import hashlib
import tempfile
import unittest
from pathlib import Path

from agents.qa_scope import qa_requirements_for_edit, qa_targets_for_events
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
        scopes = qa_requirements_for_edit(
            old, new, image_changed=True, target_status='publish')
        self.assertIn('content-mobile-desktop', scopes)
        self.assertIn('layout-accessibility', scopes)
        self.assertIn('featured-image', scopes)
        self.assertIn('public-page', scopes)

    def test_event_qa_targets_are_stable_and_event_name_scoped(self):
        bundle = sample()
        bundle['plan']['sections'].extend([
            {'heading': '행사 A', 'paragraphs': [], 'event_name': '행사 A'},
            {'heading': '행사 B', 'paragraphs': [], 'event_name': '행사 B'},
        ])
        self.assertEqual(
            [{'kind': 'event-section', 'event_name': '행사 B'}],
            qa_targets_for_events(bundle, ['없는 행사', '행사 B']),
        )

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

    def test_event_delta_qa_completion_requires_each_scoped_event_target(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            sha = hashlib.sha256(b'event body').hexdigest()
            start_task_state(
                657, action='edit-post', edit_intent='행사 한 곳 정보 수정',
                baseline={'desired_content_sha256': sha},
                qa_requirements=['content-mobile-desktop'],
                validation_plan={
                    'qa_targets': [
                        {'kind': 'event-section', 'event_name': '대구콘텐츠페어'},
                    ],
                },
                root=root,
            )
            update_task_state(
                657, status='saved_pending_qa', completed=['wordpress_saved'],
                result={'desired_content_sha256': sha}, root=root)
            with self.assertRaisesRegex(ValueError, 'browser_qa_target_incomplete'):
                mark_browser_qa_complete(
                    657, sha, completed_scopes=['content-mobile-desktop'], root=root)
            state = mark_browser_qa_complete(
                657, sha, completed_scopes=['content-mobile-desktop'],
                completed_event_names=['대구콘텐츠페어'], root=root)
        self.assertEqual('complete', state['status'])
        self.assertEqual(['대구콘텐츠페어'], state['result']['qa_completed_event_names'])


if __name__ == '__main__':
    unittest.main()
