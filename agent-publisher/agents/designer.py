import hashlib
import io
import random
import sys
import tempfile
import urllib.request
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from config import GEMINI_API_KEY

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


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


def split_title(text: str, max_first_line: int = 22) -> list[str]:
    """문맥(쉼표, 및, 괄호, 어절 균형)에 따라 제목을 1~2줄로 자연스럽게 분할 (말줄임표 절대 금지)"""
    text = text.strip()
    if len(text) <= max_first_line:
        return [text]

    # 1. 쉼표 기준 분할
    if ", " in text:
        parts = text.split(", ", 1)
        if 10 <= len(parts[0]) <= 28 and len(parts[1]) <= 34:
            return [parts[0] + ",", parts[1]]

    # 2. ' 및 ' 기준 분할
    if " 및 " in text:
        idx = text.find(" 및 ")
        before = text[:idx].strip()
        after = text[idx + 1:].strip()
        if 12 <= len(before) <= 24 and len(after) <= 30:
            return [before, after]

    # 3. 괄호 기준 분할
    if " (" in text:
        parts = text.split(" (", 1)
        if 15 <= len(parts[0]) <= 32 and len(parts[1]) <= 32:
            return [parts[0], "(" + parts[1]]

    # 4. 어절 단위 최적 중간 분할
    words = text.split()
    best_split = len(words) // 2
    min_diff = 999
    for i in range(1, len(words)):
        l1 = " ".join(words[:i])
        l2 = " ".join(words[i:])
        if len(l1) > 28:
            continue
        diff = abs(len(l1) - len(l2))
        if diff < min_diff:
            min_diff = diff
            best_split = i
    l1 = " ".join(words[:best_split])
    l2 = " ".join(words[best_split:])
    return [l1, l2] if l2 else [l1]


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
    "tax": [
        "photo-1554224155-6726b3ff858f",  # 세금 계산기 및 서류
        "photo-1554224154-26032ffc0d07",  # 세무 신고 서류 및 펜
        "photo-1559526324-4b87b5e36e44",  # 재정 분석 및 절세 계획
        "photo-1579621970563-ebec7560ff3e",  # 세액공제 및 환급 저축
        "photo-1450133064473-71024230f91b",  # 금융 자산 및 세금 안내
    ],
}


class DesignerAgent:
    """
    [생활정보 24] 차세대 멀티 비주얼 썸네일 엔진
    - 대안 1: 별도 검토된 포스터 사진 클린 렌더링 (Blur-Fit)
    - 대안 2: 제목 중심 모바일 타이포 카드
    - 대안 3: 키워드 매칭 감성 실사스톡 + 에디토리얼 배너
    - 대안 4: 하이브리드 (별도 검토된 포스터 + 브랜드와 제목 합성)
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
        reviewed_poster_url: str | None = None,
    ) -> int:
        """
        제목/카테고리 및 별도 검토된 포스터 유무에 따라 렌더링 방식 선택.
        curated 안의 이미지 주소나 자체 검토 표식은 출처 검증으로 취급하지 않는다.
        """
        search_target = title

        # 1. 공연/콘서트 카테고리
        if category_key == "concert" or any(w in search_target for w in ["콘서트", "티켓", "예매", "뮤지컬", "페스티벌"]):
            if reviewed_poster_url and reviewed_poster_url.startswith(("https://", "http://")):
                # 포스터 이미지가 있으면 하이브리드 프레임(대안 4) 적용
                return 4
            # 포스터가 없으면 제목 중심의 타이포 카드(대안 2)
            return 2

        # 2. 정부 복지/지원금 카테고리
        if category_key == "welfare" or any(w in search_target for w in ["지원금", "연금", "바우처", "환급금", "장려금", "돌봄"]):
            # 복지 정책은 지원 금액과 신청 자격이 핵심이므로 토스풍 타이포 카드(대안 2)가 최상
            return 2

        # 3. 생활/건강 카테고리
        if category_key == "life-health":
            # 수치나 명확한 대상/의료·비상 정보는 대안 2(토스 타이포)
            if any(w in search_target for w in ["무료", "환급", "대상", "자격", "검진", "기준", "요금제", "접종", "병원", "약국", "응급", "진료", "의료", "비상", "소아", "연휴", "명절", "추석", "설날", "통행료", "고속도로", "하이패스"]):
                return 2
            # 일상 관리나 생활 가이드는 감성 실사스톡(대안 3)
            return 3

        # 4. 생활 세금/절세 카테고리
        if category_key == "tax" or any(w in search_target for w in ["세금", "절세", "연말정산", "종합소득세", "자동차세", "환급금", "소득공제", "세액공제"]):
            # 세금/환급 정보는 환급액, 공제 항목, 신청 기한이 핵심이므로 토스풍 타이포 카드(대안 2)가 최상
            return 2

        # 기본값: 신뢰도 높은 토스풍 타이포 카드 (대안 2)
        return 2

    # =========================================================================
    # 대안 4: 하이브리드 (검토된 포스터 + 브랜드 및 제목)
    # =========================================================================
    def _render_hybrid_poster(
        self,
        poster_url: str,
        title: str,
        category_name: str,
        curated: dict | None,
        output_path: Path,
    ):
        """제공된 포스터를 16:9 비율로 맞추고 제목과 브랜드만 합성."""
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
        t_draw.text((56, 39), "생활정보 24", font=font_badge, fill=(255, 255, 255))

        # 4. 하단 정보 요약 띠지 (그라데이션 스크림)
        scrim_y = height - 160
        for y in range(scrim_y, height):
            alpha = int(240 * ((y - scrim_y) / (height - scrim_y)))
            t_draw.line([(0, y), (width, y)], fill=(5, 10, 20, alpha))

        lines = split_title(title.strip())
        max_l = max(len(l) for l in lines)
        if len(lines) == 1:
            font_title = _load_font(34 if max_l <= 24 else 30, bold=True)
            t_draw.text((45, height - 120), lines[0], font=font_title, fill=(255, 255, 255))
        else:
            font_title = _load_font(28 if max_l <= 24 else 25, bold=True)
            t_draw.text((45, height - 138), lines[0], font=font_title, fill=(255, 255, 255))
            t_draw.text((45, height - 104), lines[1], font=font_title, fill=(255, 255, 255))

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
        """제목과 카테고리만 표기하는 타이포 카드."""
        width, height = 1200, 675
        combined_text = f"{title} {category_name}"

        # 0. 카테고리 및 주제별 테마 색상 & 태그 라벨 결정
        if "공연" in category_name or "콘서트" in category_name or any(w in combined_text for w in ["콘서트", "티켓", "예매", "뮤지컬"]):
            bg_start = (18, 16, 42)
            bg_end = (34, 24, 60)
            badge_bg = (245, 158, 11)
            accent_col = (251, 191, 36)
        elif any(w in combined_text for w in ["통행료", "고속도로", "하이패스", "교통"]):
            bg_start = (12, 28, 46)
            bg_end = (20, 48, 76)
            badge_bg = (14, 165, 233)
            accent_col = (56, 189, 248)
        elif any(w in combined_text for w in ["병원", "약국", "응급", "진료", "의료", "달빛어린이"]):
            bg_start = (8, 36, 40)
            bg_end = (16, 56, 62)
            badge_bg = (13, 148, 136)
            accent_col = (45, 212, 191)
        elif "세금" in category_name or "절세" in category_name or any(w in combined_text for w in ["재산세", "세금", "절세", "세액공제"]):
            bg_start = (6, 32, 28)
            bg_end = (12, 54, 46)
            badge_bg = (16, 185, 129)
            accent_col = (52, 211, 153)
        elif any(w in combined_text for w in ["환급금", "미환급금"]):
            bg_start = (10, 30, 44)
            bg_end = (18, 50, 72)
            badge_bg = (14, 165, 233)
            accent_col = (56, 189, 248)
        elif any(w in combined_text for w in ["근로장려금", "자녀장려금", "장려금"]):
            bg_start = (10, 26, 50)
            bg_end = (18, 46, 84)
            badge_bg = (59, 130, 246)
            accent_col = (96, 165, 250)
        elif "복지" in category_name or any(w in combined_text for w in ["기초연금", "바우처", "지원금"]):
            bg_start = (10, 24, 52)
            bg_end = (18, 44, 88)
            badge_bg = (59, 130, 246)
            accent_col = (52, 211, 153)
        else:
            bg_start = (12, 28, 44)
            bg_end = (20, 46, 70)
            badge_bg = (14, 165, 233)
            accent_col = (56, 189, 248)

        tag_label = category_name or "생활정보 24"

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
        margin_x, margin_y = 60, 42
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
        font_badge = _load_font(21, bold=True)
        font_brand = _load_font(20, bold=False)

        # 4. 상단 배지 바
        pad_x = margin_x + 50
        pad_y = margin_y + 36

        badge_text = f"  {tag_label}  "
        bbox = font_badge.getbbox(badge_text)
        bw = bbox[2] - bbox[0] + 16
        bh = bbox[3] - bbox[1] + 10

        draw.rounded_rectangle([pad_x, pad_y, pad_x + bw, pad_y + bh], radius=8, fill=badge_bg)
        draw.text((pad_x + 8, pad_y + 3), badge_text, font=font_badge, fill=(255, 255, 255))
        draw.text((margin_x + card_w - 180, pad_y + 6), "생활정보 24", font=font_brand, fill=(160, 180, 205))

        # Use only the reviewed article title and category. Curator hints and
        # keyword matches do not establish ticket, benefit, deadline or source facts.
        title_lines = split_title(title.strip() or "생활정보 24")
        longest = max(map(len, title_lines))
        font_size = 46 if longest <= 18 else 35 if longest <= 25 else 29
        font_title = _load_font(font_size, bold=True)
        title_y = pad_y + 135
        for i, line in enumerate(title_lines):
            draw.text((pad_x, title_y + i * (font_size + 17)), line, font=font_title, fill=(255, 255, 255))

        # Nonverbal accents leave the lower area clear of unsupported claims.
        draw.rounded_rectangle([pad_x, height - 164, pad_x + 170, height - 156], radius=4, fill=accent_col)
        draw.line([(pad_x, height - 128), (pad_x + card_w - 100, height - 128)], fill=(160, 180, 205), width=2)

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
        elif "세금" in category_name or "절세" in category_name:
            theme_key = "tax"

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
        draw.text((badge_x + bw + 16, badge_y + 6), "생활정보 24", font=font_brand, fill=(203, 213, 225))

        title_lines = split_title(title.strip())
        max_line_len = max(len(l) for l in title_lines)
        if len(title_lines) == 1:
            font_title = _load_font(36 if max_line_len <= 20 else 32, bold=True)
            draw.text((badge_x, badge_y + bh + 16), title_lines[0], font=font_title, fill=(255, 255, 255))
        else:
            font_title = _load_font(30 if max_line_len <= 24 else 26, bold=True)
            line_h = 38 if max_line_len <= 24 else 34
            for i, line in enumerate(title_lines):
                draw.text((badge_x, badge_y + bh + 14 + (i * line_h)), line, font=font_title, fill=(255, 255, 255))

        final_img = Image.alpha_composite(img, overlay).convert("RGB")
        final_img.save(output_path, "JPEG", quality=95)
        print(f"[DesignerAgent] 🌄 [대안 3: 키워드 매칭 실사스톡] 생성 완료: {output_path}")

    # =========================================================================
    # 대안 1: 검토된 포스터 클린 렌더링 (Blur-Fit)
    # =========================================================================
    def _render_clean_poster(
        self,
        poster_url: str,
        title: str,
        category_name: str,
        output_path: Path,
    ):
        """제공된 포스터 원본을 16:9 비율로 블러 확장하여 배치."""
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

        base.save(output_path, "JPEG", quality=95)
        print(f"[DesignerAgent] 📸 [대안 1: 클린 포스터] 생성 완료: {output_path}")

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
        reviewed_poster_url: str | None = None,
    ) -> Path:
        """
        기본은 제목·카테고리만 출력한다. 독립 검토한 이미지 주소를 별도 인자로
        전달한 경우에만 포스터를 사용하며 네트워크 실패 시 타이포로 폴백한다.
        """
        h = hashlib.md5(title.encode("utf-8")).hexdigest()[:8]
        tmp_dir = Path(tempfile.gettempdir())
        output_path = tmp_dir / f"thumb_{h}.jpg"

        mode = self.select_mode(category_key, curated, title, keyword, reviewed_poster_url)
        poster_url = reviewed_poster_url

        print(f"[DesignerAgent] 🎨 썸네일 자동 라우팅: [대안 {mode}번] 선정 (주제: '{title[:20]}...', 카테고리: {category_name})")

        # 1. 모드 4: 하이브리드 포스터
        if mode == 4 and poster_url:
            try:
                self._render_hybrid_poster(poster_url, title, category_name, curated, output_path)
                return output_path
            except Exception as e:
                print(f"[DesignerAgent] ⚠️ 하이브리드 포스터 생성 실패 ({e}) -> 대안 2(토스풍 타이포)로 안전 폴백")

        # 2. 모드 1: 클린 포스터
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
            for index, line in enumerate(split_title(title.strip() or "생활정보 24")):
                draw.text((60, 275 + index * 50), line, fill=(255, 255, 255))
            img.save(output_path, "JPEG")
            return output_path
