"""Run on the WordPress host before topic selection; failure stops the pipeline."""
import json
import subprocess
from datetime import datetime
from agents.temporal_validation import KST
from agents.search_intent import INVENTORY


def sync_inventory():
    result = subprocess.run(['sudo', 'docker', 'exec', 'wordpress_app', 'wp', 'post', 'list',
                             '--post_type=post', '--post_status=publish,draft,pending,future,private',
                             '--posts_per_page=-1', '--fields=ID,post_title,post_status,post_content',
                             '--format=json', '--allow-root'], check=True, capture_output=True, text=True, timeout=60)
    posts = json.loads(result.stdout)
    if not isinstance(posts, list):
        raise ValueError('Invalid WordPress inventory')
    INVENTORY.parent.mkdir(parents=True, exist_ok=True)
    temp = INVENTORY.with_suffix('.tmp')
    temp.write_text(json.dumps({'checked_on': datetime.now(KST).date().isoformat(), 'posts': posts}, ensure_ascii=False), encoding='utf-8')
    temp.replace(INVENTORY)


if __name__ == '__main__':
    sync_inventory()
