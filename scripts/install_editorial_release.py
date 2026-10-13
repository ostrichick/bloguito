"""Run on OCI with a reviewed release folder; preserve secrets and the cron schedule."""
import argparse
import ast
from contextlib import contextmanager
import hashlib
import json
import os
import shutil
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

CANONICAL_INVENTORY_DIGEST = '5a787314c492dfc7aad16705dcaa49929fd4520e00870b0b34d5450bfa7f68f3'
WP_MU_RELATIVE = 'wordpress/mu-plugins/bloguito-post-row-actions.php'
WP_MU_CONTAINER_PATH = '/var/www/html/wp-content/mu-plugins/bloguito-post-row-actions.php'


@contextmanager
def exclusive_release_window(app: Path):
    """Prevent installer/editorial/scheduler overlap during multi-file replacement.

    The editorial directory lock is shared with content mutation; flock is the
    same kernel lock used by cron/main and independent growth-state writers.
    Never unlink the scheduler lock, including after SIGKILL.
    """
    app = Path(app)
    data = app / 'data'
    editorial = data / '.editorial-publish.lock'
    growth_dir = data / 'growth'
    growth = growth_dir / '.scheduler-run.lock'
    if (data.is_symlink() or editorial.is_symlink() or growth_dir.is_symlink()
            or growth.is_symlink()):
        raise ValueError('release_lock_symlink_refused')
    data.mkdir(parents=True, exist_ok=True)
    try:
        editorial.mkdir()
    except FileExistsError as exc:
        raise ValueError('release_editorial_writer_busy') from exc
    descriptor = None
    acquired = False
    try:
        growth_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        if growth_dir.is_symlink() or growth.is_symlink():
            raise ValueError('release_growth_lock_symlink_refused')
        if os.name == 'posix' and growth_dir.stat().st_mode & 0o077:
            raise ValueError('release_growth_lock_directory_permissions')
        descriptor = os.open(growth, os.O_RDWR | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        if os.name == 'posix':
            import fcntl
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise ValueError('release_scheduler_running') from exc
        elif os.name == 'nt':
            import msvcrt
            if os.fstat(descriptor).st_size == 0:
                os.write(descriptor, b'\0')
            os.lseek(descriptor, 0, os.SEEK_SET)
            try:
                msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise ValueError('release_scheduler_running') from exc
        else:
            raise ValueError('release_lock_unsupported_platform')
        acquired = True
        yield
    finally:
        if descriptor is not None:
            if acquired:
                if os.name == 'posix':
                    fcntl.flock(descriptor, fcntl.LOCK_UN)
                else:
                    os.lseek(descriptor, 0, os.SEEK_SET)
                    msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
            os.close(descriptor)
        editorial.rmdir()
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
    actual = {p.relative_to(release).as_posix() for folder in ('agent-publisher', 'docs', 'wordpress')
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
        'agent-publisher/agents/growth_run_lock.py',
        'agent-publisher/agents/editorial.py',
        'agent-publisher/agents/editorial_schema.py',
        'agent-publisher/agents/public_fast_edit.py',
        'agent-publisher/agents/publish_gate.py',
        'agent-publisher/agents/source_collector.py',
        'agent-publisher/agents/source_extractors.py',
        'agent-publisher/agents/validation_router.py',
        'agent-publisher/agents/wordpress_mutation.py',
        'agent-publisher/data/renderer_provenance.json',
        'agent-publisher/data/reviewed_content_provenance.json',
        'agent-publisher/editorial_cli.py',
        'agent-publisher/editorial_policy.json',
        'agent-publisher/run_daily.sh',
        WP_MU_RELATIVE,
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


def verify_installed_mu_compatibility(manifest, *, installed_digest=None):
    """Read-only preflight before ANY app file write; never silently skip MU gate.

    `installed_digest` is a dependency-injection seam used only by disposable
    tests; the production CLI always reads the Docker container's actual file.
    """
    expected = manifest['files'][WP_MU_RELATIVE]
    if installed_digest is None:
        result = subprocess.run(
            ['sudo', 'docker', 'exec', 'wordpress_app', 'sha256sum', WP_MU_CONTAINER_PATH],
            capture_output=True, text=True, encoding='utf-8', errors='strict',
            check=True, timeout=15)
        parts = result.stdout.strip().split()
        if len(parts) != 2 or parts[1] != WP_MU_CONTAINER_PATH:
            raise ValueError('wp_mu_preflight_invalid_response')
        installed_digest = parts[0]
    if installed_digest != expected:
        raise ValueError('wp_mu_release_incompatible:install_matching_mu_separately_first')
    return expected


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


def preflight_release(release, app, *, installed_mu_digest=None):
    """Prove the release and server-side plugin ABI before any file mutation."""
    release, app = release.resolve(), app.resolve()
    if not (app/'main.py').is_file() or not (app/'config.py').is_file():
        raise ValueError('existing_publisher_required')
    release_manifest = verify_release_manifest(release)
    verified_mu = verify_installed_mu_compatibility(
        release_manifest, installed_digest=installed_mu_digest)
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
        if ((p.suffix not in {'.py', '.json'} and not attestation
             and relative != 'run_daily.sh')
                or '.env' in p.parts or '__pycache__' in p.parts):
            raise ValueError('unexpected_release_file')
    return release_manifest, verified_mu


def _install_with_window(release, app, *, installed_mu_digest=None):
    release, app = release.resolve(), app.resolve()
    release_manifest, verified_mu = preflight_release(
        release, app, installed_mu_digest=installed_mu_digest)
    files = [p for p in (release/'agent-publisher').rglob('*') if p.is_file()]
    backup = app/'backups'/('editorial-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:12])
    backup.mkdir(parents=True, mode=0o700, exist_ok=False)
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
        # Lexical path containment alone is not safe when an existing runtime
        # directory or leaf file is a symlink into another OS path.
        allowed_boundary = app if target.is_relative_to(app) else app.parent/'docs'
        if (allowed_boundary.is_symlink() or any(part.is_symlink() for part in (target, *(
                parent for parent in target.parents if parent != allowed_boundary
                and parent.is_relative_to(allowed_boundary))))):
            raise ValueError('release_target_symlink_refused')
        existed = target.exists()
        original = target.read_bytes() if existed else None
        token = str(len(changes))
        if existed:
            (backup/token).write_bytes(original)
            (backup/token).chmod(0o600)
        mode = (target.stat().st_mode & 0o777) if existed else None
        changes.append({'target':str(target),'backup':token if existed else None,
                        'mode':mode})
        (backup/'manifest.json').write_text(json.dumps(changes,indent=2),encoding='utf-8')
        target.parent.mkdir(parents=True,exist_ok=True)
        tmp=target.with_name(target.name+'.editorial-new')
        tmp.write_bytes(data);tmp.replace(target)
        if target.name == 'run_daily.sh':
            target.chmod(mode if mode is not None and mode & 0o111 else 0o750)
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
        subprocess.run([str(python),'-B','-c','import main, editorial_cli; import agents.edit_post; import agents.publish_gate; import agents.section_image; from agents.editorial_writer import Plan; from agents.editorial import policy, validate_renderer_provenance_registry, validate_reviewed_content_provenance_registry; from agents.critical_facts import validate_critical_fact_registry; validate_critical_fact_registry(); validate_renderer_provenance_registry(); validate_reviewed_content_provenance_registry(); print("Editorial entrypoints, publish gate and provenance registries ready; minimum days:",policy()["min_remaining_days"])'],cwd=app,check=True)
        # Confirm actual installed bytes rather than only trusting successful
        # os.replace() calls or a smoke import. This also detects mid-install
        # external writers before the installed release receipt is committed.
        for name, expected_sha in release_manifest['files'].items():
            if name == WP_MU_RELATIVE:
                continue  # Independently probed inside the WordPress container.
            if name.startswith('agent-publisher/'):
                target = app / name[len('agent-publisher/'):]
            elif name.startswith('docs/'):
                target = app.parent / name
            else:
                raise ValueError('release_readback_unrecognized_asset:' + name)
            if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != expected_sha:
                raise ValueError('release_readback_mismatch:' + name)
        # The MU gate could have changed after preflight while app files were
        # being copied. A drift is an installation failure, triggering rollback.
        verify_installed_mu_compatibility(release_manifest, installed_digest=installed_mu_digest)
        installed_hashes = {str(Path(change['target']).relative_to(app.parent)): hashlib.sha256(Path(change['target']).read_bytes()).hexdigest() for change in changes if Path(change['target']).exists()}
        manifest_sha256 = hashlib.sha256((release/'release-manifest.json').read_bytes()).hexdigest()
        put(app/'data'/'editorial-release.json', json.dumps({
            'schema_version': 2, 'revision': release_manifest['revision'],
            'release_manifest_sha256': manifest_sha256,
            'inventory_digest': release_manifest['inventory_digest'],
            'verified_mu_plugin_sha256': verified_mu,
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
                if change.get('mode') is not None:
                    target.chmod(change['mode'])
        raise


def install(release, app, *, installed_mu_digest=None):
    # Verify immutable package/MU before creating a kernel lock file.
    preflight_release(Path(release).resolve(), Path(app).resolve(),
                      installed_mu_digest=installed_mu_digest)
    with exclusive_release_window(Path(app).resolve()):
        # Recheck inside the window before the first runtime file write.
        return _install_with_window(release, app, installed_mu_digest=installed_mu_digest)


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('release',type=Path);p.add_argument('app',type=Path)
    p.add_argument('--preflight-only', action='store_true',
                   help='read-only manifest/config/MU compatibility check; do not install')
    a=p.parse_args()
    if a.preflight_only:
        manifest, mu_digest = preflight_release(a.release, a.app)
        print(json.dumps({'status': 'ready_for_separate_approval',
                          'revision': manifest['revision'],
                          'inventory_digest': manifest['inventory_digest'],
                          'mu_plugin_sha256': mu_digest}, indent=2))
    else:
        install(a.release, a.app)
