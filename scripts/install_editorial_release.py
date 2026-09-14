"""Run on OCI with a reviewed release folder; preserve secrets and the cron schedule."""
import argparse
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def install(release, app):
    release, app = release.resolve(), app.resolve()
    if not (app/'main.py').is_file() or not (app/'config.py').is_file():
        raise ValueError('existing_publisher_required')
    files = [p for p in (release/'agent-publisher').rglob('*') if p.is_file()]
    for p in files:
        if p.suffix not in {'.py', '.json'} or '.env' in p.parts or '__pycache__' in p.parts:
            raise ValueError('unexpected_release_file')
    backup = app/'backups'/('editorial-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    backup.mkdir(parents=True, mode=0o700)
    changes = []
    def put(target, data):
        # app files plus the single shared policy document are the only allowed targets.
        if not target.is_relative_to(app) and target != app.parent/'docs'/'EDITORIAL_SYSTEM.md':
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
            if relative.name in {'config.py', 'main.py'}:
                raise ValueError('config_and_main_must_be_patched_not_replaced')
            # Existing topic research is user data. Do not replace the server's reviewed list.
            if relative.as_posix()=='data/search_briefs.json' and (app/relative).exists():
                continue
            put(app/relative,file.read_bytes())
        put(app.parent/'docs'/'EDITORIAL_SYSTEM.md',(release/'docs'/'EDITORIAL_SYSTEM.md').read_bytes())
        text=(app/'config.py').read_text(encoding='utf-8')
        import ast
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
        python=app/'venv'/'bin'/'python'
        subprocess.run([str(python),'-c','import main; from agents.editorial_writer import Plan; from agents.editorial import policy; print("Editorial imports ready; minimum days:",policy()["min_remaining_days"])'],cwd=app,check=True)
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
