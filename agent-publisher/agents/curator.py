import re
import urllib.parse
import requests
from bs4 import BeautifulSoup
from googlenewsdecoder import new_decoderv1


class CuratorAgent:
    """기사 원본 링크를 디코딩하여 실제 본문을 충실히 추출하고 공식 예매처 상세 정보를 능동 수집하는 큐레이터 에이전트"""

    def __init__(self):
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
        real_url = self.decode_url(url)
        try:
            resp = requests.get(real_url, headers=self.headers, timeout=12)
            if resp.status_code == 200:
                # 한글 인코딩 안전망: ISO-8859-1 등으로 잘못 잡힌 경우 실제 인코딩(EUC-KR/CP949/UTF-8)으로 보정
                if resp.encoding and resp.encoding.lower() in ["iso-8859-1", "ascii"]:
                    resp.encoding = resp.apparent_encoding or "utf-8"

                soup = BeautifulSoup(resp.text, "html.parser")

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

    def discover_nol_ticket_info(self, query: str) -> dict | None:
        """NOL 티켓(구 인터파크)에서 공연/가수명을 실시간 검색하여 공식 상세페이지와 좌석별 가격 정보 능동 수집 (판매중 필터 적용)"""
        encoded = urllib.parse.quote(query)
        # 현재 판매중(ENTERTAINMENT_SALE_STATUS_SALE) 필터 토큰 적용
        active_sale_filter = "Iiw0JwQnH3WmtXGyJ5rdjj3dkKg0FXd382IRSpxwfSefDnXepYDTL8Fbf88Yu1xaNDouUSnvHowixDLzJK8W8b8oBZfFTgLW5uxL8G3ULvpZtka7hxVmXkMUAtZAWLYFxnpmSA7fdJ4cOuenY9A0QODtkZVxKtNV"
        search_url = f"https://nol.yanolja.com/discovery/list/search/PRODUCT_CATEGORY_ENTERTAINMENT?filter={active_sale_filter}&q={encoded}"
        try:
            resp = requests.get(search_url, headers=self.headers, timeout=10)
            if resp.status_code != 200:
                return None

            product_ids = re.findall(r"/ticket/products/(\d+)", resp.text)
            if not product_ids:
                return None

            product_id = product_ids[0]
            product_url = f"https://nol.yanolja.com/ticket/products/{product_id}"

            p_resp = requests.get(product_url, headers=self.headers, timeout=10)
            if p_resp.status_code != 200:
                return None

            html = p_resp.text
            ticket_info = {"product_url": product_url, "product_id": product_id}

            ticket_match = re.search(r"-\s*티켓:\s*([^<]+)", html)
            if ticket_match:
                ticket_info["price_str"] = ticket_match.group(1).strip()

            date_match = re.search(r"-\s*일시:\s*([^<]+)", html)
            if date_match:
                ticket_info["date_str"] = date_match.group(1).strip()

            place_match = re.search(r"-\s*장소:\s*([^<]+)", html)
            if place_match:
                ticket_info["place_str"] = place_match.group(1).strip()

            return ticket_info
        except Exception as e:
            print(f"[CuratorAgent] ⚠️ NOL 티켓 상세 가격 조회 중 오류: {e}")
            return None

    def curate(self, raw_item: dict) -> dict | None:
        """기사 본문을 실시간 추출하고, 예매처 정보를 능동 수집하여 팩트 기반 데이터 가공"""
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
        if cat_key == "concert" or any(w in title or w in kw for w in ["콘서트", "티켓", "예매", "NOL", "인터파크"]):
            known_entities = [
                "무명전설", "임영웅", "이찬원", "영탁", "나훈아", "정동원", "장민호",
                "김호중", "송가인", "양지은", "박서진", "진해성", "안성훈", "손태진",
                "아이유", "성시경", "싸이", "데이식스", "헤드윅", "지킬앤하이드"
            ]
            target_entity = None
            for cand in known_entities:
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
                print(f"[CuratorAgent] 🔍 공식 티켓 예매처(NOL 티켓)에서 '{target_entity}' 실시간 가격 및 상품 탐색...")
                ticket_data = self.discover_nol_ticket_info(target_entity)
                if ticket_data:
                    print(f"[CuratorAgent] 🎯 공식 티켓 상세 확인 완료: {ticket_data.get('product_url')} (가격: {ticket_data.get('price_str')})")
                    body += (
                        f"\n\n[🚨 공식 예매처(NOL 티켓) 실시간 연동 정보]\n"
                        f"- 공식 상품 상세페이지 URL: {ticket_data['product_url']}\n"
                        f"- 공식 좌석별 티켓 가격: {ticket_data.get('price_str', '상세페이지 참조')}\n"
                        f"- 공식 공연 일시: {ticket_data.get('date_str', '')}\n"
                        f"- 공식 공연 장소: {ticket_data.get('place_str', '')}\n"
                    )

        curated_data = {
            **raw_item,
            "link": real_url,
            "full_content": body,
            "direct_product_url": ticket_data.get("product_url") if ticket_data else None,
            "ticket_prices": ticket_data.get("price_str") if ticket_data else None,
        }
        return curated_data
