from PIL import Image, ImageDraw, ImageFont
import math

def create_card_thumbnail(
    category_badge="공연 / 콘서트 예매",
    main_title="연세유업 부모님 효도 이벤트",
    sub_title="트로트 콘서트 티켓 증정 & 예매 꿀팁",
    highlights=["신청 대상: 연세유업 구매 고객", "주요 혜택: 콘서트 티켓 무료 증정", "티켓팅 실전 성공 가이드 총정리"],
    theme="concert", # concert, welfare, health
    output_path="/tmp/sample_card_thumb.jpg"
):
    width, height = 1200, 675
    
    # 테마별 프리미엄 그라데이션 컬러 정의
    if theme == "concert":
        start_color = (20, 24, 55)   # 딥 미드나잇 네이비
        end_color = (68, 30, 95)     # 럭셔리 바이올렛
        badge_bg = (245, 158, 11)    # 앰버 골드
        badge_fg = (255, 255, 255)
        accent_color = (251, 191, 36) # 골드 옐로우
    elif theme == "welfare":
        start_color = (15, 35, 75)   # 딥 사파이어 블루
        end_color = (30, 64, 120)    # 로열 오션 블루
        badge_bg = (59, 130, 246)    # 비비드 블루
        badge_fg = (255, 255, 255)
        accent_color = (147, 197, 253) # 소프트 스카이
    else: # health
        start_color = (6, 78, 59)     # 딥 에메랄드
        end_color = (16, 125, 85)    # 포레스트 그린
        badge_bg = (16, 185, 129)    # 민트 에메랄드
        badge_fg = (255, 255, 255)
        accent_color = (110, 231, 183)

    # 1. 배경 그라데이션 렌더링
    base = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(base)
    
    for y in range(height):
        ratio = y / height
        r = int(start_color[0] * (1 - ratio) + end_color[0] * ratio)
        g = int(start_color[1] * (1 - ratio) + end_color[1] * ratio)
        b = int(start_color[2] * (1 - ratio) + end_color[2] * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    # 2. 부드러운 배경 디자인 악센트 (원형 글로우 효과)
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    o_draw = ImageDraw.Draw(overlay)
    o_draw.ellipse([width - 350, -100, width + 250, 500], fill=(255, 255, 255, 12))
    o_draw.ellipse([width - 250, 200, width + 400, 750], fill=(badge_bg[0], badge_bg[1], badge_bg[2], 25))
    o_draw.ellipse([-150, height - 300, 300, height + 150], fill=(255, 255, 255, 8))
    
    base = Image.alpha_composite(base.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(base)

    # 3. 폰트 로드
    font_bold_path = "/usr/share/fonts/truetype/nanum/NanumSquareB.ttf"
    font_regular_path = "/usr/share/fonts/truetype/nanum/NanumSquareR.ttf"
    
    font_badge = ImageFont.truetype(font_bold_path, 26)
    font_title = ImageFont.truetype(font_bold_path, 54)
    font_subtitle = ImageFont.truetype(font_bold_path, 42)
    font_hl = ImageFont.truetype(font_bold_path, 28)
    font_brand = ImageFont.truetype(font_bold_path, 22)

    # 4. 카드 컨테이너 라운딩 박스 (미려한 글래스모피즘 효과)
    card_margin_x = 70
    card_margin_y = 50
    card_w = width - (card_margin_x * 2)
    card_h = height - (card_margin_y * 2)
    
    card_overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    c_draw = ImageDraw.Draw(card_overlay)
    c_draw.rounded_rectangle(
        [card_margin_x, card_margin_y, card_margin_x + card_w, card_margin_y + card_h],
        radius=24,
        fill=(255, 255, 255, 18),
        outline=(255, 255, 255, 60),
        width=2
    )
    base = Image.alpha_composite(base.convert("RGBA"), card_overlay).convert("RGB")
    draw = ImageDraw.Draw(base)

    # 5. 카테고리 뱃지 그리기
    badge_x = card_margin_x + 50
    badge_y = card_margin_y + 45
    badge_bbox = font_badge.getbbox(category_badge)
    badge_text_w = badge_bbox[2] - badge_bbox[0]
    badge_text_h = badge_bbox[3] - badge_bbox[1]
    
    padding_x, padding_y = 20, 10
    draw.rounded_rectangle(
        [badge_x, badge_y, badge_x + badge_text_w + (padding_x * 2), badge_y + badge_text_h + (padding_y * 2) + 4],
        radius=14,
        fill=badge_bg
    )
    draw.text((badge_x + padding_x, badge_y + padding_y - 2), category_badge, font=font_badge, fill=badge_fg)

    # 6. 메인 타이틀
    title_y = badge_y + 65
    draw.text((badge_x, title_y), main_title, font=font_title, fill=(255, 255, 255))
    
    # 7. 서브 타이틀 (골드/액센트 컬러)
    sub_y = title_y + 75
    draw.text((badge_x, sub_y), sub_title, font=font_subtitle, fill=accent_color)

    # 8. 구분선
    line_y = sub_y + 65
    draw.line([(badge_x, line_y), (card_margin_x + card_w - 50, line_y)], fill=(255, 255, 255, 70), width=1)

    # 9. 핵심 체크포인트 3개 (아이콘 뱃지 스타일)
    hl_y = line_y + 30
    for idx, hl in enumerate(highlights):
        item_y = hl_y + (idx * 48)
        # 세련된 원형 불릿 포인트
        bullet_r = 6
        draw.ellipse([badge_x + 6, item_y + 8, badge_x + 6 + (bullet_r * 2), item_y + 8 + (bullet_r * 2)], fill=accent_color)
        # 텍스트
        draw.text((badge_x + 28, item_y), hl, font=font_hl, fill=(240, 244, 248))

    # 10. 하단 블로그 브랜딩 바
    brand_text = "생활정보 24 | 알기 쉬운 대한민국 생활·복지·공연 가이드"
    draw.text((card_margin_x + 50, card_margin_y + card_h - 45), brand_text, font=font_brand, fill=(180, 195, 210))

    # 저장
    base.save(output_path, "JPEG", quality=98)
    print(f"Card thumbnail successfully created at {output_path}")

if __name__ == "__main__":
    create_card_thumbnail()
