import hashlib
import json
import unittest
from pathlib import Path
from PIL import Image, ImageFont

from agents.designer import (
    FEATURED_IMAGE_POLICY,
    _font_has_hangul,
    _load_display_font,
    get_available_display_font_paths,
)


class DesignerFontRotationTests(unittest.TestCase):
    def setUp(self):
        self.policy_path = Path(__file__).resolve().parents[1] / "editorial_policy.json"
        self.assertTrue(self.policy_path.exists(), "editorial_policy.json must exist")
        with open(self.policy_path, "r", encoding="utf-8") as f:
            self.policy_data = json.load(f)

    def test_editorial_policy_prohibits_generic_gothic_and_requires_rotation(self):
        """이미지 생성 정책에 기본 고딕 금지 및 다중 폰트 순환 로테이션이 명시되어 있는지 검증"""
        feat_policy = self.policy_data.get("featured_image_policy", {})
        text_policy = feat_policy.get("text", {})

        # 기본 고딕 금지 플래그 검증
        self.assertTrue(
            text_policy.get("prohibit_generic_gothic_for_headline"),
            "Policy must have prohibit_generic_gothic_for_headline set to True",
        )
        self.assertTrue(
            text_policy.get("font_rotation_required"),
            "Policy must have font_rotation_required set to True",
        )
        self.assertTrue(
            text_policy.get("single_font_monopoly_prohibited"),
            "Policy must have single_font_monopoly_prohibited set to True",
        )
        self.assertEqual(
            text_policy.get("rotation_strategy"),
            "diverse_distinctive_pool_round_robin",
        )
        self.assertTrue(
            text_policy.get("prohibit_middle_dot_for_enumeration"),
            "Policy must forbid middle dot '·' for enumerations",
        )
        self.assertTrue(
            text_policy.get("mandate_comma_for_enumeration"),
            "Policy must mandate commas ',' for enumerations",
        )
        self.assertTrue(
            text_policy.get("prohibit_bullet_characters"),
            "Policy must forbid bullet characters that cause tofu boxes",
        )
        self.assertEqual(text_policy.get("primary_max_lines"), 2)
        self.assertEqual(text_policy.get("primary_min_font_size_px"), 64)
        self.assertGreaterEqual(text_policy.get("primary_short_font_size_px", 0), 84)
        self.assertTrue(
            text_policy.get("prefer_copy_shortening_over_font_reduction"),
            "Policy must shorten cover copy before shrinking the headline",
        )
        self.assertTrue(
            text_policy.get("headline_must_be_visually_dominant"),
            "Policy must require the headline to remain visually dominant",
        )

        prohibited = [p.lower() for p in text_policy.get("prohibited_headline_fonts", [])]
        for prohibited_name in ["malgun gothic", "맑은 고딕", "nanumgothic", "나눔고딕", "noto sans", "본고딕"]:
            self.assertIn(prohibited_name, prohibited)

    def test_available_display_fonts_pool_has_multiple_distinct_fonts(self):
        """가용 디스플레이 폰트 풀에 3종 이상의 서로 다른 유효한 한글 디스플레이 폰트가 존재하는지 검증"""
        font_paths = get_available_display_font_paths()
        self.assertGreaterEqual(
            len(font_paths),
            3,
            f"Available display fonts must have at least 3 fonts, got: {font_paths}",
        )

        # 모든 가용 폰트는 실제 파일이 존재하고 한글을 렌더링할 수 있어야 함
        for path in font_paths:
            self.assertTrue(path.exists(), f"Font path does not exist: {path}")
            font = ImageFont.truetype(str(path), 32)
            self.assertTrue(
                _font_has_hangul(font),
                f"Font {path} must support Hangul glyphs",
            )

        # 금지된 기본 고딕 폰트가 풀에 포함되지 않았는지 철저 검증
        prohibited_keywords = ["malgun", "nanumgothic", "notosans", "dotum", "gulim", "arial"]
        for path in font_paths:
            name_lower = path.name.lower()
            for kw in prohibited_keywords:
                self.assertNotIn(
                    kw,
                    name_lower,
                    f"Prohibited gothic font {kw} found in display pool: {path}",
                )

    def test_display_font_rotates_across_different_posts(self):
        """서로 다른 포스트 제목/시드에 대해 동일한 폰트로 고정되지 않고 순환 교차 선택되는지 검증"""
        test_titles = [
            "2027 최저임금 시급 계산법",
            "청년도약계좌 조건 신청 총정리",
            "국민연금 조기수령 감액율 비교",
            "임플란트 건강보험 적용 기준",
            "전기차 충전요금 할인 혜택 모음",
        ]

        loaded_font_names = []
        for title in test_titles:
            font = _load_display_font(size=48, seed_key=title)
            # PIL Font 객체에서 실제 로드된 폰트 패밀리명 또는 파일 경로 확인
            loaded_font_names.append(font.font.family)

        unique_fonts = set(loaded_font_names)
        self.assertGreaterEqual(
            len(unique_fonts),
            2,
            f"Across 5 different titles, at least 2 or more distinct fonts must be rotated. Got: {loaded_font_names}",
        )


if __name__ == "__main__":
    unittest.main()
