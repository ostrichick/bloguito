import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from agents.publisher import PublisherAgent


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
        self.patcher1.start()
        self.patcher2.start()

        self.publisher = PublisherAgent(container_name="mock_container")

    def tearDown(self):
        self.patcher1.stop()
        self.patcher2.stop()
        self.temp_dir.cleanup()

    @patch("subprocess.run")
    def test_record_draft_goes_only_to_drafts_file(self, mock_run):
        """초안(draft) 포스트 등록 시 draft_posts.json에만 기록되고 published_posts.json에는 기록되지 않음"""
        mock_run.return_value = MagicMock(returncode=0, stdout="http://localhost/?p=101\n")

        self.publisher._record_post(
            post_id=101,
            title="임시 작성중인 복지 글",
            category_id=3,
            category_name="정부 복지·지원금",
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
        self.publisher._record_post(102, "콘서트 예매 안내", 2, "공연·콘서트 예매", status="draft")
        drafts = json.loads(self.draft_file.read_text(encoding="utf-8"))
        self.assertEqual(len(drafts), 1)

        # 2. 공개(publish)로 재등록 (승격)
        self.publisher._record_post(102, "콘서트 예매 안내 [확정]", 2, "공연·콘서트 예매", status="publish", expires_at="2026-12-25")

        drafts_after = json.loads(self.draft_file.read_text(encoding="utf-8"))
        self.assertEqual(len(drafts_after), 0, "Drafts list should be empty after promotion")

        published = json.loads(self.pub_file.read_text(encoding="utf-8"))
        self.assertEqual(len(published), 1)
        self.assertEqual(published[0]["id"], 102)
        self.assertEqual(published[0]["title"], "콘서트 예매 안내 [확정]")
        self.assertEqual(published[0]["status"], "publish")

if __name__ == "__main__":
    unittest.main()
