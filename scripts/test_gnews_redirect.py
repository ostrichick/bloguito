import requests
from bs4 import BeautifulSoup
import re

url = "https://news.google.com/rss/articles/CBMiWkFVX3lxTFB5X3QwcC1UODFtWEdFeVlnZWdGaGZqTDNsNDdIVGtUeVhOZmtQRndObVU4SnhqMVpRVXBlbkhmaThLTEZiUFo0Vm1nNjcxclBjTEF4ZllMNmNrQQ?oc=5"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

resp = requests.get(url, headers=headers, allow_redirects=True)
print("Status:", resp.status_code)
print("Final URL:", resp.url)

# In Google News, the HTML contains the real target URL in <c-wiz> or <a ...> or javascript
soup = BeautifulSoup(resp.text, "html.parser")
links = [a.get("href") for a in soup.find_all("a") if a.get("href") and a.get("href").startswith("http")]
print("Found links:", links[:5])

# Search for real article URL
real_url_match = re.search(r'data-n-au="([^"]+)"', resp.text)
if real_url_match:
    print("Found real URL via data-n-au:", real_url_match.group(1))
