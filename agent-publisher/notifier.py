"""
Bloguito - Notification Helper (Telegram Bot & Discord Webhook)
Sends instantaneous operational alerts when articles are published or if any errors occur.
"""

import os
import urllib.request
import json
from pathlib import Path
from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")


def send_alert(message: str, title: str = "📢 [생활정보 24] 알림") -> bool:
    """Send notification to Telegram and/or Discord if configured."""
    success = False
    full_text = f"<b>{title}</b>\n\n{message}"

    # 1. Telegram
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            payload = json.dumps({
                "chat_id": TELEGRAM_CHAT_ID,
                "text": full_text,
                "parse_mode": "HTML"
            }).encode("utf-8")
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    success = True
                    print("✅ 텔레그램 알림 발송 완료")
        except Exception as e:
            print(f"⚠️ 텔레그램 알림 발송 실패 (설정 확인 필요): {e}")

    # 2. Discord Webhook
    if DISCORD_WEBHOOK_URL:
        try:
            payload = json.dumps({
                "content": f"**{title}**\n{message}"
            }).encode("utf-8")
            req = urllib.request.Request(DISCORD_WEBHOOK_URL, data=payload, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status in (200, 204):
                    success = True
                    print("✅ 디스코드 웹훅 알림 발송 완료")
        except Exception as e:
            print(f"⚠️ 디스코드 알림 발송 실패: {e}")

    # If neither is configured, fallback to console log
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID) and not DISCORD_WEBHOOK_URL:
        print(f"ℹ️ [알림 모의 발송] {title} - {message}")

    return success


def notify_published(post_title: str, category_name: str, post_url: str, used_model: str = None):
    """Notify when an article is successfully published, including model and quota info."""
    try:
        from agents.quota_tracker import format_quota_summary
        quota_info = "\n\n📊 <b>UTC 기준 로컬 호출 기록(실제 API 잔여량 아님):</b>\n" + format_quota_summary()
    except Exception:
        quota_info = ""

    model_label = used_model or "사용 모델 미기록"
    msg = (
        f"✅ <b>새 기사 임시글 생성 완료!</b>\n"
        f"• <b>제목</b>: {post_title}\n"
        f"• <b>분야</b>: {category_name}\n"
        f"• <b>링크</b>: {post_url}\n"
        f"• <b>작성 AI 모델</b>: <code>{model_label}</code>"
        f"{quota_info}"
    )
    send_alert(msg, title="🚀 [생활정보 24] 초안 생성 성공")


def notify_error(stage: str, error_msg: str):
    """Notify when an error occurs in the publishing pipeline."""
    msg = (
        f"🚨 <b>발행 파이프라인 에러 발생</b>\n"
        f"• <b>단계</b>: {stage}\n"
        f"• <b>오류 내용</b>: {error_msg}"
    )
    send_alert(msg, title="⚠️ [생활정보 24] 파이프라인 장애 알림")


def notify_pipeline_summary(stats: dict):
    """Notify the consolidated daily pipeline execution summary to prevent silent failures."""
    total_candidates = stats.get("candidates", 0)
    total_published = stats.get("published", 0)
    total_held = stats.get("held", 0)
    total_errors = stats.get("errors", 0)
    categories = ", ".join(stats.get("categories", []))

    msg = (
        f"📊 <b>파이프라인 실행 종합 리포트</b>\n"
        f"• <b>대상 분야</b>: {categories}\n"
        f"• <b>탐색 소식 후보</b>: {total_candidates}건\n"
        f"• <b>신규 임시글 등록</b>: {total_published}건\n"
        f"• <b>검증 보류/스킵</b>: {total_held}건\n"
        f"• <b>장애/에러</b>: {total_errors}건"
    )
    if stats.get("held_reasons"):
        reasons_text = "\n".join(f"  - {r}" for r in stats["held_reasons"][:3])
        msg += f"\n• <b>주요 보류 사유</b>:\n{reasons_text}"

    send_alert(msg, title="📈 [생활정보 24] 파이프라인 일일 요약")
