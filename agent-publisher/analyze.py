import feedparser
import requests
from bs4 import BeautifulSoup
import json

def analyze_infolspot():
    # Blogger Atom feed (전체 게시물 수집)
    feed_url = "https://www.infolspot.com/feeds/posts/default?max-results=150"
    feed = feedparser.parse(feed_url)
    
    print(f"총 수집된 게시물 수: {len(feed.entries)}")
    
    posts = []
    category_counter = {}
    
    for i, entry in enumerate(feed.entries):
        title = entry.title
        link = entry.link
        published = entry.get("published", "")
        
        # 카테고리 태그
        tags = [t.get("term", "") for t in entry.get("tags", [])]
        for t in tags:
            category_counter[t] = category_counter.get(t, 0) + 1
            
        content_html = ""
        if "content" in entry:
            content_html = entry.content[0].value
        elif "summary" in entry:
            content_html = entry.summary
            
        soup = BeautifulSoup(content_html, "html.parser")
        
        # 소제목(h2, h3, h4) 분석
        headings = [h.get_text().strip() for h in soup.find_all(["h2", "h3", "h4"])]
        
        # 표(table) 존재 여부
        tables = len(soup.find_all("table"))
        
        # 리스트(ul, ol) 존재 여부
        lists = len(soup.find_all(["ul", "ol"]))
        
        # 이미지 수
        images = len(soup.find_all("img"))
        
        # 링크 수
        links = [a.get("href") for a in soup.find_all("a") if a.get("href")]
        
        text = soup.get_text()
        
        posts.append({
            "title": title,
            "link": link,
            "published": published,
            "tags": tags,
            "headings": headings,
            "tables": tables,
            "lists": lists,
            "images": images,
            "outbound_links_count": len(links),
            "text_length": len(text),
            "full_text_sample": text[:800],
            "html_structure": [tag.name for tag in soup.find_all(True)[:30]],
        })
        
    # 결과 요약 저장 및 출력
    analysis_result = {
        "total_posts": len(posts),
        "categories": category_counter,
        "average_length": sum(p["text_length"] for p in posts) // len(posts) if posts else 0,
        "sample_posts": posts[:5]
    }
    
    with open("infolspot_analysis.json", "w", encoding="utf-8") as f:
        json.dump(analysis_result, f, ensure_ascii=False, indent=2)
        
    print(f"평균 글자 수: {analysis_result['average_length']}자")
    print(f"주요 카테고리 분포: {category_counter}")
    print("\n최신 게시물 제목 및 구조 샘플:")
    for p in posts[:8]:
        print(f"- 제목: {p['title']}")
        print(f"  소제목 목록: {p['headings']}")
        print(f"  표: {p['tables']}개, 리스트: {p['lists']}개, 글자수: {p['text_length']}자")
        print()

if __name__ == "__main__":
    analyze_infolspot()
