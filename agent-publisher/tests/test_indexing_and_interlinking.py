import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch, MagicMock

import config
from agents.publisher import PublisherAgent
from agents.copywriter import CopywriterAgent


class IndexingAndInterlinkingTests(unittest.TestCase):
    """Task 5 & 6: 초안/공개 색인 분리 및 마감 글 내부 추천 제외 회귀 테스트"""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self.pub_file = self.data_dir / "published_posts.json"
        self.draft_file = self.data_dir / "draft_posts.json"

        # config 파일 경로를 임시 디렉터리로 패치
        self.patcher1 = patch("agents.publisher.POSTS_INDEX_FILE", self.pub_file)
        self.patcher2 = patch("agents.publisher.DRAFTS_INDEX_FILE", self.draft_file)
        self.patcher3 = patch("agents.copywriter.POSTS_INDEX_FILE", self.pub_file)
        self.patcher1.start()
        self.patcher2.start()
        self.patcher3.start()

        self.publisher = PublisherAgent(container_name="mock_container")
        self.copywriter = CopywriterAgent()

    def tearDown(self):
        self.patcher1.stop()
        self.patcher2.stop()
        self.patcher3.stop()
        self.temp_dir.cleanup()

    @patch("subprocess.run")
    def test_record_draft_goes_only_to_drafts_file(self, mock_run):
        """초안(draft) 포스트 등록 시 draft_posts.json에만 기록되고 published_posts.json에는 기록되지 않음"""
        mock_run.return_value = MagicMock(returncode=0, stdout="http://localhost/?p=101\n")

        self.publisher._record_post(
            post_id=101,
            title="임시 작성중인 복지 글",
            category_id=3,
            category_name="정부 복지/지원금",
            status="draft",
            expires_at="2026-12-31"
        )

        self.assertTrue(self.draft_file.exists())
        self.assertFalse(self.pub_file.exists())

        drafts = json.loads(self.draft_file.read_text(encoding="utf-8"))
        self.assertEqual(len(drafts), 1)
        self.assertEqual(drafts[0]["id"], 101)
        self.assertEqual(drafts[0]["status"], "draft")
        self.assertEqual(drafts[0]["expires_at"], "2026-12-31")

    @patch("subprocess.run")
    def test_record_publish_promotes_from_drafts_to_published(self, mock_run):
        """초안(draft) 상태였던 글이 정식 발행(publish)되면 draft 목록에서 제거되고 published 목록에 추가됨"""
        mock_run.return_value = MagicMock(returncode=0, stdout="http://localhost/?p=102\n")

        # 1. 먼저 초안으로 등록
        self.publisher._record_post(102, "콘서트 예매 안내", 2, "공연/콘서트 예매", status="draft")
        drafts = json.loads(self.draft_file.read_text(encoding="utf-8"))
        self.assertEqual(len(drafts), 1)

        # 2. 공개(publish)로 재등록 (승격)
        self.publisher._record_post(102, "콘서트 예매 안내 [확정]", 2, "공연/콘서트 예매", status="publish", expires_at="2026-12-25")

        drafts_after = json.loads(self.draft_file.read_text(encoding="utf-8"))
        self.assertEqual(len(drafts_after), 0, "Drafts list should be empty after promotion")

        published = json.loads(self.pub_file.read_text(encoding="utf-8"))
        self.assertEqual(len(published), 1)
        self.assertEqual(published[0]["id"], 102)
        self.assertEqual(published[0]["title"], "콘서트 예매 안내 [확정]")
        self.assertEqual(published[0]["status"], "publish")

    def test_interlink_excludes_expired_posts(self):
        """이미 마감된 글(expires_at < today)은 내부 추천 카드에서 제외됨"""
        ref_today = date(2026, 9, 13)

        posts_data = [
            {
                "id": 1,
                "title": "지난 8월 마감된 여름 페스티벌",
                "url": "http://localhost/summer-fest/",
                "category_id": 2,
                "category_name": "공연/콘서트",
                "status": "publish",
                "expires_at": "2026-08-31"  # 과거 (만료)
            },
            {
                "id": 2,
                "title": "2026 크리스마스 수원 콘서트",
                "url": "http://localhost/xmas-suwon/",
                "category_id": 2,
                "category_name": "공연/콘서트",
                "status": "publish",
                "expires_at": "2026-12-25"  # 미래 (유효)
            },
            {
                "id": 3,
                "title": "상시 신청 가능한 국민건강검진 가이드",
                "url": "http://localhost/health-check/",
                "category_id": 4,
                "category_name": "생활/건강",
                "status": "publish",
                "expires_at": None  # 상시 유효
            },
            {
                "id": 4,
                "title": "명시적으로 마감 플래그가 붙은 지원금",
                "url": "http://localhost/closed-welfare/",
                "category_id": 3,
                "category_name": "정부 복지",
                "status": "publish",
                "is_closed": True  # 마감
            }
        ]
        self.pub_file.write_text(json.dumps(posts_data, ensure_ascii=False), encoding="utf-8")

        content = "<p>본문 내용입니다.</p>"
        result = self.copywriter._inject_internal_links(
            content=content,
            current_cat_id=2,
            current_title="현재 작성 중인 신규 공연 글",
            reference_date=ref_today
        )

        # 검증: 만료된 글(여름 페스티벌)과 마감 글은 포함되지 않아야 함
        self.assertNotIn("지난 8월 마감된 여름 페스티벌", result)
        self.assertNotIn("명시적으로 마감 플래그가 붙은 지원금", result)

        # 검증: 유효한 미래 일정 글과 상시 유효 글은 포함되어야 함
        self.assertIn("2026 크리스마스 수원 콘서트", result)
        self.assertIn("상시 신청 가능한 국민건강검진 가이드", result)

    def test_interlink_prevents_self_linking(self):
        """현재 작성 중인 글과 제목이 동일한 글은 추천 카드에서 제외됨"""
        posts_data = [
            {
                "id": 10,
                "title": "2026 독감 예방접종 무료 대상",
                "url": "http://localhost/flu-shot/",
                "category_id": 4,
                "status": "publish",
                "expires_at": "2026-11-30"
            }
        ]
        self.pub_file.write_text(json.dumps(posts_data, ensure_ascii=False), encoding="utf-8")

        content = "<p>본문입니다.</p>"
        result = self.copywriter._inject_internal_links(
            content=content,
            current_cat_id=4,
            current_title="2026 독감 예방접종 무료 대상"  # 동일 제목
        )

        # 추천 상자가 추가되지 않고 원문 그대로 반환되어야 함
        self.assertEqual(result, content)


if __name__ == "__main__":
    unittest.main()