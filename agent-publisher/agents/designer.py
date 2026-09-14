import hashlib
import io
import json
import os
import random
import re
import tempfile
import urllib.request
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from config import GEMINI_API_KEY

STATE_FILE = Path(__file__).parent.parent / "data" / "designer_state.json"


def _load_font(size: int = 24, bold: bool = True) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Linux(Ubuntu)와 Windows 환경을 모두 지원하는 크로스 플랫폼 폰트 안전 로더"""
    candidates = []
    if bold:
        candidates = [
            "/usr/share/fonts/truetype/nanum/NanumSquareB.ttf",
            "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
            "C:/Windows/Fonts/malgunbd.ttf",
            "C:/Windows/Fonts/NanumSquareB.ttf",
            "C:/Windows/Fonts/NanumGothicBold.ttf",
            "arialbd.ttf",
        ]
    else:
        candidates = [
            "/usr/share/fonts/truetype/nanum/NanumSquareR.ttf",
            "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
            "C:/Windows/Fonts/malgun.ttf",
            "C:/Windows/Fonts/NanumSquareR.ttf",
            "C:/Windows/Fonts/NanumGothic.ttf",
            "arial.ttf",
        ]

    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue

    try:
        return ImageFont.load_default(size=size)
    except Exception:
        return ImageFont.load_default()

# 고화질(4K) 검증된 테마별 실사 스톡 사진 라이브러리 (Unsplash CDN 직결)
STOCK_PHOTOS = {
    "concert": [
        "photo-1514525253161-7a46d19cd819",  # 웅장한 콘서트 조명 & 열광하는 관객
        "photo-1470225620780-dba8ba36b745",  # 페스티벌 레이저 쇼
        "photo-1465847899084-d164df4dedc6",  # 라이브 음악 무대
        "photo-1501386761578-eac5c94b800a",  # 화려한 무대 공연
        "photo-1429962714451-bb934ecdc4ec",  # 콘서트 축제 축하 폭죽
    ],
    "welfare": [
        "photo-1579621970563-ebec7560ff3e",  # 금융 지원 및 저축 성장
        "photo-1554224155-8d04cb21cd6c",  # 정부 신청 서류 및 작성 가이드
        "photo-1553729459-efe14ef6055d",  # 지원금 혜택 및 안락한 생활
        "photo-1450133064473-71024230f91b",  # 따뜻한 지원의 손길
        "photo-1576267423445-b2e0074d68a4",  # 평화롭고 행복한 가정 생활
    ],
    "life-health": [
        "photo-1452626038306-9aae5e071dd3",  # 활기찬 도심 러닝크루 / 마라톤
        "photo-1476480862126-209bfaa8edc8",  # 건강한 조깅 및 워킹 운동
        "photo-1506126613408-eca07ce68773",  # 맑은 아침 건강 요가/스트레칭
        "photo-1518611012118-696072aa579a",  # 야외 피트니스 및 활력
        "photo-1540420773420-3366772f4999",  # 신선한 웰빙 건강 식단
    ],
}


class DesignerAgent:
    """
    [생활정보 24] 차세대 멀티 비주얼 썸네일 엔진
    - 대안 1: 공식 포스터/보도자료 사진 클린 렌더링 (Blur-Fit)
    - 대안 2: 토스/핀테크풍 모바일 인포그래픽 타이포 카드 (핵심 수치/체크리스트 극대화)
    - 대안 3: 키워드 매칭 감성 실사스톡 + 에디토리얼 배너
    - 대안 4: 하이브리드 (공식 포스터 + 블로그 인증 배지 & 요약 띠지 합성)
    """

    def __init__(self):
        self.client = None
        if GEMINI_API_KEY:
            try:
                from google import genai
                self.client = genai.Client(api_key=GEMINI_API_KEY)
            except Exception as e:
                print(f"[DesignerAgent] ⚠️ Gemini 초기화 실패: {e}")

    def select_mode(
        self,
        category_key: str,
        curated: dict | None = None,
        title: str = "",
        keyword: str = "",
    ) -> int:
        """
        글의 카테고리, 수집된 팩트, 포스터 URL 유무에 따라 대안 1~4 중 최적의 모드를 지능적으로 선택
        """
        curated = curated or {}
        poster_url = curated.get("poster_url") or curated.get("article_image_url")
        search_target = f"{title} {keyword} {curated.get('title', '')}"

        # 1. 공연/콘서트 카테고리
        if category_key == "concert" or any(w in search_target for w in ["콘서트", "티켓", "예매", "뮤지컬", "페스티벌"]):
            if poster_url and poster_url.startswith("http"):
                # 검증된 공식 포스터가 있으면 하이브리드 프레임(대안 4) 적용
                return 4
            # 포스터가 없으면 핵심 일정/가격을 담은 토스풍 타이포 카드(대안 2)
            return 2

        # 2. 정부 복지/지원금 카테고리
        if category_key == "welfare" or any(w in search_target for w in ["지원금", "연금", "바우처", "환급금", "장려금", "돌봄"]):
            # 복지 정책은 지원 금액과 신청 자격이 핵심이므로 토스풍 타이포 카드(대안 2)가 최상
            return 2

        # 3. 생활/건강 카테고리
        if category_key == "life-health":
            # 수치나 명확한 대상이 있는 정보는 대안 2(토스 타이포)
            if any(w in search_target for w in ["무료", "환급", "대상", "자격", "검진", "기준", "요금제", "접종"]):
                return 2
            # 일상 관리나 생활 가이드는 감성 실사스톡(대안 3)
            return 3

        # 기본값: 신뢰도 높은 토스풍 타이포 카드 (대안 2)
        return 2

    def _get_next_mode(self) -> int:
        """레거시 호환용 순환 모드 조회"""
        last_mode = 2
        try:
            if STATE_FILE.exists():
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    last_mode = data.get("last_mode", 2)
        except Exception:
            pass

        next_mode = 1 if last_mode == 2 else 2
        try:
            STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump({"last_mode": next_mode}, f)
        except Exception:
            pass
        return next_mode

    # =========================================================================
    # 대안 4: 하이브리드 (공식 포스터 + 블로그 인증 배지 & 티켓팅 띠지)
    # =========================================================================
    def _render_hybrid_poster(
        self,
        poster_url: str,
        title: str,
        category_name: str,
        curated: dict | None,
        output_path: Path,
    ):
        """실제 공식 포스터를 16:9 비율로 맞추고 상단 배지 및 하단 요약 띠지를 합성"""
        width, height = 1200, 675
        req = urllib.request.Request(
            poster_url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            img_bytes = resp.read()

        orig_img = Image.open(io.BytesIO(img_bytes)).convert("RGB")

        # 1. 배경: 포스터를 1200x675로 채우고 강한 가우시안 블러 및 틴트 적용
        bg = orig_img.resize((width, height), Image.Resampling.LANCZOS)
        bg = bg.filter(ImageFilter.GaussianBlur(radius=24))

        # 배경 어둡게 오버레이
        dim_overlay = Image.new("RGBA", (width, height), (0, 0, 0, 130))
        base = Image.alpha_composite(bg.convert("RGBA"), dim_overlay).convert("RGB")

        # 2. 전경: 포스터 원본 비율 유지하여 중앙 배치
        target_h = int(height * 0.90)  # ~607px
        scale = target_h / orig_img.height
        target_w = int(orig_img.width * scale)

        if target_w > width - 100:
            scale = (width - 100) / orig_img.width
            target_w = int(orig_img.width * scale)
            target_h = int(orig_img.height * scale)

        fg = orig_img.resize((target_w, target_h), Image.Resampling.LANCZOS)

        fg_x = (width - target_w) // 2
        fg_y = (height - target_h) // 2

        fg_shadow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        s_draw = ImageDraw.Draw(fg_shadow)
        s_draw.rectangle([fg_x - 6, fg_y - 6, fg_x + target_w + 6, fg_y + target_h + 6], fill=(0, 0, 0, 100))
        base = Image.alpha_composite(base.convert("RGBA"), fg_shadow).convert("RGB")
        base.paste(fg, (fg_x, fg_y))

        # 3. 상단 브랜드 배지 바
        top_bar = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        t_draw = ImageDraw.Draw(top_bar)

        font_badge = _load_font(20, bold=True)
        t_draw.rounded_rectangle([40, 30, 230, 72], radius=8, fill=(37, 99, 235, 245))
        t_draw.text((56, 39), "생활정보 24 PICK", font=font_badge, fill=(255, 255, 255))

        t_draw.rounded_rectangle([240, 30, 420, 72], radius=8, fill=(0, 0, 0, 180), outline=(251, 191, 36, 160), width=1)
        t_draw.text((254, 40), "공식 예매처 직결", font=font_badge, fill=(251, 191, 36))

        # 4. 하단 정보 요약 띠지 (그라데이션 스크림)
        scrim_y = height - 160
        for y in range(scrim_y, height):
            alpha = int(240 * ((y - scrim_y) / (height - scrim_y)))
            t_draw.line([(0, y), (width, y)], fill=(5, 10, 20, alpha))

        font_title = _load_font(34, bold=True)
        font_sub = _load_font(22, bold=False)

        clean_title = title.strip()
        if len(clean_title) > 32:
            clean_title = clean_title[:31] + "..."
        t_draw.text((45, height - 125), clean_title, font=font_title, fill=(255, 255, 255))

        sub_items = []
        if curated and curated.get("ticket_prices"):
            sub_items.append(f"티켓 가격: {curated['ticket_prices']}")
        else:
            sub_items.append("공식 단독 예매처 오픈")

        if curated and curated.get("temporal_verification", {}).get("expires_at"):
            sub_items.append(f"기한: ~{curated['temporal_verification']['expires_at'][:10]}")
        else:
            sub_items.append("일정 및 예매 성공 팁")

        sub_text = "  ·  ".join(sub_items)
        t_draw.text((45, height - 65), f"✓ {sub_text}", font=font_sub, fill=(147, 197, 253))

        final_img = Image.alpha_composite(base.convert("RGBA"), top_bar).convert("RGB")
        final_img.save(output_path, "JPEG", quality=95)
        print(f"[DesignerAgent] 👑 [대안 4: 하이브리드 포스터] 생성 완료: {output_path}")

    # =========================================================================
    # 대안 2: 토스풍 모바일 인포그래픽 타이포 카드
    # =========================================================================
    def _render_toss_typography(
        self,
        title: str,
        category_name: str,
        keyword: str,
        curated: dict | None,
        output_path: Path,
    ):
        """군더더기 없는 배경 위에 핵심 수치와 자격 체크리스트를 극대화한 현대적 타이포 카드"""
        width, height = 1200, 675
        curated = curated or {}

        if "공연" in category_name or "콘서트" in category_name:
            bg_start = (18, 16, 42)
            bg_end = (34, 24, 60)
            badge_bg = (245, 158, 11)
            accent_col = (251, 191, 36)
            tag_label = "2026 티켓예매"
        elif "건강" in category_name or "생활" in category_name:
            bg_start = (10, 32, 38)
            bg_end = (18, 52, 58)
            badge_bg = (14, 165, 233)
            accent_col = (56, 189, 248)
            tag_label = "생활·건강 정보"
        else:
            bg_start = (10, 24, 52)
            bg_end = (18, 44, 88)
            badge_bg = (59, 130, 246)
            accent_col = (52, 211, 153)
            tag_label = "2026 정부지원금"

        base = Image.new("RGB", (width, height))
        draw = ImageDraw.Draw(base)

        # 1. 배경 세로 그라데이션
        for y in range(height):
            ratio = y / height
            r = int(bg_start[0] * (1 - ratio) + bg_end[0] * ratio)
            g = int(bg_start[1] * (1 - ratio) + bg_end[1] * ratio)
            b = int(bg_start[2] * (1 - ratio) + bg_end[2] * ratio)
            draw.line([(0, y), (width, y)], fill=(r, g, b))

        # 2. 모던한 카드 쉘
        margin_x, margin_y = 60, 45
        card_w, card_h = width - (margin_x * 2), height - (margin_y * 2)

        card_overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        c_draw = ImageDraw.Draw(card_overlay)

        c_draw.ellipse([width - 300, -100, width + 100, 300], fill=(*badge_bg, 20))
        c_draw.ellipse([-50, height - 250, 350, height + 150], fill=(*accent_col, 15))

        c_draw.rounded_rectangle(
            [margin_x, margin_y, margin_x + card_w, margin_y + card_h],
            radius=20,
            fill=(255, 255, 255, 14),
            outline=(255, 255, 255, 45),
            width=2,
        )
        base = Image.alpha_composite(base.convert("RGBA"), card_overlay).convert("RGB")
        draw = ImageDraw.Draw(base)

        # 3. 폰트 세팅
        font_badge = _load_font(22, bold=True)
        font_brand = _load_font(20, bold=False)
        font_callout = _load_font(24, bold=False)
        font_title = _load_font(44, bold=True)
        font_highlight = _load_font(38, bold=True)
        font_bullet = _load_font(26, bold=False)

        # 4. 상단 배지 바
        pad_x = margin_x + 50
        pad_y = margin_y + 40

        badge_text = f"  {tag_label}  "
        bbox = font_badge.getbbox(badge_text)
        bw = bbox[2] - bbox[0] + 16
        bh = bbox[3] - bbox[1] + 10

        draw.rounded_rectangle([pad_x, pad_y, pad_x + bw, pad_y + bh], radius=8, fill=badge_bg)
        draw.text((pad_x + 8, pad_y + 3), badge_text, font=font_badge, fill=(255, 255, 255))
        draw.text((margin_x + card_w - 180, pad_y + 6), "생활정보 24", font=font_brand, fill=(160, 180, 205))

        # 5. 서브 콜아웃
        callout_y = pad_y + bh + 25
        callout_text = "공식 기준에 따른 핵심 요약 가이드"
        if "공연" in category_name:
            callout_text = "공식 예매처 티켓 오픈 및 일정 안내"
        elif "복지" in category_name:
            callout_text = "지원 대상자 및 신청 방법 필수 확인"
        draw.text((pad_x, callout_y), callout_text, font=font_callout, fill=(180, 200, 220))

        # 6. 메인 타이틀
        title_y = callout_y + 35
        clean_title = title.strip()
        if len(clean_title) > 26:
            clean_title = clean_title[:25] + "..."
        draw.text((pad_x, title_y), clean_title, font=font_title, fill=(255, 255, 255))

        # 7. 핵심 수치 강조 박스
        stat_box_y = title_y + 65
        stat_box_h = 75
        stat_box_w = card_w - 100

        draw.rounded_rectangle(
            [pad_x, stat_box_y, pad_x + stat_box_w, stat_box_y + stat_box_h],
            radius=12,
            fill=(0, 0, 0, 80),
            outline=(*accent_col, 100),
            width=1,
        )

        money_match = re.search(r"(\d+만\s*\d*원?|\d+,\d+원|\d+만원|최대\s*[\d,]+원)", f"{title} {curated.get('ticket_prices', '')}")
        if money_match:
            stat_text = f"★ 핵심 혜택: {money_match.group(1)} 지원/오픈"
        elif "공연" in category_name and curated.get("ticket_prices"):
            stat_text = f"★ 좌석 가격: {curated['ticket_prices']}"
        else:
            stat_text = "★ 2026년 최신 기준 반영 및 온라인 간편 신청"

        draw.text((pad_x + 25, stat_box_y + 16), stat_text, font=font_highlight, fill=accent_col)

        # 8. 체크리스트 3개 항목
        bullets_y = stat_box_y + stat_box_h + 30
        bullets = [
            "자격 요건 및 지원 대상자 기준 확인",
            "정부24 및 공식 주관처 간편 신청",
            "필수 제출 서류 및 유의사항 총정리",
        ]
        if "공연" in category_name:
            bullets = [
                "공식 단독 예매처(NOL/인터파크) 직결",
                "전 좌석 배치도 및 관람 회차 안내",
                "선예매 인증 및 티켓팅 성공 꿀팁",
            ]

        for i, b in enumerate(bullets):
            by = bullets_y + (i * 38)
            draw.text((pad_x, by), "✓", font=font_bullet, fill=accent_col)
            draw.text((pad_x + 30, by), b, font=font_bullet, fill=(225, 235, 245))

        base.save(output_path, "JPEG", quality=98)
        print(f"[DesignerAgent] 📱 [대안 2: 토스풍 타이포 카드] 생성 완료: {output_path}")

    # =========================================================================
    # 대안 3: 키워드 매칭 감성 실사스톡
    # =========================================================================
    def _render_keyword_stock(
        self,
        keyword: str,
        category_name: str,
        title: str,
        output_path: Path,
    ):
        """주제별 맞춤 실사 사진 다운로드 + 하단 에디토리얼 타이포그래피 배너"""
        width, height = 1200, 675
        theme_key = "life-health"
        if "공연" in category_name or "콘서트" in category_name:
            theme_key = "concert"
        elif "복지" in category_name:
            theme_key = "welfare"

        pool = STOCK_PHOTOS.get(theme_key, STOCK_PHOTOS["life-health"])
        chosen_id = random.choice(pool)
        url = f"https://images.unsplash.com/{chosen_id}?w=1200&h=675&fit=crop&q=85"

        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            img_bytes = resp.read()

        img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
        if img.size != (width, height):
            img = img.resize((width, height), Image.Resampling.LANCZOS)

        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        grad_y = 415
        for y in range(grad_y, height):
            alpha = int(230 * ((y - grad_y) / (height - grad_y)))
            draw.line([(0, y), (width, y)], fill=(8, 12, 24, alpha))

        font_badge = _load_font(22, bold=True)
        font_title = _load_font(38, bold=True)
        font_brand = _load_font(18, bold=False)

        badge_x, badge_y = 60, 475
        badge_text = f"  {category_name}  "
        bbox = font_badge.getbbox(badge_text)
        bw = bbox[2] - bbox[0] + 16
        bh = bbox[3] - bbox[1] + 10

        draw.rounded_rectangle([badge_x, badge_y, badge_x + bw, badge_y + bh], radius=8, fill=(16, 185, 129, 235))
        draw.text((badge_x + 8, badge_y + 3), badge_text, font=font_badge, fill=(255, 255, 255))
        draw.text((badge_x + bw + 16, badge_y + 6), "생활정보 24 공식 에디토리얼", font=font_brand, fill=(203, 213, 225))

        clean_title = title.strip()
        if len(clean_title) > 30:
            clean_title = clean_title[:29] + "..."
        draw.text((badge_x, badge_y + bh + 16), clean_title, font=font_title, fill=(255, 255, 255))

        final_img = Image.alpha_composite(img, overlay).convert("RGB")
        final_img.save(output_path, "JPEG", quality=95)
        print(f"[DesignerAgent] 🌄 [대안 3: 키워드 매칭 실사스톡] 생성 완료: {output_path}")

    # =========================================================================
    # 대안 1: 공식 포스터 클린 렌더링 (Blur-Fit)
    # =========================================================================
    def _render_clean_poster(
        self,
        poster_url: str,
        title: str,
        category_name: str,
        output_path: Path,
    ):
        """실제 공식 포스터 원본을 왜곡 없이 16:9 비율로 블러 확장하여 배치"""
        width, height = 1200, 675
        req = urllib.request.Request(poster_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            img_bytes = resp.read()

        orig = Image.open(io.BytesIO(img_bytes)).convert("RGB")

        bg = orig.resize((width, height), Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(25))
        dim = Image.new("RGBA", (width, height), (0, 0, 0, 100))
        base = Image.alpha_composite(bg.convert("RGBA"), dim).convert("RGB")

        target_h = int(height * 0.94)
        scale = target_h / orig.height
        target_w = int(orig.width * scale)
        fg = orig.resize((target_w, target_h), Image.Resampling.LANCZOS)
        base.paste(fg, ((width - target_w) // 2, (height - target_h) // 2))

        draw = ImageDraw.Draw(base)
        font_tag = _load_font(16, bold=False)
        draw.text((width - 160, height - 30), "공식 보도자료 이미지", font=font_tag, fill=(220, 220, 220))

        base.save(output_path, "JPEG", quality=95)
        print(f"[DesignerAgent] 📸 [대안 1: 클린 공식 포스터] 생성 완료: {output_path}")

    # =========================================================================
    # 메인 엔트리포인트: 자율 라우팅 및 렌더링
    # =========================================================================
    def generate_image(
        self,
        title: str,
        category_name: str,
        keyword: str,
        curated: dict | None = None,
        category_key: str = "",
    ) -> Path:
        """
        주제와 팩트에 따라 대안 1~4 중 최적의 모드를 지능적으로 선택하고,
        네트워크나 외부 에셋 문제 발생 시 대안 2(토스풍 타이포)로 무중단 안전 폴백하는 메인 엔트리포인트
        """
        h = hashlib.md5(title.encode("utf-8")).hexdigest()[:8]
        tmp_dir = Path(tempfile.gettempdir())
        output_path = tmp_dir / f"thumb_{h}.jpg"

        curated = curated or {}
        mode = self.select_mode(category_key, curated, title, keyword)
        poster_url = curated.get("poster_url") or curated.get("article_image_url")

        print(f"[DesignerAgent] 🎨 썸네일 자동 라우팅: [대안 {mode}번] 선정 (주제: '{title[:20]}...', 카테고리: {category_name})")

        # 1. 모드 4: 하이브리드 포스터
        if mode == 4 and poster_url:
            try:
                self._render_hybrid_poster(poster_url, title, category_name, curated, output_path)
                return output_path
            except Exception as e:
                print(f"[DesignerAgent] ⚠️ 하이브리드 포스터 생성 실패 ({e}) -> 대안 2(토스풍 타이포)로 안전 폴백")

        # 2. 모드 1: 클린 공식 포스터
        elif mode == 1 and poster_url:
            try:
                self._render_clean_poster(poster_url, title, category_name, output_path)
                return output_path
            except Exception as e:
                print(f"[DesignerAgent] ⚠️ 클린 포스터 생성 실패 ({e}) -> 대안 2(토스풍 타이포)로 안전 폴백")

        # 3. 모드 3: 키워드 매칭 감성 실사스톡
        elif mode == 3:
            try:
                self._render_keyword_stock(keyword, category_name, title, output_path)
                return output_path
            except Exception as e:
                print(f"[DesignerAgent] ⚠️ 실사스톡 다운로드 실패 ({e}) -> 대안 2(토스풍 타이포)로 안전 폴백")

        # 4. 모드 2 (기본 및 안전망): 토스풍 모바일 타이포 카드
        try:
            self._render_toss_typography(title, category_name, keyword, curated, output_path)
            return output_path
        except Exception as e:
            print(f"[DesignerAgent] ❌ 타이포 카드 렌더링 중 오류 ({e}), 최소 카드 저장 시도")
            img = Image.new("RGB", (1200, 675), color=(15, 23, 42))
            draw = ImageDraw.Draw(img)
            draw.text((60, 300), title[:25], fill=(255, 255, 255))
            img.save(output_path, "JPEG")
            return output_path

    # 레거시 호환 메서드
    def _render_card_image(self, card_data: dict, output_path: Path):
        title = card_data.get("main_title", "")
        category_name = card_data.get("category_badge", "")
        self._render_toss_typography(title, category_name, "", {}, output_path)

    def _generate_card_data(self, title: str, category_name: str, keyword: str) -> dict:
        return {"category_badge": category_name, "main_title": title[:22], "sub_title": "핵심 가이드", "highlights": []}

    def _download_stock_image(self, category_name: str, output_path: Path):
        theme_key = "life-health"
        if "공연" in category_name:
            theme_key = "concert"
        elif "복지" in category_name:
            theme_key = "welfare"
        chosen_id = random.choice(STOCK_PHOTOS.get(theme_key, STOCK_PHOTOS["welfare"]))
        url = f"https://images.unsplash.com/{chosen_id}?w=1200&h=675&fit=crop&q=85"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            output_path.write_bytes(resp.read())

    def _apply_editorial_banner(self, img_path: Path, category_name: str, title: str):
        pass
