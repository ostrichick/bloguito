"""Rendered thumbnail text must not invent claims from curator hints or keywords."""

import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PIL import Image, ImageDraw

from agents.designer import DesignerAgent, derive_cover_copy, split_title


class DesignerSafetyTests(unittest.TestCase):
    def setUp(self):
        self.designer = DesignerAgent(scheduler_context=True)
        self.designer.client = None
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.cover_root = self.enterContext(
            patch("agents.designer.generated_cover_root", return_value=Path(self.temp_dir.name))
        )

    def test_generate_image_requires_scheduler_context(self):
        manual = DesignerAgent()
        with self.assertRaisesRegex(ValueError, "scheduler_only"):
            manual.generate_image("수동 글", "행정/생활서비스", "수동")

    def capture_text(self, render):
        drawn = []
        original = ImageDraw.ImageDraw.text

        def record(draw, xy, text, *args, **kwargs):
            drawn.append(str(text).strip())
            return original(draw, xy, text, *args, **kwargs)

        with patch.object(ImageDraw.ImageDraw, "text", new=record):
            render()
        return drawn

    def assert_only_reviewed_cover_copy(self, drawn, title, keyword):
        primary, secondary = derive_cover_copy(title, keyword)
        allowed = set(split_title(primary, max_first_line=min(16, 22)))
        if secondary:
            allowed.add(secondary)
        self.assertTrue(drawn)
        self.assertTrue(set(drawn) <= allowed, f"Unexpected unsupported image text: {drawn!r}")
        self.assertNotIn(keyword, drawn if keyword not in title else [])

    def test_policy_subjects_do_not_generate_claims_or_trust_curated_fields(self):
        cases = [
            ("2026 추석 고속도로 통행료 적용 조건", "교통/자동차", "transport"),
            ("정부 미환급금 신청 방법", "금융/경제", "finance"),
            ("재산세 분할납부 대상", "세금/절세", "tax"),
            ("기초연금 노인 수급 자격", "복지/지원금", "welfare"),
            ("콘서트 예매 정보", "공연/콘서트", "concert"),
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
                self.assertEqual(self.designer.select_mode(key, curated, title, "100% 면제"), 5)
                with patch("urllib.request.urlopen", side_effect=AssertionError("Unreviewed assets must not be fetched")), \
                     patch.object(self.designer, "_generated_scene", return_value=Image.new("RGB", (1200, 675), "white")), \
                     patch.object(self.designer, "_vision_review_cover", return_value=(True, [])):
                    try:
                        drawn = self.capture_text(
                            lambda: self.designer.generate_image(
                                title, category, "100% 면제", curated=curated, category_key=key
                            )
                        )
                    except RuntimeError as exc:
                        # A title that cannot satisfy the fixed safe text plan must
                        # fail closed rather than fall back to unreviewed copy.
                        self.assertIn("featured_image_generation_failed_no_publishable_fallback", str(exc))
                        continue
                self.assert_only_reviewed_cover_copy(drawn, title, "100% 면제")
                self.assertFalse(any("330만원" in text or "공식 인증" in text for text in drawn))

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
        category = "공연/콘서트"
        self.designer.client = MagicMock()
        self.designer.client.models.generate_content.return_value = MagicMock(
            text='{"pass": true, "issues": []}'
        )
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
        self.assertEqual(drawn, [])

    def test_editorial_fallback_does_not_claim_official_status(self):
        title = "실내 습도 관리 방법"
        path = Path(self.temp_dir.name) / "fallback.jpg"
        primary, secondary = derive_cover_copy(title, "건강")
        with self.assertRaisesRegex(RuntimeError, "featured_image_generation_failed_no_publishable_fallback"):
            self.designer._render_minimal_fallback(primary, secondary, "life_service", path)
        self.assertFalse(path.exists())

    def test_reviewed_poster_network_failure_falls_back_without_curator_claims(self):
        title = "콘서트 티켓 예매"
        category = "공연/콘서트"
        with patch("urllib.request.urlopen", side_effect=OSError("offline")), \
             patch.object(self.designer, "_generated_scene", return_value=Image.new("RGB", (1200, 675), "white")), \
             patch.object(self.designer, "_vision_review_cover", return_value=(True, [])):
            drawn = self.capture_text(
                lambda: self.designer.generate_image(
                    title, category, "예매", category_key="concert",
                    curated={"stat_text": "100% 확정", "callout": "공식 승인"},
                    reviewed_poster_url="https://example.com/reviewed.jpg"
                )
            )
        self.assert_only_reviewed_cover_copy(drawn, title, "예매")

    def test_official_poster_identity_review_failure_falls_back_to_editorial_cover(self):
        title = "테스트가수 서울 콘서트 예매"
        with patch("urllib.request.urlopen", return_value=self.mock_poster_response()), \
             patch.object(self.designer, "_generated_scene", return_value=Image.new("RGB", (1200, 675), "white")), \
             patch.object(
                 self.designer,
                 "_vision_review_cover",
                 side_effect=[
                     (False, ["generic vendor preview or artist mismatch"]),
                     (True, []),
                 ],
             ):
            drawn = self.capture_text(
                lambda: self.designer.generate_image(
                    title,
                    "공연/콘서트",
                    "테스트가수 서울 콘서트",
                    curated={},
                    category_key="concert",
                    reviewed_poster_url="https://example.com/official-candidate.jpg",
                )
            )
        self.assertTrue(drawn)
        self.assertFalse(any("generic vendor" in text for text in drawn))


if __name__ == "__main__":
    unittest.main()
