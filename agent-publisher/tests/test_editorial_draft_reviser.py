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
from test_editorial_system import NOW, sample, sign


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

    def test_full_reviewed_draft_revision_updates_reviewed_rank_math_metadata(self):
        old = sample()
        new = copy.deepcopy(old)
        new["brief"]["primary_keyword"] = "선풍기 무료 배출"
        new["brief"]["seo"] = {
            "title": "선풍기 무료 배출: 서초구 배출 방법",
            "description": "선풍기 무료 배출 방법과 서초구 수거 위치를 공식 기준으로 확인합니다.",
        }
        sign(new)
        old_body = render(old["plan"], old["sources"])
        live = {
            "ID": 393,
            "post_title": old["plan"]["title"],
            "post_status": "draft",
            "post_name": "same-slug",
            "post_content": old_body,
            "post_excerpt": excerpt_from_lead(old["plan"]["lead"]),
        }
        meta = {
            "rank_math_focus_keyword": "old keyword",
            "rank_math_title": "old title",
            "rank_math_description": "old description",
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

            def run(args, **kwargs):
                if args[5:7] == ["post", "get"]:
                    return Mock(stdout=json.dumps(live))
                if args[5:8] == ["post", "meta", "get"]:
                    return Mock(returncode=0, stdout=meta[args[9]] + "\n", stderr="")
                if args[5:8] == ["post", "meta", "set"]:
                    meta[args[9]] = args[10]
                    return Mock(returncode=0, stdout="Success\n", stderr="")
                if args[5] == "eval":
                    payload = json.loads(kwargs["input"])
                    live.update(payload["updates"])
                    return Mock(stdout=json.dumps({"status": "ok", "saved": live}))
                raise AssertionError(args)

            inventory = {"checked_on": NOW.date().isoformat(), "posts": [live]}
            with patch("agents.editorial_draft_reviser.ROOT", root), \
                 patch("agents.editorial_draft_reviser.DRAFTS_INDEX_FILE", index), \
                 patch("agents.editorial_draft_reviser.sync_inventory"), \
                 patch("agents.editorial_draft_reviser.invalidate_inventory"), \
                 patch("agents.editorial_draft_reviser.load_inventory", return_value=inventory), \
                 patch("agents.editorial_draft_reviser.validate_bundle", return_value={"status": "ready", "reasons": []}), \
                 patch("agents.editorial_draft_reviser.verify_sources_unchanged", return_value={
                     "reused_source_ids": [], "refetched_source_ids": [s["id"] for s in new["sources"]],
                     "all_unchanged": True,
                 }), \
                 patch("agents.editorial_draft_reviser.save_report"), \
                 patch("agents.editorial_draft_reviser.subprocess.run", side_effect=run):
                result = revise_reviewed_draft(
                    393,
                    new,
                    hashlib.sha256(old_body.encode()).hexdigest(),
                    confirmed=True,
                )

            self.assertEqual(result, 393)
            self.assertEqual(meta, {
                "rank_math_focus_keyword": "선풍기 무료 배출",
                "rank_math_title": "선풍기 무료 배출: 서초구 배출 방법",
                "rank_math_description": "선풍기 무료 배출 방법과 서초구 수거 위치를 공식 기준으로 확인합니다.",
            })
            backup = json.loads(next((data / "editorial_runs").glob("draft-revision-393-*.json")).read_text(encoding="utf-8"))
            self.assertEqual(backup["rank_math_meta"], {
                "rank_math_focus_keyword": "old keyword",
                "rank_math_title": "old title",
                "rank_math_description": "old description",
            })

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

    def test_location_card_compact_renderer_migration_is_normalized(self):
        old = (
            '<div class="festival-location-card">'
            '<div style="font-weight:700;color:#1e293b;font-size:15px;margin-bottom:8px">📍 행사장 위치</div>'
            '<div style="font-size:14px;color:#475569;margin-bottom:10px;line-height:1.6">'
            '<strong>장소</strong>: 서초 행사장<br/><strong>위치</strong>: 서울 서초구 안내로 1</div>'
            '</div>'
        )
        new = (
            '<div class="festival-location-card">'
            '<div style="font-weight:700;color:#1e293b;font-size:15px;margin-bottom:4px">'
            '📍 행사장 위치: 서초 행사장</div>'
            '<div style="font-size:14px;color:#475569;margin-bottom:10px;line-height:1.6">'
            '<strong>주소</strong>: 서울 서초구 안내로 1</div>'
            '</div>'
        )
        self.assertEqual(
            _normalize_renderer_migrations(old),
            _normalize_renderer_migrations(new),
        )

    def test_location_card_duplicate_address_removal_is_normalized(self):
        old = (
            '<div class="festival-location-card">'
            '<div style="font-weight:700;color:#1e293b;font-size:15px;margin-bottom:8px">📍 행사장 위치</div>'
            '<div style="font-size:14px;color:#475569;margin-bottom:10px;line-height:1.6">'
            '<strong>장소</strong>: 삼락생태공원<br/><strong>위치</strong>: 삼락생태공원</div>'
            '</div>'
        )
        new = (
            '<div class="festival-location-card">'
            '<div style="font-weight:700;color:#1e293b;font-size:15px;margin-bottom:10px">'
            '📍 행사장 위치: 삼락생태공원</div>'
            '</div>'
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

    def test_mobile_semantic_unit_renderer_migration_is_normalized(self):
        old = (
            '<article><div>광안리 M 드론라이트쇼 10월 공연</div>'
            '<p>검토된 본문</p></article>'
        )
        new = (
            '<article><div>광안리 <span class="bloguito-semantic-unit">'
            'M 드론라이트쇼</span> 10월 공연</div>'
            '<p>검토된 본문</p></article>'
        )
        self.assertEqual(
            _normalize_renderer_migrations(old),
            _normalize_renderer_migrations(new),
        )

    def test_mobile_semantic_unit_migration_does_not_hide_prose_change(self):
        old = '<div>광안리 M 드론라이트쇼 10월 공연</div><p>검토된 본문</p>'
        edited = (
            '<div>광안리 <span class="bloguito-semantic-unit">M 드론라이트쇼</span> '
            '10월 공연</div><p>사람이 바꾼 본문</p>'
        )
        self.assertNotEqual(
            _normalize_renderer_migrations(old),
            _normalize_renderer_migrations(edited),
        )


if __name__ == "__main__":
    unittest.main()
