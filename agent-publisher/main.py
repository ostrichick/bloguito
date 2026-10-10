import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
from config import CATEGORIES
from agents.growth_analysis import GrowthAnalysisError, load_policy, refresh_growth_inputs
from agents.growth_planner import GrowthPlannerError, decide_daily_action, save_daily_plan
from agents.growth_work_log import (
    empty_work_log,
    record_new_draft_completion,
    save_work_log,
)
from agents.radar import RadarAgent
from agents.curator import CuratorAgent
from agents.editorial_writer import EditorialWriterAgent as CopywriterAgent
from agents.designer import (
    DesignerAgent, ScheduledImageGenerationUnavailable, cleanup_generated_cover,
)
from agents.publisher import PublisherAgent
from sync_wordpress_inventory import ensure_inventory, sync_inventory
from notifier import AlertDelivery, notify_published, notify_error, notify_pipeline_summary
from agents.temporal_validation import KST


GROWTH_DIR = Path(__file__).resolve().parent / 'data' / 'growth'
DATA_DIR = Path(__file__).resolve().parent / 'data'
ANALYTICS_DIR = DATA_DIR / 'analytics'
GROWTH_OPPORTUNITIES = GROWTH_DIR / 'latest-opportunities.json'
TOPIC_SCORES = GROWTH_DIR / 'topic-candidate-scores.json'
GROWTH_WORK_LOG = GROWTH_DIR / 'growth-work-log.json'
GROWTH_POLICY = Path(__file__).resolve().parent / 'growth_policy.json'
GROWTH_INPUT_FAILURE_REASONS = frozenset({
    'growth_inputs_unavailable_or_stale',
    'growth_planner_runtime_unavailable',
    'growth_plan_new_draft_target_invalid',
})


def _load_private_json(path: Path):
    if path.is_symlink():
        raise GrowthPlannerError('growth_runtime_symlink_not_allowed')
    return json.loads(path.read_text(encoding='utf-8'))


def build_scheduled_growth_plan(category_keys: list) -> dict:
    """Build and persist the read-only decision that gates scheduled writing."""
    try:
        refresh = refresh_growth_inputs(
            analytics_dir=ANALYTICS_DIR,
            growth_dir=GROWTH_DIR,
            data_dir=DATA_DIR,
            policy_path=GROWTH_POLICY,
            as_of=datetime.now(KST).date(),
        )
        print(
            "[Growth Inputs] analytics=" + str(refresh.get('analytics_snapshot'))
            + " opportunities_refreshed=" + str(refresh.get('opportunities_refreshed')).lower()
            + " topic_scores_refreshed=" + str(refresh.get('topic_scores_refreshed')).lower()
        )
        opportunities = _load_private_json(GROWTH_OPPORTUNITIES)
        scores = _load_private_json(TOPIC_SCORES)
        refresh_id = opportunities.get('refresh_id') if isinstance(opportunities, dict) else None
        opportunity_digest = (
            opportunities.get('opportunity_payload_sha256')
            if isinstance(opportunities, dict) else None
        )
        if (not isinstance(refresh_id, str) or len(refresh_id) != 64
                or scores.get('refresh_id') != refresh_id
                or not isinstance(opportunity_digest, str) or len(opportunity_digest) != 64
                or scores.get('opportunity_payload_sha256') != opportunity_digest):
            raise GrowthAnalysisError('growth_input_pair_not_committed')
        if GROWTH_WORK_LOG.exists():
            work_log = _load_private_json(GROWTH_WORK_LOG)
        else:
            work_log = {'schema_version': 1, 'entries': []}
        policy = load_policy(GROWTH_POLICY)
        slug_map = {key: value['slug'] for key, value in CATEGORIES.items()}
        plan = decide_daily_action(
            opportunities, scores, policy,
            as_of=datetime.now(KST).date(),
            work_log=work_log,
            category_keys=category_keys,
            category_slug_map=slug_map,
        )
        if plan.get('action') == 'new_draft':
            target = plan.get('target') or {}
            if (target.get('category_key') not in category_keys
                    or not isinstance(target.get('brief_id'), str)):
                raise GrowthPlannerError('growth_plan_new_draft_target_invalid')
        plan['plan_persisted'] = True
        save_daily_plan(plan, GROWTH_DIR)
        return plan
    except Exception as exc:
        # Missing or malformed private growth state is not evidence that a new
        # article should be written. Always replace yesterday's decision.
        detail = str(exc)
        if (not detail or len(detail) > 96 or not detail.isascii()
                or not detail.replace('_', '').isalnum()):
            detail = type(exc).__name__
        plan = {
            'schema_version': 1,
            'generated_at_utc': datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'as_of_date': datetime.now(KST).date().isoformat(),
            'action': 'no_action',
            'target': None,
            'reason': 'growth_planner_runtime_unavailable',
            'details': [detail],
            'plan_persisted': True,
        }
        try:
            save_daily_plan(plan, GROWTH_DIR)
        except Exception as save_error:
            # Do not leave a previous actionable plan as the latest decision.
            plan['plan_persisted'] = False
            plan['details'].append('daily_growth_plan_persist_failed')
            previous = GROWTH_DIR / 'daily-growth-plan.json'
            try:
                if not GROWTH_DIR.is_symlink() and not previous.is_symlink():
                    previous.unlink(missing_ok=True)
                else:
                    plan['details'].append('daily_growth_plan_invalidation_failed')
            except OSError:
                plan['details'].append('daily_growth_plan_invalidation_failed')
            print('[Growth Planner] failure decision could not be saved: '
                  + type(save_error).__name__)
        return plan


def _record_notification(stats: dict, callback, *args, **kwargs) -> None:
    """Account for unconfigured delivery and each failed configured channel."""
    try:
        delivery = callback(*args, **kwargs)
        if isinstance(delivery, AlertDelivery):
            if delivery.configured == 0:
                stats['notification_unconfigured'] += 1
            if delivery.failed:
                stats['notification_errors'] += 1
                stats['notification_channel_failures'] += delivery.failed
        elif delivery is False:
            # Support notification adapters exposing the legacy bool contract.
            stats['notification_errors'] += 1
    except Exception as exc:
        stats['notification_errors'] += 1
        print(f"⚠️ 알림 처리 실패: {type(exc).__name__}")


def record_scheduled_new_draft_completion(growth_plan: dict, *, post_id: int, title: str) -> None:
    """Persist a successful scheduled draft without turning log failure into duplicate creation."""
    policy = load_policy(GROWTH_POLICY)
    if GROWTH_WORK_LOG.exists():
        log = _load_private_json(GROWTH_WORK_LOG)
    else:
        log = empty_work_log()
    updated = record_new_draft_completion(
        log, growth_plan, policy,
        post_id=post_id,
        completed_on=datetime.now(KST).date(),
        title=title,
    )
    save_work_log(updated, GROWTH_WORK_LOG)


def run_pipeline(category_keys: list, limit_per_cat: int = 1):
    print("=" * 60)
    print("📢 [생활정보 24] 멀티 에이전트 자율 발행 파이프라인 가동")
    print("=" * 60)

    valid_categories = [key for key in category_keys if key in CATEGORIES]
    growth_plan = build_scheduled_growth_plan(valid_categories)
    selected = growth_plan.get('target') or {}
    selected_brief_id = selected.get('brief_id') if growth_plan.get('action') == 'new_draft' else None
    selected_category = selected.get('category_key') if growth_plan.get('action') == 'new_draft' else None

    if growth_plan.get('action') == 'new_draft':
        if selected_category not in valid_categories or not isinstance(selected_brief_id, str):
            growth_plan = {
                'action': 'no_action', 'target': None,
                'reason': 'growth_plan_new_draft_target_invalid', 'details': [],
            }
        else:
            valid_categories = [selected_category]

    stats = {
        "categories": [CATEGORIES[key]['name'] for key in valid_categories],
        "candidates": 0,
        "published": 0,
        "held": 0,
        "errors": 0,
        "notification_errors": 0,
        "notification_channel_failures": 0,
        "notification_unconfigured": 0,
        "growth_log_errors": 0,
        "held_reasons": [],
        "growth_action": growth_plan.get('action', 'no_action'),
        "growth_reason": growth_plan.get('reason', ''),
        "growth_details": growth_plan.get('details', []),
        "growth_plan_persisted": growth_plan.get('plan_persisted'),
        "growth_target": growth_plan.get('target'),
        "growth_outcome": (
            'input_failure' if growth_plan.get('reason') in GROWTH_INPUT_FAILURE_REASONS
            else 'editorial_hold' if growth_plan.get('action') == 'existing_improvement'
            else 'no_action' if growth_plan.get('action') == 'no_action'
            else 'new_draft_selected'
        ),
    }

    def hold_image_generation_unavailable(category_name: str) -> None:
        # The server cannot call ChatGPT image_gen. This is a policy hold, not
        # a provider outage to retry or a successful new-draft completion.
        reason = 'held_image_generation_unavailable'
        stats['held'] += 1
        stats['image_generation_status'] = reason
        stats['held_reasons'].append(f"[{category_name}] {reason}")
        print(f"[Pipeline] {reason}: ChatGPT image_gen unavailable to unattended scheduler; "
              "no draft created, no generator fallback or retry")

    if growth_plan.get('action') != 'new_draft':
        if growth_plan.get('action') == 'existing_improvement':
            target = growth_plan.get('target') or {}
            print("[Growth Planner] 기존 글 개선 우선: Post #"
                  + str(target.get('post_id')) + " - " + str(target.get('title') or ''))
            print("[Growth Planner] 공개 글을 자동 수정하지 않고 이번 신규 draft 실행을 보류합니다.")
            stats['held_reasons'].append(
                "[Growth Planner] existing improvement: Post #" + str(target.get('post_id')))
        else:
            print("[Growth Planner] 오늘 자동 작성할 신규 주제가 없습니다: "
                  + str(growth_plan.get('reason') or 'no_action'))
        _record_notification(stats, notify_pipeline_summary, stats)
        return stats

    # Only a planner-approved new draft reaches WordPress inventory refresh and
    # the existing editorial pipeline.
    sync_inventory()
    radar = RadarAgent()
    curator = CuratorAgent()
    # Scheduled/server automation is the only in-repo path that asks the
    # configured Gemini adapter to write a new plan. Interactive ChatGPT work
    # supplies an already-written plan through editorial_cli.py manual-review.
    copywriter = CopywriterAgent(writing_enabled=True)
    designer = DesignerAgent(scheduler_context=True)
    publisher = PublisherAgent()

    for cat_key in valid_categories:
        if cat_key not in CATEGORIES:
            print(f"⚠️ 존재하지 않는 카테고리: {cat_key}")
            continue

        cat_info = CATEGORIES[cat_key]
        print(f"\n📂 [{cat_info['name']}] 카테고리 작업 시작")

        # 1. 탐색 (Radar) - 키워드당 2개 후보 수집하여 팩트 검증 탈락 시 예비 버퍼 확보
        candidates = radar.search_news(
            cat_key, max_items_per_keyword=2, selected_brief_id=selected_brief_id)
        if not candidates:
            print(f"ℹ️ 새로운 소식이 없습니다.")
            continue

        stats["candidates"] += len(candidates)
        processed_for_this_cat = 0
        for raw_item in candidates:
            if processed_for_this_cat >= limit_per_cat:
                break

            try:
                # A previous successful draft write invalidates the cached full
                # inventory. Refresh only when another candidate actually needs it.
                ensure_inventory()
                # 2. 기획 및 팩트체크 (Curator)
                curated = curator.curate(raw_item)
                if not curated:
                    print("[Pipeline] ⏩ 기사 원문 추출 실패/품질 미달로 다음 기사를 탐색합니다.")
                    stats["held"] += 1
                    stats["held_reasons"].append(f"[{cat_info['name']}] 원문 추출 실패/품질 미달")
                    continue

                # Only an explicitly curator-reviewed official poster can
                # bypass interactive ChatGPT image generation on this server.
                # Avoid writer/model cost for generic covers that are known to
                # be impossible here; do not consume the growth work log.
                reviewed_poster_url = curated.get('reviewed_poster_url')
                if (not isinstance(reviewed_poster_url, str)
                        or not reviewed_poster_url.startswith(('https://', 'http://'))):
                    hold_image_generation_unavailable(cat_info['name'])
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
                try:
                    img_path = designer.generate_image(
                        title=article["title"],
                        category_name=cat_info["name"],
                        keyword=raw_item["keyword"],
                        curated=curated,
                        category_key=cat_key,
                        reviewed_poster_url=reviewed_poster_url,
                    )
                except ScheduledImageGenerationUnavailable:
                    # An official-poster path can become unusable and fall
                    # through to generated-scene mode. Never treat that as a
                    # retryable server failure or run an alternate generator.
                    hold_image_generation_unavailable(cat_info['name'])
                    continue
                image_review_evidence = designer.last_review_evidence_sha256
                if not image_review_evidence:
                    raise RuntimeError("scheduled_featured_image_review_evidence_missing")

                # 5. 워드프레스 포스팅 및 썸네일 등록 (Publisher)
                try:
                    post_id = publisher.publish(
                        article,
                        image_path=img_path,
                        image_alt_text=article["title"],
                        image_approval_kind="automated_visual_review",
                        image_approval_evidence_sha256=image_review_evidence,
                    )
                finally:
                    cleanup_generated_cover(img_path)

                # The WordPress draft already exists at this point. A private
                # work-log failure must not make the scheduler recreate it.
                try:
                    record_scheduled_new_draft_completion(
                        growth_plan, post_id=post_id, title=article['title'])
                except Exception as growth_log_error:
                    stats["growth_log_errors"] += 1
                    stats["held_reasons"].append(
                        "[Growth Planner] 신규 draft 완료 기록 실패: "
                        + type(growth_log_error).__name__)
                    _record_notification(stats, notify_error, "Growth work log",
                                         str(growth_log_error))

                # 6. 중복 방지 히스토리 저장 (구글 뉴스 URL + 언론사 원문 URL 모두 기록)
                radar.save_to_history(raw_item.get("link", ""), curated.get("link", ""))

                processed_for_this_cat += 1
                stats["published"] += 1
                print(f"🎉 처리 완료 ({processed_for_this_cat}/{limit_per_cat}): Post #{post_id} - {article['title']}")
                _record_notification(stats, notify_published, article['title'],
                                     cat_info['name'], f"Post #{post_id}",
                                     used_model=article.get('used_model'))

            except Exception as e:
                print(f"❌ 작업 중 에러 발생: {e}")
                stats["errors"] += 1
                stats["held_reasons"].append(f"[{cat_info['name']}] 오류: {str(e)[:30]}")
                _record_notification(stats, notify_error, f"{cat_info['name']} 발행 단계", str(e))

    print("\n" + "=" * 60)
    print(f"🎉 총 {stats['published']}건의 포스팅 작업 완료 (탐색: {stats['candidates']}건, 보류: {stats['held']}건, 에러: {stats['errors']}건)")
    print("=" * 60)

    if (stats['growth_outcome'] == 'new_draft_selected' and stats['held']
            and not stats['published'] and not stats['errors']):
        stats['growth_outcome'] = 'editorial_hold'

    # 파이프라인 일일 종합 리포트 발송 (사일런트 실패 방지)
    _record_notification(stats, notify_pipeline_summary, stats)
    return stats


def main(argv=None):
    parser = argparse.ArgumentParser(description="생활정보 24 멀티 에이전트 발행기")
    parser.add_argument(
        "--category",
        choices=[*CATEGORIES.keys(), "all"],
        default="all",
        help="발행할 카테고리 선택 (기본: all)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=1,
        help="카테고리당 발행할 글 개수 (기본: 1)",
    )

    args = parser.parse_args(argv)
    if args.limit < 1:
        parser.error('--limit must be a positive integer')

    if args.category == "all":
        targets = list(CATEGORIES.keys())
    else:
        targets = [args.category]

    stats = run_pipeline(targets, limit_per_cat=args.limit)
    # Holds and an empty candidate list are valid editorial outcomes. Actual
    # processing errors must propagate to cron/systemd even after partial success.
    result = {key: stats.get(key, 0) for key in (
        'candidates', 'published', 'held', 'errors', 'notification_errors', 'growth_log_errors',
        'notification_channel_failures', 'notification_unconfigured')}
    result['growth_action'] = stats.get('growth_action', 'unknown')
    result['growth_reason'] = stats.get('growth_reason', '')
    result['growth_details'] = stats.get('growth_details', [])
    result['growth_outcome'] = stats.get('growth_outcome', 'unknown')
    if stats.get('growth_plan_persisted') is not None:
        result['growth_plan_persisted'] = stats['growth_plan_persisted']
    if stats.get('image_generation_status'):
        result['image_generation_status'] = stats['image_generation_status']
    result['status'] = (
        'failed' if stats['errors'] or result['growth_outcome'] == 'input_failure' else
        'held_image_generation_unavailable'
        if stats.get('image_generation_status') and not stats['published']
        else 'completed'
    )
    print('PIPELINE_RESULT ' + json.dumps(result, ensure_ascii=False))
    return 1 if result['status'] == 'failed' else 0


if __name__ == "__main__":
    raise SystemExit(main())
