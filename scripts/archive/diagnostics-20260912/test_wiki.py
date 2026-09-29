import requests

def search_wikimedia(query="concert stage live"):
    headers = {"User-Agent": "LifeInfo24Bot/1.0 (asulcoreano@gmail.com)"}
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": f"{query} filetype:bitmap",
        "gsrlimit": 5,
        "prop": "imageinfo",
        "iiprop": "url|dimensions|mime",
    }
    resp = requests.get("https://commons.wikimedia.org/w/api.php", params=params, headers=headers)
    print("Status:", resp.status_code)
    data = resp.json()
    pages = data.get("query", {}).get("pages", {})
    print("Found pages:", len(pages))
    for pid, p in pages.items():
        title = p.get("title")
        ii = p.get("imageinfo", [{}])[0]
        url = ii.get("url")
        w = ii.get("width")
        h = ii.get("height")
        print(f"- {title}: {w}x{h} -> {url}")

if __name__ == "__main__":
    search_wikimedia("concert stage live")
