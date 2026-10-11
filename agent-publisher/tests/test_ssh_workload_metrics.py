"""The outer SSH receipt must contain the same bounded workload used by reports."""
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agents.workflow_metrics import workflow_run

SCRIPT = Path(__file__).resolve().parents[2] / 'scripts/editorial_cli_via_ssh.py'


class SshWorkloadMetricTests(unittest.TestCase):
    def test_outer_ssh_receipt_has_bounded_workload_and_route(self):
        spec = importlib.util.spec_from_file_location('ssh_metrics_test', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        sensitive = {'sources': [{'url': 'private_url', 'text': 'private_article'}] * 3}
        scenarios = (
            ('prepare-draft', sensitive, False, 'create', 'sources-3/image-no'),
            ('edit-post', sensitive, True, 'fast', 'sources-3/image-yes'),
            ('replace-featured-image', None, True, 'image-only', 'sources-na/image-yes'),
        )
        for action, bundle, image, route, signature in scenarios:
            with self.subTest(action=action), tempfile.TemporaryDirectory() as folder:
                filename = Path(folder) / 'metrics.jsonl'
                with patch.dict(os.environ, {'EDITORIAL_METRICS_FILE': str(filename)}):
                    with workflow_run('ssh-' + action):
                        module._annotate_primary_workload(action, bundle, image_present=image)
                        if action == 'edit-post':
                            module.annotate(route='fast')
                data = filename.read_text(encoding='utf-8')
                receipt = json.loads(data)
                self.assertEqual(route, receipt['route'])
                self.assertEqual(signature, receipt['workload_signature'])
                self.assertNotIn('private_article', data)
                self.assertNotIn('private_url', data)

    def test_unclassifiable_source_count_does_not_block_workflow(self):
        spec = importlib.util.spec_from_file_location('ssh_metrics_bad_bundle_test', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'metrics.jsonl'
            with patch.dict(os.environ, {'EDITORIAL_METRICS_FILE': str(target)}):
                with workflow_run('ssh-edit-post'):
                    module._annotate_primary_workload('edit-post', {'brief': {}}, image_present=False)
            row = json.loads(target.read_text(encoding='utf-8'))
            self.assertNotIn('workload_signature', row)


if __name__ == '__main__':
    unittest.main()
