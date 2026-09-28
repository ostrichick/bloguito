# -*- coding: utf-8 -*-
"""Unit tests for Rank Math audit and diagnostic analysis engine."""
import unittest
from typing import Dict, Any


def diagnose_rank_math_post(post: Dict[str, Any]) -> Dict[str, Any]:
    """Diagnose a post's Rank Math SEO status, identify root causes, and assign optimization tier."""
    kw = (post.get("rank_math_focus_keyword") or "").strip()
    score_raw = str(post.get("rank_math_seo_score") or "").strip()
    score = int(score_raw) if score_raw.isdigit() else 0
    title = (post.get("post_title") or "").strip()
    meta_title = (post.get("rank_math_title") or "").strip()
    effective_title = meta_title or title
    desc = (post.get("rank_math_description") or "").strip()
    word_count = int(post.get("word_count") or 0)
    has_h2 = bool(post.get("has_h2", False))

    issues = []

    # 1. Focus Keyword Checks
    if not kw:
        issues.append("MISSING_FOCUS_KEYWORD")
    else:
        # Check keyword length (more than 3 words or 25 chars often fails exact match in Rank Math)
        kw_words = kw.split()
        if len(kw_words) >= 4 or len(kw) > 25:
            issues.append("KEYWORD_TOO_LONG")

        # Check title match
        if kw not in effective_title:
            issues.append("KEYWORD_NOT_IN_TITLE")

        # Check description match
        if kw not in desc:
            issues.append("KEYWORD_NOT_IN_DESC")

    # 2. Meta description checks
    if not desc or len(desc) < 30:
        issues.append("MISSING_META_DESC")

    # 3. Content structural checks
    if word_count < 450:
        issues.append("LOW_WORD_COUNT")
    if not has_h2:
        issues.append("MISSING_H2")

    # Tier Classification
    if score >= 60:
        tier = "TIER_3_STABLE"
        priority = "LOW"
    elif word_count >= 450 and has_h2:
        tier = "TIER_1_META_QUICK_WIN"
        priority = "HIGH"
    else:
        tier = "TIER_2_CONTENT_EXPANSION"
        priority = "MEDIUM"

    return {
        "id": post.get("ID"),
        "score": score,
        "is_measured": bool(score_raw.isdigit() and score > 0),
        "issues": issues,
        "tier": tier,
        "priority": priority,
    }


class TestRankMathAuditEngine(unittest.TestCase):
    def test_stable_post_tier(self):
        """Posts with score >= 60 should be classified as TIER_3_STABLE."""
        post = {
            "ID": 233,
            "post_title": "휴일에 약국이 닫았다면",
            "rank_math_focus_keyword": "휴일 약국",
            "rank_math_seo_score": "74",
            "rank_math_title": "휴일 약국 찾는 법과 24시간 편의점 안전상비의약품 11종 가격",
            "rank_math_description": "휴일 약국 및 심야 당번약국 찾는 방법과...",
            "word_count": 620,
            "has_h2": True,
        }
        res = diagnose_rank_math_post(post)
        self.assertEqual(res["tier"], "TIER_3_STABLE")
        self.assertEqual(res["priority"], "LOW")
        self.assertEqual(res["score"], 74)
        self.assertTrue(res["is_measured"])

    def test_meta_quick_win_tier(self):
        """Good content (words >= 450, has H2) but missing keyword/meta should be TIER_1_META_QUICK_WIN."""
        post = {
            "ID": 471,
            "post_title": "안심상속 원스톱서비스 신청: 사망월 말일부터 1년, 준비서류와 조회 재산",
            "rank_math_focus_keyword": "안심상속 원스톱서비스 신청기한 준비서류 조회 재산",  # too long!
            "rank_math_seo_score": "16",
            "rank_math_title": "",
            "rank_math_description": "",
            "word_count": 520,
            "has_h2": True,
        }
        res = diagnose_rank_math_post(post)
        self.assertEqual(res["tier"], "TIER_1_META_QUICK_WIN")
        self.assertEqual(res["priority"], "HIGH")
        self.assertIn("KEYWORD_TOO_LONG", res["issues"])
        self.assertIn("MISSING_META_DESC", res["issues"])

    def test_unmeasured_post_missing_keyword(self):
        """Unmeasured post with no keyword should be diagnosed correctly."""
        post = {
            "ID": 393,
            "post_title": "인천공항 출국장 대기시간 확인: T1, T2 예상 혼잡도 보는 법",
            "rank_math_focus_keyword": "",
            "rank_math_seo_score": "",
            "rank_math_title": "",
            "rank_math_description": "",
            "word_count": 350,
            "has_h2": True,
        }
        res = diagnose_rank_math_post(post)
        self.assertEqual(res["score"], 0)
        self.assertFalse(res["is_measured"])
        self.assertIn("MISSING_FOCUS_KEYWORD", res["issues"])
        self.assertEqual(res["tier"], "TIER_2_CONTENT_EXPANSION")


if __name__ == "__main__":
    unittest.main()
