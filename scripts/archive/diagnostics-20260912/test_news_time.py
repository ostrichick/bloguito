import urllib.parse
import feedparser

q = urllib.parse.quote("정부 지원금 when:7d")
url = f"https://news.google.com/rss/search?q={q}&hl=ko&gl=KR&ceid=KR:ko"
feed = feedparser.parse(url)
print("Total entries with when:7d:", len(feed.entries))
for e in feed.entries[:5]:
    print("-", e.get("title"))
    print("  Published:", e.get("published"))
