import requests
import re
from bs4 import BeautifulSoup

url = 'https://nol.yanolja.com/discovery/list/search/PRODUCT_CATEGORY_ENTERTAINMENT?q=%EB%AC%B4%EB%AA%85%EC%A0%84%EC%84%A4'
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}
resp = requests.get(url, headers=headers, timeout=10)
print('Search Page Status:', resp.status_code)
matches = re.findall(r'/ticket/products/(\d+)', resp.text)
print('Direct product links in HTML:', set(matches))

# Check Interpark ticket search API or Interpark web search
headers_interpark = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://tickets.interpark.com/'
}
ip_url = 'https://tickets.interpark.com/contents/search?q=%EB%AC%B4%EB%AA%85%EC%A0%84%EC%84%A4'
resp_ip = requests.get(ip_url, headers=headers_interpark, timeout=10)
print('Interpark search page status:', resp_ip.status_code)
ip_matches = re.findall(r'/goods/(\d+)', resp_ip.text)
print('Interpark goods matches:', set(ip_matches))
