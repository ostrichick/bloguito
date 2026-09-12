import urllib.request

photos = {
    "concert": [
        "photo-1514525253161-7a46d19cd819",
        "photo-1470225620780-dba8ba36b745",
        "photo-1465847899084-d164df4dedc6",
        "photo-1501386761578-eac5c94b800a",
        "photo-1429962714451-bb934ecdc4ec"
    ],
    "welfare": [
        "photo-1579621970563-ebec7560ff3e",
        "photo-1554224155-8d04cb21cd6c",
        "photo-1553729459-efe14ef6055d",
        "photo-1450133064473-71024230f91b",
        "photo-1576267423445-b2e0074d68a4"
    ],
    "life-health": [
        "photo-1476480862126-209bfaa8edc8",
        "photo-1452626038306-9aae5e071dd3",
        "photo-1506126613408-eca07ce68773",
        "photo-1518611012118-696072aa579a",
        "photo-1540420773420-3366772f4999"
    ]
}

def verify():
    for cat, p_list in photos.items():
        print(f"Checking {cat}...")
        for pid in p_list:
            url = f"https://images.unsplash.com/{pid}?w=1200&h=675&fit=crop&q=85"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            try:
                with urllib.request.urlopen(req) as resp:
                    data = resp.read()
                    print(f"  {pid}: OK ({resp.status}, size: {len(data)} bytes)")
            except Exception as e:
                print(f"  {pid}: FAILED ({e})")

if __name__ == "__main__":
    verify()
