from duckduckgo_search import DDGS

def test_search():
    with DDGS() as ddgs:
        results = ddgs.images("비바브라보 트로트 콘서트", max_results=3)
        for r in results:
            print("Title:", r.get("title"))
            print("Image:", r.get("image"))
            print("Source:", r.get("url"))
            print("---")

if __name__ == "__main__":
    test_search()
