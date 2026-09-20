"""Rendered thumbnail text must not invent claims from curator hints or keywords."""

import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PIL import Image, ImageDraw

from agents.designer import DesignerAgent, split_title


class DesignerSafetyTests(unittest.TestCase):
    def setUp(self):
        self.designer = DesignerAgent()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

    def capture_text(self, render):
        drawn = []
        original = ImageDraw.ImageDraw.text

        def record(draw, xy, text, *args, **kwargs):
            drawn.append(str(text).strip())
            return original(draw, xy, text, *args, **kwargs)

        with patch.object(ImageDraw.ImageDraw, "text", new=record):
            render()
        return drawn

    def assert_only_article_labels(self, drawn, title, category):
        allowed = set(split_title(title)) | {category, "생활정보 24"}
        self.assertTrue(drawn)
        self.assertTrue(set(drawn) <= allowed, f"Unexpected unsupported image text: {drawn!r}")
        self.assertTrue(set(split_title(title)) <= set(drawn))

    def test_policy_subjects_do_not_generate_claims_or_trust_curated_fields(self):
        cases = [
            ("2026 추석 고속도로 통행료 적용 조건", "생활·건강", "life-health"),
            ("정부 미환급금 신청 방법", "정부 복지/지원금", "welfare"),
            ("재산세 분할납부 대상", "생활 세금/절세", "tax"),
            ("기초연금 노인 수급 자격", "정부 복지/지원금", "welfare"),
            ("콘서트 예매 정보", "공연/콘서트 예매", "concert"),
        ]
        curated = {
            "title": "검토되지 않은 별도 제목",
            "callout": "국세청 공식 인증 완료",
            "stat_text": "전 국민 100% 면제 및 330만원 확정 지급",
            "bullets": ["신청 즉시 2~3일 내 입금", "무조건 환급", "조건 없이 신청"],
            "ticket_prices": "전 좌석 0원",
            "temporal_verification": {"expires_at": "2026-12-25"},
            "poster_url": "https://example.com/unreviewed-poster.jpg",
            "article_image_url": "https://example.com/unreviewed-article.jpg",
            "reviewed_poster_url": "https://example.com/self-asserted-review.jpg",
        }
        for title, category, key in cases:
            with self.subTest(title=title):
                self.assertEqual(self.designer.select_mode(key, curated, title, "100% 면제"), 2)
                with patch("urllib.request.urlopen", side_effect=AssertionError("Unreviewed assets must not be fetched")):
                    drawn = self.capture_text(
                        lambda: self.designer.generate_image(
                            title, category, "100% 면제", curated=curated, category_key=key
                        )
                    )
                self.assert_only_article_labels(drawn, title, category)

    @staticmethod
    def mock_poster_response():
        buf = io.BytesIO()
        Image.new("RGB", (120, 180), color=(40, 70, 100)).save(buf, format="JPEG")
        response = MagicMock()
        response.read.return_value = buf.getvalue()
        response.__enter__.return_value = response
        return response

    def test_hybrid_uses_reviewed_poster_without_unsourced_overlays(self):
        title = "공연 일정 안내"
        category = "공연/콘서트 예매"
        with patch("urllib.request.urlopen", return_value=self.mock_poster_response()) as urlopen:
            drawn = self.capture_text(
                lambda: self.designer.generate_image(
                    title, category, "예매", curated={
                        "callout": "공식 확인", "ticket_prices": "154,000원",
                        "temporal_verification": {"expires_at": "2026-12-25"},
                    }, category_key="concert", reviewed_poster_url="https://example.com/reviewed.jpg"
                )
            )
        self.assertEqual(urlopen.call_count, 1)
        self.assertEqual(set(drawn), {title, "생활정보 24"})

    def test_clean_poster_has_no_fabricated_source_watermark(self):
        path = Path(self.temp_dir.name) / "clean.jpg"
        with patch("urllib.request.urlopen", return_value=self.mock_poster_response()):
            drawn = self.capture_text(
                lambda: self.designer._render_clean_poster(
                    "https://example.com/reviewed.jpg", "공연 제목", "공연/콘서트 예매", path
                )
            )
        self.assertEqual(drawn, [])
        with Image.open(path) as image:
            self.assertEqual(image.size, (1200, 675))

    def test_stock_badge_does_not_claim_official_status(self):
        title = "실내 습도 관리 방법"
        category = "생활·건강"
        path = Path(self.temp_dir.name) / "stock.jpg"
        with patch("urllib.request.urlopen", return_value=self.mock_poster_response()):
            drawn = self.capture_text(
                lambda: self.designer._render_keyword_stock("건강", category, title, path)
            )
        self.assert_only_article_labels(drawn, title, category)

    def test_reviewed_poster_network_failure_falls_back_without_curator_claims(self):
        title = "콘서트 티켓 예매"
        category = "공연/콘서트 예매"
        with patch("urllib.request.urlopen", side_effect=OSError("offline")):
            drawn = self.capture_text(
                lambda: self.designer.generate_image(
                    title, category, "예매", category_key="concert",
                    curated={"stat_text": "100% 확정", "callout": "공식 승인"},
                    reviewed_poster_url="https://example.com/reviewed.jpg"
                )
            )
        self.assert_only_article_labels(drawn, title, category)


if __name__ == "__main__":
    unittest.main()
