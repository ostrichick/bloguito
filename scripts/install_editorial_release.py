"""Run on OCI with a reviewed release folder; preserve secrets and the cron schedule."""
import argparse
import ast
import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def verify_release_manifest(release):
    """Verify an explicit release inventory before touching operational files."""
    manifest = json.loads((release / 'release-manifest.json').read_text(encoding='utf-8'))
    if (manifest.get('schema_version') != 1
            or not isinstance(manifest.get('revision'), str)
            or len(manifest['revision']) != 40
            or any(char not in '0123456789abcdef' for char in manifest['revision'])
            or not isinstance(manifest.get('files'), dict)):
        raise ValueError('invalid_release_manifest')
    expected = manifest['files']
    actual = {p.relative_to(release).as_posix() for folder in ('agent-publisher', 'docs')
              for p in (release / folder).rglob('*') if p.is_file()}
    if set(expected) != actual:
        raise ValueError('release_inventory_mismatch')
    for name, digest in expected.items():
        path = (release / name).resolve()
        if not path.is_relative_to(release.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('release_file_hash_mismatch')
    required = {'agent-publisher/agents/edit_post.py', 'agent-publisher/editorial_cli.py',
                'agent-publisher/agents/edit_orchestration.py', 'agent-publisher/editorial_policy.json',
                'agent-publisher/agents/article_renderer.py', 'agent-publisher/agents/editorial_schema.py',
                'agent-publisher/agents/source_collector.py', 'agent-publisher/agents/source_extractors.py'}
    if not required.issubset(expected):
        raise ValueError('required_release_module_missing')
    retired = manifest.get('retired_files', [])
    if not isinstance(retired, list) or set(retired) - {'agents/copywriter.py'}:
        raise ValueError('invalid_release_retirement_scope')
    if retired and any('agents.copywriter' in (release / name).read_text(encoding='utf-8')
                       for name in expected if name.endswith('.py')):
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
    replace_entrypoints = (release / 'agent-publisher/main.py').is_file() or (release / 'agent-publisher/config.py').is_file()
    if replace_entrypoints and (
            not (release / 'agent-publisher/main.py').is_file()
            or not (release / 'agent-publisher/config.py').is_file()
            or not environment_config_is_external((app / 'config.py').read_text(encoding='utf-8'))
            or not environment_config_is_external((release / 'agent-publisher/config.py').read_text(encoding='utf-8'))):
        raise ValueError('entrypoint_release_requires_external_environment_config')
    files = [p for p in (release/'agent-publisher').rglob('*') if p.is_file()]
    for p in files:
        if p.suffix not in {'.py', '.json'} or '.env' in p.parts or '__pycache__' in p.parts:
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
            # Existing topic research is user data. Do not replace the server's reviewed list.
            if relative.as_posix()=='data/search_briefs.json' and (app/relative).exists():
                continue
            put(app/relative,file.read_bytes())
        for name in policy_documents:
            source = release/'docs'/name
            if not source.is_file():
                raise ValueError('required_policy_document_missing:' + name)
            put(app.parent/'docs'/name, source.read_bytes())
        text=(app/'config.py').read_text(encoding='utf-8')
        names={node.id for node in ast.walk(ast.parse(text)) if isinstance(node,ast.Name) and isinstance(node.ctx,ast.Store)}
        if 'DRAFTS_INDEX_FILE' not in names:
            text+='\nDRAFTS_INDEX_FILE = DATA_DIR / "draft_posts.json"\n'
        if 'SITE_URL' not in names:
            text+='\nSITE_URL = "http://localhost"  # Fallback only; actual permalinks are read from WordPress.\n'
        put(app/'config.py',text.encode('utf-8'))
        text=(app/'main.py').read_text(encoding='utf-8')
        old='from agents.copywriter import CopywriterAgent'
        new='from agents.editorial_writer import EditorialWriterAgent as CopywriterAgent'
        if old not in text and new not in text:
            raise ValueError('unknown_main_entry_point')
        text=text.replace(old,new)
        if 'from sync_wordpress_inventory import sync_inventory' not in text:
            text=text.replace(new,new+'\nfrom sync_wordpress_inventory import sync_inventory')
        if '    sync_inventory()' not in text:
            text=text.replace('    radar = RadarAgent()', '    sync_inventory()\n    radar = RadarAgent()')
        put(app/'main.py',text.encode('utf-8'))
        for relative in release_manifest.get('retired_files', []):
            target = app / relative
            if target.exists():
                put(target, b'')
                target.unlink()
        python=app/'venv'/'bin'/'python'
        subprocess.run([str(python),'-B','-c','import main, editorial_cli; import agents.edit_post; from agents.editorial_writer import Plan; from agents.editorial import policy; from agents.critical_facts import validate_critical_fact_registry; validate_critical_fact_registry(); print("Editorial entrypoints and critical-fact registry ready; minimum days:",policy()["min_remaining_days"])'],cwd=app,check=True)
        installed_hashes = {str(Path(change['target']).relative_to(app.parent)): hashlib.sha256(Path(change['target']).read_bytes()).hexdigest() for change in changes if Path(change['target']).exists()}
        put(app/'data'/'editorial-release.json', json.dumps({
            'schema_version': 1, 'revision': release_manifest['revision'],
            'installed_at_utc': datetime.now(timezone.utc).isoformat(),
            'files': installed_hashes,
            'retired_files': release_manifest.get('retired_files', []),
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
