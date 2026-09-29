# -*- coding: utf-8 -*-
"""Automated Test Harness for docs/POST_CATALOG.md and sync_post_catalog.py."""
import re
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT_DIR = Path(__file__).resolve().parents[2]
CATALOG_MD = ROOT_DIR / "docs" / "POST_CATALOG.md"
sys.path.insert(0, str(ROOT_DIR / "scripts"))

from sync_post_catalog import extract_backlog_rows, generate_catalog_markdown, run_ssh_inventory

class TestPostCatalog(unittest.TestCase):
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

if __name__ == "__main__":
    unittest.main()
