import sys
sys.path.append("/home/ubuntu/agent-publisher")
from agents.curator import CuratorAgent

c = CuratorAgent()
res = c.curate({
    "title": "경주",
    "link": "https://news.google.com/rss/articles/CBMiWkFVX3lxTFB5X3QwcC1UODFtWEdFeVlnZWdGaGZqTDNsNDdIVGtUeVhOZmtQRndObVU4SnhqMVpRVXBlbkhmaThLTEZiUFo0Vm1nNjcxclBjTEF4ZllMNmNrQQ?oc=5",
    "raw_summary": ""
})
print("=== ORIGINAL ARTICLE TEXT ===")
print(res["full_content"])
