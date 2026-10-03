"""Reviewed search-brief narrow-merge storage tests."""

from __future__ import annotations

from datetime import date
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from merge_search_brief import SearchBriefMergeError, merge_search_brief


def brief(brief_id="new-brief"):
    return {
        "id": brief_id,
        "intent_type": "application",
        "ai_answerability": "medium",
        "added_value": ["official_action", "troubleshooting"],
        "category_key": "life-admin",
        "approved": True,
        "entity": "테스트민원",
        "primary_keyword": "테스트민원 온라인 신청",
        "question": "테스트민원을 온라인으로 신청하는 절차는 무엇인가?",
        "angle": "공식 신청 절차와 오류 해결만 설명한다.",
        "required_title_terms": ["테스트민원", "신청"],
        "official_urls": ["https://example.go.kr/apply"],
        "queries": ["테스트민원 온라인 신청"],
        "serp_urls": ["https://example.go.kr/help"],
        "reviewed_at": "2026-10-03",
        "review_until": "2026-10-31",
        "content_type": "evergreen",
        "useful_until": None,
        "evergreen_reason": "특정 마감에 종속되지 않는 상시 행정 절차",
        "volatility": "timeless-procedure",
        "requires_live_state": False,
        "reader_questions": [{"id": "q1", "question": "신청 경로는?"}],
    }


class SearchBriefMergeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.target = self.root / "data" / "search_briefs.json"
        self.target.parent.mkdir()
        self.backups = self.root / "backups"
        self.original = [brief("existing-brief")]
        self.target.write_text(
            json.dumps(self.original, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self.today = date(2026, 10, 3)

    def test_append_preserves_non_target_rows_and_exact_backup(self):
        original_bytes = self.target.read_bytes()
        result = merge_search_brief(
            self.target, brief(), today=self.today, backup_root=self.backups, confirm=True)
        self.assertEqual("merged", result["status"])
        self.assertEqual("append", result["action"])
        rows = json.loads(self.target.read_text(encoding="utf-8"))
        self.assertEqual(self.original[0], rows[0])
        self.assertEqual(brief(), rows[1])
        backup = Path(result["backup"]) / "search_briefs.json"
        self.assertEqual(original_bytes, backup.read_bytes())

    def test_dry_run_does_not_write_or_create_backup(self):
        original_bytes = self.target.read_bytes()
        result = merge_search_brief(
            self.target, brief(), today=self.today, backup_root=self.backups, confirm=False)
        self.assertEqual("dry_run", result["status"])
        self.assertEqual(original_bytes, self.target.read_bytes())
        self.assertFalse(self.backups.exists())

    def test_identical_existing_row_is_idempotent_noop(self):
        result = merge_search_brief(
            self.target, self.original[0], today=self.today,
            backup_root=self.backups, confirm=True)
        self.assertEqual("no_change", result["status"])
        self.assertFalse(self.backups.exists())

    def test_existing_id_change_requires_explicit_replace(self):
        changed = dict(self.original[0], angle="다른 검토 각도")
        with self.assertRaisesRegex(SearchBriefMergeError, "already_exists"):
            merge_search_brief(
                self.target, changed, today=self.today,
                backup_root=self.backups, confirm=True)
        result = merge_search_brief(
            self.target, changed, today=self.today, backup_root=self.backups,
            replace_existing=True, confirm=True)
        self.assertEqual("replace", result["action"])
        rows = json.loads(self.target.read_text(encoding="utf-8"))
        self.assertEqual([changed], rows)

    def test_duplicate_target_ids_fail_closed_before_backup(self):
        self.target.write_text(
            json.dumps([self.original[0], self.original[0]], ensure_ascii=False),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(SearchBriefMergeError, "search_briefs_invalid"):
            merge_search_brief(
                self.target, brief(), today=self.today,
                backup_root=self.backups, confirm=True)
        self.assertFalse(self.backups.exists())

    def test_expected_sha_mismatch_fails_before_mutation(self):
        before = self.target.read_bytes()
        with self.assertRaisesRegex(SearchBriefMergeError, "expected_sha_mismatch"):
            merge_search_brief(
                self.target, brief(), today=self.today, backup_root=self.backups,
                expected_sha256="0" * 64, confirm=True)
        self.assertEqual(before, self.target.read_bytes())
        self.assertFalse(self.backups.exists())

    def test_manifest_records_pre_and_post_hashes(self):
        pre = hashlib.sha256(self.target.read_bytes()).hexdigest()
        result = merge_search_brief(
            self.target, brief(), today=self.today, backup_root=self.backups, confirm=True)
        manifest = json.loads(
            (Path(result["backup"]) / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(pre, manifest["pre_sha256"])
        self.assertEqual(result["post_sha256"], manifest["post_sha256"])
        self.assertEqual("new-brief", manifest["target_id"])


if __name__ == "__main__":
    unittest.main()
