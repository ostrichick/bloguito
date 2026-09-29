from googlenewsdecoder import new_decoderv1
import requests
from bs4 import BeautifulSoup

url = "https://news.google.com/rss/articles/CBMiWkFVX3lxTFB5X3QwcC1UODFtWEdFeVlnZWdGaGZqTDNsNDdIVGtUeVhOZmtQRndObVU4SnhqMVpRVXBlbkhmaThLTEZiUFo0Vm1nNjcxclBjTEF4ZllMNmNrQQ?oc=5"
res = new_decoderv1(url)
print("Decoded URL:", res)

real_url = res.get("decoded_url") if isinstance(res, dict) else res
if real_url:
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    resp = requests.get(real_url, headers=headers, timeout=10)
    print("Fetched original article status:", resp.status_code)
    soup = BeautifulSoup(resp.text, "html.parser")
    for s in soup(["script", "style", "nav", "footer", "header", "aside"]):
        s.decompose()
    text = " ".join([p.get_text().strip() for p in soup.find_all("p") if len(p.get_text().strip()) > 20])
    print("=== REAL ARTICLE TEXT (First 600 chars) ===")
    print(text[:600])
