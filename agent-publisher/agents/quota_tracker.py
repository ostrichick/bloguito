"""
Gemini API Daily Quota Tracker and Priority Model Router.
Tracks successful in-process calls on a UTC calendar day. Not provider quota data.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
QUOTA_FILE = DATA_DIR / "quota_usage.json"

CYCLE_TZ = timezone.utc

MODEL_LIMITS = {
    "gemini-3.6-flash": 20,
    "gemini-3.5-flash": 20,
    "gemini-3.5-flash-lite": 500,
}

# Priority cascade: Primary high-quality model -> High-capacity fallback model
MODEL_CASCADE = [
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite",
]


def get_quota_date() -> str:
    """Return UTC day; provider reset and real remaining quota are NOT observable here."""
    return datetime.now(CYCLE_TZ).strftime("%Y-%m-%d")


def _load_data() -> dict:
    if not QUOTA_FILE.exists():
        return {"date": get_quota_date(), "usage": {}}
    try:
        data = json.loads(QUOTA_FILE.read_text(encoding="utf-8"))
        if data.get("date") != get_quota_date():
            # Reset for the new PDT day
            return {"date": get_quota_date(), "usage": {}}
        return data
    except Exception:
        return {"date": get_quota_date(), "usage": {}}


def _save_data(data: dict):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        QUOTA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"⚠️ [QuotaTracker] 할당량 데이터 저장 실패: {e}")


def record_usage(model_name: str, count: int = 1) -> dict:
    """Increment and record usage for a model."""
    data = _load_data()
    clean_model = model_name.replace("models/", "")
    usage = data.setdefault("usage", {})
    usage[clean_model] = usage.get(clean_model, 0) + count
    _save_data(data)
    return get_model_status(clean_model)


def get_model_status(model_name: str) -> dict:
    """Return a configured local estimate; not actual provider allowance."""
    clean_model = model_name.replace("models/", "")
    data = _load_data()
    used = data.get("usage", {}).get(clean_model, 0)
    limit = MODEL_LIMITS.get(clean_model, 20)
    remaining = max(0, limit - used)
    return {
        "model": clean_model,
        "limit": limit,
        "used": used,
        "remaining": remaining,
    }


def get_all_status() -> list[dict]:
    """Return status for all tracked models."""
    return [get_model_status(m) for m in MODEL_CASCADE]


def format_quota_summary() -> str:
    """Format a human-readable quota summary for notifications."""
    lines = []
    for m in MODEL_CASCADE:
        st = get_model_status(m)
        tag = "⭐최신" if m == MODEL_CASCADE[0] else "🛡️백업"
        lines.append(f"• [{tag}] {st['model']}: 로컬 기록 {st['used']}회 / 가정 한도 {st['limit']}회 (추정 잔여 {st['remaining']}회; 실제 API 할당량 아님)")
    return "\n".join(lines)


def get_model_cascade(preferred_model: str = None) -> list[str]:
    """Return list of models to attempt in order of priority."""
    candidates = []
    if preferred_model:
        clean_pref = preferred_model.replace("models/", "")
        candidates.append(clean_pref)
    for m in MODEL_CASCADE:
        if m not in candidates:
            candidates.append(m)
    return candidates
