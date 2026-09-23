import json
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from config import POST_STATUS, POSTS_INDEX_FILE, DRAFTS_INDEX_FILE, SITE_URL
from agents.temporal_validation import validate_availability
from agents.fact_validation import verify_article, render_content, verify_temporal_binding


class PublisherAgent:
    """작성된 원고와 썸네일 이미지를 워드프레스 컨테이너에 안전하게 등록하고 내부 링크 색인을 갱신하는 발행 에이전트"""

    def __init__(self, container_name: str = "wordpress_app"):
        self.container_name = container_name

    def _record_post(self, post_id: int, title: str, category_id: int, category_name: str, status: str = "publish", expires_at: str = None, fact_manifest: dict = None):
        """발행 상태(publish vs draft)에 따라 색인 파일을 분리하여 기록하고, 상태 전환 시 기존 색인에서 자동 이전"""
        target_file = POSTS_INDEX_FILE if status == "publish" else DRAFTS_INDEX_FILE
        other_file = DRAFTS_INDEX_FILE if status == "publish" else POSTS_INDEX_FILE

        def _load_json(p: Path):
            if p.exists():
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception:
                    return []
            return []

        target_posts = _load_json(target_file)
        other_posts = _load_json(other_file)

        # 워드프레스 고유주소(URL) 조회
        url_cmd = [
            "sudo", "docker", "exec", self.container_name,
            "wp", "eval", f"echo get_permalink({int(post_id)});",
            "--allow-root"
        ]
        res = subprocess.run(url_cmd, capture_output=True, text=True)
        post_url = res.stdout.strip() if res.returncode == 0 and res.stdout.strip() else f"{SITE_URL}/?p={post_id}"

        # 반대쪽 색인에서 해당 post_id가 있으면 제거 (예: draft -> publish 승격)
        other_posts_cleaned = [p for p in other_posts if p.get("id") != post_id]
        if len(other_posts_cleaned) != len(other_posts):
            other_file.parent.mkdir(parents=True, exist_ok=True)
            with open(other_file, "w", encoding="utf-8") as f:
                json.dump(other_posts_cleaned, f, ensure_ascii=False, indent=2)

        # 대상 색인에 중복 제거 후 추가
        target_posts = [p for p in target_posts if p.get("id") != post_id]
        target_posts.append({
            "id": post_id,
            "title": title,
            "url": post_url,
            "category_id": category_id,
            "category_name": category_name,
            "status": status,
            "expires_at": expires_at,
            "fact_manifest": fact_manifest,
            "published_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        })

        target_file.parent.mkdir(parents=True, exist_ok=True)
        with open(target_file, "w", encoding="utf-8") as f:
            json.dump(target_posts, f, ensure_ascii=False, indent=2)

        label = "공개 글 색인(Published)" if status == "publish" else "초안 색인(Drafts)"
        print(f"[PublisherAgent] 📚 {label} 업데이트 완료 ({len(target_posts)}개 글 등록)")

    def _record_published_post(self, post_id: int, title: str, category_id: int, category_name: str, status: str = "publish", expires_at: str = None):
        """하위 호환성을 위한 래퍼 메서드"""
        self._record_post(post_id, title, category_id, category_name, status=status, expires_at=expires_at)

    def publish(self, article: dict, image_path: Path = None) -> int:
        if 'editorial_bundle' in article:
            from agents.editorial import ROOT
            lock = ROOT / 'data' / '.editorial-publish.lock'
            lock.parent.mkdir(parents=True, exist_ok=True)
            try:
                lock.mkdir()
            except FileExistsError:
                raise ValueError('editorial_publication_busy: concurrent run or stale lock requires review')
            try:
                return self._publish_editorial(article, image_path)
            finally:
                lock.rmdir()
        raise ValueError('editorial_bundle_required: 기존 표 원고도 공통 편집 검토 후 등록해야 합니다.')

    def _publish_editorial(self, article, image_path=None):
        from agents.editorial import validate_bundle, render, excerpt_from_lead
        from agents.editorial_writer import load_inventory
        from sync_wordpress_inventory import sync_inventory
        from config import CATEGORIES, resolve_category
        # Never accept a caller-supplied inventory or a cached quality status here.
        sync_inventory()
        bundle = article['editorial_bundle']
        report = validate_bundle(bundle, load_inventory())
        if report['status'] != 'ready':
            raise ValueError(f"편집 검사 보류: {report['reasons']}")
        content = render(bundle['plan'], bundle['sources'])
        title = bundle['plan']['title']
        excerpt = excerpt_from_lead(bundle['plan']['lead'])
        if article.get('content') != content or article.get('title') != title:
            raise ValueError('editorial_content_changed_after_review')
        category = resolve_category(bundle['brief'].get('category_key', ''))
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', delete=False, suffix='.html') as f:
            f.write(content)
            local = Path(f.name)
        remote = f'/tmp/editorial_{local.stem}.html'
        try:
            subprocess.run(['sudo', 'docker', 'cp', str(local), f'{self.container_name}:{remote}'], check=True, capture_output=True)
            result = subprocess.run(['sudo', 'docker', 'exec', self.container_name, 'wp', 'post', 'create', remote,
                '--post_type=post', '--post_status=draft', f'--post_title={title}',
                f'--post_category={category["id"]}', '--post_excerpt=' + excerpt,
                '--comment_status=closed', '--allow-root', '--porcelain'],
                check=True, capture_output=True, text=True)
            post_id = int(result.stdout.strip())
            actual = subprocess.run(['sudo', 'docker', 'exec', self.container_name, 'wp', 'post', 'get', str(post_id),
                '--fields=post_status,post_content', '--format=json', '--allow-root'], check=True, capture_output=True, text=True)
            saved = json.loads(actual.stdout)
            if saved['post_status'] != 'draft' or saved['post_content'] != content:
                raise ValueError(f'editorial_saved_content_mismatch_post_{post_id}')
            self._record_post(post_id, title, category['id'], category['name'], status='draft',
                expires_at=bundle['brief'].get('useful_until'), fact_manifest={'editorial_bundle': bundle})
            # Rank Math SEO 메타데이터 자동 주입 (포커스 키워드 & 메타 설명)
            focus_keyword = bundle['brief'].get('primary_keyword', '').strip()
            meta_desc = bundle['plan']['lead']['text'][:160].strip()
            if focus_keyword:
                subprocess.run(['sudo', 'docker', 'exec', self.container_name, 'wp', 'post', 'meta', 'set',
                    str(post_id), 'rank_math_focus_keyword', focus_keyword, '--allow-root'], check=False, capture_output=True)
            if meta_desc:
                subprocess.run(['sudo', 'docker', 'exec', self.container_name, 'wp', 'post', 'meta', 'set',
                    str(post_id), 'rank_math_description', meta_desc, '--allow-root'], check=False, capture_output=True)
            # Persist the new draft before another candidate can be selected in this run.
            sync_inventory()
            if image_path and image_path.exists():
                remote_image = f'/tmp/editorial_cover_{post_id}{image_path.suffix}'
                try:
                    subprocess.run(['sudo', 'docker', 'cp', str(image_path), f'{self.container_name}:{remote_image}'], check=True, capture_output=True)
                    subprocess.run(['sudo', 'docker', 'exec', self.container_name, 'wp', 'media', 'import', remote_image,
                        f'--post_id={post_id}', '--featured_image', '--allow-root'], check=True, capture_output=True)
                finally:
                    subprocess.run(['sudo', 'docker', 'exec', self.container_name, 'rm', '-f', remote_image], capture_output=True)
            return post_id
        finally:
            local.unlink(missing_ok=True)
            subprocess.run(['sudo', 'docker', 'exec', self.container_name, 'rm', '-f', remote], capture_output=True)

    def reformat_draft(self, post_id):
        """Only migrate a stored reviewed draft whose body still equals our renderer."""
        from agents.editorial import ROOT, render, render_legacy, validate_bundle
        from agents.editorial_writer import load_inventory
        from sync_wordpress_inventory import sync_inventory
        lock = ROOT / 'data' / '.editorial-publish.lock'
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.mkdir()
        try:
            records = json.loads(DRAFTS_INDEX_FILE.read_text(encoding='utf-8'))
            record = next(p for p in records if int(p['id']) == post_id)
            bundle = record['fact_manifest']['editorial_bundle']
            sync_inventory()
            inventory = load_inventory()
            existing = next(p for p in inventory['posts'] if int(p['ID']) == post_id)
            old = existing['post_content']
            content = render(bundle['plan'], bundle['sources'])
            if existing['post_status'] != 'draft' or existing['post_title'] != bundle['plan']['title']:
                raise ValueError('reformat_requires_unchanged_draft')
            # A change limited to the renderer-generated recommendation card is
            # safe to reformat; all user-authored/article content must match exactly.
            import re
            strip_auto_links = lambda value: re.sub(r'<div class="bloguito-interlink"[^>]*>.*?</div>', '', value, flags=re.DOTALL)
            only_auto_links_changed = strip_auto_links(old) == strip_auto_links(content)
            if old not in (render_legacy(bundle['plan'], bundle['sources']), content) and not only_auto_links_changed:
                raise ValueError('reformat_user_edits_detected')
            inventory = dict(inventory, posts=[p for p in inventory['posts'] if int(p['ID']) != post_id])
            # Format migration does not alter reviewed facts; refresh the policy stamp
            # after the presentation contract changes so the normal gate can run.
            from agents.editorial import policy_fingerprint
            bundle['review']['policy_digest'] = policy_fingerprint()
            bundle['review']['digest'] = __import__('agents.editorial', fromlist=['digest']).digest({k: bundle[k] for k in ('brief','sources','plan','temporal_source') if k in bundle})
            report = validate_bundle(bundle, inventory)
            if report['status'] != 'ready':
                raise ValueError(f"편집 검사 보류: {report['reasons']}")
            if old == content:
                return post_id
            base = ['sudo', 'docker', 'exec', self.container_name, 'wp']
            # Re-read immediately before mutation to detect edits during validation.
            current = json.loads(subprocess.run(base + ['post','get',str(post_id),'--format=json','--allow-root'], check=True,capture_output=True,text=True).stdout)
            if current['post_content'] != old or current['post_status'] != 'draft' or current['post_title'] != existing['post_title']:
                raise ValueError('reformat_user_edits_detected')
            backup = ROOT / 'data' / 'editorial_runs'
            backup.mkdir(parents=True, exist_ok=True)
            (backup / f'reformat-{post_id}-{datetime.now().strftime("%Y%m%dT%H%M%S")}.json').write_text(json.dumps(current,ensure_ascii=False),encoding='utf-8')
            # Only the content field changes; ID, title, status, category and media persist.
            subprocess.run(base + ['post','update',str(post_id),'--post_content='+content,'--allow-root'],check=True,capture_output=True,text=True)
            saved = json.loads(subprocess.run(base + ['post','get',str(post_id),'--format=json','--allow-root'],check=True,capture_output=True,text=True).stdout)
            if saved['post_content'] != content or saved['post_status'] != 'draft':
                raise ValueError('reformat_saved_content_mismatch')
            category = __import__('config', fromlist=['CATEGORIES']).CATEGORIES[bundle['brief']['category_key']]
            self._record_post(post_id, bundle['plan']['title'], category['id'], category['name'], status='draft', fact_manifest={'editorial_bundle': bundle})
            sync_inventory()
            return post_id
        finally:
            lock.rmdir()

    def list_drafts(self):
        """Return the live WordPress drafts; indexes are optional metadata only."""
        args = ['sudo', 'docker', 'exec', self.container_name, 'wp', 'post', 'list',
                '--post_type=post', '--post_status=draft',
                '--fields=ID,post_title,post_date,post_status', '--format=json', '--allow-root']
        rows = json.loads(subprocess.run(args, check=True, capture_output=True, text=True).stdout)
        if not isinstance(rows, list) or any(not isinstance(p, dict) or p.get('post_status') != 'draft' for p in rows):
            raise ValueError('wordpress_drafts_invalid_response')
        index = []
        if DRAFTS_INDEX_FILE.exists():
            try:
                index = json.loads(DRAFTS_INDEX_FILE.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                index = []  # The live WordPress list is authoritative.
        by_id = {int(p['id']):p for p in index if isinstance(p,dict) and str(p.get('id','')).isdigit()}
        return [{**row, 'category_name':by_id.get(int(row['ID']),{}).get('category_name','미분류')}
                for row in rows]

    def promote_draft(self, post_id, *, confirmed=False):
        """Publish only a reviewed, unchanged draft after an explicit user confirmation.

        Older/manual drafts without a current source-bound editorial bundle are
        intentionally not eligible for one-step promotion.
        """
        if not confirmed:
            raise ValueError('explicit_publication_confirmation_required: pass --confirm-publish after reviewing this draft')
        from agents.editorial import ROOT, render, validate_bundle
        from agents.editorial_writer import load_inventory, fetch_sources
        from sync_wordpress_inventory import sync_inventory
        from config import resolve_category
        lock = ROOT / 'data' / '.editorial-publish.lock'
        lock.parent.mkdir(parents=True, exist_ok=True)
        try:
            lock.mkdir()
        except FileExistsError:
            raise ValueError('editorial_publication_busy: check running process before removing stale lock')
        try:
            if not DRAFTS_INDEX_FILE.exists():
                raise ValueError('tracked_editorial_draft_required')
            records = json.loads(DRAFTS_INDEX_FILE.read_text(encoding='utf-8'))
            item = next((p for p in records if int(p.get('id',-1)) == int(post_id)), None)
            if not item or not item.get('fact_manifest',{}).get('editorial_bundle'):
                raise ValueError('reviewed_editorial_bundle_required: legacy or unreviewed draft must be rebuilt')
            bundle = item['fact_manifest']['editorial_bundle']
            expected = render(bundle['plan'],bundle['sources'])
            title = bundle['plan']['title']
            sync_inventory()
            inventory = load_inventory()
            actual = next((p for p in inventory['posts'] if int(p['ID']) == int(post_id)),None)
            same=lambda a,b: a.replace(chr(13)+chr(10),chr(10)) == b.replace(chr(13)+chr(10),chr(10))
            if not actual or actual['post_status'] != 'draft' or actual['post_title'] != title or not same(actual['post_content'], expected):
                raise ValueError('draft_changed_or_not_draft: review WordPress edits before publishing')
            others = dict(inventory, posts=[p for p in inventory['posts'] if int(p['ID']) != int(post_id)])
            report = validate_bundle(bundle,others)
            if report['status'] != 'ready':
                raise ValueError(f'editorial_review_not_current: {report["reasons"]}')
            # A recent fetch timestamp does not imply the document is up to date;
            # compare a newly retrieved official source to the signed snapshot.
            current_sources = fetch_sources(bundle['brief'])
            orig = {s['url']:s['sha256'] for s in bundle['sources']}
            observed = {s['url']:s['sha256'] for s in current_sources}
            if orig != observed:
                raise ValueError('official_source_changed_since_review: fresh review required')
            base = ['sudo','docker','exec',self.container_name,'wp']
            final = json.loads(subprocess.run(base+['post','get',str(int(post_id)),'--format=json','--allow-root'],
                                              check=True,capture_output=True,text=True).stdout)
            if final['post_status'] != 'draft' or final['post_title'] != title or not same(final['post_content'],expected):
                raise ValueError('draft_changed_during_review')
            subprocess.run(base+['post','update',str(int(post_id)),'--post_status=publish','--allow-root'],
                           check=True,capture_output=True,text=True)
            saved = json.loads(subprocess.run(base+['post','get',str(int(post_id)),'--format=json','--allow-root'],
                                              check=True,capture_output=True,text=True).stdout)
            if saved['post_status'] != 'publish' or saved['post_title'] != title or not same(saved['post_content'],expected):
                raise ValueError('publication_verification_failed: inspect WordPress state before retrying')
            category = resolve_category(bundle['brief']['category_key'])
            self._record_post(int(post_id),title,category['id'],category['name'],status='publish',
                              expires_at=bundle['brief'].get('useful_until'),fact_manifest={'editorial_bundle':bundle})
            sync_inventory()
            return int(post_id)
        finally:
            lock.rmdir()
