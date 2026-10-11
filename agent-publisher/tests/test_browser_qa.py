"""Deterministic QA verifier tests. Screenshots are synthetic test fixtures.

These tests DO NOT assert that a WordPress page was opened in a real browser.
"""
import copy
import hashlib
import json
import subprocess
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

from agents.browser_qa import evaluate_browser_qa, verify_qa_completion_receipt


REPO = Path(__file__).resolve().parents[2]


def fixture(root, *, render_source='wordpress_theme', scopes=None, cta=False, calculator=False):
    """Create two synthetic screenshot fixtures and plausible test-only DOM data."""
    scopes = scopes if scopes is not None else ['content-mobile-desktop', 'layout-accessibility']
    url = ('file:///C:/test.html' if render_source == 'local_static'
           else 'https://lifeinfo24.org/?p=641&preview=1' if render_source == 'authenticated_preview'
           else 'https://lifeinfo24.org/?p=641')
    config = {'cta_targets': ['https://example.org/allowed'] if cta else [],
              'calculator_cases': [{'id': 'basic', 'expected_text': '42'}] if calculator else []}
    screens = []
    for width, height in [(390, 844), (1280, 900)]:
        name = f'fixture-{width}.png'
        img = root / name
        Image.new('RGB', (width, height), 'white').save(img)
        image_sha = hashlib.sha256(img.read_bytes()).hexdigest()
        small = width == 390
        observation = {
            'ready_state': 'complete', 'inner_width': width,
            'client_width': width, 'scroll_width': width,
            'wp_theme_dom': render_source != 'local_static',
            'authenticated_dom': render_source == 'authenticated_preview',
            'zoom_simulated_half_viewport': {
                'kind': 'css_half_width_reflow_not_native_zoom',
                'width': width // 2,
                'metrics': {'inner_width': width // 2, 'client_width': width // 2,
                            'scroll_width': width // 2},
            },
            'toc': {'links': [{'href': '#step-1', 'target_found': True,
                               'target_unique': True, 'click_hash_matched': True}]},
            'tables': [{'caption': 'Comparison', 'headers': 3, 'rows': 2,
                        'region': True, 'focusable': True, 'visible': not small,
                        'has_mobile_cards': True, 'cards_visible': small,
                        'card_count': 2, 'client_width': 310 if small else 900,
                        'scroll_width': 580 if small else 900,
                        'keyboard_scroll_delta': 0}],
            'links': [{'href': '#step-1', 'valid': True, 'target_existing': True}],
            'ctas': [{'href': 'https://example.org/allowed', 'target': '_self',
                      'click_navigation_verified': cta,
                      'navigated_url': 'https://example.org/allowed' if cta else ''}],
            'calculator_present': calculator,
            'calculator_cases': [{'id': 'basic', 'inputs_executed': True,
                                  'result_observed': True, 'text': 'result is 42'}] if calculator else [],
        }
        screens.append({'viewport': {'width': width, 'height': height},
                        'url': url, 'screenshot': {'path': name, 'sha256': image_sha},
                        'observation': observation})
    return {'schema': 1, 'post_id': 641, 'content_sha256': 'a' * 64,
            'render_source': render_source, 'url': url,
            'executed_at': datetime.now(timezone.utc).isoformat(),
            'execution': {'engine': 'existing_cdp_session', 'target_id': 'test-only-target-123',
                          'user_agent': 'synthetic-test-not-a-real-browser'},
            'required_scopes': scopes, 'config': config, 'screens': screens}


class BrowserQaEvidenceTests(unittest.TestCase):
    def test_theme_receipt_passes_from_two_observed_viewports(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            evidence = fixture(root)
            decision = evaluate_browser_qa(evidence, evidence_dir=root)
            self.assertEqual('browser_pass', decision['status'])
            self.assertEqual(['content-mobile-desktop', 'layout-accessibility'],
                             decision['eligible_wp_completed_scopes'])
            self.assertEqual('not_verified_by_cdp_viewport_simulation', decision['native_zoom_200pct'])

    def test_static_browser_render_cannot_complete_wordpress_task(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            evidence = fixture(root, render_source='local_static')
            decision = evaluate_browser_qa(evidence, evidence_dir=root)
            self.assertEqual('local_static_browser_pass_only', decision['status'])
            self.assertEqual([], decision['eligible_wp_completed_scopes'])
            path = root / 'browser.json'
            path.write_text(json.dumps(evidence), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'scope_unverified'):
                verify_qa_completion_receipt(path, post_id=641,
                                             content_sha256='a' * 64,
                                             required_scopes={'content-mobile-desktop'})

    def test_no_browser_execution_metadata_does_not_masquerade_as_pass(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            evidence = fixture(root)
            evidence['execution'] = {'engine': 'static_html_scan', 'target_id': 'fake', 'user_agent': 'manual'}
            evidence['status'] = 'browser_pass'  # never trusted
            with self.assertRaisesRegex(ValueError, 'actual_execution_evidence_required'):
                evaluate_browser_qa(evidence, evidence_dir=root)

    def test_mobile_body_overflow_blocks_completion(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            evidence = fixture(root)
            evidence['screens'][0]['observation']['scroll_width'] = 600
            result = evaluate_browser_qa(evidence, evidence_dir=root)
            self.assertEqual('needs_browser_or_manual_review', result['status'])
            self.assertIn('390:document_overflow:fail',
                          result['incomplete_scopes']['content-mobile-desktop'])

    def test_missing_table_keyboard_scroll_or_toc_id_blocks(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            evidence = fixture(root)
            evidence['screens'][1]['observation']['tables'][0].update(
                scroll_width=1100, keyboard_scroll_delta=0)
            evidence['screens'][0]['observation']['toc']['links'][0]['target_unique'] = False
            result = evaluate_browser_qa(evidence, evidence_dir=root)
            self.assertIn('1280:tables_cards_keyboard:fail',
                          result['incomplete_scopes']['layout-accessibility'])
            self.assertIn('390:toc_anchors:fail',
                          result['incomplete_scopes']['content-mobile-desktop'])

    def test_cards_must_match_table_rows_by_viewport(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            evidence=fixture(root)
            evidence['screens'][0]['observation']['tables'][0]['card_count']=1
            result=evaluate_browser_qa(evidence,evidence_dir=root)
            self.assertIn('390:tables_cards_keyboard:fail',
                          result['incomplete_scopes']['content-mobile-desktop'])

    def test_zoom_half_width_reflow_failure_blocks_accessibility_not_claim_native(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            evidence=fixture(root)
            evidence['screens'][0]['observation']['zoom_simulated_half_viewport']['metrics']['scroll_width']=410
            result=evaluate_browser_qa(evidence,evidence_dir=root)
            self.assertIn('390:zoom_reflow_simulated:fail',
                          result['incomplete_scopes']['layout-accessibility'])
            self.assertEqual('not_verified_by_cdp_viewport_simulation',result['native_zoom_200pct'])

    def test_cta_href_alone_without_actual_navigation_is_unverified(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            evidence=fixture(root, scopes=['cta-destination'])
            result=evaluate_browser_qa(evidence,evidence_dir=root)
            self.assertEqual('unverified',result['observed_checks']['390']['cta_destination'])
            self.assertEqual([],result['completed_scopes'])
            evidence=fixture(root, scopes=['cta-destination'], cta=True)
            self.assertEqual(['cta-destination'],evaluate_browser_qa(evidence,evidence_dir=root)['completed_scopes'])

    def test_calculator_requires_input_and_result_expectations(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            evidence=fixture(root,calculator=True)
            result=evaluate_browser_qa(evidence,evidence_dir=root)
            self.assertEqual('browser_pass',result['status'])
            evidence['screens'][0]['observation']['calculator_cases'][0]['text']='wrong result'
            result=evaluate_browser_qa(evidence,evidence_dir=root)
            self.assertIn('calculator_inputs_results_incomplete',
                          result['incomplete_scopes']['layout-accessibility'])
            evidence['config']['calculator_cases']=[]
            result=evaluate_browser_qa(evidence,evidence_dir=root)
            self.assertIn('calculator_inputs_results_incomplete',
                          result['incomplete_scopes']['content-mobile-desktop'])

    def test_missing_or_modified_screenshot_cannot_pass(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            evidence=fixture(root)
            (root/'fixture-390.png').write_bytes(b'not-the-screenshot')
            with self.assertRaisesRegex(ValueError,'screenshot_hash_mismatch'):
                evaluate_browser_qa(evidence,evidence_dir=root)
            evidence['screens'][0]['screenshot']['sha256']=hashlib.sha256(b'not-the-screenshot').hexdigest()
            with self.assertRaisesRegex(ValueError,'screenshot_decode_failed'):
                evaluate_browser_qa(evidence,evidence_dir=root)

    def test_wrong_post_sha_and_preview_provenance_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            evidence=fixture(root)
            path=root/'evidence.json'
            path.write_text(json.dumps(evidence),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'content_binding_mismatch'):
                verify_qa_completion_receipt(path,post_id=642,content_sha256='a'*64,
                                             required_scopes={'content-mobile-desktop'})
            evidence['render_source']='authenticated_preview'
            with self.assertRaisesRegex(ValueError,'render_source_url_conflict'):
                evaluate_browser_qa(evidence,evidence_dir=root)

    def test_unsupported_public_page_or_featured_image_not_auto_approved(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            evidence=fixture(root,scopes=['public-page','featured-image'])
            result=evaluate_browser_qa(evidence,evidence_dir=root)
            self.assertFalse(result['eligible_wp_completed_scopes'])
            self.assertEqual('outside_q1_browser_harness',result['incomplete_scopes']['public-page'])

    def test_node_browser_runner_requires_existing_cdp_target(self):
        script=REPO/'scripts/browser_qa_harness.mjs'
        syntax=subprocess.run(['node','--check',str(script)],capture_output=True,text=True)
        self.assertEqual(0,syntax.returncode,syntax.stderr)
        invocation=subprocess.run(['node',str(script)],capture_output=True,text=True)
        self.assertNotEqual(0,invocation.returncode)
        self.assertIn('required_browser_qa_options_missing',invocation.stderr)


if __name__=='__main__':
    unittest.main()
