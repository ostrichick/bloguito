import os
import json
import hashlib
import random
import urllib.request
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from config import GEMINI_API_KEY

FONT_BOLD = "/usr/share/fonts/truetype/nanum/NanumSquareB.ttf"
FONT_REGULAR = "/usr/share/fonts/truetype/nanum/NanumSquareR.ttf"
STATE_FILE = Path(__file__).parent.parent / "data" / "designer_state.json"

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
    [생활정보 24] 차세대 디자이너 에이전트
    - 모드 1: 초고해상도 타이포그래피 인포그래픽 카드뉴스 (Pillow + NanumSquare)
    - 모드 2: 4K 고화질 실사 스톡 사진 + 매거진 에디토리얼 타이포그래피 배너 오버레이
    -> 두 모드를 번갈아가며 자동 교차 생성하여 시각적 다양성 및 검색 클릭률(CTR) 극대화
    """

    def __init__(self):
        self.client = None
        if GEMINI_API_KEY:
            try:
                from google import genai
                self.client = genai.Client(api_key=GEMINI_API_KEY)
                print("[DesignerAgent] 🎨 디자이너 에이전트 준비 완료 (카드뉴스 & 실사 스톡 듀얼 엔진)")
            except Exception as e:
                print(f"[DesignerAgent] ⚠️ Gemini 초기화 실패: {e}")

    def _get_next_mode(self) -> int:
        """이전 발행 모드를 조회하여 1(카드뉴스)과 2(실사스톡)를 번갈아가며 교차 반환"""
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
        except Exception as e:
            print(f"[DesignerAgent] 상태 저장 실패: {e}")

        return next_mode

    def _generate_card_data(self, title: str, category_name: str, keyword: str) -> dict:
        """Gemini 3.6 Flash를 통해 카드뉴스용 정밀 3줄 요약 및 헤드라인 추출"""
        theme = "welfare"
        if "공연" in category_name or "콘서트" in category_name:
            theme = "concert"
        elif "건강" in category_name or "생활" in category_name:
            theme = "health"

        if not self.client:
            return {
                "category_badge": category_name,
                "main_title": title[:22],
                "sub_title": "핵심 신청 자격 및 일정 가이드",
                "highlights": ["상세 자격 요건 및 대상 확인", "공식 절차에 따른 온라인 접수", "주의사항 및 필수 서류 총정리"],
                "theme": theme,
            }

        prompt = f"""
당신은 대한민국 1등 정보 블로그 카드뉴스 수석 에디터입니다.
아래 글의 핵심을 모바일에서 단 1초 만에 파악할 수 있는 카드뉴스 썸네일 카피를 작성해 주세요.

[글 정보]
- 카테고리: {category_name}
- 키워드: {keyword}
- 제목: {title}

[작성 규칙 - 반드시 엄수]
1. main_title: 가장 중요한 핵심 주제 (최대 18자 이내, 간결하고 명확하게)
2. sub_title: 세부 핵심 내용 요약 (최대 24자 이내)
3. highlights: 독자가 가장 궁금해할 핵심 정보 3개 배열 (각 항목 22자 이내, 완전한 문장이 아닌 개조식 명사형 종결)
4. 오직 아래 JSON 포맷으로만 응답하세요:
{{
    "category_badge": "{category_name}",
    "main_title": "핵심 큰 제목",
    "sub_title": "부제목",
    "highlights": [
        "포인트 1",
        "포인트 2",
        "포인트 3"
    ],
    "theme": "{theme}"
}}
"""
        import time
        models_to_try = ["gemini-flash-latest", "gemini-3.5-flash"]
        for model_name in models_to_try:
            try:
                res = self.client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
                raw = res.text.strip()
                if "```json" in raw:
                    raw = raw.split("```json")[1].split("```")[0].strip()
                elif "```" in raw:
                    raw = raw.split("```")[1].split("```")[0].strip()
                return json.loads(raw)
            except Exception as e:
                err_str = str(e)
                print(f"[DesignerAgent] ⚠️ {model_name} 카드 데이터 생성 실패 ({err_str[:80]}), 대체 시도...")
                time.sleep(1)

        print("[DesignerAgent] 카드 데이터 기본 템플릿 사용")
        return {
            "category_badge": category_name,
            "main_title": title[:20],
            "sub_title": "핵심 신청 자격 및 일정 안내",
            "highlights": ["주요 지원 혜택 및 신청 요건", "공식 홈페이지 온라인 접수", "실전 단계별 필수 팁 총정리"],
            "theme": theme,
        }

    def _render_card_image(self, card_data: dict, output_path: Path):
        """Pillow로 나눔스퀘어 폰트 기반 1200x675 초고화질 인포그래픽 카드 렌더링"""
        width, height = 1200, 675
        theme = card_data.get("theme", "welfare")

        if theme == "concert":
            start_color = (20, 24, 55)
            end_color = (68, 30, 95)
            badge_bg = (245, 158, 11)
            badge_fg = (255, 255, 255)
            accent_color = (251, 191, 36)
        elif theme == "welfare":
            start_color = (15, 35, 75)
            end_color = (30, 64, 120)
            badge_bg = (59, 130, 246)
            badge_fg = (255, 255, 255)
            accent_color = (147, 197, 253)
        else:
            start_color = (6, 78, 59)
            end_color = (16, 125, 85)
            badge_bg = (16, 185, 129)
            badge_fg = (255, 255, 255)
            accent_color = (110, 231, 183)

        # 1. 배경 그라데이션
        base = Image.new("RGB", (width, height))
        draw = ImageDraw.Draw(base)
        for y in range(height):
            ratio = y / height
            r = int(start_color[0] * (1 - ratio) + end_color[0] * ratio)
            g = int(start_color[1] * (1 - ratio) + end_color[1] * ratio)
            b = int(start_color[2] * (1 - ratio) + end_color[2] * ratio)
            draw.line([(0, y), (width, y)], fill=(r, g, b))

        # 2. 부드러운 배경 원형 악센트
        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        o_draw = ImageDraw.Draw(overlay)
        o_draw.ellipse([width - 350, -100, width + 250, 500], fill=(255, 255, 255, 12))
        o_draw.ellipse([width - 250, 200, width + 400, 750], fill=(badge_bg[0], badge_bg[1], badge_bg[2], 25))
        o_draw.ellipse([-150, height - 300, 300, height + 150], fill=(255, 255, 255, 8))
        base = Image.alpha_composite(base.convert("RGBA"), overlay).convert("RGB")
        draw = ImageDraw.Draw(base)

        # 3. 폰트 로드
        font_badge = ImageFont.truetype(FONT_BOLD, 26)
        font_title = ImageFont.truetype(FONT_BOLD, 52)
        font_subtitle = ImageFont.truetype(FONT_BOLD, 40)
        font_hl = ImageFont.truetype(FONT_BOLD, 28)
        font_brand = ImageFont.truetype(FONT_BOLD, 22)

        # 4. 카드 컨테이너
        card_margin_x, card_margin_y = 70, 50
        card_w, card_h = width - (card_margin_x * 2), height - (card_margin_y * 2)
        card_overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        c_draw = ImageDraw.Draw(card_overlay)
        c_draw.rounded_rectangle(
            [card_margin_x, card_margin_y, card_margin_x + card_w, card_margin_y + card_h],
            radius=24, fill=(255, 255, 255, 18), outline=(255, 255, 255, 60), width=2
        )
        base = Image.alpha_composite(base.convert("RGBA"), card_overlay).convert("RGB")
        draw = ImageDraw.Draw(base)

        # 5. 카테고리 뱃지
        badge_text = card_data.get("category_badge", "생활정보")
        badge_x, badge_y = card_margin_x + 50, card_margin_y + 45
        bbox = font_badge.getbbox(badge_text)
        bw, bh = bbox[2] - bbox[0], bbox[3] - bbox[1]
        px, py = 20, 10
        draw.rounded_rectangle([badge_x, badge_y, badge_x + bw + (px * 2), badge_y + bh + (py * 2) + 4], radius=14, fill=badge_bg)
        draw.text((badge_x + px, badge_y + py - 2), badge_text, font=font_badge, fill=badge_fg)

        # 6. 메인 타이틀 & 서브 타이틀
        title_text = card_data.get("main_title", "")
        title_y = badge_y + 65
        draw.text((badge_x, title_y), title_text, font=font_title, fill=(255, 255, 255))

        sub_text = card_data.get("sub_title", "")
        sub_y = title_y + 72
        draw.text((badge_x, sub_y), sub_text, font=font_subtitle, fill=accent_color)

        # 7. 구분선
        line_y = sub_y + 65
        draw.line([(badge_x, line_y), (card_margin_x + card_w - 50, line_y)], fill=(255, 255, 255, 70), width=1)

        # 8. 핵심 체크포인트 3개
        hl_y = line_y + 30
        highlights = card_data.get("highlights", [])[:3]
        for idx, hl in enumerate(highlights):
            item_y = hl_y + (idx * 48)
            bullet_r = 6
            draw.ellipse([badge_x + 6, item_y + 8, badge_x + 6 + (bullet_r * 2), item_y + 8 + (bullet_r * 2)], fill=accent_color)
            draw.text((badge_x + 28, item_y), hl, font=font_hl, fill=(240, 244, 248))

        # 9. 하단 브랜딩 바
        brand_text = "생활정보 24 | 알기 쉬운 대한민국 생활·복지·공연 가이드"
        draw.text((card_margin_x + 50, card_margin_y + card_h - 45), brand_text, font=font_brand, fill=(180, 195, 210))

        base.save(output_path, "JPEG", quality=98)
        print(f"[DesignerAgent] 💎 [모드 1: 카드뉴스] 초고화질 썸네일 생성 완료: {output_path}")

    def _download_stock_image(self, category_name: str, output_path: Path):
        """라이브러리에서 4K 실사 스톡 사진 선별 다운로드"""
        theme_key = "welfare"
        if "공연" in category_name or "콘서트" in category_name:
            theme_key = "concert"
        elif "건강" in category_name or "생활" in category_name:
            theme_key = "life-health"

        photo_pool = STOCK_PHOTOS.get(theme_key, STOCK_PHOTOS["welfare"])
        chosen_id = random.choice(photo_pool)
        url = f"https://images.unsplash.com/{chosen_id}?w=1200&h=675&fit=crop&q=85"

        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as resp:
            with open(output_path, "wb") as f:
                f.write(resp.read())

        print(f"[DesignerAgent] 📸 [모드 2: 실사스톡] 4K 실사 썸네일 다운로드 완료 ({chosen_id}): {output_path}")

    def _apply_editorial_banner(self, img_path: Path, category_name: str, title: str):
        """실사 스톡 사진 하단에 세련된 반투명 다크 그라데이션 및 매거진 타이포그래피 배너 합성"""
        try:
            img = Image.open(img_path).convert("RGBA")
            if img.size != (1200, 675):
                img = img.resize((1200, 675), Image.Resampling.LANCZOS)

            overlay = Image.new("RGBA", (1200, 675), (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)

            # 하단 245px 부드러운 다크 그라데이션
            gradient_start_y = 430
            for y in range(gradient_start_y, 675):
                progress = (y - gradient_start_y) / (675 - gradient_start_y)
                alpha = int(225 * progress)
                draw.line([(0, y), (1200, y)], fill=(10, 15, 30, alpha))

            # 폰트 로드
            try:
                font_badge = ImageFont.truetype(FONT_BOLD, 22)
                font_title = ImageFont.truetype(FONT_BOLD, 38)
                font_brand = ImageFont.truetype(FONT_REGULAR, 18)
            except Exception:
                font_badge = ImageFont.load_default()
                font_title = ImageFont.load_default()
                font_brand = ImageFont.load_default()

            theme_color = (37, 99, 235)  # welfare blue
            if "공연" in category_name or "콘서트" in category_name:
                theme_color = (217, 119, 6)  # concert amber
            elif "건강" in category_name or "생활" in category_name:
                theme_color = (16, 185, 129)  # health green

            badge_text = f"  {category_name}  "
            badge_x = 60
            badge_y = 480
            badge_bbox = font_badge.getbbox(badge_text)
            badge_w = badge_bbox[2] - badge_bbox[0] + 16
            badge_h = badge_bbox[3] - badge_bbox[1] + 12

            draw.rounded_rectangle(
                [badge_x, badge_y, badge_x + badge_w, badge_y + badge_h],
                radius=8,
                fill=(*theme_color, 240),
            )
            draw.text((badge_x + 8, badge_y + 4), badge_text, font=font_badge, fill=(255, 255, 255))

            # 브랜딩 라벨
            draw.text((badge_x + badge_w + 16, badge_y + 6), "생활정보 24 공식 가이드", font=font_brand, fill=(203, 213, 225))

            # 메인 타이틀 (최대 30자)
            clean_title = title.strip()
            if len(clean_title) > 30:
                clean_title = clean_title[:29] + "..."
            draw.text((badge_x, badge_y + badge_h + 14), clean_title, font=font_title, fill=(255, 255, 255))

            final_img = Image.alpha_composite(img, overlay).convert("RGB")
            final_img.save(img_path, "JPEG", quality=95)
            print(f"[DesignerAgent] ✨ [모드 2: 실사스톡] 매거진 에디토리얼 타이포그래피 배너 합성 완료!")
        except Exception as e:
            print(f"[DesignerAgent] ⚠️ 실사 배너 합성 실패 (원문 사진 유지): {e}")

    def generate_image(self, title: str, category_name: str, keyword: str) -> Path:
        """1번(카드뉴스)과 2번(실사스톡)을 자율 교차 생성하는 메인 엔트리포인트"""
        h = hashlib.md5(title.encode("utf-8")).hexdigest()[:8]
        mode = self._get_next_mode()

        if mode == 1:
            output_path = Path(f"/tmp/card_{h}.jpg")
            print(f"[DesignerAgent] 🎨 [모드 1: 카드뉴스 인포그래픽] 생성 시작: {title}")
            card_data = self._generate_card_data(title, category_name, keyword)
            self._render_card_image(card_data, output_path)
            return output_path
        else:
            output_path = Path(f"/tmp/stock_{h}.jpg")
            print(f"[DesignerAgent] 📷 [모드 2: 고화질 실사 스톡 사진] 생성 시작: {category_name}")
            try:
                self._download_stock_image(category_name, output_path)
                self._apply_editorial_banner(output_path, category_name, title)
                return output_path
            except Exception as e:
                print(f"[DesignerAgent] 실사 사진 다운로드 실패({e}), 카드뉴스로 대체 생성")
                card_data = self._generate_card_data(title, category_name, keyword)
                self._render_card_image(card_data, output_path)
                return output_path
