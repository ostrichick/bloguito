import re
import urllib.parse
import requests
from bs4 import BeautifulSoup
from googlenewsdecoder import new_decoderv1
from agents.ticket_validation import extract_expectation, parse_product, select_product
from agents.temporal_validation import extract_evidence, validate_availability
from agents.fact_validation import snapshot, build_manifest
from config import KNOWN_ENTITIES, NOL_ACTIVE_SALE_FILTER_TOKEN


class CuratorAgent:
    """기사 원본 링크를 디코딩하여 실제 본문을 충실히 추출하고 공식 예매처 상세 정보를 능동 수집하는 큐레이터 에이전트"""

    def __init__(self):
        self.last_ticket_verification = {"status": "not_checked"}
        self.last_article_image_url = None
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        }

    def decode_url(self, google_url: str) -> str:
        """구글 뉴스 암호화 링크를 언론사 실제 원문 URL로 디코딩"""
        try:
            res = new_decoderv1(google_url)
            real_url = res.get("decoded_url") if isinstance(res, dict) else res
            if real_url and real_url.startswith("http"):
                return real_url
        except Exception as e:
            print(f"[CuratorAgent] URL 디코딩 실패: {e}")
        return google_url

    def fetch_article_content(self, url: str) -> tuple[str, str]:
        """언론사 실제 원문 웹페이지에서 순수 기사 본문 텍스트 추출 (한글 인코딩 안전망 적용)"""
        # This agent processes multiple items. An image from an earlier article
        # must never become the thumbnail of a later article without og:image.
        self.last_article_image_url = None
        real_url = self.decode_url(url)
        try:
            resp = requests.get(real_url, headers=self.headers, timeout=12)
            if resp.status_code == 200:
                # 한글 인코딩 안전망: ISO-8859-1 등으로 잘못 잡힌 경우 실제 인코딩(EUC-KR/CP949/UTF-8)으로 보정
                if resp.encoding and resp.encoding.lower() in ["iso-8859-1", "ascii"]:
                    resp.encoding = resp.apparent_encoding or "utf-8"

                soup = BeautifulSoup(resp.text, "html.parser")

                og_img = soup.find("meta", property="og:image") or soup.find("meta", {"name": "twitter:image"})
                if og_img and og_img.get("content"):
                    img_src = og_img.get("content").strip()
                    if img_src.startswith("http"):
                        self.last_article_image_url = img_src

                for s in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
                    s.decompose()

                paragraphs = soup.find_all("p")
                text = " ".join([p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 20])
                if len(text) > 150:
                    return text[:4000], real_url

                # fallback: 본문 텍스트 라인 취합
                all_text = soup.get_text()
                lines = [line.strip() for line in all_text.splitlines() if len(line.strip()) > 30]
                text = " ".join(lines)
                if len(text) > 150:
                    return text[:4000], real_url
        except Exception as e:
            print(f"[CuratorAgent] ⚠️ 원문 수집 실패 ({real_url}): {e}")

        return "", real_url

    def discover_nol_ticket_info(self, query: str, expected: dict | None = None) -> dict | None:
        """Select a unique verified product, never the first search hit."""
        self.last_ticket_verification = {"status": "needs_review", "reason": "article_identity_incomplete_or_ambiguous"}
        if not expected or not expected.get("entity") or not expected.get("region") or len(expected.get("event_dates", [])) != 1:
            return None
        encoded = urllib.parse.quote(query)
        search_url = f"https://nol.yanolja.com/discovery/list/search/PRODUCT_CATEGORY_ENTERTAINMENT?filter={NOL_ACTIVE_SALE_FILTER_TOKEN}&q={encoded}"
        try:
            resp = requests.get(search_url, headers=self.headers, timeout=10)
            if resp.status_code != 200:
                self.last_ticket_verification["reason"] = f"search_http_{resp.status_code}"
                return None

            product_ids = list(dict.fromkeys(re.findall(r"/ticket/products/(\d+)", resp.text)))
            if not product_ids:
                self.last_ticket_verification["reason"] = "search_has_no_product_links"
                return None
            if len(product_ids) > 8:
                self.last_ticket_verification["reason"] = "candidate_limit_exceeded"
                return None
            products = []
            failed = []
            for product_id in product_ids:
                url = f"https://nol.yanolja.com/ticket/products/{product_id}"
                try:
                    p_resp = requests.get(url, headers=self.headers, timeout=10, allow_redirects=False)
                    if p_resp.status_code != 200:
                        failed.append({"product_url": url, "reasons": [f"product_http_{p_resp.status_code}"]})
                        continue
                    if p_resp.encoding and p_resp.encoding.lower() in ["iso-8859-1", "ascii"]:
                        p_resp.encoding = p_resp.apparent_encoding or "utf-8"
                    products.append(parse_product(p_resp.text, product_id))
                except requests.RequestException:
                    failed.append({"product_url": url, "reasons": ["product_fetch_failed"]})
            result = select_product(expected, products)
            result["checks"].extend(failed)
            # An unreadable candidate might be a second match; uniqueness is unproven.
            if failed:
                result.update(status="needs_review", reason="candidate_fetch_incomplete", product=None)
            self.last_ticket_verification = result
            return result["product"]
        except Exception as e:
            self.last_ticket_verification["reason"] = "search_or_parse_failed"
            print(f"[CuratorAgent] ⚠️ NOL 티켓 상세 가격 조회 중 오류: {e}")
            return None

    def curate(self, raw_item: dict) -> dict | None:
        """기사 본문을 실시간 추출하고, 예매처 정보를 능동 수집하여 팩트 기반 데이터 가공"""
        if raw_item.get('editorial_direct'):
            from agents.editorial import topic_reasons
            brief = raw_item.get('search_brief', {})
            if topic_reasons(brief) or brief.get('content_type') != 'evergreen':
                return None
            # The shared writer fetches each reviewed official URL itself.
            return {**raw_item, 'ticket_verification': {'status': 'not_applicable'}}
        print(f"[CuratorAgent] 📋 원문 기사 디코딩 및 팩트 추출: {raw_item['title']}")

        body, real_url = self.fetch_article_content(raw_item["link"])
        if not body or len(body.strip()) < 150:
            print(f"[CuratorAgent] ❌ 기사 원문 추출 실패 (본문 150자 미만) -> 허위 날조 방지를 위해 폐기")
            return None

        print(f"[CuratorAgent] ✅ 원문 팩트 확보 완료 ({len(body)}자 | 원문 URL: {real_url})")

        # 콘서트/공연 카테고리이거나 티켓팅 관련 소식인 경우 공식 예매처 실시간 능동 수집
        cat_key = raw_item.get("category_key", "")
        title = raw_item.get("title", "")
        kw = raw_item.get("keyword", "")

        ticket_data = None
        fact_sources = [snapshot(real_url, title, body, "article")]
        temporal_evidence = extract_evidence(body, real_url)
        self.last_ticket_verification = {"status": "not_applicable"}
        if cat_key == "concert" or any(w in title or w in kw for w in ["콘서트", "티켓", "예매", "NOL", "인터파크"]):
            self.last_ticket_verification = {"status": "needs_review", "reason": "article_identity_incomplete_or_ambiguous"}
            target_entity = None
            for cand in KNOWN_ENTITIES:
                if cand in title or cand in kw:
                    target_entity = cand
                    break

            if not target_entity:
                # 대괄호 안의 고유명사 우선 검토
                bracketed = re.findall(r"[\[【]([^\]】]+)[\]】]", title)
                if bracketed:
                    cand = re.sub(r"단독|공지|속보|종합|포토|현장|종합", "", bracketed[0]).strip()
                    if len(cand) >= 2:
                        target_entity = cand

            if not target_entity:
                quoted = re.findall(r"['\"‘“]([^'\"’”]+)['\"’”]", title)
                if quoted:
                    target_entity = quoted[0].strip()

            if not target_entity:
                clean_kw = re.sub(r"202\d|콘서트|예매|티켓팅|신청|자격|방법|일정|하반기|연말|투어|앵콜|오픈|전국투어|단독", "", kw).strip()
                target_entity = clean_kw if len(clean_kw) >= 2 else kw

            if target_entity:
                expected = extract_expectation(target_entity, title, body)
                is_free = re.search(r"(?:관람료|입장료|전석)\s*[:：]?\s*무료(?!\s*(?:가\s*)?(?:아니|아닌|아님|아닙))", body)
                if is_free:
                    self.last_ticket_verification = {"status": "not_required_free_event"}
                else:
                    print(f"[CuratorAgent] 🔍 NOL 티켓 '{target_entity}' 공연명·지역·공연일 대조: {expected}")
                    ticket_data = self.discover_nol_ticket_info(target_entity, expected)
                    if not ticket_data:
                        print(f"[CuratorAgent] ⏸ 검토 필요: {self.last_ticket_verification}")
                if ticket_data:
                    if ticket_data.get("fact_source"):
                        fact_sources.append(ticket_data["fact_source"])
                    temporal_evidence.extend(ticket_data.get("temporal_evidence", []))
                    print(f"[CuratorAgent] 🎯 공식 티켓 상세 확인 완료: {ticket_data.get('product_url')} (가격: {ticket_data.get('price_str')})")
                    body += (
                        f"\n\n[🚨 공식 예매처(NOL 티켓) 실시간 연동 정보]\n"
                        f"- 공식 상품 상세페이지 URL: {ticket_data['product_url']}\n"
                        f"- 공식 좌석별 티켓 가격: {ticket_data.get('price_str', '상세페이지 참조')}\n"
                        f"- 공식 공연 일시: {ticket_data.get('date_str', '')}\n"
                        f"- 공식 공연 장소: {ticket_data.get('place_str', '')}\n"
                    )

        poster_url = None
        if ticket_data and ticket_data.get("poster_url"):
            poster_url = ticket_data["poster_url"]
        elif self.last_article_image_url:
            poster_url = self.last_article_image_url

        curated_data = {
            **raw_item,
            "link": real_url,
            "full_content": body,
            "direct_product_url": ticket_data.get("product_url") if ticket_data else None,
            "ticket_prices": ticket_data.get("price_str") if ticket_data else None,
            "poster_url": poster_url,
            "article_image_url": self.last_article_image_url,
            "ticket_verification": self.last_ticket_verification,
            "temporal_source": {"evidence": temporal_evidence, "requires_sale": self.last_ticket_verification.get("status") == "matched", "sale_source_url": ticket_data.get("product_url") if ticket_data else None},
        }
        curated_data["temporal_verification"] = validate_availability(curated_data["temporal_source"])
        curated_data["fact_manifest"] = build_manifest(fact_sources, cat_key)
        return curated_data
