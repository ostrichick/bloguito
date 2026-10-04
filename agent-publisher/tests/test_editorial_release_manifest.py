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
        for relative in builder.release_inventory(ROOT):
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'original')
            self.files[relative] = hashlib.sha256(b'original').hexdigest()
        self.manifest = {
            'schema_version': 2,
            'revision': 'a' * 40,
            'inventory_digest': installer.inventory_digest(self.files),
            'files': self.files,
            'retired_files': list(builder.RETIRED_FILES),
        }
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
        self.manifest['inventory_digest'] = installer.inventory_digest(self.files)
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, 'contract_mismatch'):
            installer.verify_release_manifest(self.root)

    def test_manifest_schema_rejects_unknown_or_missing_keys(self):
        self.manifest['unexpected'] = True
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, 'invalid_release_manifest'):
            installer.verify_release_manifest(self.root)
        self.manifest.pop('unexpected')
        self.manifest.pop('retired_files')
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, 'invalid_release_manifest'):
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

    def test_retired_agent_modules_must_not_be_referenced_by_release(self):
        target = self.root / 'agent-publisher' / 'main.py'
        target.write_text('import agents.editorial_legacy_draft\n', encoding='utf-8')
        self.files['agent-publisher/main.py'] = hashlib.sha256(target.read_bytes()).hexdigest()
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, 'retired_module_still_referenced'):
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
        (self.root / 'docs').mkdir(exist_ok=True)
        for name in ('EDITORIAL_SYSTEM.md', 'GENERAL_POST_STANDARD.md', 'EVENT_POST_STANDARD.md', 'FEATURED_IMAGE_STANDARD.md'):
            path = self.root / 'docs' / name
            path.write_text('policy document')
            self.files['docs/' + name] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.write_manifest()
        return app

    def test_entrypoint_install_is_exact_and_does_not_replace_environment(self):
        app = self.entrypoint_release()
        with patch.object(installer.subprocess, 'run') as run:
            installer.install(self.root, app)
        self.assertEqual((self.root / 'agent-publisher/main.py').read_bytes(), (app / 'main.py').read_bytes())
        self.assertEqual('GEMINI_API_KEY=private-environment-value', (app / '.env').read_text())
        receipt = json.loads((app / 'data/editorial-release.json').read_text())
        self.assertEqual('a' * 40, receipt['revision'])
        self.assertEqual(
            hashlib.sha256((self.root / 'release-manifest.json').read_bytes()).hexdigest(),
            receipt['release_manifest_sha256'])
        self.assertEqual(installer.CANONICAL_INVENTORY_DIGEST, receipt['inventory_digest'])
        smoke = run.call_args.args[0]
        self.assertIn('validate_reviewed_content_provenance_registry', smoke[-1])
        self.assertIn('validate_renderer_provenance_registry', smoke[-1])
        self.assertIn('agents.section_image', smoke[-1])

    def test_failed_entrypoint_smoke_restores_original_files(self):
        app = self.entrypoint_release()
        with patch.object(installer.subprocess, 'run', side_effect=RuntimeError('import failed')):
            with self.assertRaisesRegex(RuntimeError, 'import failed'):
                installer.install(self.root, app)
        self.assertEqual('old main', (app / 'main.py').read_text())
        self.assertFalse((app / 'agents/edit_post.py').exists())
        self.assertFalse((app / 'data/editorial-release.json').exists())
        self.assertEqual('GEMINI_API_KEY=private-environment-value', (app / '.env').read_text())

    def test_install_rejects_unknown_agent_module_but_ignores_root_one_off_script(self):
        app = self.entrypoint_release()
        (app / 'agents').mkdir(exist_ok=True)
        (app / 'agents' / 'unknown_runtime.py').write_text('# stale runtime')
        (app / 'one_off_maintenance.py').write_text('# not an import-package member')
        with patch.object(installer.subprocess, 'run'):
            with self.assertRaisesRegex(ValueError, 'unexpected_existing_runtime_module'):
                installer.install(self.root, app)
        (app / 'agents' / 'unknown_runtime.py').unlink()
        with patch.object(installer.subprocess, 'run'):
            installer.install(self.root, app)

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
        self.assertNotIn('agent-publisher/data/search_briefs.json', inventory)
        self.assertIn('agent-publisher/data/renderer_provenance.json', inventory)
        self.assertIn('agent-publisher/data/reviewed_content_provenance.json', inventory)
        self.assertIn(
            'agent-publisher/data/provenance_attestations/post-665-reviewed.html', inventory)
        self.assertFalse(any('/tests/' in name or name.endswith('.example.json') for name in inventory))
        self.assertFalse(any('.env' in name for name in inventory))
        self.assertEqual(
            installer.CANONICAL_INVENTORY_DIGEST,
            builder.inventory_digest(inventory))

    def test_canonical_builder_output_passes_installer_manifest_verification(self):
        with tempfile.TemporaryDirectory() as folder:
            release = Path(folder) / 'release'
            real_git = builder._git
            def clean_inventory_git(root, *args):
                if args == ('diff', 'HEAD', '--name-only'):
                    return ''
                return real_git(root, *args)
            with patch.object(builder, '_git', side_effect=clean_inventory_git):
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

    def test_builder_rejects_untracked_runtime_inventory(self):
        with tempfile.TemporaryDirectory() as folder:
            release = Path(folder) / 'release'
            with patch.object(builder, 'release_inventory',
                              return_value=['agent-publisher/agents/untracked.py']), \
                 patch.object(builder, '_git', side_effect=lambda root, *args: {
                     ('rev-parse', 'HEAD'): 'a' * 40,
                     ('ls-files',): '',
                     ('diff', 'HEAD', '--name-only'): '',
                 }.get(args, '')):
                with self.assertRaisesRegex(ValueError, 'untracked_file'):
                    builder.build_release(release, root=ROOT, require_clean=False)

    def test_builder_rejects_inventory_bytes_not_at_head(self):
        with tempfile.TemporaryDirectory() as folder:
            release = Path(folder) / 'release'
            inventory = builder.release_inventory(ROOT)
            changed = inventory[0]
            real_git = builder._git
            def changed_inventory_git(root, *args):
                if args == ('diff', 'HEAD', '--name-only'):
                    return changed
                return real_git(root, *args)
            with patch.object(builder, '_git', side_effect=changed_inventory_git):
                with self.assertRaisesRegex(ValueError, 'not_at_head'):
                    builder.build_release(release, root=ROOT, require_clean=False)
