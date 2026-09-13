import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agents.fact_validation import snapshot, build_manifest, render_content, verify_article, verify_temporal_binding
from agents.temporal_validation import extract_evidence
from agents.copywriter import CopywriterAgent
from agents.publisher import PublisherAgent

TEXT = "신청기간: 2020.09.01 ~ 2099.09.30\n지원대상: 만 65세 이상\n신청조건: 중복 수급 불가\n제외대상: 이미 지원받은 가구\n지원금액: 월 100,000원\n신청방법: 주민센터 방문"


class FactTests(unittest.TestCase):
    def setUp(self):
        self.source = snapshot("https://example.com/notice", "지원 사업 안내", TEXT, "article")
        self.manifest = build_manifest([self.source], "welfare")
        self.article = {"title": self.source["title"], "content": render_content(self.manifest), "tags": []}

    def test_snapshot_quotes_spans_and_urls(self):
        self.assertEqual(self.manifest["status"], "verified")
        for fact in self.manifest["facts"]:
            start, end = fact["span"]
            self.assertEqual(TEXT[start:end], fact["quote"])
            self.assertEqual(fact["source_url"], self.source["url"])
        self.assertEqual(verify_article(self.article, self.manifest)["status"], "verified")

    def test_changed_amount_date_eligibility_condition_venue(self):
        for before, after in [("100,000", "200,000"), ("09.30", "10.30"), ("65세", "60세"), ("수급 불가", "수급 가능"), ("주민센터 방문", "온라인 신청")]:
            with self.subTest(before=before):
                article = {**self.article, "content": self.article["content"].replace(before, after)}
                self.assertEqual(verify_article(article, self.manifest)["status"], "needs_review")

    def test_omitted_or_added_claim(self):
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(self.article["content"], "html.parser")
        soup.find(attrs={"data-fact-id": self.manifest["facts"][0]["id"]}).decompose()
        for content in [str(soup), self.article["content"] + "<p>누구나 신청 가능</p>"]:
            self.assertEqual(verify_article({**self.article, "content": content}, self.manifest)["status"], "needs_review")

    def test_forged_manifest_or_snapshot(self):
        for location in ["facts", "sources"]:
            manifest = copy.deepcopy(self.manifest)
            manifest[location][0]["value" if location == "facts" else "text"] = "허위 내용"
            self.assertEqual(verify_article(self.article, manifest)["status"], "needs_review")

    def test_unknown_source_link_title_tags(self):
        for article in [{**self.article, "content": self.article["content"].replace("https://example.com/notice", "https://example.org/fake")}, {**self.article, "title": "누구나 20만원"}, {**self.article, "tags": ["전국민"]}]:
            self.assertEqual(verify_article(article, self.manifest)["status"], "needs_review")

    def test_required_fields_and_conflicts(self):
        self.assertEqual(build_manifest([snapshot(self.source["url"], "안내", "신청기간: 2099.09.01 ~ 09.30", "article")], "welfare")["status"], "needs_review")
        conflict = snapshot("https://example.com/other", "다른 안내", TEXT.replace("65세", "60세"), "article")
        self.assertIn("conflicting_core_facts", build_manifest([self.source, conflict], "welfare")["reasons"])

    def test_period_evidence_must_match_snapshot(self):
        self.assertFalse(verify_temporal_binding({"evidence": extract_evidence(TEXT.replace("2099.09.30", "2100.09.30"), self.source["url"])}, self.manifest))

    def test_gemini_json_paths_use_same_gate(self):
        import json
        from agents.copywriter import BlogPostSchema
        writer = object.__new__(CopywriterAgent)
        writer.client = Mock()
        item = {"title": self.source["title"], "category_id": 2, "link": self.source["url"], "keyword": "지원", "fact_manifest": self.manifest, "temporal_source": {"evidence": extract_evidence(TEXT, self.source["url"])}}
        data = {**self.article, "is_valid_and_active": True}
        for response in [Mock(parsed=BlogPostSchema(**data)), Mock(parsed=None, text=json.dumps(data))]:
            writer.client.models.generate_content.return_value = response
            self.assertIsNotNone(writer.write_article(item))
        writer.client.models.generate_content.return_value = Mock(parsed=None, text=json.dumps(self.article))
        self.assertIsNone(writer.write_article(item))

    def test_markup_injection_and_escaped_evidence(self):
        self.assertEqual(verify_article({**self.article, "content": self.article["content"] + "<script>alert(1)</script>"}, self.manifest)["status"], "needs_review")
        source = snapshot(self.source["url"], "안내", TEXT + '\n문의: <img src=x onerror=alert(1)>', "article")
        self.assertNotIn("<img", render_content(build_manifest([source], "welfare")))

    def test_writer_checks_real_generated_article(self):
        writer = object.__new__(CopywriterAgent)
        writer.client = True
        writer._generate_with_gemini = Mock(return_value=copy.deepcopy(self.article))
        item = {"title": self.source["title"], "fact_manifest": self.manifest, "temporal_source": {"evidence": extract_evidence(TEXT, self.source["url"])}}
        self.assertIsNotNone(writer.write_article(item))
        writer._generate_with_gemini.return_value = {**self.article, "content": self.article["content"].replace("65세", "60세")}
        self.assertIsNone(writer.write_article(item))

    @patch("agents.publisher.subprocess.run")
    def test_publisher_rejects_tampering_before_writes(self, run):
        article = {**self.article, "content": "<p>누구나 지원</p>", "fact_manifest": self.manifest, "temporal_source": {"evidence": extract_evidence(TEXT, self.source["url"])}}
        with self.assertRaises(ValueError):
            PublisherAgent().publish(article)
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
