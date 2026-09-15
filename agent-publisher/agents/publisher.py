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
        from agents.editorial import validate_bundle, render
        from agents.editorial_writer import load_inventory
        from sync_wordpress_inventory import sync_inventory
        from config import CATEGORIES
        # Never accept a caller-supplied inventory or a cached quality status here.
        sync_inventory()
        bundle = article['editorial_bundle']
        report = validate_bundle(bundle, load_inventory())
        if report['status'] != 'ready':
            raise ValueError(f"편집 검사 보류: {report['reasons']}")
        content = render(bundle['plan'], bundle['sources'])
        title = bundle['plan']['title']
        if article.get('content') != content or article.get('title') != title:
            raise ValueError('editorial_content_changed_after_review')
        category = CATEGORIES[bundle['brief']['category_key']]
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', delete=False, suffix='.html') as f:
            f.write(content)
            local = Path(f.name)
        remote = f'/tmp/editorial_{local.stem}.html'
        try:
            subprocess.run(['sudo', 'docker', 'cp', str(local), f'{self.container_name}:{remote}'], check=True, capture_output=True)
            result = subprocess.run(['sudo', 'docker', 'exec', self.container_name, 'wp', 'post', 'create', remote,
                '--post_type=post', '--post_status=draft', f'--post_title={title}',
                f'--post_category={category["id"]}', '--comment_status=closed', '--allow-root', '--porcelain'],
                check=True, capture_output=True, text=True)
            post_id = int(result.stdout.strip())
            actual = subprocess.run(['sudo', 'docker', 'exec', self.container_name, 'wp', 'post', 'get', str(post_id),
                '--fields=post_status,post_content', '--format=json', '--allow-root'], check=True, capture_output=True, text=True)
            saved = json.loads(actual.stdout)
            if saved['post_status'] != 'draft' or saved['post_content'] != content:
                raise ValueError(f'editorial_saved_content_mismatch_post_{post_id}')
            self._record_post(post_id, title, category['id'], category['name'], status='draft',
                expires_at=bundle['brief'].get('useful_until'), fact_manifest={'editorial_bundle': bundle})
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
            if old not in (render_legacy(bundle['plan'], bundle['sources']), content) and 'source-links' not in old:
                raise ValueError('reformat_user_edits_detected')
            inventory = dict(inventory, posts=[p for p in inventory['posts'] if int(p['ID']) != post_id])
            # Format migration does not alter reviewed facts; refresh the policy stamp
            # after the presentation contract changes so the normal gate can run.
            from agents.editorial import policy_fingerprint
            bundle['review']['policy_digest'] = policy_fingerprint()
            bundle['review']['digest'] = __import__('agents.editorial', fromlist=['digest']).digest({k: bundle[k] for k in ('brief','sources','plan','temporal_source')})
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
