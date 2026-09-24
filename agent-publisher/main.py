import argparse
import sys
import time
from config import CATEGORIES
from agents.radar import RadarAgent
from agents.curator import CuratorAgent
from agents.editorial_writer import EditorialWriterAgent as CopywriterAgent
from agents.designer import DesignerAgent
from agents.publisher import PublisherAgent
from sync_wordpress_inventory import sync_inventory
from notifier import notify_published, notify_error, notify_pipeline_summary


def run_pipeline(category_keys: list, limit_per_cat: int = 1):
    print("=" * 60)
    print("📢 [생활정보 24] 5대 멀티 에이전트 자율 발행 파이프라인 가동")
    print("=" * 60)

    sync_inventory()
    radar = RadarAgent()
    curator = CuratorAgent()
    # Scheduled/server automation is the only in-repo path that asks the
    # configured Gemini adapter to write a new plan. Interactive ChatGPT work
    # supplies an already-written plan through editorial_cli.py manual-review.
    copywriter = CopywriterAgent(writing_enabled=True)
    designer = DesignerAgent()
    publisher = PublisherAgent()

    stats = {
        "categories": [],
        "candidates": 0,
        "published": 0,
        "held": 0,
        "errors": 0,
        "held_reasons": []
    }

    for cat_key in category_keys:
        if cat_key not in CATEGORIES:
            print(f"⚠️ 존재하지 않는 카테고리: {cat_key}")
            continue

        cat_info = CATEGORIES[cat_key]
        stats["categories"].append(cat_info["name"])
        print(f"\n📂 [{cat_info['name']}] 카테고리 작업 시작")

        # 1. 탐색 (Radar) - 키워드당 2개 후보 수집하여 팩트 검증 탈락 시 예비 버퍼 확보
        candidates = radar.search_news(cat_key, max_items_per_keyword=2)
        if not candidates:
            print(f"ℹ️ 새로운 소식이 없습니다.")
            continue

        stats["candidates"] += len(candidates)
        processed_for_this_cat = 0
        for raw_item in candidates:
            if processed_for_this_cat >= limit_per_cat:
                break

            try:
                # 2. 기획 및 팩트체크 (Curator)
                curated = curator.curate(raw_item)
                if not curated:
                    print("[Pipeline] ⏩ 기사 원문 추출 실패/품질 미달로 다음 기사를 탐색합니다.")
                    stats["held"] += 1
                    stats["held_reasons"].append(f"[{cat_info['name']}] 원문 추출 실패/품질 미달")
                    continue

                # 3. 인포머티브 딥다이브 원고 집필 (Copywriter)
                article = copywriter.write_article(curated)
                if not article:
                    print(f"[Pipeline] ⏩ 검증 미완료/시점 만료/부적격 소식은 발행하지 않고 다음 후보를 탐색합니다.")
                    stats["held"] += 1
                    stats["held_reasons"].append(f"[{cat_info['name']}] 팩트/기간/중복 검증 보류")
                    time.sleep(2)
                    continue

                # 4. 맞춤형 썸네일 이미지 자율 디자인 (Designer)
                img_path = designer.generate_image(
                    title=article["title"],
                    category_name=cat_info["name"],
                    keyword=raw_item["keyword"],
                    curated=curated,
                    category_key=cat_key,
                )

                # 5. 워드프레스 포스팅 및 썸네일 등록 (Publisher)
                post_id = publisher.publish(article, image_path=img_path)

                # 6. 중복 방지 히스토리 저장 (구글 뉴스 URL + 언론사 원문 URL 모두 기록)
                radar.save_to_history(raw_item.get("link", ""), curated.get("link", ""))

                processed_for_this_cat += 1
                stats["published"] += 1
                print(f"🎉 처리 완료 ({processed_for_this_cat}/{limit_per_cat}): Post #{post_id} - {article['title']}")
                notify_published(article['title'], cat_info['name'], f"Post #{post_id}", used_model=article.get('used_model'))

            except Exception as e:
                print(f"❌ 작업 중 에러 발생: {e}")
                stats["errors"] += 1
                stats["held_reasons"].append(f"[{cat_info['name']}] 오류: {str(e)[:30]}")
                notify_error(f"{cat_info['name']} 발행 단계", str(e))

    print("\n" + "=" * 60)
    print(f"🎉 총 {stats['published']}건의 포스팅 작업 완료 (탐색: {stats['candidates']}건, 보류: {stats['held']}건, 에러: {stats['errors']}건)")
    print("=" * 60)

    # 파이프라인 일일 종합 리포트 발송 (사일런트 실패 방지)
    try:
        notify_pipeline_summary(stats)
    except Exception as e:
        print(f"⚠️ 요약 리포트 발송 실패: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="생활정보 24 멀티 에이전트 발행기")
    parser.add_argument(
        "--category",
        choices=["concert", "welfare", "life-health", "tax", "all"],
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
