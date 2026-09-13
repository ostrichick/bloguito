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
POST_STATUS = os.getenv("POST_STATUS", "draft")  # draft or publish
SITE_URL = os.getenv("SITE_URL", "http://localhost")

CATEGORIES = {
    "concert": {
        "id": 2,
        "name": "공연/콘서트 예매",
        "keywords": [
            "2026 하반기 트로트 콘서트 티켓 예매",
            "2026 연말 단독 콘서트 티켓팅",
            "임영웅 콘서트 예매 일정 2026",
            "이찬원 전국투어 콘서트 예매",
            "영탁 단독 콘서트 티켓 오픈",
            "2026 연말 뮤지컬 티켓 예매 인터파크",
            "2026 가을 페스티벌 콘서트 일정",
            "송가인 전국투어 콘서트 예매",
            "정동원 연말 콘서트 예매 일정",
            "박서진 단독 콘서트 티켓팅",
        ],
    },
    "welfare": {
        "id": 3,
        "name": "정부 복지/지원금",
        "keywords": [
            "기초연금 신청 자격 방법 2026",
            "2026 에너지바우처 신청 자격 및 기간",
            "국민건강보험 환급금 본인부담상한제 신청",
            "어르신 임플란트 틀니 건강보험 지원 혜택",
            "2026 근로장려금 정기 반기 신청 방법",
            "2026 소상공인 정책자금 지원금 신청",
            "정부24 지자체 민생회복 지원금 신청",
            "노인 맞춤 돌봄 서비스 신청 자격",
        ],
    },
    "life-health": {
        "id": 4,
        "name": "생활/건강 정보",
        "keywords": [
            "2026 독감 예방접종 무료 대상 지정 병원",
            "중장년 환절기 혈압 혈당 관리 상식 가이드",
            "국민건강검진 대상자 조회 및 검사항목",
            "알뜰폰 시니어 효도 요금제 비교 추천",
            "퇴행성 관절염 예방 운동 영양제 가이드",
            "숨은 보험금 찾기 통합 조회 서비스 신청",
            "실생활 난방비 전기세 절약 꿀팁",
        ],
    },
}
