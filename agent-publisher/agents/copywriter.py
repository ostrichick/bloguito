import json
import re
import urllib.parse
from datetime import date, datetime
from pydantic import BaseModel, Field
from bs4 import BeautifulSoup
from config import GEMINI_API_KEY, POSTS_INDEX_FILE
from agents.temporal_validation import validate_availability
from agents.fact_validation import render_content, verify_article, verify_temporal_binding


class BlogPostSchema(BaseModel):
    is_valid_and_active: bool = Field(
        description="이 기사/공고에 언급된 주요 일정이나 혜택이 오늘(현재 시점) 이후에도 여전히 유효하고 참여/신청/예매 가능한지 여부. 만약 모든 일정이 이미 종료된 과거 일정이면 false로 설정"
    )
    rejection_reason: str = Field(
        default="",
        description="is_valid_and_active가 false인 경우, 거부 사유 (예: '2026년 4월에 이미 종료된 콘서트임', '신청 마감일이 5월이었음')"
    )
    title: str = Field(description="제공된 출처 제목과 정확히 동일한 제목")
    content: str = Field(
        description="제공된 검증 HTML의 구조·텍스트·출처 링크를 그대로 유지한 본문"
    )
    tags: list[str] = Field(description="빈 배열. 근거 없는 태그를 추가하지 않음")


class CopywriterAgent:
    """수집된 팩트 데이터를 바탕으로 최고 품질의 생활 정보 블로그 글을 집필하는 전문 에디터 에이전트"""

    def __init__(self):
        self.client = None
        if GEMINI_API_KEY:
            try:
                from google import genai
                self.client = genai.Client(api_key=GEMINI_API_KEY)
            except Exception as e:
                print(f"[CopywriterAgent] ⚠️ Gemini 클라이언트 초기화 실패: {e}")

    def _build_targeted_deep_links(self, item: dict) -> dict:
        """키워드/제목에서 핵심 고유명사(가수명, 공연명, 지원금명)를 추출하여 완성형 타겟 딥링크 맵 생성"""
        title = item.get("title", "")
        kw = item.get("keyword", "")

        entity = ""
        # 1. 잘 알려진 주요 트로트/대형 가수 우선 매칭
        known_singers = [
            "무명전설", "임영웅", "이찬원", "영탁", "나훈아", "정동원", "장민호",
            "김호중", "송가인", "양지은", "박서진", "진해성", "안성훈", "손태진",
            "아이유", "성시경", "싸이", "데이식스", "헤드윅", "지킬앤하이드"
        ]
        for singer in known_singers:
            if singer in title or singer in kw:
                entity = singer
                break

        if not entity:
            quoted = re.findall(r"['\"‘“]([^'\"’”]+)['\"’”]", title)
            if quoted:
                entity = quoted[0].strip()

        if not entity:
            clean_kw = re.sub(
                r"202\d|콘서트|예매|티켓팅|신청|자격|방법|일정|하반기|연말|투어|앵콜|가을|겨울|총정리|안내",
                "",
                kw,
            ).strip()
            entity = clean_kw if len(clean_kw) >= 2 else kw

        encoded = urllib.parse.quote(entity)
        # NOL 티켓 판매중 필터 토큰 적용 (마감/종료 공연 배제, 실구매 가능 콘서트만 노출)
        active_sale_filter = "Iiw0JwQnH3WmtXGyJ5rdjj3dkKg0FXd382IRSpxwfSefDnXepYDTL8Fbf88Yu1xaNDouUSnvHowixDLzJK8W8b8oBZfFTgLW5uxL8G3ULvpZtka7hxVmXkMUAtZAWLYFxnpmSA7fdJ4cOuenY9A0QODtkZVxKtNV"
        return {
            "entity": entity,
            "nol_search": f"https://nol.yanolja.com/discovery/list/search/PRODUCT_CATEGORY_ENTERTAINMENT?filter={active_sale_filter}&q={encoded}",
            "interpark_search": f"https://tickets.interpark.com/search?q={encoded}",
            "yes24_search": f"http://ticket.yes24.com/Search/SearchResult.aspx?SearchText={encoded}",
            "gov24_search": f"https://www.gov.kr/portal/service/serviceExSearch?searchTotalQ={encoded}",
        }

    def _inject_internal_links(self, content: str, current_cat_id: int, current_title: str, reference_date: date = None) -> str:
        """기존 발행된 공개 글(Interlinking) 중 유효한 글만 본문 하단에 자동 삽입하여 체류시간 및 SEO 극대화"""
        if not POSTS_INDEX_FILE.exists():
            return content

        try:
            with open(POSTS_INDEX_FILE, "r", encoding="utf-8") as f:
                posts = json.load(f)
        except Exception:
            return content

        today = reference_date or date.today()

        # 1. 유효성 필터링: URL 필수, 현재 글 제외, 초안 제외, 마감글/만료글 제외
        candidates = []
        for p in posts:
            if not p.get("url") or p.get("title") == current_title:
                continue
            # 초안(draft) 배제
            if p.get("status") == "draft":
                continue
            # 명시적 마감 플래그 배제
            if p.get("is_closed") is True:
                continue
            # 만료일(공연일/접수마감일) 비교 배제
            exp_str = p.get("expires_at")
            if exp_str:
                try:
                    exp_date = datetime.strptime(str(exp_str)[:10], "%Y-%m-%d").date()
                    if exp_date < today:
                        continue
                except Exception:
                    pass
            candidates.append(p)

        if not candidates:
            return content

        same_cat = [p for p in candidates if p.get("category_id") == current_cat_id]
        diff_cat = [p for p in candidates if p.get("category_id") != current_cat_id]

        selected = same_cat[:2]
        if len(selected) < 2:
            selected += diff_cat[:(2 - len(selected))]

        if not selected:
            return content

        items_html = "".join([
            f'<li style="margin-bottom: 12px;"><a href="{item["url"]}" target="_blank" rel="noopener noreferrer" style="color: #2563eb; text-decoration: none; font-weight: bold; font-size: 1.05em;">👉 [{item.get("category_name", "생활정보")}] {item["title"]} (새창)</a></li>'
            for item in selected
        ])

        interlink_box = f"""
<div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-left: 5px solid #2563eb; border-radius: 8px; padding: 20px; margin: 35px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.04);">
  <h3 style="margin-top: 0; color: #1e293b; font-size: 1.2em; display: flex; align-items: center;">🔗 함께 보면 유익한 생활 정보 추천</h3>
  <ul style="margin-bottom: 0; padding-left: 20px; line-height: 1.8;">
    {items_html}
  </ul>
</div>
"""
        return content + interlink_box

    def write_article(self, curated_item: dict) -> dict | None:
        if curated_item.get("ticket_verification", {}).get("status") == "needs_review":
            print("[CopywriterAgent] ⏸ 공연 상품 일치 검증이 완료되지 않아 집필·발행을 보류합니다.")
            return None
        print(f"[CopywriterAgent] ✍️ 인포머티브 딥다이브 원고 집필 및 시점 검증 시작: {curated_item['title']}")
        temporal = validate_availability(curated_item.get("temporal_source", {}))
        if temporal["status"] != "active":
            print(f"[CopywriterAgent] ⏸ 기간·상태 검증 보류: {temporal['reasons']}")
            return None
        manifest = curated_item.get("fact_manifest")
        if not manifest or manifest.get("status") != "verified":
            print("[CopywriterAgent] ⏸ 핵심 사실·출처 구조화 미완료로 집필을 보류합니다.")
            return None
        if not verify_temporal_binding(curated_item.get("temporal_source", {}), manifest):
            print("[CopywriterAgent] ⏸ 기간 검사 근거가 원문 기록과 일치하지 않습니다.")
            return None
        if self.client:
            article = self._generate_with_gemini(curated_item)
            if not article:
                return None
            facts = verify_article(article, manifest)
            if facts["status"] != "verified":
                print(f"[CopywriterAgent] ⏸ 원고·근거 불일치: {facts['reasons']}")
                return None
            # Publish only the escaped canonical markup, never model-supplied attributes.
            article["content"] = render_content(manifest)
            article["fact_manifest"] = manifest
            article["fact_verification"] = facts
            verification = curated_item.get("ticket_verification", {})
            links = [urllib.parse.urlparse(a.get("href", "")) for a in BeautifulSoup(article["content"], "html.parser").find_all("a")]
            if verification.get("status") == "not_required_free_event":
                if any(link.hostname in {"nol.yanolja.com", "tickets.interpark.com", "ticket.yes24.com", "www.ticketlink.co.kr"} for link in links):
                    print("[CopywriterAgent] ⏸ 무료 행사 원고에 티켓 판매처 링크가 있어 발행을 보류합니다.")
                    return None
            if verification.get("status") == "matched":
                target = urllib.parse.urlparse(curated_item["direct_product_url"])
                product_links = [link for link in links if link.hostname == target.hostname and link.path.startswith("/ticket/products/")]
                if not product_links or any(link.path != target.path or link.scheme != "https" for link in product_links):
                    print("[CopywriterAgent] ⏸ 원고의 상품 링크가 검증된 공연 상세페이지와 달라 발행을 보류합니다.")
                    return None
            article["temporal_source"] = curated_item["temporal_source"]
            article["temporal_verification"] = temporal
            article["expires_at"] = temporal["expires_at"]
            return article
        else:
            print("[CopywriterAgent] ❌ Gemini 클라이언트가 없어 팩트 검증이 불가하므로 발행을 중단합니다.")
            return None

    def _generate_with_gemini(self, item: dict) -> dict | None:
        from google.genai import types

        import time
        prompt = f"""아래 출처 검증 원고를 JSON으로 반환하세요. 새로운 사실이나 설명을 추가하지 마세요.
title은 아래 제목과 정확히 같아야 하고 content는 아래 HTML의 구조·행·텍스트·링크를 유지해야 합니다.
tags는 빈 배열입니다. is_valid_and_active는 추가 적합성 검토 결과이며 false로 거부할 수 있습니다.
제목: {item['fact_manifest']['sources'][0]['title']}
HTML: {render_content(item['fact_manifest'])}
구조화된 근거: {json.dumps(item['fact_manifest'], ensure_ascii=False)}
"""
        models_to_try = ["gemini-flash-latest", "gemini-3.5-flash"]
        last_err = None

        for model_name in models_to_try:
            for attempt in range(2):
                try:
                    response = self.client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            response_schema=BlogPostSchema,
                        ),
                    )

                    parsed = response.parsed
                    if parsed:
                        if not parsed.is_valid_and_active:
                            print(f"[CopywriterAgent] 🛑 시점 만료/부적격 소식으로 판정되어 발행 제외: {parsed.rejection_reason}")
                            return None

                        title = parsed.title
                        content = parsed.content

                        return {
                            "title": title,
                            "content": content,
                            "tags": parsed.tags,
                            "category_id": item["category_id"],
                            "category_name": item.get("category_name", ""),
                            "source_url": item["link"],
                        }
                    else:
                        data = json.loads(response.text)
                        if data.get("is_valid_and_active") is not True:
                            print(f"[CopywriterAgent] 🛑 시점 만료/부적격 소식으로 판정: {data.get('rejection_reason', '만료됨')}")
                            return None

                        title = data.get("title", "")
                        content = data.get("content", "")

                        return {
                            "title": title,
                            "content": content,
                            "tags": data.get("tags", [item["keyword"]]),
                            "category_id": item["category_id"],
                            "category_name": item.get("category_name", ""),
                            "source_url": item["link"],
                        }
                except Exception as e:
                    last_err = e
                    err_str = str(e)
                    is_transient = any(code in err_str for code in ["429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE"])
                    if is_transient and attempt == 0:
                        print(f"[CopywriterAgent] ⏳ {model_name} 일시적 지연 감지, 3초 후 재시도...")
                        time.sleep(3)
                        continue
                    else:
                        print(f"[CopywriterAgent] ⚠️ {model_name} 호출 실패 ({e}), 다음 모델로 전환합니다.")
                        break

        print(f"[CopywriterAgent] ❌ 모든 Gemini 모델 검증 실패 ({last_err}) -> 허위/만료글 방지를 위해 발행을 취소합니다.")
        return None

    def _clean_titles_and_terms(self, text: str, item: dict = None) -> str:
        """어색한 호칭 제거 및 메인 홈 베어(Bare) 링크를 타겟 딥링크로 자동 치환"""
        text = text.replace("어르신 여러분", "여러분").replace("독자 여러분", "여러분")
        text = text.replace("어르신분들", "여러분").replace("어르신들", "여러분")
        text = text.replace("어르신의", "").replace("어르신께", "여러분께").replace("어르신", "")
        text = text.replace("선생님 여러분", "여러분").replace("선생님들", "여러분")
        text = text.replace("선생님의", "여러분의").replace("선생님께", "여러분께").replace("선생님", "")
        text = text.replace("독자분들", "여러분").replace("독자들의", "여러분의").replace("독자들에게", "여러분에게")
        text = text.replace("노인", "시니어")

        if item:
            deep_links = self._build_targeted_deep_links(item)
            preferred_ticket_url = item.get("direct_product_url") or deep_links["nol_search"]

            # 메인 홈으로만 걸린 인터파크 링크를 타겟 상품 또는 NOL 검색 결과로 자동 치환
            text = re.sub(
                r'href=[\'"]https?://tickets\.interpark\.com/?[\'"]',
                f'href="{preferred_ticket_url}"',
                text,
            )
            # 메인 홈으로만 걸린 예스24 링크를 타겟 Yes24 검색 결과로 자동 치환
            text = re.sub(
                r'href=[\'"]https?://ticket\.yes24\.com/?[\'"]',
                f'href="{deep_links["yes24_search"]}"',
                text,
            )
            # 메인 홈으로만 걸린 gov.kr 링크를 정부24 검색 결과로 자동 치환
            text = re.sub(
                r'href=[\'"]https?://(?:www\.)?gov\.kr/?[\'"]',
                f'href="{deep_links["gov24_search"]}"',
                text,
            )

        return text
