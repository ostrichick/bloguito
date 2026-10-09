import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from PIL import Image
from agents.designer import (
    DesignerAgent,
    ScheduledImageGenerationUnavailable,
    _centered_block_top,
    _cover_profile,
    _load_display_font,
    _load_font,
    build_cover_line_plan,
    build_editorial_cover_prompt,
    cleanup_generated_cover,
    derive_cover_copy,
    split_title,
)


class DesignerRoutingTests(unittest.TestCase):
    def setUp(self):
        self.designer = DesignerAgent(scheduler_context=True)
        self.designer.client = None
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.enterContext(
            patch("agents.designer.generated_cover_root", return_value=Path(self.temp_dir.name))
        )

    def test_generated_cover_cleanup_is_scoped_to_bloguito_temp_root(self):
        generated = Path(self.temp_dir.name) / "thumb_test.jpg"
        generated.write_bytes(b"generated")
        self.assertTrue(cleanup_generated_cover(generated))
        self.assertFalse(generated.exists())

        with tempfile.TemporaryDirectory() as external_dir:
            external = Path(external_dir) / "user-cover.jpg"
            external.write_bytes(b"user")
            self.assertFalse(cleanup_generated_cover(external))
            self.assertTrue(external.exists())

    def test_generate_image_removes_reserved_temp_file_when_rendering_fails(self):
        with patch.object(self.designer, "_render_editorial_cover", side_effect=RuntimeError("render failed")):
            with self.assertRaisesRegex(RuntimeError, "render failed"):
                self.designer.generate_image(
                    title="실패 테스트",
                    category_name="행정/생활서비스",
                    keyword="실패",
                    category_key="life-admin",
                )
        self.assertEqual([], list(Path(self.temp_dir.name).glob("thumb_*.jpg")))

    def test_mode_selection_concert_with_unreviewed_poster(self):
        curated = {"poster_url": "https://example.com/poster.jpg", "title": "임영웅 콘서트"}
        mode = self.designer.select_mode("concert", curated=curated, title="임영웅 콘서트", keyword="콘서트 예매")
        self.assertEqual(mode, 5)

    def test_mode_selection_concert_with_explicitly_reviewed_poster(self):
        mode = self.designer.select_mode(
            "concert", title="임영웅 콘서트", reviewed_poster_url="https://example.com/poster.jpg"
        )
        self.assertEqual(mode, 4)

    def test_mode_selection_concert_without_poster(self):
        curated = {"poster_url": None, "title": "임영웅 콘서트"}
        mode = self.designer.select_mode("concert", curated=curated, title="임영웅 콘서트", keyword="콘서트 예매")
        self.assertEqual(mode, 5)

    def test_mode_selection_welfare(self):
        curated = {"poster_url": None, "title": "2026 기초연금 신청 자격"}
        mode = self.designer.select_mode("welfare", curated=curated, title="2026 기초연금 신청", keyword="기초연금")
        self.assertEqual(mode, 5)

    def test_mode_selection_health_with_numbers(self):
        curated = {"poster_url": None, "title": "2026 독감 예방접종 무료 대상자 안내"}
        mode = self.designer.select_mode("health", curated=curated, title="독감 예방접종 무료 대상", keyword="독감 무료")
        self.assertEqual(mode, 5)

    def test_mode_selection_health_lifestyle_guide(self):
        curated = {"poster_url": None, "title": "환절기 건강 관리 및 실내 습도 조절 꿀팁"}
        mode = self.designer.select_mode("health", curated=curated, title="환절기 건강 관리 팁", keyword="건강 관리")
        self.assertEqual(mode, 5)

    def test_mode_selection_tax(self):
        curated = {"poster_url": None, "title": "2026 연말정산 환급금 조회 및 소득공제"}
        mode = self.designer.select_mode("tax", curated=curated, title="2026 연말정산 환급금 조회", keyword="연말정산 환급금")
        self.assertEqual(mode, 5)

    def test_active_categories_have_distinct_cover_profiles(self):
        self.assertEqual(_cover_profile("재산세 납부 방법", "tax", "세금/절세"), "tax")
        self.assertEqual(_cover_profile("전입신고 온라인 신청", "life-admin", "행정/생활서비스"), "life_admin")
        self.assertEqual(_cover_profile("국가건강검진 대상자 조회", "health", "건강/의료"), "health")
        self.assertEqual(_cover_profile("KTX 취소표", "transport", "교통/자동차"), "transport")
        self.assertEqual(_cover_profile("카드포인트 조회", "finance", "금융/경제"), "finance")
        self.assertEqual(_cover_profile("전주 10월 축제", "events", "지역 축제/행사"), "events")

    def test_movein_benchmark_copy_is_shorter_than_article_title(self):
        title = "전입신고 온라인 신청과 세대주 확인: 필요한 경우, 8일 기한, 정부24 방법"
        primary, secondary = derive_cover_copy(title, "전입신고 온라인 신청")
        self.assertEqual(primary, "전입신고 온라인 신청")
        self.assertEqual(secondary, "세대주 확인")
        self.assertNotEqual(primary, title)

    def test_multiword_article_title_is_not_repeated_verbatim(self):
        primary, secondary = derive_cover_copy("기초연금 신청 방법", "기초연금 신청 방법")
        self.assertEqual(primary, "기초연금 신청")
        self.assertIsNone(secondary)
        self.assertNotEqual(primary, "기초연금 신청 방법")

    def test_two_word_article_title_is_not_repeated_verbatim(self):
        primary, secondary = derive_cover_copy("기초연금 신청", "기초연금 신청")
        self.assertEqual(primary, "기초연금")
        self.assertIsNone(secondary)
        self.assertNotEqual(primary, "기초연금 신청")

    def test_single_topic_word_may_remain_the_cover_title(self):
        primary, secondary = derive_cover_copy("전입신고", "전입신고")
        self.assertEqual(primary, "전입신고")
        self.assertIsNone(secondary)

    def test_colon_tail_can_supply_a_short_timeless_secondary_line(self):
        primary, secondary = derive_cover_copy(
            "전입신고 온라인 신청: 세대주 확인, 정부24 신청 방법",
            "전입신고 온라인 신청",
        )
        self.assertEqual(primary, "전입신고 온라인 신청")
        self.assertEqual(secondary, "세대주 확인, 정부24 신청 방법")

    def test_overlong_unbroken_primary_requires_manual_cover_copy(self):
        title = "가나다라마바사아자차카타파하가나다라마바사아자차카타파하"
        with self.assertRaisesRegex(ValueError, "cover_copy_requires_review"):
            derive_cover_copy(title, "")
        self.assertEqual(split_title(title), [title])

    def test_editorial_prompt_follows_common_policy_order_and_reserves_text_area(self):
        prompt = build_editorial_cover_prompt(
            "전입신고 온라인 신청과 세대주 확인",
            "전입신고 온라인 신청",
            "life-admin",
            "행정/생활서비스",
            "전입신고 온라인 신청",
            "세대주 확인",
        )
        markers = ["1) Purpose", "2) Topic", "3) Main subject", "4) Composition", "5) Text", "6) Style", "7) Prohibited"]
        positions = [prompt.index(marker) for marker in markers]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("left 45%", prompt)
        self.assertIn("strict left-text/right-scene split", prompt)
        self.assertIn("Render NO text", prompt)
        self.assertIn("cropped face head hands", prompt)

    def test_font_loader_returns_valid_font(self):
        font_bold = _load_font(24, bold=True)
        font_reg = _load_font(18, bold=False)
        self.assertIsNotNone(font_bold)
        self.assertIsNotNone(font_reg)
        bbox = font_bold.getbbox("테스트")
        self.assertTrue(len(bbox) == 4)
        self.assertNotEqual(bytes(font_bold.getmask("가")), bytes(font_bold.getmask("나")))

    def test_font_loader_fails_closed_when_no_hangul_font_is_available(self):
        with patch("agents.designer.ImageFont.truetype", side_effect=OSError("font missing")):
            with self.assertRaisesRegex(RuntimeError, "Hangul-capable font unavailable"):
                _load_font(24, bold=True)

    def test_featured_primary_font_uses_verified_display_face(self):
        for role in ('primary', 'secondary', 'chip'):
            with self.subTest(role=role):
                font = _load_display_font(32, role=role)
                self.assertIsNotNone(font)
                family, style = font.getname()
                self.assertIn(family, {'Noto Serif KR', 'Noto Serif CJK KR'})
                self.assertEqual(style, 'Black')
                self.assertNotIn('Malgun', family)

    def test_cover_overlay_never_uses_generic_font_loader_for_visible_copy(self):
        image = Image.new('RGB', (1200, 675), color=(240, 246, 243))
        with patch('agents.designer._load_font', side_effect=AssertionError('generic cover font used')):
            rendered = self.designer._overlay_cover_copy(
                image,
                primary_text='광주 10월 축제',
                secondary_text='공연과 체험 일정',
                chip_text='2026',
            )
        self.assertEqual((1200, 675), rendered.size)

    def test_display_font_selects_korean_face_from_cjk_collection(self):
        korean = MagicMock()
        korean.getname.return_value = ('Noto Serif CJK KR', 'Black')
        japanese = MagicMock()
        japanese.getname.return_value = ('Noto Serif CJK JP', 'Black')

        def collection_font(path, size, index=0):
            if not path.endswith('.ttc'):
                raise OSError('variable font absent')
            return korean if index == 1 else japanese

        with patch('agents.designer.ImageFont.truetype', side_effect=collection_font), \
             patch('agents.designer._font_has_hangul', return_value=True):
            self.assertIs(_load_display_font(32), korean)

    def test_display_font_fails_closed_instead_of_using_generic_gothic(self):
        with patch("agents.designer.ImageFont.truetype", side_effect=OSError("display font missing")):
            with self.assertRaisesRegex(RuntimeError, "Brand Hangul display font unavailable"):
                _load_display_font(32)

    def test_text_block_is_centered_vertically_with_safe_margin(self):
        self.assertEqual(_centered_block_top(675, 275, 54), 200)
        with self.assertRaisesRegex(ValueError, "vertical_safe_area"):
            _centered_block_top(675, 620, 54)

    def test_title_split_keeps_numeric_range_phrase_together(self):
        self.assertEqual(
            split_title("2026~2027 65세 이상 독감 무료접종 일정"),
            ["2026~2027 65세 이상", "독감 무료접종 일정"],
        )
        for title in (
            "2026 지원금 10만원 미만 신청 대상 안내",
            "영유아 3개월 이하 예방접종 준비사항 안내",
            "주차 2시간 이내 무료 이용 방법 안내",
        ):
            rendered = "\n".join(split_title(title))
            self.assertNotRegex(rendered, r"(?:10만원|3개월|2시간)\n(?:미만|이하|이내)")

    def test_cover_line_plan_is_determined_before_font_metrics(self):
        title = "2026~2027 65세 이상 독감 무료접종 일정"
        with patch("agents.designer._load_display_font", side_effect=AssertionError("font loaded during line planning")):
            lines = build_cover_line_plan(title)
        self.assertEqual(lines, ["2026~2027 65세 이상", "독감 무료접종 일정"])

    def test_cover_overlay_does_not_reflow_when_font_size_changes(self):
        image = Image.new("RGB", (1200, 675), color=(240, 246, 243))
        title = "세종 10월 축제 일정 안내"
        expected = build_cover_line_plan(title)
        with patch("agents.designer.build_cover_line_plan", wraps=build_cover_line_plan) as planner:
            rendered = self.designer._overlay_cover_copy(
                image,
                primary_text=title,
                secondary_text="접종 일정 확인",
                chip_text="2026",
            )
        self.assertEqual((1200, 675), rendered.size)
        self.assertEqual(planner.call_count, 1)
        self.assertEqual(planner.call_args.args[0], title)
        self.assertEqual(expected, build_cover_line_plan(title))

    def test_low_quality_local_fallback_is_not_publishable(self):
        out_path = Path(self.temp_dir.name) / "test_editorial_fallback_output.jpg"
        with self.assertRaisesRegex(RuntimeError, "no_publishable_fallback"):
            self.designer._render_minimal_fallback(
                primary_text="기초연금 신청",
                secondary_text="자격 확인",
                profile="welfare",
                output_path=out_path,
            )
        self.assertFalse(out_path.exists())

    def test_generated_editorial_scene_is_used_when_image_client_is_available(self):
        out_path = Path(self.temp_dir.name) / "test_generated_editorial_output.jpg"
        with patch.object(
            self.designer, "_generated_scene",
            return_value=Image.new("RGB", (1200, 675), color=(232, 244, 240))
        ) as scene, patch.object(
            self.designer, "_vision_review_cover", return_value=(True, [])
        ) as review:
            self.designer._render_editorial_cover(
                title="전입신고 온라인 신청과 세대주 확인",
                keyword="전입신고 온라인 신청",
                category_key="life-admin",
                category_name="행정/생활서비스",
                output_path=out_path,
            )
        self.assertEqual(1, scene.call_count)
        self.assertIn("Render NO text", scene.call_args.args[0])
        review.assert_called_once()
        with Image.open(out_path) as img:
            self.assertEqual(img.size, (1200, 675))
        self.assertRegex(self.designer.last_review_evidence_sha256 or "", r"^[0-9a-f]{64}$")

    def test_generated_editorial_scene_retries_after_visual_review_failure(self):
        out_path = Path(self.temp_dir.name) / "test_generated_editorial_retry.jpg"
        with patch.object(
            self.designer, "_generated_scene",
            return_value=Image.new("RGB", (1200, 675), color=(232, 244, 240))
        ) as scene, patch.object(
            self.designer, "_vision_review_cover",
            side_effect=[(False, ["cropped hand"]), (True, [])],
        ):
            self.designer._render_editorial_cover(
                title="전입신고 온라인 신청과 세대주 확인",
                keyword="전입신고 온라인 신청",
                category_key="life-admin",
                category_name="행정/생활서비스",
                output_path=out_path,
            )
        self.assertEqual(scene.call_count, 2)
        retry_prompt = scene.call_args_list[1].args[0]
        self.assertIn("cropped hand", retry_prompt)
        self.assertTrue(out_path.exists())
        self.assertRegex(self.designer.last_review_evidence_sha256 or "", r"^[0-9a-f]{64}$")

    def test_render_hybrid_poster_with_mock(self):
        # Create a tiny mock in-memory JPEG poster (100x140)
        mock_img = Image.new("RGB", (100, 140), color=(50, 80, 150))
        buf = io.BytesIO()
        mock_img.save(buf, format="JPEG")
        raw_bytes = buf.getvalue()

        mock_resp = MagicMock()
        mock_resp.read.return_value = raw_bytes
        mock_resp.__enter__.return_value = mock_resp

        out_path = Path(self.temp_dir.name) / "test_hybrid_output.jpg"
        with patch("urllib.request.urlopen", return_value=mock_resp):
            self.designer._render_hybrid_poster(
                poster_url="https://example.com/poster.jpg",
                title="2026 임영웅 서울 앵콜 콘서트 예매",
                category_name="공연/콘서트",
                curated={"ticket_prices": "R석 154,000원", "temporal_verification": {"expires_at": "2026-12-25"}},
                output_path=out_path,
            )

        self.assertTrue(out_path.exists())
        with Image.open(out_path) as img:
            self.assertEqual(img.size, (1200, 675))

    def test_render_hybrid_poster_network_failure_does_not_make_low_quality_fallback(self):
        with patch("urllib.request.urlopen", side_effect=Exception("Connection refused")):
            with self.assertRaisesRegex(
                ScheduledImageGenerationUnavailable,
                "chatgpt_image_gen_required_unavailable_in_server_scheduler",
            ):
                self.designer.generate_image(
                    title="2026 단독 콘서트 예매",
                    category_name="공연/콘서트",
                    keyword="콘서트",
                    curated={"poster_url": "https://example.com/unreviewed.jpg"},
                    category_key="concert",
                    reviewed_poster_url="https://example.com/broken_poster.jpg",
                )

    def test_backward_compatible_call(self):
        # Call shape remains valid, but without an image client it fails closed.
        with self.assertRaisesRegex(
            ScheduledImageGenerationUnavailable,
            "chatgpt_image_gen_required_unavailable_in_server_scheduler",
        ):
            self.designer.generate_image(
                title="기초연금 신청 자격 안내",
                category_name="복지/지원금",
                keyword="기초연금",
            )


if __name__ == "__main__":
    unittest.main()
