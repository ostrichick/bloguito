import json
import urllib.parse
from datetime import datetime
import feedparser
from config import HISTORY_FILE, CATEGORIES
from agents.search_intent import load_briefs, matches_brief


class RadarAgent:
    """최신 뉴스 및 공고를 탐색하고 중복을 필터링하는 레이더 에이전트"""

    def __init__(self):
        self.history = self._load_history()

    def _load_history(self) -> set:
        if HISTORY_FILE.exists():
            try:
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return set(data.get("published_urls", []))
            except Exception:
                return set()
        return set()

    def save_to_history(self, *urls: str):
        """구글 뉴스 링크 및 실제 언론사 원문 링크 모두 히스토리에 기록하여 다중 RSS 간 중복 방지"""
        added = False
        for url in urls:
            if url and url not in self.history:
                self.history.add(url)
                added = True

        if added:
            HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "updated_at": datetime.now().isoformat(),
                        "published_urls": list(self.history),
                    },
                    f,
                    ensure_ascii=False,
                    indent=2,
                )

    def search_news(self, category_key: str, max_items_per_keyword: int = 2) -> list:
        """키워드별로 최대 N개의 뉴스 후보를 수집하여 Curator/Copywriter의 팩트체크용 버퍼 풀 확보"""
        if category_key not in CATEGORIES:
            raise ValueError(f"Unknown category: {category_key}")

        cat_info = CATEGORIES[category_key]
        collected = []

        print(f"[RadarAgent] 🔍 카테고리 '{cat_info['name']}' 탐색 시작 (키워드당 최대 {max_items_per_keyword}건)...")

        briefs = load_briefs(category_key)
        if not briefs:
            print("[RadarAgent] 검색 의도 검토가 완료된 유효 주제가 없어 보류합니다.")
        # Evergreen service questions need not have a recent news article.
        for brief in briefs:
            if brief.get('content_type') == 'evergreen':
                collected.append({'category_key': category_key, 'category_id': cat_info['id'],
                    'category_name': cat_info['name'], 'keyword': brief['primary_keyword'],
                    'title': brief['primary_keyword'], 'link': brief['official_urls'][0],
                    'search_brief': brief, 'editorial_direct': True})
        briefs = [b for b in briefs if b.get('content_type') != 'evergreen']
        seen = set()
        for brief, keyword in [(b, q) for b in briefs for q in b['queries']]:
            encoded_query = urllib.parse.quote(keyword)
            # Google News RSS (한국어, 대한민국 지역)
            rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ko&gl=KR&ceid=KR:ko"

            try:
                feed = feedparser.parse(rss_url)
                count = 0
                for entry in feed.entries:
                    link = entry.get("link", "")
                    title = entry.get("title", "")

                    if not link or link in self.history or link in seen or not matches_brief(title, brief):
                        continue
                    seen.add(link)

                    collected.append({
                        "category_key": category_key,
                        "category_id": cat_info["id"],
                        "category_name": cat_info["name"],
                        "keyword": keyword,
                        "title": title,
                        "link": link,
                        "published": entry.get("published", ""),
                        "raw_summary": entry.get("summary", ""),
                        "search_brief": brief,
                    })

                    count += 1
                    if count >= max_items_per_keyword:
                        break

            except Exception as e:
                print(f"[RadarAgent] ⚠️ 키워드 '{keyword}' 수집 중 오류: {e}")

        print(f"[RadarAgent] ✅ 총 {len(collected)}건의 신규 소식 후보를 발굴했습니다.")
        return collected
