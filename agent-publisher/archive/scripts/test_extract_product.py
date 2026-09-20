import requests

url = 'https://nol.yanolja.com/ticket/products/26013136'
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}
resp = requests.get(url, headers=headers, timeout=10)
idx = resp.text.find('154,000')
if idx != -1:
    print('Found 154,000 at index', idx)
    print(resp.text[max(0, idx - 300):min(len(resp.text), idx + 300)])
else:
    print('154,000 not found in text, search R석')
    idx2 = resp.text.find('R석')
    if idx2 != -1:
        print(resp.text[max(0, idx2 - 300):min(len(resp.text), idx2 + 300)])
