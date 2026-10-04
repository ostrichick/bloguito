"""Run on OCI with a reviewed release folder; preserve secrets and the cron schedule."""
import argparse
import ast
import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

CANONICAL_INVENTORY_DIGEST = 'b44ce045a958c27e6bcd2e72451570febc1cec64a459228153464cbb62a42995'
ALLOWED_RETIRED_FILES = {
    'agents/copywriter.py',
    'agents/editorial_draft_updater.py',
    'agents/editorial_legacy_draft.py',
}


def inventory_digest(names):
    encoded = json.dumps(sorted(names), ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def verify_release_manifest(release):
    """Verify an explicit release inventory before touching operational files."""
    manifest_path = release / 'release-manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if (set(manifest) != {'schema_version', 'revision', 'inventory_digest', 'files', 'retired_files'}
            or manifest.get('schema_version') != 2
            or not isinstance(manifest.get('revision'), str)
            or len(manifest['revision']) != 40
            or any(char not in '0123456789abcdef' for char in manifest['revision'])
            or not isinstance(manifest.get('files'), dict)
            or not isinstance(manifest.get('inventory_digest'), str)
            or not isinstance(manifest.get('retired_files'), list)):
        raise ValueError('invalid_release_manifest')
    expected = manifest['files']
    computed_inventory_digest = inventory_digest(expected)
    if (manifest['inventory_digest'] != computed_inventory_digest
            or computed_inventory_digest != CANONICAL_INVENTORY_DIGEST):
        raise ValueError('release_inventory_contract_mismatch')
    actual = {p.relative_to(release).as_posix() for folder in ('agent-publisher', 'docs')
              for p in (release / folder).rglob('*') if p.is_file()}
    if set(expected) != actual:
        raise ValueError('release_inventory_mismatch')
    for name, digest in expected.items():
        path = (release / name).resolve()
        if not path.is_relative_to(release.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('release_file_hash_mismatch')
    required = {
        'agent-publisher/main.py',
        'agent-publisher/config.py',
        'agent-publisher/agents/edit_post.py',
        'agent-publisher/agents/edit_orchestration.py',
        'agent-publisher/agents/editorial.py',
        'agent-publisher/agents/editorial_schema.py',
        'agent-publisher/agents/public_fast_edit.py',
        'agent-publisher/agents/source_collector.py',
        'agent-publisher/agents/source_extractors.py',
        'agent-publisher/agents/validation_router.py',
        'agent-publisher/agents/wordpress_mutation.py',
        'agent-publisher/data/renderer_provenance.json',
        'agent-publisher/data/reviewed_content_provenance.json',
        'agent-publisher/editorial_cli.py',
        'agent-publisher/editorial_policy.json',
    }
    if not required.issubset(expected):
        raise ValueError('required_release_module_missing')
    retired = manifest['retired_files']
    if set(retired) != ALLOWED_RETIRED_FILES or len(retired) != len(ALLOWED_RETIRED_FILES):
        raise ValueError('invalid_release_retirement_scope')
    retired_modules = {
        relative[:-3].replace('/', '.')
        for relative in retired
        if relative.endswith('.py')
    }
    if retired_modules and any(
            module in (release / name).read_text(encoding='utf-8')
            for name in expected if name.endswith('.py')
            for module in retired_modules):
        raise ValueError('retired_module_still_referenced')
    return manifest


def environment_config_is_external(text):
    """Refuse replacement of a legacy config containing inline credentials."""
    expected = {'GEMINI_API_KEY', 'KAKAO_MAP_JAVASCRIPT_KEY', 'SITE_URL'}
    expressions = {target.id: node.value for node in ast.parse(text).body
                   if isinstance(node, ast.Assign) for target in node.targets
                   if isinstance(target, ast.Name) and target.id in expected}
    return (set(expressions) == expected and all(
        isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute)
        and isinstance(value.func.value, ast.Name) and value.func.value.id == 'os'
        and value.func.attr == 'getenv'
        for value in expressions.values()))


def install(release, app):
    release, app = release.resolve(), app.resolve()
    if not (app/'main.py').is_file() or not (app/'config.py').is_file():
        raise ValueError('existing_publisher_required')
    release_manifest = verify_release_manifest(release)
    if (not environment_config_is_external((app / 'config.py').read_text(encoding='utf-8'))
            or not environment_config_is_external((release / 'agent-publisher/config.py').read_text(encoding='utf-8'))):
        raise ValueError('entrypoint_release_requires_external_environment_config')
    release_runtime = {
        Path(name).relative_to('agent-publisher').as_posix()
        for name in release_manifest['files']
        if name.startswith('agent-publisher/') and name.endswith('.py')
    }
    existing_agent_runtime = {
        path.relative_to(app).as_posix()
        for path in (app / 'agents').glob('*.py')
        if path.is_file()
    }
    expected_agent_runtime = {
        name for name in release_runtime if name.startswith('agents/')
    }
    unexpected_existing = (
        existing_agent_runtime - expected_agent_runtime - ALLOWED_RETIRED_FILES
    )
    if unexpected_existing:
        raise ValueError('unexpected_existing_runtime_module:' + sorted(unexpected_existing)[0])
    files = [p for p in (release/'agent-publisher').rglob('*') if p.is_file()]
    for p in files:
        relative = p.relative_to(release / 'agent-publisher').as_posix()
        attestation = (
            relative.startswith('data/provenance_attestations/') and p.suffix == '.html'
        )
        if ((p.suffix not in {'.py', '.json'} and not attestation)
                or '.env' in p.parts or '__pycache__' in p.parts):
            raise ValueError('unexpected_release_file')
    backup = app/'backups'/('editorial-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    backup.mkdir(parents=True, mode=0o700)
    changes = []
    policy_documents = (
        'EDITORIAL_SYSTEM.md',
        'GENERAL_POST_STANDARD.md',
        'EVENT_POST_STANDARD.md',
        'FEATURED_IMAGE_STANDARD.md',
    )
    def put(target, data):
        # App files plus the explicit shared policy modules are the only allowed targets.
        allowed_docs = {app.parent/'docs'/name for name in policy_documents}
        if not target.is_relative_to(app) and target not in allowed_docs:
            raise ValueError('target_outside_release_scope')
        existed = target.exists()
        original = target.read_bytes() if existed else None
        token = str(len(changes))
        if existed:
            (backup/token).write_bytes(original)
            (backup/token).chmod(0o600)
        changes.append({'target':str(target),'backup':token if existed else None})
        (backup/'manifest.json').write_text(json.dumps(changes,indent=2),encoding='utf-8')
        target.parent.mkdir(parents=True,exist_ok=True)
        tmp=target.with_name(target.name+'.editorial-new')
        tmp.write_bytes(data);tmp.replace(target)
    try:
        for file in files:
            relative=file.relative_to(release/'agent-publisher')
            put(app/relative,file.read_bytes())
        for name in policy_documents:
            source = release/'docs'/name
            if not source.is_file():
                raise ValueError('required_policy_document_missing:' + name)
            put(app.parent/'docs'/name, source.read_bytes())
        for relative in release_manifest.get('retired_files', []):
            target = app / relative
            if target.exists():
                put(target, b'')
                target.unlink()
        python=app/'venv'/'bin'/'python'
        subprocess.run([str(python),'-B','-c','import main, editorial_cli; import agents.edit_post; import agents.section_image; from agents.editorial_writer import Plan; from agents.editorial import policy, validate_renderer_provenance_registry, validate_reviewed_content_provenance_registry; from agents.critical_facts import validate_critical_fact_registry; validate_critical_fact_registry(); validate_renderer_provenance_registry(); validate_reviewed_content_provenance_registry(); print("Editorial entrypoints and provenance registries ready; minimum days:",policy()["min_remaining_days"])'],cwd=app,check=True)
        installed_hashes = {str(Path(change['target']).relative_to(app.parent)): hashlib.sha256(Path(change['target']).read_bytes()).hexdigest() for change in changes if Path(change['target']).exists()}
        manifest_sha256 = hashlib.sha256((release/'release-manifest.json').read_bytes()).hexdigest()
        put(app/'data'/'editorial-release.json', json.dumps({
            'schema_version': 2, 'revision': release_manifest['revision'],
            'release_manifest_sha256': manifest_sha256,
            'inventory_digest': release_manifest['inventory_digest'],
            'installed_at_utc': datetime.now(timezone.utc).isoformat(),
            'files': installed_hashes,
            'retired_files': release_manifest['retired_files'],
        }, indent=2).encode('utf-8'))
        print('Installed. Rollback manifest:',backup/'manifest.json')
    except Exception:
        for change in reversed(changes):
            target=Path(change['target'])
            if change['backup'] is None:
                target.unlink(missing_ok=True)
            else:
                shutil.copy2(backup/change['backup'],target)
        raise


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('release',type=Path);p.add_argument('app',type=Path)
    a=p.parse_args();install(a.release,a.app)
