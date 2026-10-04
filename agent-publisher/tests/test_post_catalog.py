# -*- coding: utf-8 -*-
"""Automated Test Harness for docs/POST_CATALOG.md and sync_post_catalog.py."""
import re
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT_DIR = Path(__file__).resolve().parents[2]
CATALOG_MD = ROOT_DIR / "docs" / "POST_CATALOG.md"
sys.path.insert(0, str(ROOT_DIR / "scripts"))

from sync_post_catalog import (
    catalog_type,
    extract_backlog_rows,
    generate_catalog_markdown,
    reconcile_reviewed_statuses,
    run_ssh_inventory,
)
import sync_post_catalog as catalog_sync

class TestPostCatalog(unittest.TestCase):
    def test_lifecycle_metadata_requires_matching_review_and_live_content(self):
        from tests.test_editorial_system import sample, sign
        bundle = sample()
        bundle['brief']['volatility'] = 'annual-policy'
        bundle['brief']['content_type'] = 'dated'
        bundle['brief']['useful_until'] = '2026-12-31'
        sign(bundle)
        post = {'post_title': '2026 국가건강검진 대상자 조회', 'categories': ['건강/의료'],
                'content_sha256': hashlib.sha256(b'rendered').hexdigest()}
        with patch('agents.editorial.render', return_value='rendered'):
            self.assertEqual('연간 기준 (저장 원고 기준)', catalog_type(post, bundle))
            post['content_sha256'] = 'different live content'
            self.assertEqual('에버그린 (추정)', catalog_type(post, bundle))
            post['content_sha256'] = hashlib.sha256(b'rendered').hexdigest()
            bundle['brief']['volatility'] = 'timeless-procedure'
            self.assertEqual('에버그린 (추정)', catalog_type(post, bundle))

    def test_category_slug_keeps_estimate_stable_across_display_name_changes(self):
        post = {'post_title': '지역 문화 프로그램', 'categories': ['바뀐 표시명'], 'category_slugs': ['local-events']}
        self.assertEqual('시즌형 (추정)', catalog_type(post))

    def test_catalog_file_exists(self):
        """Verify docs/POST_CATALOG.md exists and is non-empty."""
        self.assertTrue(CATALOG_MD.exists(), f"Catalog file does not exist: {CATALOG_MD}")
        self.assertGreater(CATALOG_MD.stat().st_size, 500, "Catalog file should have substantial content")

    def test_catalog_table_headers(self):
        """Verify published table contains required headers."""
        content = CATALOG_MD.read_text(encoding="utf-8")
        self.assertIn("# 📚 Bloguito 콘텐츠 카탈로그 & 주제 관리 대시보드", content)
        self.assertIn("## 1. 🟢 발행 완료 글 (Published)", content)
        self.assertIn("## 2. 🟡 작업 중 / 임시글 (Draft)", content)
        self.assertIn("## 3. 🎯 추진 예정 백로그 (Topic Backlog)", content)
        self.assertIn("| ID | 제목 | 카테고리 | 유형 | 포커스 키워드 |", content)

    def test_recent_posts_included(self):
        """Verify recent key posts (#474, #471, #231, #233) are indexed properly."""
        content = CATALOG_MD.read_text(encoding="utf-8")
        self.assertIn("#474", content, "Post #474 must be in the catalog")
        self.assertIn("#471", content, "Post #471 must be in the catalog")
        self.assertIn("#231", content, "Post #231 must be in the catalog")
        self.assertIn("#233", content, "Post #233 must be in the catalog")
        self.assertIn("휴일 약국", content, "Post #233 keyword must be in the catalog")

    def test_topic_backlog_present(self):
        """Verify remaining reviewed topics are registered in the backlog."""
        content = CATALOG_MD.read_text(encoding="utf-8")
        self.assertIn("국민연금 조기노령연금", content)
        self.assertIn("국가건강검진", content)

    def test_completed_topic_is_removed_from_backlog(self):
        """A topic already represented by a draft must not stay in the backlog."""
        content = CATALOG_MD.read_text(encoding="utf-8")
        backlog = content.split("## 3. 🎯 추진 예정 백로그 (Topic Backlog)", 1)[1]
        self.assertNotIn("임플란트 건강보험", backlog)

    def test_existing_manual_backlog_rows_are_preserved(self):
        """Synchronizing should reuse curated rows instead of replacing them with defaults."""
        sample = """## 3. 🎯 추진 예정 백로그 (Topic Backlog)

| 우선순위 | 주제명 | 핵심 타깃 및 검색 의도 | 주요 포커스 키워드 | 공식 출처 |
|:---:|---|---|---|---|
| **1순위** | **테스트 주제** | 테스트 의도 | `테스트 키워드` | 테스트 기관 |

---
"""
        self.assertEqual(
            extract_backlog_rows(sample),
            ["| **1순위** | **테스트 주제** | 테스트 의도 | `테스트 키워드` | 테스트 기관 |"],
        )

    def test_generated_catalog_filters_topic_already_in_draft(self):
        """Backlog filtering uses current titles and focus keywords across statuses."""
        posts = [
            {
                "ID": 598,
                "post_title": "만 65세 이상 임플란트 건강보험 적용 기준과 본인부담금 2개 총정리",
                "post_status": "draft",
                "rank_math_focus_keyword": "임플란트 건강보험",
                "rank_math_seo_score": "",
                "categories": ["보건의료"],
            }
        ]
        rows = [
            "| **1순위** | **만 65세 이상 임플란트 건강보험 적용 기준** | 테스트 | `임플란트 건강보험` | 국민건강보험공단 |",
            "| **2순위** | **국민연금 조기노령연금** | 테스트 | `국민연금 조기노령연금` | 국민연금공단 |",
        ]
        content = generate_catalog_markdown(posts, rows)
        backlog = content.split("## 3. 🎯 추진 예정 백로그 (Topic Backlog)", 1)[1]
        self.assertNotIn("임플란트 건강보험", backlog)
        self.assertIn("| **1순위** | **국민연금 조기노령연금**", backlog)

    def test_explicit_empty_backlog_does_not_restore_defaults(self):
        """An intentionally empty catalog backlog stays empty on later syncs."""
        content = generate_catalog_markdown([], [])
        backlog = content.split("## 3. 🎯 추진 예정 백로그 (Topic Backlog)", 1)[1]
        self.assertIn("현재 검토 대기 후보가 없습니다", backlog)
        self.assertNotIn("임플란트 건강보험", backlog)

    def test_remote_inventory_accepts_utf8_bom(self):
        payload = '\ufeff[{"ID":648,"post_status":"draft"}]'
        with patch('sync_post_catalog.subprocess.run', return_value=Mock(
                returncode=0, stdout=payload, stderr='')):
            rows = run_ssh_inventory()
        self.assertEqual(648, rows[0]['ID'])

    def test_catalog_php_collects_current_permalink_for_growth_mapping(self):
        self.assertIn("'permalink' => (string)get_permalink($id)", catalog_sync.CATALOG_PHP)

    def test_catalog_sync_keeps_editorial_inventory_separate(self):
        """Catalog metadata must never overwrite the scheduler/editorial inventory."""
        posts = [{
            "ID": 901,
            "post_title": "테스트 글",
            "post_status": "publish",
            "post_name": "test",
            "post_date": "2026-10-03 08:00:00",
            "content_sha256": "0" * 64,
            "category_slugs": ["life-admin"],
            "categories": ["행정/생활서비스"],
            "rank_math_focus_keyword": "테스트",
            "rank_math_seo_score": "75",
        }]
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            catalog_md = root / "POST_CATALOG.md"
            catalog_inventory = root / "catalog_inventory.json"
            canonical_inventory = root / "wordpress_inventory.json"
            canonical_payload = '{"schema_version":2,"checked_on":"2026-10-03","posts":[]}'
            canonical_inventory.write_text(canonical_payload, encoding="utf-8")

            with (patch.object(catalog_sync, "CATALOG_MD", catalog_md),
                  patch.object(catalog_sync, "CATALOG_INVENTORY_JSON", catalog_inventory),
                  patch.object(catalog_sync, "run_ssh_inventory", return_value=posts),
                  patch.object(catalog_sync, "reconcile_reviewed_statuses",
                               return_value={"moved": [], "skipped": []}),
                  patch.object(catalog_sync, "load_reviewed_bundles", return_value={})):
                catalog_sync.sync_catalog()

            self.assertTrue(catalog_md.is_file())
            self.assertEqual(posts, json.loads(
                catalog_inventory.read_text(encoding="utf-8")))
            self.assertEqual(canonical_payload,
                             canonical_inventory.read_text(encoding="utf-8"))

    @staticmethod
    def _reviewed_record(post_id=844, status='draft', title='테스트 글'):
        from tests.test_editorial_system import sample, sign
        from agents.editorial import render
        bundle = sample()
        bundle['plan']['title'] = title
        sign(bundle)
        return ({
            'id': post_id,
            'title': title,
            'url': f'https://lifeinfo24.org/?p={post_id}',
            'category_id': 275,
            'category_name': '건강·의료',
            'status': status,
            'expires_at': None,
            'fact_manifest': {'editorial_bundle': bundle},
            'published_at': '2026-10-03 10:00',
        }, render(bundle['plan'], bundle['sources']))

    def test_reviewed_status_reconcile_moves_exact_unchanged_draft_to_publish(self):
        record, content = self._reviewed_record()
        with tempfile.TemporaryDirectory() as folder:
            data = Path(folder)
            (data / 'draft_posts.json').write_text(
                json.dumps([record], ensure_ascii=False), encoding='utf-8')
            (data / 'published_posts.json').write_text('[]', encoding='utf-8')
            live = [{
                'ID': 844,
                'post_title': record['title'],
                'post_status': 'publish',
                'permalink': 'https://lifeinfo24.org/test/',
                'content_sha256': hashlib.sha256(content.encode('utf-8')).hexdigest(),
            }]

            result = reconcile_reviewed_statuses(live, data)

            self.assertEqual([{
                'post_id': 844, 'from_status': 'draft', 'to_status': 'publish'
            }], result['moved'])
            self.assertEqual([], json.loads((data / 'draft_posts.json').read_text(encoding='utf-8')))
            published = json.loads((data / 'published_posts.json').read_text(encoding='utf-8'))
            self.assertEqual('publish', published[0]['status'])
            self.assertEqual('https://lifeinfo24.org/test/', published[0]['url'])
            self.assertEqual([], result['metadata_updated'])

    def test_reviewed_status_reconcile_refuses_live_content_change(self):
        record, _content = self._reviewed_record()
        with tempfile.TemporaryDirectory() as folder:
            data = Path(folder)
            original = json.dumps([record], ensure_ascii=False)
            (data / 'draft_posts.json').write_text(original, encoding='utf-8')
            (data / 'published_posts.json').write_text('[]', encoding='utf-8')
            live = [{
                'ID': 844,
                'post_title': record['title'],
                'post_status': 'publish',
                'permalink': 'https://lifeinfo24.org/test/',
                'content_sha256': hashlib.sha256(b'user edited content').hexdigest(),
            }]

            result = reconcile_reviewed_statuses(live, data)

            self.assertEqual([], result['moved'])
            self.assertEqual(
                [{'post_id': 844, 'reason': 'live_content_changed'}],
                result['skipped'])
            self.assertEqual(json.loads(original), json.loads(
                (data / 'draft_posts.json').read_text(encoding='utf-8')))
            self.assertEqual([], json.loads(
                (data / 'published_posts.json').read_text(encoding='utf-8')))

    def test_reviewed_status_reconcile_accepts_exact_known_previous_renderer(self):
        from agents.editorial import _previous_responsive_layout_variant
        record, content = self._reviewed_record()
        previous = _previous_responsive_layout_variant(content)
        self.assertNotEqual(content, previous)
        with tempfile.TemporaryDirectory() as folder:
            data = Path(folder)
            (data / 'draft_posts.json').write_text(
                json.dumps([record], ensure_ascii=False), encoding='utf-8')
            (data / 'published_posts.json').write_text('[]', encoding='utf-8')
            live = [{
                'ID': 844,
                'post_title': record['title'],
                'post_status': 'publish',
                'permalink': 'https://lifeinfo24.org/test/',
                'content_sha256': hashlib.sha256(previous.encode('utf-8')).hexdigest(),
            }]

            result = reconcile_reviewed_statuses(live, data)

            self.assertEqual([{
                'post_id': 844,
                'from_status': 'draft',
                'to_status': 'publish',
                'renderer_variant': 'pre-responsive-layout-v1',
            }], result['moved'])
            self.assertEqual([], json.loads(
                (data / 'draft_posts.json').read_text(encoding='utf-8')))

    def test_reviewed_status_reconcile_moves_exact_publish_back_to_draft(self):
        record, content = self._reviewed_record(status='publish')
        with tempfile.TemporaryDirectory() as folder:
            data = Path(folder)
            (data / 'draft_posts.json').write_text('[]', encoding='utf-8')
            (data / 'published_posts.json').write_text(
                json.dumps([record], ensure_ascii=False), encoding='utf-8')
            live = [{
                'ID': 844,
                'post_title': record['title'],
                'post_status': 'draft',
                'permalink': 'https://lifeinfo24.org/?p=844',
                'content_sha256': hashlib.sha256(content.encode('utf-8')).hexdigest(),
            }]

            result = reconcile_reviewed_statuses(live, data)

            self.assertEqual([{
                'post_id': 844, 'from_status': 'publish', 'to_status': 'draft'
            }], result['moved'])
            drafts = json.loads((data / 'draft_posts.json').read_text(encoding='utf-8'))
            self.assertEqual('draft', drafts[0]['status'])
            self.assertEqual([], json.loads(
                (data / 'published_posts.json').read_text(encoding='utf-8')))

    def test_reviewed_metadata_reconcile_updates_safe_outer_fields_only(self):
        record, content = self._reviewed_record(status='publish', title='현재 제목')
        record['title'] = '예전 제목'
        record['category_id'] = 2
        record['category_name'] = '공연/콘서트 예매'
        with tempfile.TemporaryDirectory() as folder:
            data = Path(folder)
            (data / 'draft_posts.json').write_text('[]', encoding='utf-8')
            (data / 'published_posts.json').write_text(
                json.dumps([record], ensure_ascii=False), encoding='utf-8')
            live = [{
                'ID': 844,
                'post_title': '현재 제목',
                'post_status': 'publish',
                'permalink': 'https://lifeinfo24.org/current/',
                'content_sha256': hashlib.sha256(content.encode('utf-8')).hexdigest(),
                'category_slugs': ['concert'],
                'categories': ['공연/콘서트'],
            }]

            result = reconcile_reviewed_statuses(live, data)

            self.assertEqual([], result['moved'])
            self.assertEqual([{
                'post_id': 844,
                'status': 'publish',
                'fields': ['category_name', 'title', 'url'],
            }], result['metadata_updated'])
            saved = json.loads(
                (data / 'published_posts.json').read_text(encoding='utf-8'))[0]
            self.assertEqual('현재 제목', saved['title'])
            self.assertEqual('https://lifeinfo24.org/current/', saved['url'])
            self.assertEqual('공연/콘서트', saved['category_name'])
            self.assertEqual(2, saved['category_id'])

if __name__ == "__main__":
    unittest.main()
