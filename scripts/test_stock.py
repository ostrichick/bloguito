import requests
from bs4 import BeautifulSoup
import re

def test_pexels(keyword="concert"):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    url = f"https://www.pexels.com/search/{keyword}/"
    resp = requests.get(url, headers=headers)
    print("Pexels status:", resp.status_code)
    matches = re.findall(r'https://images\.pexels\.com/photos/\d+/[^"\'? ]+', resp.text)
    print("Pexels matches:", len(matches))
    if matches:
        print("First match:", matches[0])
        return matches[0]
    return None

def test_unsplash(keyword="concert"):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    url = f"https://unsplash.com/s/photos/{keyword}"
    resp = requests.get(url, headers=headers)
    print("Unsplash status:", resp.status_code)
    matches = re.findall(r'https://images\.unsplash\.com/photo-[^"\'? ]+', resp.text)
    print("Unsplash matches:", len(matches))
    if matches:
        print("First match:", matches[0])
        return matches[0]
    return None

if __name__ == "__main__":
    test_pexels("concert")
    test_unsplash("concert")
