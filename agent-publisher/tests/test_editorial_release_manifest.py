import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('release_installer', ROOT / 'scripts/install_editorial_release.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)
builder_spec = importlib.util.spec_from_file_location(
    'release_builder', ROOT / 'scripts/build_editorial_release.py')
builder = importlib.util.module_from_spec(builder_spec)
builder_spec.loader.exec_module(builder)


class ReleaseManifestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.files = {}
        for name in (
                'agents/edit_post.py', 'editorial_cli.py', 'agents/edit_orchestration.py',
                'editorial_policy.json', 'agents/article_renderer.py', 'agents/editorial.py',
                'agents/editorial_schema.py', 'agents/public_fast_edit.py',
                'agents/source_collector.py', 'agents/source_extractors.py',
                'agents/validation_router.py', 'agents/wordpress_mutation.py',
                'data/renderer_provenance.json'):
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

    def entrypoint_release(self):
        app = self.root / 'existing-app'
        app.mkdir()
        config = "import os\nGEMINI_API_KEY=os.getenv('GEMINI_API_KEY', '')\nKAKAO_MAP_JAVASCRIPT_KEY=os.getenv('KAKAO_MAP_JAVASCRIPT_KEY', '')\nSITE_URL=os.getenv('SITE_URL', 'http://localhost')\n"
        (app / 'config.py').write_text(config)
        (app / 'main.py').write_text('old main')
        (app / '.env').write_text('GEMINI_API_KEY=private-environment-value')
        for name, text in {'agent-publisher/config.py': config, 'agent-publisher/main.py': '# exact new entrypoint\n'}.items():
            (self.root / name).write_text(text)
            self.files[name] = hashlib.sha256((self.root / name).read_bytes()).hexdigest()
        (self.root / 'docs').mkdir()
        for name in ('EDITORIAL_SYSTEM.md', 'GENERAL_POST_STANDARD.md', 'EVENT_POST_STANDARD.md', 'FEATURED_IMAGE_STANDARD.md'):
            path = self.root / 'docs' / name
            path.write_text('policy document')
            self.files['docs/' + name] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.write_manifest()
        return app

    def test_entrypoint_install_is_exact_and_does_not_replace_environment(self):
        app = self.entrypoint_release()
        with patch.object(installer.subprocess, 'run'):
            installer.install(self.root, app)
        self.assertEqual((self.root / 'agent-publisher/main.py').read_bytes(), (app / 'main.py').read_bytes())
        self.assertEqual('GEMINI_API_KEY=private-environment-value', (app / '.env').read_text())
        self.assertEqual('a' * 40, json.loads((app / 'data/editorial-release.json').read_text())['revision'])

    def test_failed_entrypoint_smoke_restores_original_files(self):
        app = self.entrypoint_release()
        with patch.object(installer.subprocess, 'run', side_effect=RuntimeError('import failed')):
            with self.assertRaisesRegex(RuntimeError, 'import failed'):
                installer.install(self.root, app)
        self.assertEqual('old main', (app / 'main.py').read_text())
        self.assertFalse((app / 'agents/edit_post.py').exists())
        self.assertFalse((app / 'data/editorial-release.json').exists())
        self.assertEqual('GEMINI_API_KEY=private-environment-value', (app / '.env').read_text())

    def test_canonical_builder_includes_all_agent_runtime_modules_and_excludes_tests(self):
        inventory = builder.release_inventory(ROOT)
        runtime_agents = {
            path.relative_to(ROOT).as_posix()
            for path in (ROOT / 'agent-publisher' / 'agents').glob('*.py')
        }
        self.assertTrue(runtime_agents.issubset(set(inventory)))
        self.assertIn('agent-publisher/agents/editorial.py', inventory)
        self.assertIn('agent-publisher/agents/public_fast_edit.py', inventory)
        self.assertIn('agent-publisher/agents/validation_router.py', inventory)
        self.assertIn('agent-publisher/data/search_briefs.json', inventory)
        self.assertIn('agent-publisher/data/renderer_provenance.json', inventory)
        self.assertFalse(any('/tests/' in name or name.endswith('.example.json') for name in inventory))
        self.assertFalse(any('.env' in name for name in inventory))

    def test_canonical_builder_output_passes_installer_manifest_verification(self):
        with tempfile.TemporaryDirectory() as folder:
            release = Path(folder) / 'release'
            result = builder.build_release(release, root=ROOT, require_clean=False)
            manifest = installer.verify_release_manifest(release)
        self.assertEqual(builder._git(ROOT, 'rev-parse', 'HEAD'), manifest['revision'])
        self.assertEqual(result['files'], len(manifest['files']))
        self.assertIn('agent-publisher/agents/editorial.py', manifest['files'])

    def test_canonical_builder_rejects_revision_not_matching_checkout_head(self):
        with tempfile.TemporaryDirectory() as folder:
            release = Path(folder) / 'release'
            with self.assertRaisesRegex(ValueError, 'revision_must_match_head'):
                builder.build_release(
                    release, root=ROOT, revision='b' * 40, require_clean=False)
            self.assertFalse(release.exists())
