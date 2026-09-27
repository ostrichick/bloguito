import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from PIL import Image
from agents.designer import (
    DesignerAgent,
    _cover_profile,
    _load_font,
    build_editorial_cover_prompt,
    derive_cover_copy,
    split_title,
)


class DesignerRoutingTests(unittest.TestCase):
    def setUp(self):
        self.designer = DesignerAgent()
        self.designer.client = None

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
        mode = self.designer.select_mode("life-health", curated=curated, title="독감 예방접종 무료 대상", keyword="독감 무료")
        self.assertEqual(mode, 5)

    def test_mode_selection_health_lifestyle_guide(self):
        curated = {"poster_url": None, "title": "환절기 건강 관리 및 실내 습도 조절 꿀팁"}
        mode = self.designer.select_mode("life-health", curated=curated, title="환절기 건강 관리 팁", keyword="건강 관리")
        self.assertEqual(mode, 5)

    def test_mode_selection_tax(self):
        curated = {"poster_url": None, "title": "2026 연말정산 환급금 조회 및 소득공제"}
        mode = self.designer.select_mode("tax", curated=curated, title="2026 연말정산 환급금 조회", keyword="연말정산 환급금")
        self.assertEqual(mode, 5)

    def test_tax_is_life_admin_unless_the_topic_is_explicitly_cost_comparison(self):
        self.assertEqual(_cover_profile("재산세 납부 방법", "tax", "생활 세금/절세"), "life_admin")
        self.assertEqual(_cover_profile("자동차 검사비 비용 비교", "tax", "생활 세금/절세"), "price_compare")

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
            "life-health",
            "생활/건강 정보",
            "전입신고 온라인 신청",
            "세대주 확인",
        )
        markers = ["1) Purpose", "2) Topic", "3) Main subject", "4) Composition", "5) Text", "6) Style", "7) Prohibited"]
        positions = [prompt.index(marker) for marker in markers]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("left 42%", prompt)
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

    def test_render_editorial_fallback_outputs_valid_image(self):
        out_path = Path(tempfile.gettempdir()) / "test_editorial_fallback_output.jpg"
        self.designer._render_minimal_fallback(
            primary_text="기초연금 신청",
            secondary_text="자격 확인",
            profile="welfare",
            output_path=out_path,
        )
        self.assertTrue(out_path.exists())
        with Image.open(out_path) as img:
            self.assertEqual(img.size, (1200, 675))
            self.assertEqual(img.format, "JPEG")

    def test_generated_editorial_scene_is_used_when_image_client_is_available(self):
        generated = MagicMock()
        generated.inline_data = MagicMock()
        generated.as_image.return_value = Image.new("RGB", (1200, 675), color=(232, 244, 240))
        self.designer.client = MagicMock()
        self.designer.client.models.generate_content.side_effect = [
            MagicMock(parts=[generated]),
            MagicMock(text='{"pass": true, "issues": []}'),
        ]

        out_path = Path(tempfile.gettempdir()) / "test_generated_editorial_output.jpg"
        self.designer._render_editorial_cover(
            title="전입신고 온라인 신청과 세대주 확인",
            keyword="전입신고 온라인 신청",
            category_key="life-health",
            category_name="생활/건강 정보",
            output_path=out_path,
        )
        generation_call = self.designer.client.models.generate_content.call_args_list[0]
        review_call = self.designer.client.models.generate_content.call_args_list[1]
        self.assertEqual(generation_call.kwargs["model"], "gemini-3.1-flash-image")
        self.assertEqual(generation_call.kwargs["config"].image_config.aspect_ratio, "16:9")
        self.assertEqual(generation_call.kwargs["config"].image_config.image_size, "1K")
        self.assertIn("Render NO text", generation_call.kwargs["contents"])
        self.assertEqual(review_call.kwargs["model"], "gemini-3.5-flash")
        with Image.open(out_path) as img:
            self.assertEqual(img.size, (1200, 675))

    def test_generated_editorial_scene_retries_after_visual_review_failure(self):
        generated = MagicMock()
        generated.inline_data = MagicMock()
        generated.as_image.return_value = Image.new("RGB", (1200, 675), color=(232, 244, 240))
        self.designer.client = MagicMock()
        self.designer.client.models.generate_content.side_effect = [
            MagicMock(parts=[generated]),
            MagicMock(text='{"pass": false, "issues": ["cropped hand"]}'),
            MagicMock(parts=[generated]),
            MagicMock(text='{"pass": true, "issues": []}'),
        ]

        out_path = Path(tempfile.gettempdir()) / "test_generated_editorial_retry.jpg"
        self.designer._render_editorial_cover(
            title="전입신고 온라인 신청과 세대주 확인",
            keyword="전입신고 온라인 신청",
            category_key="life-health",
            category_name="생활/건강 정보",
            output_path=out_path,
        )
        self.assertEqual(self.designer.client.models.generate_content.call_count, 4)
        retry_prompt = self.designer.client.models.generate_content.call_args_list[2].kwargs["contents"]
        self.assertIn("cropped hand", retry_prompt)
        self.assertTrue(out_path.exists())

    def test_render_hybrid_poster_with_mock(self):
        # Create a tiny mock in-memory JPEG poster (100x140)
        mock_img = Image.new("RGB", (100, 140), color=(50, 80, 150))
        buf = io.BytesIO()
        mock_img.save(buf, format="JPEG")
        raw_bytes = buf.getvalue()

        mock_resp = MagicMock()
        mock_resp.read.return_value = raw_bytes
        mock_resp.__enter__.return_value = mock_resp

        out_path = Path(tempfile.gettempdir()) / "test_hybrid_output.jpg"
        with patch("urllib.request.urlopen", return_value=mock_resp):
            self.designer._render_hybrid_poster(
                poster_url="https://example.com/poster.jpg",
                title="2026 임영웅 서울 앵콜 콘서트 예매",
                category_name="공연/콘서트 예매",
                curated={"ticket_prices": "R석 154,000원", "temporal_verification": {"expires_at": "2026-12-25"}},
                output_path=out_path,
            )

        self.assertTrue(out_path.exists())
        with Image.open(out_path) as img:
            self.assertEqual(img.size, (1200, 675))

    def test_render_hybrid_poster_network_failure_falls_back_to_editorial_cover(self):
        out_path = Path(tempfile.gettempdir()) / "test_fallback_output.jpg"
        with patch("urllib.request.urlopen", side_effect=Exception("Connection refused")):
            # generate_image should catch exception and fallback to Mode 2
            res_path = self.designer.generate_image(
                title="2026 단독 콘서트 예매",
                category_name="공연/콘서트 예매",
                keyword="콘서트",
                curated={"poster_url": "https://example.com/unreviewed.jpg"},
                category_key="concert",
                reviewed_poster_url="https://example.com/broken_poster.jpg",
            )

        self.assertTrue(res_path.exists())
        with Image.open(res_path) as img:
            self.assertEqual(img.size, (1200, 675))

    def test_backward_compatible_call(self):
        # Call without curated or category_key
        res_path = self.designer.generate_image(
            title="기초연금 신청 자격 안내",
            category_name="정부 복지/지원금",
            keyword="기초연금",
        )
        self.assertTrue(res_path.exists())
        with Image.open(res_path) as img:
            self.assertEqual(img.size, (1200, 675))


if __name__ == "__main__":
    unittest.main()
