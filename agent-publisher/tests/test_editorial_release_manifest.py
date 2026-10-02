import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('release_installer', ROOT / 'scripts/install_editorial_release.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class ReleaseManifestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.files = {}
        for name in ('agents/edit_post.py', 'editorial_cli.py', 'agents/edit_orchestration.py', 'editorial_policy.json',
                     'agents/article_renderer.py', 'agents/editorial_schema.py', 'agents/source_collector.py', 'agents/source_extractors.py'):
            path = self.root / 'agent-publisher' / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'original')
            self.files['agent-publisher/' + name] = hashlib.sha256(b'original').hexdigest()
        self.manifest = {'schema_version': 1, 'revision': 'a' * 40, 'files': self.files}
        self.write_manifest()

    def write_manifest(self):
        (self.root / 'release-manifest.json').write_text(json.dumps(self.manifest))

    def test_exact_inventory_and_hashes_are_required(self):
        self.assertEqual(installer.verify_release_manifest(self.root), self.manifest)
        (self.root / 'agent-publisher/editorial_cli.py').write_bytes(b'tampered')
        with self.assertRaisesRegex(ValueError, 'hash_mismatch'):
            installer.verify_release_manifest(self.root)

    def test_unlisted_file_is_rejected(self):
        (self.root / 'agent-publisher/unlisted.py').write_text('unexpected')
        with self.assertRaisesRegex(ValueError, 'inventory_mismatch'):
            installer.verify_release_manifest(self.root)

    def test_missing_required_module_is_rejected(self):
        name = 'agent-publisher/agents/edit_orchestration.py'
        (self.root / name).unlink()
        del self.files[name]
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, 'module_missing'):
            installer.verify_release_manifest(self.root)

    def test_entrypoint_replacement_requires_environment_credentials(self):
        external = "import os\nGEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')\nKAKAO_MAP_JAVASCRIPT_KEY = os.getenv('KAKAO_MAP_JAVASCRIPT_KEY', '')\nSITE_URL = os.getenv('SITE_URL', 'http://localhost')\n"
        self.assertTrue(installer.environment_config_is_external(external))
        self.assertFalse(installer.environment_config_is_external(external.replace("os.getenv('GEMINI_API_KEY', '')", "'inline-credential'")))

    def test_retirement_cannot_delete_arbitrary_operational_files(self):
        self.manifest['retired_files'] = ['data/published_posts.json']
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, 'retirement_scope'):
            installer.verify_release_manifest(self.root)
