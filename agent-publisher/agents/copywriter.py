import json
import re
import urllib.parse
from datetime import datetime
from pydantic import BaseModel, Field
from config import GEMINI_API_KEY, POSTS_INDEX_FILE


class BlogPostSchema(BaseModel):
    is_valid_and_active: bool = Field(
        description="이 기사/공고에 언급된 주요 일정이나 혜택이 오늘(현재 시점) 이후에도 여전히 유효하고 참여/신청/예매 가능한지 여부. 만약 모든 일정이 이미 종료된 과거 일정이면 false로 설정"
    )
    rejection_reason: str = Field(
        default="",
        description="is_valid_and_active가 false인 경우, 거부 사유 (예: '2026년 4월에 이미 종료된 콘서트임', '신청 마감일이 5월이었음')"
    )
    title: str = Field(description="클릭률(CTR)과 SEO를 극대화한 매력적인 완성형 포스팅 제목 (어르신, 독자 등 인위적 호칭 금지)")
    content: str = Field(
        description="풍부한 가독성을 제공하는 완결된 HTML 본문 (표, 요약 박스, STEP 1~5 가이드, 새창 하이퍼링크 버튼 필수 포함)"
    )
    tags: list[str] = Field(description="검색 유입을 위한 관련 핵심 태그 5~7개")


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

    def _inject_internal_links(self, content: str, current_cat_id: int, current_title: str) -> str:
        """기존 발행된 관련 글(Interlinking)을 본문 하단에 자동 삽입하여 체류시간 및 SEO 극대화"""
        if not POSTS_INDEX_FILE.exists():
            return content

        try:
            with open(POSTS_INDEX_FILE, "r", encoding="utf-8") as f:
                posts = json.load(f)
        except Exception:
            return content

        candidates = [p for p in posts if p.get("title") != current_title and p.get("url")]
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
        print(f"[CopywriterAgent] ✍️ 인포머티브 딥다이브 원고 집필 및 시점 검증 시작: {curated_item['title']}")
        if self.client:
            return self._generate_with_gemini(curated_item)
        else:
            print("[CopywriterAgent] ❌ Gemini 클라이언트가 없어 팩트 검증이 불가하므로 발행을 중단합니다.")
            return None

    def _generate_with_gemini(self, item: dict) -> dict | None:
        from google.genai import types

        today_str = datetime.now().strftime("%Y년 %m월 %d일")
        deep_links = self._build_targeted_deep_links(item)
        target_direct_url = item.get("direct_product_url") or deep_links["nol_search"]

        ticket_notice = ""
        if item.get("ticket_prices") and item.get("direct_product_url"):
            ticket_notice = f"""
[🎯 공식 예매처 실시간 가격 및 상세페이지 수집 완료 - 반드시 본문에 반영!]
- 공식 좌석별 티켓 가격: {item['ticket_prices']}
- 공식 단독 예매 상품 링크: {item['direct_product_url']}
- [작성 필수]: 표(Table)와 한눈에 보는 요약 박스, FAQ에 "가격 미정"이나 "원문 미표기"라고 적지 말고, 반드시 위 공식 가격({item['ticket_prices']})을 명확히 기재하세요!
- [버튼 필수]: 바로가기 버튼의 연결 링크는 반드시 공식 상세 URL({item['direct_product_url']})로 연결하세요!
"""

        prompt = f"""
당신은 대한민국 최고 수준의 고품질 생활 정보 전문 블로거입니다. (벤치마크: infolspot.com 스타일의 완전 백과사전식 딥다이브 정보 + 무결점 새창 하이퍼링크)
블로그 이름은 '생활정보 24'입니다.

[🚨 팩트체크 및 무단 날조(Hallucination) 절대 금지 규칙]
1. 오늘 기준 현재 날짜: '{today_str}'
2. [원문 팩트 100% 엄수]:
   - 반드시 아래 제공된 [본문/상세 내용]에 실제로 존재하는 사실(Fact)에만 기반하여 글을 작성하세요.
   - ❌ 원문에 없는 가상의 티켓 가격(예: R석 5만원, VIP석 15만원 등)을 절대로 지어내지 마세요!
   - ❌ 무료 행사(지자체 무료 문화사업, 야외 특설무대 등)를 유료 콘서트로 둔갑시키거나 인터파크/예스24 티켓 구매 링크를 달지 마세요!
   - 관람료가 무료인 경우: 반드시 "관람료: 전석 무료 (현장 선착순 무료 관람)"로 정직하게 안내하고, 바로가기 버튼도 인터파크가 아니라 공식 주최 기관 공고 링크({item['link']})로 연결하세요.
   - 대형 상업 콘서트(인터파크 공식 판매 등)인 경우에만 실제 예매처 링크와 공식 가격을 작성하세요.
3. [시점 및 날짜 팩트 검증]:
   - 기사에 언급된 모든 행사/공연/신청 일자가 오늘 날짜({today_str}) 이전에 이미 종료된 과거 일정이면, 절대로 향후 일정인 것처럼 날조하지 말고 `is_valid_and_active: false`로 즉시 거부(Drop)하세요.
   - 만약 여러 회차 중 오늘({today_str}) 이후에 예정된 일정이 원문에 실제로 남아있는 경우라면, 앞으로 열릴 일정만 집중 안내하고 지난 회차(예: 9월 4일 공연)는 이미 종료되었음을 사실대로 명시하세요.

{ticket_notice}

아래 뉴스 원문 정보를 철저하게 분석하여, 독자에게 100% 진실되고 유익한 완결형 블로그 글을 작성해 주세요.

[원본 정보]
- 카테고리: {item['category_name']}
- 핵심 키워드: {item['keyword']}
- 원본 기사 제목: {item['title']}
- 본문/상세 내용 (이 팩트에만 기반할 것): {item['full_content']}
- 출처/관련 링크: {item['link']}


[🚨 링크 작성 및 바로가기 버튼 필수 규칙 - 메인 홈 링크 절대 금지, 타겟 딥링크(Deep Link) 의무화]
1. ❌ 절대로 예매처나 포털의 메인 홈(예: https://tickets.interpark.com, https://www.gov.kr 메인 등)을 걸지 마세요!
   사용자가 메인으로 이동하면 다시 검색창을 찾아 헤매야 하므로 극히 불친절한 저품질 글이 됩니다.
2. ⭕ 반드시 사용자가 버튼을 눌렀을 때 해당 공연/가수/지원금의 [공식 상세 페이지]나 [직접 검색 결과 목록]으로 바로 이동할 수 있는 완성형 딥링크를 연결하세요:
   - 상업 유료 콘서트 예매인 경우:
     공식 상세페이지 URL이 있다면 반드시 1순위로 상세페이지 연결:
     👉 우선 권장 상세 URL: {target_direct_url}
     공연 검색 목록(현재 판매중인 회차 모아보기):
     👉 NOL 티켓 현재 판매중 전체 검색 URL: {deep_links['nol_search']}
     예스24인 경우:
     👉 권장 예스24 검색 URL: {deep_links['yes24_search']}
   - 정부 복지/지원금 신청인 경우:
     👉 권장 정부24 검색 URL: {deep_links['gov24_search']} 또는 복지로(https://www.bokjiro.go.kr)
   - 무료 공공 행사/지자체 사업인 경우:
     원문 출처 및 주최 지자체 공식 안내 링크 ({item['link']})
3. 필수 바로가기 버튼 예시:
   `<div style="text-align: center; margin: 30px 0;"><a href="{target_direct_url}" target="_blank" rel="noopener noreferrer" style="display: inline-block; background-color: #2b6cb0; color: #ffffff; padding: 16px 36px; border-radius: 8px; text-decoration: none; font-weight: bold; font-size: 1.15em; box-shadow: 0 4px 6px rgba(0,0,0,0.15);">👉 [{deep_links['entity']}] 공식 예매 페이지 바로가기 (새창)</a></div>`

[🚨 호칭 및 톤앤매너 필수 규칙]
1. ❌ 인위적인 호칭 절대 금지: '어르신', '노인', '선생님', '독자 여러분' 금지.
2. ⭕ 호칭은 가급적 생략하고 담백하게 서술하되, 굳이 부를 때는 오직 '여러분'만 사용.
   - 인삿말: "안녕하세요, 생활정보 24입니다."
   - 제도 대상: '만 65세 이상 대상자', '신청 대상 가구', '신청인'
   - 문체: 친절하고 정중한 '해요체'

[글 작성 및 SEO 목차 구성 가이드라인]
1. 제목: 핵심 키워드와 혜택/방법 명확 명시 (어르신, 선생님 등 호칭 금지)
2. 본문 목차:
   - 📌 [한눈에 보는 핵심 요약 박스]
   - 1. 기본 개요 및 특징
   - 2. 상세 정보 및 일정·가격표 (table 태그 필수)
   - 3. 단계별 실전 가이드 (STEP 1 ~ STEP 5) 및 [새창 바로가기 버튼]
   - 4. 장소/교통 안내 및 신청 경로
   - 5. 신청/관람 전 필수 체크리스트 & 주의사항
   - 6. 자주 묻는 질문 (FAQ)
   - 7. 공식 접수처 및 문의 채널 안내 (실제 새창 링크 포함)

3. 출력 형식 (JSON):
   - title: 매력적인 검색 최적화 제목
   - content: 완성된 무결점 고밀도 HTML 본문
   - tags: 관련 태그 5~7개 배열
"""
        import time
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

                        title = self._clean_titles_and_terms(parsed.title, item)
                        content = self._clean_titles_and_terms(parsed.content, item)
                        # 내부 링크(Interlinking) 자동 주입
                        content = self._inject_internal_links(content, item.get("category_id", 0), title)

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
                        if not data.get("is_valid_and_active", True):
                            print(f"[CopywriterAgent] 🛑 시점 만료/부적격 소식으로 판정: {data.get('rejection_reason', '만료됨')}")
                            return None

                        title = self._clean_titles_and_terms(data.get("title", item["title"]), item)
                        content = self._clean_titles_and_terms(data.get("content", ""), item)
                        content = self._inject_internal_links(content, item.get("category_id", 0), title)

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
