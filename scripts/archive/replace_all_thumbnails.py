import os
import subprocess
import urllib.request
from PIL import Image, ImageDraw, ImageFont

UPLOADS_DIR = "/var/lib/docker/volumes/wordpress_wp_data/_data/wp-content/uploads/2026/09"
FONT_BOLD = "/usr/share/fonts/truetype/nanum/NanumSquareB.ttf"
FONT_REGULAR = "/usr/share/fonts/truetype/nanum/NanumSquareR.ttf"

def create_card_thumbnail(category_badge, main_title, sub_title, highlights, theme, output_path):
    width, height = 1200, 675
    
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

    base = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(base)
    for y in range(height):
        ratio = y / height
        r = int(start_color[0] * (1 - ratio) + end_color[0] * ratio)
        g = int(start_color[1] * (1 - ratio) + end_color[1] * ratio)
        b = int(start_color[2] * (1 - ratio) + end_color[2] * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    o_draw = ImageDraw.Draw(overlay)
    o_draw.ellipse([width - 350, -100, width + 250, 500], fill=(255, 255, 255, 12))
    o_draw.ellipse([width - 250, 200, width + 400, 750], fill=(badge_bg[0], badge_bg[1], badge_bg[2], 25))
    o_draw.ellipse([-150, height - 300, 300, height + 150], fill=(255, 255, 255, 8))
    base = Image.alpha_composite(base.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(base)

    font_badge = ImageFont.truetype(FONT_BOLD, 26)
    font_title = ImageFont.truetype(FONT_BOLD, 52)
    font_subtitle = ImageFont.truetype(FONT_BOLD, 40)
    font_hl = ImageFont.truetype(FONT_BOLD, 28)
    font_brand = ImageFont.truetype(FONT_BOLD, 22)

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

    # 카테고리 뱃지
    badge_x, badge_y = card_margin_x + 50, card_margin_y + 45
    bbox = font_badge.getbbox(category_badge)
    bw, bh = bbox[2] - bbox[0], bbox[3] - bbox[1]
    px, py = 20, 10
    draw.rounded_rectangle([badge_x, badge_y, badge_x + bw + (px * 2), badge_y + bh + (py * 2) + 4], radius=14, fill=badge_bg)
    draw.text((badge_x + px, badge_y + py - 2), category_badge, font=font_badge, fill=badge_fg)

    # 타이틀
    title_y = badge_y + 65
    draw.text((badge_x, title_y), main_title, font=font_title, fill=(255, 255, 255))

    # 서브타이틀
    sub_y = title_y + 72
    draw.text((badge_x, sub_y), sub_title, font=font_subtitle, fill=accent_color)

    # 구분선
    line_y = sub_y + 65
    draw.line([(badge_x, line_y), (card_margin_x + card_w - 50, line_y)], fill=(255, 255, 255, 70), width=1)

    # 핵심 포인트
    hl_y = line_y + 30
    for idx, hl in enumerate(highlights):
        item_y = hl_y + (idx * 48)
        bullet_r = 6
        draw.ellipse([badge_x + 6, item_y + 8, badge_x + 6 + (bullet_r * 2), item_y + 8 + (bullet_r * 2)], fill=accent_color)
        draw.text((badge_x + 28, item_y), hl, font=font_hl, fill=(240, 244, 248))

    brand_text = "생활정보 24 | 알기 쉬운 대한민국 생활·복지·공연 가이드"
    draw.text((card_margin_x + 50, card_margin_y + card_h - 45), brand_text, font=font_brand, fill=(180, 195, 210))

    base.save(output_path, "JPEG", quality=98)
    print(f"Created card thumbnail: {output_path}")

def download_stock_photo(photo_id, output_path):
    url = f"https://images.unsplash.com/{photo_id}?w=1200&h=675&fit=crop&q=85"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp:
        with open(output_path, "wb") as f:
            f.write(resp.read())
    print(f"Downloaded stock photo ({photo_id}) to {output_path}")

def update_wp_thumbnail(post_id, local_img_path):
    # Copy image into container and import via wp media
    filename = os.path.basename(local_img_path)
    subprocess.run(["docker", "cp", local_img_path, f"wordpress_app:/tmp/{filename}"], check=True)
    
    cmd = [
        "docker", "exec", "wordpress_app",
        "wp", "media", "import", f"/tmp/{filename}",
        f"--post_id={post_id}",
        "--featured_image",
        "--allow-root"
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    print(f"Post {post_id} updated: {res.stdout.strip()}")

def main():
    print("=== Replacing all post thumbnails (Alternating Card News & Stock Photo) ===")
    
    # 1. Post 41: 연세유업 트로트 콘서트 -> Style 1 (카드뉴스)
    p41_img = "/tmp/thumb_post41_card.jpg"
    create_card_thumbnail(
        category_badge="공연 / 콘서트 예매",
        main_title="연세유업 부모님 효도 이벤트",
        sub_title="트로트 콘서트 티켓 증정 & 예매 꿀팁",
        highlights=[
            "신청 대상: 연세유업 제품 구매 고객",
            "주요 혜택: 인기 트로트 콘서트 티켓 무료 증정",
            "실전 가이드: 티켓팅 성공 꿀팁 총정리"
        ],
        theme="concert",
        output_path=p41_img
    )
    update_wp_thumbnail(41, p41_img)

    # 2. Post 35: 광명시 러닝크루 -> Style 2 (실사 스톡 사진)
    p35_img = "/tmp/thumb_post35_stock.jpg"
    download_stock_photo("photo-1452626038306-9aae5e071dd3", p35_img) # 활기찬 도심 러닝크루
    update_wp_thumbnail(35, p35_img)

    # 3. Post 34: 고유가 피해지원금 2차 지급 -> Style 1 (카드뉴스)
    p34_img = "/tmp/thumb_post34_card.jpg"
    create_card_thumbnail(
        category_badge="정부 복지 / 지원금",
        main_title="2026 고유가 피해지원금 2차 지급",
        sub_title="신청 자격 · 지원 금액 · 접수 방법 총정리",
        highlights=[
            "지원 대상: 유류비 부담 취약계층 및 차상위",
            "신청 방법: 복지로 온라인 접수 및 주민센터 방문",
            "지급 방식: 심사 완료 후 본인 계좌 현금 입금"
        ],
        theme="welfare",
        output_path=p34_img
    )
    update_wp_thumbnail(34, p34_img)

    # 4. Post 33: 비바브라보 트로트 콘서트 -> Style 2 (실사 스톡 사진)
    p33_img = "/tmp/thumb_post33_stock.jpg"
    download_stock_photo("photo-1514525253161-7a46d19cd819", p33_img) # 웅장한 콘서트 무대 조명 & 관객
    update_wp_thumbnail(33, p33_img)

    # Regenerate thumbnails
    print("\nRegenerating WordPress thumbnails...")
    subprocess.run(["docker", "exec", "wordpress_app", "wp", "media", "regenerate", "--yes", "--allow-root"], check=True)
    print("\nAll thumbnails successfully replaced and regenerated!")

if __name__ == "__main__":
    main()
