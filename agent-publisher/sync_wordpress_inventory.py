"""Run on the WordPress host before topic selection; failure stops the pipeline."""
import json
import hashlib
import re
import subprocess
from datetime import datetime
from agents.temporal_validation import KST
from agents.search_intent import INVENTORY
from agents.workflow_metrics import increment, timed
from agents.wordpress_mutation import get_post


INVENTORY_SCHEMA = 2
LIGHTWEIGHT_INVENTORY_PHP = (
    "$q=new WP_Query(array('post_type'=>'post','post_status'=>array('publish','draft','pending','future','private'),"
    "'posts_per_page'=>-1,'orderby'=>'ID','order'=>'ASC','fields'=>'ids'));$o=array();"
    "foreach($q->posts as $id){$p=get_post($id);$c=(string)$p->post_content;"
    "$o[]=array('ID'=>(int)$id,'post_title'=>$p->post_title,'post_status'=>$p->post_status,"
    "'content_sha256'=>hash('sha256',$c),'content_urls'=>array_values(array_unique(wp_extract_urls(html_entity_decode($c,ENT_QUOTES|ENT_HTML5,'UTF-8')))));}"
    "echo wp_json_encode($o);"
)
LIGHTWEIGHT_INVENTORY_ARGS = ['eval', LIGHTWEIGHT_INVENTORY_PHP, '--allow-root']
_WP_BASE = ['sudo', 'docker', 'exec', 'wordpress_app', 'wp']


def inventory_content_sha(row):
    """Read v2 signature, with a temporary compatibility fallback for tests/v1 caches."""
    value = row.get('content_sha256') if isinstance(row, dict) else None
    if isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value):
        return value
    content = row.get('post_content') if isinstance(row, dict) else None
    if isinstance(content, str):
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    return None


def sync_inventory():
    with timed('inventory_sync'):
        increment('wp_roundtrips')
        result = subprocess.run(_WP_BASE + LIGHTWEIGHT_INVENTORY_ARGS,
                                check=True, capture_output=True, text=True, timeout=60)
    posts = json.loads(result.stdout)
    if (not isinstance(posts, list)
            or any(not isinstance(row, dict)
                   or type(row.get('ID')) is not int
                   or row.get('post_status') not in {'publish', 'draft', 'pending', 'future', 'private'}
                   or not isinstance(row.get('post_title'), str)
                   or not re.fullmatch(r'[0-9a-f]{64}', row.get('content_sha256', ''))
                   or not isinstance(row.get('content_urls'), list)
                   for row in posts)):
        raise ValueError('Invalid WordPress inventory')
    INVENTORY.parent.mkdir(parents=True, exist_ok=True)
    temp = INVENTORY.with_suffix('.tmp')
    temp.write_text(json.dumps({
        'schema_version': INVENTORY_SCHEMA,
        'checked_on': datetime.now(KST).date().isoformat(),
        'posts': posts,
    }, ensure_ascii=False), encoding='utf-8')
    temp.replace(INVENTORY)


def fetch_post_detail(post_id):
    """Fetch one post body only when a caller genuinely needs full content."""
    return get_post(_WP_BASE, post_id)


def hydrate_post(inventory, post_id):
    """Return an inventory copy with one row enriched by the live full post."""
    hydrated = dict(inventory, posts=[dict(row) for row in inventory.get('posts', [])])
    row = next((item for item in hydrated['posts'] if int(item.get('ID', -1)) == int(post_id)), None)
    if row is None:
        return hydrated
    if 'post_content' not in row:
        detail = fetch_post_detail(post_id)
        if (detail.get('post_status') != row.get('post_status')
                or detail.get('post_title') != row.get('post_title')
                or hashlib.sha256(detail.get('post_content', '').encode('utf-8')).hexdigest()
                    != inventory_content_sha(row)):
            raise ValueError('inventory_post_detail_changed')
        row.update(detail)
    return hydrated


def hydrate_duplicate_candidates(brief, inventory, related_post_ids=None):
    """Hydrate only URL-overlap candidates needing source-footer disambiguation."""
    if not isinstance(brief.get('existing_post_id'), int):
        return inventory
    official = set(brief.get('official_urls', []))
    related = set(related_post_ids or ())
    result = dict(inventory, posts=[dict(row) for row in inventory.get('posts', [])])
    for row in result['posts']:
        if int(row.get('ID', -1)) in related or row.get('post_content') is not None:
            continue
        if official.intersection(row.get('content_urls') or []):
            detail = fetch_post_detail(int(row['ID']))
            if (detail.get('post_status') != row.get('post_status')
                    or detail.get('post_title') != row.get('post_title')
                    or hashlib.sha256(detail.get('post_content', '').encode('utf-8')).hexdigest()
                        != inventory_content_sha(row)):
                raise ValueError('inventory_candidate_changed')
            row.update(detail)
    return result


def invalidate_inventory():
    """Make the cached full-site snapshot unusable after a WordPress mutation.

    Mutation commands already verify the exact target with a fresh ``post get``
    before and after the write. Re-downloading every post immediately afterward
    adds a second full inventory round trip even though the command is about to
    exit. Removing the cache forces the next independent workflow to perform its
    normal ``sync_inventory()`` first, so no later validation can mistake the
    pre-write snapshot for a current full-site inventory.
    """
    try:
        INVENTORY.unlink()
    except FileNotFoundError:
        pass


def ensure_inventory():
    """Refresh only when a previous mutation invalidated the local snapshot."""
    try:
        cached = json.loads(INVENTORY.read_text(encoding='utf-8'))
        if (cached.get('schema_version') == INVENTORY_SCHEMA
                and cached.get('checked_on') == datetime.now(KST).date().isoformat()
                and isinstance(cached.get('posts'), list)):
            return cached
    except (OSError, ValueError, KeyError):
        pass
    sync_inventory()
    return json.loads(INVENTORY.read_text(encoding='utf-8'))


if __name__ == '__main__':
    sync_inventory()
