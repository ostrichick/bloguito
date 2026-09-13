import sys
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.ticket_validation import check_identity, extract_dates, extract_expectation, parse_product, select_product
from agents.curator import CuratorAgent
from agents.copywriter import CopywriterAgent


HTML = (Path(__file__).parent / "fixtures" / "nol_product.html").read_text(encoding="utf-8")
TODAY = date(2099, 9, 13)
EXPECTED = {"entity": "테스트밴드", "region": "수원", "event_dates": ["2099-12-25"], "qualifiers": ["앵콜"]}


class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.product = parse_product(HTML, "1001")

    def test_labelled_details_ignore_open_date_and_recommendations(self):
        self.assertEqual(self.product["event_dates"], ["2099-12-25"])
        self.assertEqual(self.product["place_str"], "수원컨벤션센터")
        self.assertEqual(self.product["price_str"], "R석 50,000원, S석 40,000원")
        self.assertEqual(check_identity(EXPECTED, self.product, TODAY), [])

    def test_wrong_city_first_correct_city_second(self):
        wrong = parse_product(HTML.replace("수원", "부산"), "1000")
        result = select_product(EXPECTED, [wrong, self.product], TODAY)
        self.assertEqual(result["product"]["product_id"], "1001")
        self.assertIn("region_or_venue_mismatch", result["checks"][0]["reasons"])

    def test_same_artist_different_date_is_rejected(self):
        wrong = {**self.product, "event_dates": ["2099-12-24"]}
        self.assertIn("performance_date_mismatch_or_missing", check_identity(EXPECTED, wrong, TODAY))

    def test_different_performance_is_rejected(self):
        wrong = {**self.product, "title": "2099 다른밴드 콘서트 - 수원앵콜"}
        self.assertIn("performance_name_mismatch", check_identity(EXPECTED, wrong, TODAY))

    def test_regular_show_cannot_replace_encore(self):
        wrong = {**self.product, "title": "2099 테스트밴드 연말 콘서트 - 수원"}
        self.assertIn("performance_qualifier_mismatch", check_identity(EXPECTED, wrong, TODAY))

    def test_known_venue_must_match(self):
        expected = {**EXPECTED, "venue": "수원종합운동장"}
        self.assertIn("venue_mismatch", check_identity(expected, self.product, TODAY))

    def test_named_show_subtitle_must_match_not_just_artist(self):
        expected = extract_expectation("테스트밴드", "2099 테스트밴드 '달빛' 수원 콘서트", "공연일시: 2099.12.25")
        self.assertIn("performance_subtitle_mismatch", check_identity(expected, self.product, TODAY))

    def test_missing_details_does_not_use_unrelated_dates(self):
        missing = parse_product('<h1>2099 테스트밴드 - 수원앵콜</h1><aside>2099.12.25 수원</aside>', "2")
        self.assertEqual(select_product(EXPECTED, [missing], TODAY)["status"], "needs_review")

    def test_two_matches_are_ambiguous(self):
        second = {**self.product, "product_id": "1002"}
        self.assertEqual(select_product(EXPECTED, [self.product, second], TODAY)["reason"], "multiple_matching_products")

    def test_duplicate_links_are_not_multiple_products(self):
        self.assertEqual(select_product(EXPECTED, [self.product, self.product], TODAY)["status"], "matched")

    def test_ended_performance_is_rejected(self):
        self.assertIn("performance_already_ended", check_identity(EXPECTED, self.product, date(2100, 1, 1)))

    def test_booking_day_cannot_replace_performance_day(self):
        wrong = {**self.product, "event_dates": ["2099-09-15"]}
        self.assertNotEqual(check_identity(EXPECTED, wrong, TODAY), [])


class ExpectationTests(unittest.TestCase):
    def test_article_booking_date_excluded(self):
        expected = extract_expectation("테스트밴드", "2099 테스트밴드 수원 앵콜 콘서트", "공연은 12월 25일 수원컨벤션센터에서 열린다.\n티켓 예매는 9월 15일 오픈한다.")
        self.assertEqual(expected["event_dates"], ["2099-12-25"])
        self.assertEqual(expected["region"], "수원")

    def test_title_city_wins_over_past_tour_mentions(self):
        expected = extract_expectation("테스트밴드", "2099 테스트밴드 수원 콘서트", "부산 투어를 마쳤다.\n공연일시: 2099년 12월 25일")
        self.assertEqual(expected["region"], "수원")

    def test_no_guessed_year(self):
        self.assertEqual(extract_dates("12월 25일 공연"), [])
        self.assertEqual(extract_dates("2099년 2월 30일"), [])

    def test_multiple_cities_or_dates_require_review(self):
        expected = extract_expectation("테스트밴드", "2099 테스트밴드 콘서트", "수원 공연 2099.12.25\n부산 공연 2099.12.26")
        self.assertEqual(expected["region"], "")
        self.assertEqual(expected["event_dates"], [])

    def test_keyword_not_present_in_article_is_not_identity(self):
        expected = extract_expectation("테스트밴드", "2099 다른 공연 수원", "다른 공연일시: 2099.12.25")
        self.assertEqual(expected["entity"], "")


def response(text="", status=200):
    return Mock(text=text, status_code=status, encoding="utf-8")


class NetworkAndPipelineTests(unittest.TestCase):
    def setUp(self):
        # Isolate link regressions; temporal gates are covered in test_temporal_validation.
        self.temporal_patch = patch("agents.copywriter.validate_availability", return_value={"status": "active", "expires_at": "2099-12-25"})
        self.temporal_patch.start()
        self.addCleanup(self.temporal_patch.stop)
    @patch("agents.curator.requests.get")
    def test_discovery_checks_all_candidates_not_first(self, get):
        get.side_effect = [response('<a href="/ticket/products/1000">부산</a><a href="/ticket/products/1001">수원</a>'), response(HTML.replace("수원", "부산")), response(HTML)]
        curator = CuratorAgent()
        result = curator.discover_nol_ticket_info("테스트밴드", EXPECTED)
        self.assertEqual(result["product_id"], "1001")
        self.assertEqual(get.call_count, 3)

    @patch("agents.curator.requests.get")
    def test_unreadable_candidate_prevents_unproven_uniqueness(self, get):
        get.side_effect = [response('<a href="/ticket/products/1000"></a><a href="/ticket/products/1001"></a>'), response(status=403), response(HTML)]
        curator = CuratorAgent()
        self.assertIsNone(curator.discover_nol_ticket_info("테스트밴드", EXPECTED))
        self.assertEqual(curator.last_ticket_verification["reason"], "candidate_fetch_incomplete")

    @patch("agents.curator.requests.get")
    def test_missing_identity_does_not_fetch(self, get):
        curator = CuratorAgent()
        self.assertIsNone(curator.discover_nol_ticket_info("테스트밴드"))
        get.assert_not_called()

    @patch("agents.curator.requests.get")
    def test_search_blocked_is_review_not_fallback(self, get):
        get.return_value = response(status=403)
        curator = CuratorAgent()
        self.assertIsNone(curator.discover_nol_ticket_info("테스트밴드", EXPECTED))
        self.assertEqual(curator.last_ticket_verification["reason"], "search_http_403")

    def test_needs_review_never_calls_gemini(self):
        writer = object.__new__(CopywriterAgent)
        writer._generate_with_gemini = Mock()
        self.assertIsNone(writer.write_article({"ticket_verification": {"status": "needs_review"}}))
        writer._generate_with_gemini.assert_not_called()

    def test_gemini_cannot_replace_verified_product_link(self):
        writer = object.__new__(CopywriterAgent)
        writer.client = True
        writer._generate_with_gemini = Mock(return_value={"content": '<a href="https://nol.yanolja.com/ticket/products/9999">예매</a>'})
        self.assertIsNone(writer.write_article({"title": "테스트 공연", "ticket_verification": {"status": "matched"}, "direct_product_url": "https://nol.yanolja.com/ticket/products/1001"}))

    def test_verified_link_is_preserved(self):
        writer = object.__new__(CopywriterAgent)
        writer.client = True
        article = {"content": '<a href="https://nol.yanolja.com/ticket/products/1001">예매</a>'}
        writer._generate_with_gemini = Mock(return_value=article)
        self.assertEqual(writer.write_article({"title": "테스트 공연", "temporal_source": {}, "ticket_verification": {"status": "matched"}, "direct_product_url": "https://nol.yanolja.com/ticket/products/1001"}), article)

    def test_free_article_with_paid_link_is_rejected(self):
        writer = object.__new__(CopywriterAgent)
        writer.client = True
        writer._generate_with_gemini = Mock(return_value={"content": '<a href="https://tickets.interpark.com/search?q=test">구매</a>'})
        self.assertIsNone(writer.write_article({"title": "무료 공연", "ticket_verification": {"status": "not_required_free_event"}}))

    def test_candidate_limit_does_not_silently_truncate(self):
        with patch("agents.curator.requests.get", return_value=response(''.join(f'<a href="/ticket/products/{i}"></a>' for i in range(9)))) as get:
            curator = CuratorAgent()
            self.assertIsNone(curator.discover_nol_ticket_info("테스트밴드", EXPECTED))
            self.assertEqual(curator.last_ticket_verification["reason"], "candidate_limit_exceeded")
            self.assertEqual(get.call_count, 1)

    def test_free_shipping_does_not_bypass_verification(self):
        curator = CuratorAgent()
        curator.fetch_article_content = Mock(return_value=("테스트밴드 수원 콘서트는 무료 공연이 아니다. 티켓 무료배송. " * 20, "https://example.com/news"))
        curator.discover_nol_ticket_info = Mock(return_value=None)
        curator.curate({"title": "'테스트밴드' 수원 공연", "keyword": "콘서트", "category_key": "concert", "link": "https://example.com/news"})
        curator.discover_nol_ticket_info.assert_called_once()

    def test_free_event_never_collects_ticket_product(self):
        curator = CuratorAgent()
        curator.fetch_article_content = Mock(return_value=("테스트밴드 수원 무료 공연. 관람료: 무료. " * 20, "https://example.com/news"))
        curator.discover_nol_ticket_info = Mock()
        result = curator.curate({"title": "'테스트밴드' 수원 무료 공연", "keyword": "콘서트", "category_key": "concert", "link": "https://example.com/news"})
        self.assertEqual(result["ticket_verification"]["status"], "not_required_free_event")
        self.assertIsNone(result["direct_product_url"])
        curator.discover_nol_ticket_info.assert_not_called()


if __name__ == "__main__":
    unittest.main()
