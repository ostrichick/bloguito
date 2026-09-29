import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from agents.editorial import excerpt_from_lead, render
from agents.editorial_draft_reviser import (
    _before_generated_source_footer,
    _normalize_renderer_migrations,
    revise_reviewed_draft,
)
from test_editorial_system import NOW, sample


class EditorialDraftReviserTests(unittest.TestCase):
    def test_full_reviewed_draft_revision_can_apply_explicit_reviewed_title_change(self):
        old = sample()
        new = copy.deepcopy(old)
        new["plan"]["lead"]["text"] = "새로 독립 검토된 원고 문장입니다."
        new["plan"]["title"] = "새로 독립 검토된 제목"
        old_body = render(old["plan"], old["sources"])
        new_body = render(new["plan"], new["sources"])
        live = {
            "ID": 393,
            "post_title": old["plan"]["title"],
            "post_status": "draft",
            "post_name": "same-slug",
            "post_content": old_body,
            "post_excerpt": excerpt_from_lead(old["plan"]["lead"]),
        }

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            data = root / "data"
            data.mkdir()
            index = data / "draft_posts.json"
            index.write_text(json.dumps([{
                "id": 393,
                "fact_manifest": {"editorial_bundle": old},
            }]), encoding="utf-8")

            calls = []

            def run(args, **kwargs):
                calls.append(args)
                if args[5:7] == ["post", "get"]:
                    return Mock(stdout=json.dumps(live))
                if args[5] == "eval":
                    payload = json.loads(kwargs["input"])
                    live.update(payload["updates"])
                    return Mock(stdout=json.dumps({"status": "ok", "saved": live}))
                raise AssertionError(args)

            inventory = {"checked_on": NOW.date().isoformat(), "posts": [live]}
            with patch("agents.editorial_draft_reviser.ROOT", root), \
                 patch("agents.editorial_draft_reviser.DRAFTS_INDEX_FILE", index), \
                 patch("agents.editorial_draft_reviser.sync_inventory"), \
                 patch("agents.editorial_draft_reviser.invalidate_inventory") as invalidate, \
                 patch("agents.editorial_draft_reviser.load_inventory", return_value=inventory), \
                 patch("agents.editorial_draft_reviser.validate_bundle", return_value={"status": "ready", "reasons": []}), \
                 patch("agents.editorial_draft_reviser.verify_sources_unchanged", return_value={
                     "reused_source_ids": [], "refetched_source_ids": [s["id"] for s in new["sources"]],
                     "all_unchanged": True,
                 }) as source_recheck, \
                 patch("agents.editorial_draft_reviser.save_report"), \
                 patch("agents.editorial_draft_reviser.subprocess.run", side_effect=run):
                result = revise_reviewed_draft(
                    393,
                    new,
                    hashlib.sha256(old_body.encode()).hexdigest(),
                    confirmed=True,
                    confirm_title_change=True,
                )

            self.assertEqual(result, 393)
            invalidate.assert_called_once_with()
            self.assertEqual(live["post_status"], "draft")
            self.assertEqual(live["post_name"], "same-slug")
            self.assertEqual(live["post_title"], new["plan"]["title"])
            self.assertEqual(live["post_content"], new_body)
            saved_index = json.loads(index.read_text(encoding="utf-8"))
            self.assertEqual(saved_index[0]["fact_manifest"]["editorial_bundle"], new)
            self.assertEqual(len(list((data / "editorial_runs").glob("draft-revision-393-*.json"))), 1)
            self.assertEqual(len(list((data / "editorial_runs").glob("draft-revision-index-393-*.json"))), 1)
            # P2 keeps the initial backup snapshot, then performs final CAS,
            # mutation and readback inside one guarded WP process.
            self.assertEqual(1, sum(args[5:7] == ["post", "get"] for args in calls))
            self.assertEqual(1, sum(args[5] == "eval" for args in calls))
            source_recheck.assert_called_once()

    def test_revision_requires_confirmation(self):
        with self.assertRaisesRegex(ValueError, "specific_draft_revision_confirmation_required"):
            revise_reviewed_draft(393, {}, "0" * 64, confirmed=False)

    def test_source_footer_only_renderer_migration_is_accepted_by_comparison_helper(self):
        old = (
            '<div class="bloguito-article"><p>검토된 본문</p>'
            '<div style="margin-top:44px"><h2 id="sources">출처</h2>'
            '<ul class="source-list"><li>old</li></ul></div></div>'
        )
        new = (
            '<div class="bloguito-article"><p>검토된 본문</p>'
            '<div style="margin-top:44px"><h2 id="sources">출처</h2>'
            '<ul class="source-list"><li>new</li></ul></div></div>'
        )
        self.assertEqual(
            _before_generated_source_footer(old),
            _before_generated_source_footer(new),
        )

    def test_missing_generated_source_footer_matches_current_renderer_body(self):
        stored = '<div class="bloguito-article"><p>검토된 본문</p></div>'
        rendered = (
            '<div class="bloguito-article"><p>검토된 본문</p>'
            '<div style="margin-top:44px"><h2 id="sources">출처</h2>'
            '<ul class="source-list"><li>current</li></ul></div></div>'
        )
        self.assertEqual(
            _before_generated_source_footer(stored),
            _before_generated_source_footer(rendered),
        )

    def test_source_footer_migration_does_not_hide_prose_change(self):
        old = (
            '<div class="bloguito-article"><p>검토된 본문</p>'
            '<div><h2 id="sources">출처</h2><ul class="source-list"></ul></div></div>'
        )
        edited = (
            '<div class="bloguito-article"><p>사람이 바꾼 본문</p>'
            '<div><h2 id="sources">출처</h2><ul class="source-list"></ul></div></div>'
        )
        self.assertNotEqual(
            _before_generated_source_footer(old),
            _before_generated_source_footer(edited),
        )

    def test_event_image_caption_separator_renderer_migration_is_normalized(self):
        old = (
            '<figure><figcaption style="color:#64748b">공식 행사 이미지 · '
            '<a href="https://example.org/event" rel="noopener noreferrer">공식 자료</a>'
            '</figcaption></figure>'
        )
        new = old.replace('이미지 · ', '이미지, ')
        self.assertEqual(
            _normalize_renderer_migrations(old),
            _normalize_renderer_migrations(new),
        )

    def test_event_image_caption_migration_does_not_hide_authored_prose_change(self):
        old = (
            '<p>검토된 본문입니다.</p><figure><figcaption>공식 행사 이미지 · '
            '<a href="https://example.org/event">공식 자료</a></figcaption></figure>'
        )
        edited = old.replace('검토된 본문입니다.', '사람이 바꾼 본문입니다.')
        self.assertNotEqual(
            _normalize_renderer_migrations(old),
            _normalize_renderer_migrations(edited),
        )

    def test_location_card_google_button_removal_is_normalized(self):
        old = (
            '<div class="festival-location-card">'
            '<div style="font-weight:700;color:#1e293b;font-size:15px;margin-bottom:8px">📍 행사장 지도 및 길찾기</div>'
            '<div style="display:flex;gap:8px;flex-wrap:wrap">'
            '<a href="https://map.kakao.com/link/search/test">카카오맵 위치 보기</a>'
            '<a href="https://www.google.com/maps/dir/?api=1&amp;destination=test" target="_blank" rel="noopener noreferrer" '
            'style="display:inline-flex;align-items:center;gap:4px;padding:7px 13px;background:#ffffff;color:#0d7d59 !important;'
            'border:1px solid #0d7d59;font-size:13px;font-weight:700;border-radius:6px;text-decoration:none !important">'
            '길찾기 시작 <span aria-hidden="true">↗</span></a>'
            '</div></div>'
        )
        new = (
            '<div class="festival-location-card">'
            '<div style="font-weight:700;color:#1e293b;font-size:15px;margin-bottom:8px">📍 행사장 위치</div>'
            '<div style="display:flex;gap:8px;flex-wrap:wrap">'
            '<a href="https://map.kakao.com/link/search/test">카카오맵 위치 보기</a>'
            '</div></div>'
        )
        self.assertEqual(
            _normalize_renderer_migrations(old),
            _normalize_renderer_migrations(new),
        )

    def test_location_card_migration_does_not_hide_authored_prose_change(self):
        old = '<p>검토된 본문</p><div>📍 행사장 지도 및 길찾기</div>'
        edited = '<p>사람이 바꾼 본문</p><div>📍 행사장 위치</div>'
        self.assertNotEqual(
            _normalize_renderer_migrations(old),
            _normalize_renderer_migrations(edited),
        )

    def test_responsive_style_renderer_migration_is_normalized(self):
        old = '<div class="bloguito-article"><p>검토된 본문</p></div>'
        new = (
            '<div class="bloguito-article">'
            '<style id="bloguito-responsive-layout">.bloguito-article *{box-sizing:border-box}</style>'
            '<p>검토된 본문</p></div>'
        )
        self.assertEqual(
            _normalize_renderer_migrations(old),
            _normalize_renderer_migrations(new),
        )


if __name__ == "__main__":
    unittest.main()
