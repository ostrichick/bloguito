import argparse
import sys
import time
from config import CATEGORIES
from agents.radar import RadarAgent
from agents.curator import CuratorAgent
from agents.copywriter import CopywriterAgent
from agents.designer import DesignerAgent
from agents.publisher import PublisherAgent


def run_pipeline(category_keys: list, limit_per_cat: int = 1):
    print("=" * 60)
    print("📢 [생활정보 24] 5대 멀티 에이전트 자율 발행 파이프라인 가동")
    print("=" * 60)

    radar = RadarAgent()
    curator = CuratorAgent()
    copywriter = CopywriterAgent()
    designer = DesignerAgent()
    publisher = PublisherAgent()

    total_published = 0

    for cat_key in category_keys:
        if cat_key not in CATEGORIES:
            print(f"⚠️ 존재하지 않는 카테고리: {cat_key}")
            continue

        cat_info = CATEGORIES[cat_key]
        print(f"\n📂 [{cat_info['name']}] 카테고리 작업 시작")

        # 1. 탐색 (Radar) - 키워드당 2개 후보 수집하여 팩트 검증 탈락 시 예비 버퍼 확보
        candidates = radar.search_news(cat_key, max_items_per_keyword=2)
        if not candidates:
            print(f"ℹ️ 새로운 소식이 없습니다.")
            continue

        processed_for_this_cat = 0
        for raw_item in candidates:
            if processed_for_this_cat >= limit_per_cat:
                break

            try:
                # 2. 기획 및 팩트체크 (Curator)
                curated = curator.curate(raw_item)
                if not curated:
                    print("[Pipeline] ⏩ 기사 원문 추출 실패/품질 미달로 다음 기사를 탐색합니다.")
                    continue

                # 3. 인포머티브 딥다이브 원고 집필 (Copywriter)
                article = copywriter.write_article(curated)
                if not article:
                    print(f"[Pipeline] ⏩ 시점 만료/부적격 판정으로 발행을 건너뛰고 다음 기사를 탐색합니다.")
                    time.sleep(2)
                    continue

                # 4. 맞춤형 썸네일 이미지 자율 디자인 (Designer)
                img_path = designer.generate_image(
                    title=article["title"],
                    category_name=cat_info["name"],
                    keyword=raw_item["keyword"],
                )

                # 5. 워드프레스 포스팅 및 썸네일 등록 (Publisher)
                post_id = publisher.publish(article, image_path=img_path)

                # 6. 중복 방지 히스토리 저장 (구글 뉴스 URL + 언론사 원문 URL 모두 기록)
                radar.save_to_history(raw_item.get("link", ""), curated.get("link", ""))

                processed_for_this_cat += 1
                total_published += 1
                print(f"✅ 처리 완료 ({processed_for_this_cat}/{limit_per_cat}): Post #{post_id} - {article['title']}")

            except Exception as e:
                print(f"❌ 작업 중 에러 발생: {e}")

    print("\n" + "=" * 60)
    print(f"🎉 총 {total_published}건의 썸네일 포함 포스팅 작업이 성공적으로 완료되었습니다!")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="생활정보 24 멀티 에이전트 발행기")
    parser.add_argument(
        "--category",
        choices=["concert", "welfare", "life-health", "all"],
        default="all",
        help="발행할 카테고리 선택 (기본: all)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=1,
        help="카테고리당 발행할 글 개수 (기본: 1)",
    )

    args = parser.parse_args()

    if args.category == "all":
        targets = list(CATEGORIES.keys())
    else:
        targets = [args.category]

    run_pipeline(targets, limit_per_cat=args.limit)
