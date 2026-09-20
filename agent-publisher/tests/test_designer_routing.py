import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from PIL import Image
from agents.designer import DesignerAgent, _load_font


class DesignerRoutingTests(unittest.TestCase):
    def setUp(self):
        self.designer = DesignerAgent()

    def test_mode_selection_concert_with_poster(self):
        curated = {"poster_url": "https://example.com/poster.jpg", "title": "임영웅 콘서트"}
        mode = self.designer.select_mode("concert", curated=curated, title="임영웅 콘서트", keyword="콘서트 예매")
        self.assertEqual(mode, 4)

    def test_mode_selection_concert_without_poster(self):
        curated = {"poster_url": None, "title": "임영웅 콘서트"}
        mode = self.designer.select_mode("concert", curated=curated, title="임영웅 콘서트", keyword="콘서트 예매")
        self.assertEqual(mode, 2)

    def test_mode_selection_welfare(self):
        curated = {"poster_url": None, "title": "2026 기초연금 신청 자격"}
        mode = self.designer.select_mode("welfare", curated=curated, title="2026 기초연금 신청", keyword="기초연금")
        self.assertEqual(mode, 2)

    def test_mode_selection_health_with_numbers(self):
        curated = {"poster_url": None, "title": "2026 독감 예방접종 무료 대상자 안내"}
        mode = self.designer.select_mode("life-health", curated=curated, title="독감 예방접종 무료 대상", keyword="독감 무료")
        self.assertEqual(mode, 2)

    def test_mode_selection_health_lifestyle_guide(self):
        curated = {"poster_url": None, "title": "환절기 건강 관리 및 실내 습도 조절 꿀팁"}
        mode = self.designer.select_mode("life-health", curated=curated, title="환절기 건강 관리 팁", keyword="건강 관리")
        self.assertEqual(mode, 3)

    def test_mode_selection_tax(self):
        curated = {"poster_url": None, "title": "2026 연말정산 환급금 조회 및 소득공제"}
        mode = self.designer.select_mode("tax", curated=curated, title="2026 연말정산 환급금 조회", keyword="연말정산 환급금")
        self.assertEqual(mode, 2)

    def test_font_loader_returns_valid_font(self):
        font_bold = _load_font(24, bold=True)
        font_reg = _load_font(18, bold=False)
        self.assertIsNotNone(font_bold)
        self.assertIsNotNone(font_reg)
        bbox = font_bold.getbbox("테스트")
        self.assertTrue(len(bbox) == 4)

    def test_render_toss_typography_outputs_valid_image(self):
        out_path = Path(tempfile.gettempdir()) / "test_toss_output.jpg"
        self.designer._render_toss_typography(
            title="2026년 기초연금 인상 및 자격 안내",
            category_name="정부 복지/지원금",
            keyword="기초연금",
            curated={"ticket_prices": None},
            output_path=out_path,
        )
        self.assertTrue(out_path.exists())
        with Image.open(out_path) as img:
            self.assertEqual(img.size, (1200, 675))
            self.assertEqual(img.format, "JPEG")

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

    def test_render_hybrid_poster_network_failure_falls_back_to_toss(self):
        out_path = Path(tempfile.gettempdir()) / "test_fallback_output.jpg"
        with patch("urllib.request.urlopen", side_effect=Exception("Connection refused")):
            # generate_image should catch exception and fallback to Mode 2
            res_path = self.designer.generate_image(
                title="2026 단독 콘서트 예매",
                category_name="공연/콘서트 예매",
                keyword="콘서트",
                curated={"poster_url": "https://example.com/broken_poster.jpg"},
                category_key="concert",
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
