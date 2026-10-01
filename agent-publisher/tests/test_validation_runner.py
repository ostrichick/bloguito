import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agents.validation_router import build_validation_plan
from agents.validation_runner import (
    ROOT,
    _load_suite,
    load_test_manifest,
    planned_validation_summary,
    selected_test_files,
)
from tests.test_editorial_system import sample


class ValidationRunnerTests(unittest.TestCase):
    def test_manifest_covers_every_active_test_file(self):
        manifest = load_test_manifest()
        self.assertIn('core-safe-edit', manifest['groups'])
        self.assertIn('full_only', manifest)

    def test_quick_profiles_select_small_subsets(self):
        old = sample()
        new = copy.deepcopy(old)
        new['plan']['sections'][0]['heading'] = '더 간단한 소제목'
        quick = build_validation_plan(old, new)
        quick_files = selected_test_files(quick)
        self.assertLess(len(quick_files), 10)
        self.assertNotIn('test_backup_recovery_v3.py', quick_files)
        self.assertNotIn('test_ticket_validation.py', quick_files)

        image_files = selected_test_files(build_validation_plan(None, None, image_changed=True))
        self.assertLess(len(image_files), len(quick_files))
        self.assertIn('test_featured_image.py', image_files)

    def test_full_regression_selects_every_test(self):
        plan = build_validation_plan(changed_files=['agent-publisher/agents/editorial.py'])
        selected = selected_test_files(plan)
        from agents.validation_runner import TESTS_DIR
        existing = sorted(path.name for path in TESTS_DIR.glob('test_*.py'))
        self.assertEqual(existing, selected)

    def test_plan_digest_tampering_is_rejected(self):
        old = sample()
        new = copy.deepcopy(old)
        new['plan']['sections'][0]['heading'] = '더 간단한 소제목'
        plan = build_validation_plan(old, new, route='fast')
        plan['profile'] = 'full-regression'
        with self.assertRaisesRegex(ValueError, 'validation_plan_digest_mismatch'):
            selected_test_files(plan)

    def test_planned_summary_is_concise_and_shows_safety_promotion(self):
        old = sample()
        new = copy.deepcopy(old)
        new['plan']['lead']['text'] += ' 999원'
        plan = build_validation_plan(old, new, route='fast')

        summary = planned_validation_summary(plan, ['test_fact_validation.py'])

        self.assertIn('Planned validation: profile=standard-fact', summary)
        self.assertIn('route=fast', summary)
        self.assertIn('promoted=quick-text->standard-fact', summary)
        self.assertIn('source=', summary)
        self.assertIn('review=', summary)
        self.assertLess(len(summary), 500)

    def test_exact_post_selector_adds_only_matching_legacy_regression(self):
        old = sample()
        new = copy.deepcopy(old)
        new['plan']['sections'][0]['heading'] = '더 간단한 소제목'
        plan = build_validation_plan(old, new, route='fast', post_id=144)
        files = selected_test_files(plan)
        self.assertIn('test_post144_property_tax_refresh.py', files)
        self.assertNotIn('test_post145_chuseok_toll_refresh.py', files)

    def test_standalone_runner_plans_by_default_and_runs_only_with_flag(self):
        root = Path(__file__).resolve().parents[2]
        script = root / 'scripts' / 'run_validation.py'
        spec = importlib.util.spec_from_file_location('p4_run_validation_test', script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        old = sample()
        new = copy.deepcopy(old)
        new['plan']['sections'][0]['heading'] = '더 간단한 소제목'
        with tempfile.TemporaryDirectory() as folder:
            before = Path(folder) / 'before.json'
            after = Path(folder) / 'after.json'
            before.write_text(json.dumps(old, ensure_ascii=False), encoding='utf-8')
            after.write_text(json.dumps(new, ensure_ascii=False), encoding='utf-8')
            with patch.object(module, 'run_validation_plan') as run, patch('builtins.print'):
                self.assertEqual(0, module.main(['--before', str(before), '--after', str(after)]))
                run.assert_not_called()
            receipt = {
                'status': 'passed', 'profile': 'quick-text', 'tests_run': 1,
                'failures': 0, 'errors': 0, 'skipped': 0, 'selected_files': [],
                'duration_ms': 1.0, 'test_groups': [], 'plan_digest': 'x',
            }
            with patch.object(module, 'run_validation_plan', return_value=receipt) as run, \
                 patch('builtins.print'):
                self.assertEqual(0, module.main([
                    '--before', str(before), '--after', str(after), '--run']))
                run.assert_called_once()

    def test_suite_loader_adds_repository_root_for_scripts_imports(self):
        original_path = list(sys.path)
        removed_modules = {
            key: value for key, value in list(sys.modules.items())
            if key == 'scripts' or key.startswith('scripts.')
        }
        try:
            root = ROOT.resolve()
            sys.path[:] = [
                item for item in sys.path
                if Path(item or '.').resolve() != root
            ]
            for key in removed_modules:
                sys.modules.pop(key, None)
            suite = _load_suite(['test_related_post_navigation.py'])
            self.assertGreater(suite.countTestCases(), 0)
            self.assertIn(str(ROOT), sys.path)
        finally:
            sys.path[:] = original_path
            sys.modules.update(removed_modules)


if __name__ == '__main__':
    unittest.main()
