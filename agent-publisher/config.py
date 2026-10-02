import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
HISTORY_FILE = DATA_DIR / "history.json"
POSTS_INDEX_FILE = DATA_DIR / "published_posts.json"
DRAFTS_INDEX_FILE = DATA_DIR / "draft_posts.json"

load_dotenv(BASE_DIR / ".env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
KAKAO_MAP_JAVASCRIPT_KEY = os.getenv("KAKAO_MAP_JAVASCRIPT_KEY", "")
SITE_URL = os.getenv("SITE_URL", "http://localhost")

# NOL (Yanolja) Tickets "Active Sale" (ENTERTAINMENT_SALE_STATUS_SALE) Filter Token
NOL_ACTIVE_SALE_FILTER_TOKEN = (
    "Iiw0JwQnH3WmtXGyJ5rdjj3dkKg0FXd382IRSpxwfSefDnXepYDTL8Fbf88Yu1xa"
    "NDouUSnvHowixDLzJK8W8b8oBZfFTgLW5uxL8G3ULvpZtka7hxVmXkMUAtZAWLYFxnpmSA7fdJ4cOuenY9A0QODtkZVxKtNV"
)

# Known high-priority performers/entities for concert entity detection
KNOWN_ENTITIES = [
    "무명전설", "임영웅", "이찬원", "영탁", "나훈아", "정동원", "장민호",
    "김호중", "송가인", "양지은", "박서진", "진해성", "안성훈", "손태진",
    "아이유", "성시경", "싸이", "데이식스", "헤드윅", "지킬앤하이드"
]

CATEGORIES = {
    "events": {
        "id": 274,
        "name": "지역 축제/행사",
        "slug": "local-events",
        "keywords": [
            "전국 지역 축제 일정",
            "이번 달 지역 행사 가족 나들이",
            "지역 문화축제 행사 일정",
            "가을 축제 날짜 장소",
        ],
    },
    "concert": {
        "id": 2,
        "name": "공연/콘서트",
        "slug": "concert",
        "keywords": [
            "2026 하반기 트로트 콘서트 티켓 예매",
            "2026 연말 단독 콘서트 티켓팅",
            "임영웅 콘서트 예매 일정 2026",
            "이찬원 전국투어 콘서트 예매",
            "영탁 단독 콘서트 티켓 오픈",
            "2026 연말 뮤지컬 티켓 예매 인터파크",
            "송가인 전국투어 콘서트 예매",
            "정동원 연말 콘서트 예매 일정",
        ],
    },
    "welfare": {
        "id": 3,
        "name": "복지/지원금",
        "slug": "welfare",
        "keywords": [
            "기초연금 신청 자격 방법 2026",
            "2026 에너지바우처 신청 자격 및 기간",
            "실업급여 모의계산 신청 방법",
            "국민연금 수령액 모의계산",
            "노인장기요양보험 등급 신청",
            "정부24 지자체 지원금 신청",
            "도시가스 요금 경감 신청",
        ],
    },
    "tax": {
        "id": 102,
        "name": "세금/절세",
        "slug": "tax",
        "keywords": [
            "2026 연말정산 환급금 조회 및 소득공제",
            "5월 종합소득세 신고 대상 및 환급",
            "자동차세 연납 할인 신청기간",
            "국세청 세금포인트 사용처 및 조회",
            "근로장려금 자녀장려금 신청 자격 및 지급일",
            "국세 지방세 미환급금 찾기",
            "월세 세액공제 신청 방법",
        ],
    },
    "health": {
        "id": 275,
        "name": "건강/의료",
        "slug": "health",
        "keywords": [
            "국가건강검진 대상자 조회",
            "독감 예방접종 무료 대상 지정 병원",
            "휴일 병원 약국 찾기",
            "본인부담상한제 환급금 조회",
            "65세 이상 임플란트 건강보험",
        ],
    },
    "transport": {
        "id": 276,
        "name": "교통/자동차",
        "slug": "transport",
        "keywords": [
            "KTX 고속버스 취소표 예매",
            "하이패스 미납통행료 조회 납부",
            "자동차검사 기간 조회 예약",
            "운전면허 적성검사 갱신",
            "공공주차장 찾기",
            "인천공항 출국장 대기시간",
        ],
    },
    "life-admin": {
        "id": 277,
        "name": "행정/생활서비스",
        "slug": "life-admin",
        "keywords": [
            "주민등록등본 인터넷 발급",
            "모바일 주민등록증 발급",
            "전입신고 온라인 신청",
            "온라인 여권 재발급",
            "우체국 주거이전 서비스",
            "폐가전 무료수거",
            "안심상속 원스톱서비스",
        ],
    },
    "finance": {
        "id": 278,
        "name": "금융/경제",
        "slug": "finance",
        "keywords": [
            "숨은 보험금 조회 청구",
            "휴면계좌 휴면예금 찾기",
            "카드포인트 통합조회 계좌입금",
            "주택연금 예상수령액 조회",
            "최저임금 월급 계산",
            "통신 미환급액 조회",
        ],
    },
}

# Historical reviewed bundles can still contain the former broad category.
# Keep its exact term metadata for replay/inspection, but never expose it to the
# active pipeline, Radar, CLI category choices, or unknown-key fallback.
LEGACY_CATEGORIES = {
    "life-health": {
        "id": 4,
        "name": "생활/건강 정보",
        "slug": "life-health",
        "active": False,
    },
}

CATEGORY_ALIASES = {
    "event": "events",
    "local-event": "events",
    "local_events": "events",
    "festival": "events",
    "life": "life-admin",
    "life_admin": "life-admin",
    "administration": "life-admin",
    "medical": "health",
    "healthcare": "health",
    "car": "transport",
    "traffic": "transport",
    "mobility": "transport",
    "money": "finance",
    "financial": "finance",
    "banking": "finance",
    "life_health": "life-health",
    "welfare-benefit": "welfare",
    "welfare_benefit": "welfare",
    "benefit": "welfare",
    "support": "welfare",
    "taxation": "tax",
    "taxes": "tax",
    "ticket": "concert",
    "tickets": "concert",
    "concerts": "concert",
}


def resolve_category(key: str, *, allow_legacy: bool = True) -> dict:
    """Resolve an explicit category key or alias.

    Unknown and empty keys fail closed. The former ``life-health`` category is
    available only for already-reviewed historical bundles and is not part of
    the active ``CATEGORIES`` mapping used for new topic discovery.
    """
    norm_key = key.strip().lower() if isinstance(key, str) else ""
    target_key = CATEGORY_ALIASES.get(norm_key, norm_key)
    if target_key in CATEGORIES:
        return CATEGORIES[target_key]
    if allow_legacy and target_key in LEGACY_CATEGORIES:
        return LEGACY_CATEGORIES[target_key]
    raise ValueError(f"unknown_category:{norm_key or '<empty>'}")


def resolve_category_key(key: str, *, allow_legacy: bool = True) -> str:
    """Return the canonical key for an explicit category or alias."""
    norm_key = key.strip().lower() if isinstance(key, str) else ""
    target_key = CATEGORY_ALIASES.get(norm_key, norm_key)
    if target_key in CATEGORIES or (allow_legacy and target_key in LEGACY_CATEGORIES):
        return target_key
    raise ValueError(f"unknown_category:{norm_key or '<empty>'}")
