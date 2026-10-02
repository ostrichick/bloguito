import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tests.test_event_post_standard import event_bundle


SCRIPT = Path(__file__).resolve().parents[2] / 'scripts' / 'event_post_tool.py'


def load_module():
    spec = importlib.util.spec_from_file_location('event_post_tool_tested', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class EventPostToolTests(unittest.TestCase):
    def test_image_manifest_normalizes_to_stable_webp_and_contact_sheet(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'source.jpg'
            Image.new('RGB', (1600, 1000), color=(220, 230, 240)).save(source, 'JPEG')
            manifest = root / 'manifest.json'
            manifest.write_text(json.dumps({
                'version': 1,
                'images': [{
                    'name': 'opera', 'input': 'source.jpg', 'event_name': '오페라축제',
                    'source_url': 'https://example.go.kr/photo', 'source_year': 2025,
                    'rights': 'open_license', 'rights_url': 'https://www.kogl.or.kr/info/licenseType1.do',
                    'license_label': '공공누리 제1유형', 'depiction': '공연 장면',
                }],
            }, ensure_ascii=False), encoding='utf-8')
            report = module.prepare_event_images(manifest, root / 'processed')
            output = Path(report['images'][0]['path'])
            with Image.open(output) as image:
                self.assertEqual((1200, 675), image.size)
            self.assertTrue(Path(report['contact_sheet']).is_file())
            self.assertEqual('open_license', report['images'][0]['rights'])
            self.assertEqual('공공누리 제1유형', report['images'][0]['license_label'])

    def test_qa_report_matches_event_section_assets(self):
        module = load_module()
        bundle = event_bundle()
        with tempfile.TemporaryDirectory() as folder:
            html = Path(folder) / 'qa.html'
            report = module.qa_event_bundle(bundle, html)
            self.assertEqual('passed', report['status'])
            self.assertTrue(report['checks']['mobile_overview'])
            self.assertTrue(html.is_file())

    def test_validate_builds_standard_event_plan_without_full_regression(self):
        module = load_module()
        bundle = event_bundle()
        report = module.validate_event_candidate(bundle, run_tests=False)
        self.assertEqual('standard-event', report['validation_plan']['profile'])
        self.assertFalse(report['validation_plan']['full_regression_required'])
        self.assertIn('test_event_post_standard.py', report['selected_test_files'])


if __name__ == '__main__':
    unittest.main()
