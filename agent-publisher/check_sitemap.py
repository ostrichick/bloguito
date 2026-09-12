import requests
import xml.etree.ElementTree as ET

def check_sitemap():
    urls = []
    for p in [1, 2]:
        try:
            r = requests.get(f"https://www.infolspot.com/sitemap.xml?page={p}", timeout=10)
            root = ET.fromstring(r.text)
            for loc in root.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}loc"):
                urls.append(loc.text)
        except Exception as e:
            print(f"Page {p} error: {e}")

    print(f"=== infolspot.com 사이트 통계 ===")
    print(f"총 게시물 수: {len(urls)}개")
    if urls:
        print("최신 글:")
        for u in urls[:3]:
            print(f"  {u}")
        print("가장 오래된 글 (사이트 개설 시점 추정):")
        print(f"  {urls[-1]}")

if __name__ == "__main__":
    check_sitemap()
