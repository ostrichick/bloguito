import hashlib
import io
import json
import os
import re
import sys
import tempfile
import urllib.request
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps
from config import GEMINI_API_KEY

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def generated_cover_root() -> Path:
    """Return the OS temp directory reserved for generated Bloguito covers."""
    root = Path(tempfile.gettempdir()) / "bloguito" / "covers"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _new_generated_cover_path(title: str) -> Path:
    digest = hashlib.md5(title.encode("utf-8")).hexdigest()[:8]
    fd, name = tempfile.mkstemp(
        prefix=f"thumb_{digest}_",
        suffix=".jpg",
        dir=generated_cover_root(),
    )
    os.close(fd)
    return Path(name)


def cleanup_generated_cover(path) -> bool:
    """Delete only a cover created in Bloguito's dedicated generated-cover temp root."""
    if not isinstance(path, (str, os.PathLike)):
        return False
    candidate = Path(path).resolve(strict=False)
    root = generated_cover_root().resolve(strict=False)
    if candidate.parent != root:
        return False
    try:
        candidate.unlink(missing_ok=True)
    except OSError:
        return False
    try:
        root.rmdir()
        root.parent.rmdir()
    except OSError:
        pass
    return True


DEFAULT_FEATURED_IMAGE_POLICY = {
    "canvas": {"width": 1200, "height": 675},
    "text": {
        "max_blocks": 2,
        "primary_max_chars": 22,
        "secondary_max_chars": 28,
        "display_font_required": True,
        "avoid_generic_system_font_for_primary": True,
    },
    "generation": {
        "default_model": "gemini-3.1-flash-image",
        "image_size": "1K",
        "max_generation_attempts": 2,
    },
    "visual_review": {
        "default_model": "gemini-3.5-flash",
    },
}


def _load_featured_image_policy() -> dict:
    """Load the common machine-readable cover policy without making import failure fatal."""
    policy_path = Path(__file__).resolve().parents[1] / "editorial_policy.json"
    try:
        raw = json.loads(policy_path.read_text(encoding="utf-8"))
        policy = raw.get("featured_image_policy") or {}
    except Exception:
        policy = {}

    merged = {
        **DEFAULT_FEATURED_IMAGE_POLICY,
        **policy,
        "canvas": {**DEFAULT_FEATURED_IMAGE_POLICY["canvas"], **policy.get("canvas", {})},
        "text": {**DEFAULT_FEATURED_IMAGE_POLICY["text"], **policy.get("text", {})},
        "generation": {**DEFAULT_FEATURED_IMAGE_POLICY["generation"], **policy.get("generation", {})},
    }
    return merged


FEATURED_IMAGE_POLICY = _load_featured_image_policy()


def _font_has_hangul(font: ImageFont.FreeTypeFont) -> bool:
    """Reject fonts that render Hangul as the same missing-glyph box."""
    try:
        masks = []
        for char in ("가", "나", "한"):
            mask = font.getmask(char)
            masks.append((mask.size, bytes(mask)))
        return len(set(masks)) >= 2 and any(any(data) for _, data in masks)
    except Exception:
        return False


def _load_font(size: int = 24, bold: bool = True) -> ImageFont.FreeTypeFont:
    """Load only a verified Hangul-capable font; broken Korean must fail closed."""
    candidates = []
    if bold:
        candidates = [
            "/usr/share/fonts/truetype/nanum/NanumSquareB.ttf",
            "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansKR-Bold.ttf",
            "C:/Windows/Fonts/malgunbd.ttf",
            "C:/Windows/Fonts/NanumSquareB.ttf",
            "C:/Windows/Fonts/NanumGothicBold.ttf",
        ]
    else:
        candidates = [
            "/usr/share/fonts/truetype/nanum/NanumSquareR.ttf",
            "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansKR-Regular.ttf",
            "C:/Windows/Fonts/malgun.ttf",
            "C:/Windows/Fonts/NanumSquareR.ttf",
            "C:/Windows/Fonts/NanumGothic.ttf",
        ]

    for path in candidates:
        try:
            font = ImageFont.truetype(path, size)
            if _font_has_hangul(font):
                return font
        except Exception:
            continue
    raise RuntimeError("Hangul-capable font unavailable; refusing to render broken Korean text")


def _load_display_font(size: int = 24) -> ImageFont.FreeTypeFont:
    """Load a conspicuous Hangul display face for featured-image primary copy.

    A generic UI Gothic is intentionally not a fallback here.  When the policy
    requires display typography, failing closed is preferable to silently
    recreating the plain-font covers the editorial standard rejects.
    """
    candidates = [
        "C:/Windows/Fonts/H2MKPB.TTF",  # HYPMokGak-Bold
        "C:/Windows/Fonts/H2HDRM.TTF",  # HYHeadLine-Medium
        "/usr/share/fonts/truetype/nanum/NanumBrush.ttf",
        "/usr/share/fonts/truetype/nanum/NanumPen.ttf",
    ]
    for path in candidates:
        try:
            font = ImageFont.truetype(path, size)
            if _font_has_hangul(font):
                return font
        except Exception:
            continue
    raise RuntimeError("Hangul display font unavailable; refusing generic featured-image typography")


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
    # 숫자+단위 뒤의 범위 표현은 하나의 의미 단위이므로 줄 사이에서 끊지 않는다.
    # 예: 65세 이상, 3개월 이하, 10만원 미만, 2시간 이내.
    words = text.split()
    if len(words) <= 1:
        return [text]
    best_split = len(words) // 2
    min_diff = 999
    range_followers = {"이상", "이하", "미만", "초과", "이내", "내외", "전후", "이전", "이후", "부터", "까지"}
    numeric_unit = re.compile(
        r"\d[\d,.~%-]*(?:세|명|인|개월|주|년|월|일|시간|분|초|원|천원|만원|억원|회|차|단계|등급|kg|g|cm|mm|m|km|%)$",
        re.I,
    )
    for i in range(1, len(words)):
        if words[i] in range_followers and numeric_unit.search(words[i - 1]):
            continue
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


def _clean_cover_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").replace("·", ",")).strip(" ,|:-")


def _has_volatile_number(text: str) -> bool:
    """Treat stable service names such as 정부24 as words, not volatile numeric claims."""
    normalized = re.sub(r"정부\s*24", "정부서비스", text or "")
    return bool(re.search(r"\d", normalized))


def _shorten_by_words(text: str, max_chars: int) -> str:
    """Shorten only at word boundaries; never use an ellipsis in cover copy."""
    text = _clean_cover_text(text)
    if len(text) <= max_chars:
        return text
    words = text.split()
    if not words or len(words[0]) > max_chars:
        return ""
    kept: list[str] = []
    for word in words:
        candidate = " ".join([*kept, word])
        if kept and len(candidate) > max_chars:
            break
        kept.append(word)
    if kept and len(" ".join(kept)) <= max_chars:
        return " ".join(kept)
    return ""


def derive_cover_copy(title: str, keyword: str = "") -> tuple[str, str | None]:
    """Derive one short headline and, only when obvious, one short supporting line.

    Copy is limited to words already present in the reviewed article title/keyword.
    It deliberately avoids copying the full SEO headline into the image.
    """
    text_policy = FEATURED_IMAGE_POLICY["text"]
    primary_limit = int(text_policy.get("primary_max_chars", 22))
    secondary_limit = int(text_policy.get("secondary_max_chars", 28))

    clean_title = _clean_cover_text(title)
    clean_keyword = _clean_cover_text(keyword)
    title_parts = re.split(r"\s*[:|]\s*", clean_title, maxsplit=1)
    title_head = title_parts[0]
    title_tail = title_parts[1] if len(title_parts) == 2 else ""

    primary = ""
    if (
        clean_keyword
        and len(clean_keyword) <= primary_limit
        and clean_keyword in clean_title
        and (clean_keyword != clean_title or len(clean_title.split()) == 1)
    ):
        # Search/radar keywords are hints, not independently reviewed claims. Use one
        # only when the same phrase is already present in the reviewed article title.
        primary = clean_keyword
    if not primary:
        primary = _shorten_by_words(title_head, primary_limit)
    if primary == clean_title and len(clean_title.split()) > 1:
        words = clean_title.split()
        generic_tail = {"방법", "안내", "정리", "총정리", "가이드", "정보", "확인", "조회", "신청방법"}
        if len(words) >= 2 and words[-1] in generic_tail:
            candidate = " ".join(words[:-1]).strip()
            if candidate and len(candidate) <= primary_limit:
                primary = candidate
        if primary == clean_title and len(words) >= 3:
            candidate = " ".join(words[:-1]).strip()
            if candidate and len(candidate) <= primary_limit:
                primary = candidate
        if primary == clean_title and len(words) == 2:
            candidate = words[0].strip()
            if candidate and len(candidate) <= primary_limit:
                primary = candidate
    if not primary:
        raise ValueError("cover_copy_requires_review: no safe primary phrase within policy limit")

    secondary: str | None = None
    if primary and title_head.startswith(primary):
        remainder = title_head[len(primary):].strip()
        remainder = re.sub(r"^(?:과|와|및|,)+\s*", "", remainder)
        remainder = _clean_cover_text(remainder)
        if 2 <= len(remainder) <= secondary_limit and remainder != primary:
            # Derived subtitles stay timeless by default. Dates/prices/ages belong in
            # the article unless a human explicitly prepares a reviewed cover line.
            if not _has_volatile_number(remainder):
                secondary = remainder

    if secondary is None and title_tail:
        tail = _clean_cover_text(title_tail)
        if len(tail) > secondary_limit and "," in tail:
            tail = _clean_cover_text(tail.split(",", 1)[0])
        if 2 <= len(tail) <= secondary_limit and tail != primary and not _has_volatile_number(tail):
            secondary = tail

    # Two text blocks must not reconstruct the full multiword article headline.
    if secondary and len(clean_title.split()) > 1:
        combined = _clean_cover_text(f"{primary} {secondary}")
        if combined == clean_title:
            secondary = None

    return primary, secondary


def _cover_profile(title: str, category_key: str, category_name: str) -> str:
    combined = f"{title} {category_name}"
    if category_key == "concert" or any(w in combined for w in ["콘서트", "공연", "뮤지컬", "페스티벌", "예매"]):
        return "concert"
    if any(w in combined for w in ["가격", "비용", "보험료", "검사비", "약값", "수수료", "요금", "비교"]):
        return "price_compare"
    if category_key == "welfare" or any(w in combined for w in ["복지", "지원금", "연금", "바우처", "장려금", "돌봄"]):
        return "welfare"
    if category_key == "tax" or any(
        w in combined
        for w in ["전입신고", "주민등록", "운전면허", "민원", "정부24", "신고", "증명서", "세금", "재산세", "연말정산", "소득공제", "세액공제"]
    ):
        return "life_admin"
    return "life_service"


def build_editorial_cover_prompt(
    title: str,
    keyword: str,
    category_key: str,
    category_name: str,
    primary_text: str,
    secondary_text: str | None,
) -> str:
    """Standard prompt used for generated background scenes.

    Korean text is overlaid locally after generation, so the image model is explicitly
    told to leave a quiet text area and render no letters or logos.
    """
    profile = _cover_profile(title, category_key, category_name)
    topic_profiles = FEATURED_IMAGE_POLICY.get("topic_profiles", {})
    subject = topic_profiles.get(
        profile,
        "Use one clear everyday subject directly connected to the topic in a natural service or lifestyle setting.",
    )
    composition = FEATURED_IMAGE_POLICY.get("composition", {})
    safe_margin = int(composition.get("safe_margin_percent", 8))
    reserved_text_area = int(composition.get("reserved_text_area_percent", 42))
    styles = ", ".join(str(item).replace("_", " ") for item in FEATURED_IMAGE_POLICY.get("style", []))
    prohibited = ", ".join(
        str(item).replace("_", " ") for item in FEATURED_IMAGE_POLICY.get("prohibited", [])
    )
    max_colors = int(FEATURED_IMAGE_POLICY.get("color", {}).get("max_main_colors", 3))
    secondary_plan = secondary_text or "none"
    sections = {
        "purpose": "Purpose: WordPress featured image, modern editorial blog cover.",
        "topic": f"Topic: {primary_text}. Article context: {title}.",
        "main_subject": f"Main subject: {subject}",
        "composition": (
            "Composition: 16:9 horizontal cover, one strong focal subject on the right half, "
            f"at least {safe_margin}% safe margin around faces, heads, hands, documents and products; reserve the left {reserved_text_area}% "
            "as calm bright negative space for later typography; mobile thumbnail must remain readable."
        ),
        "text": (
            f"Text overlay plan: primary Korean title '{primary_text}', supporting line '{secondary_plan}'. "
            "Render NO text, letters, logos, watermarks or fake UI labels in the generated scene; typography is added later."
        ),
        "style": (
            f"Style: {styles}; friendly contemporary Korean lifestyle photography/illustration, generous whitespace, "
            f"limited palette of no more than {max_colors} main colors."
        ),
        "prohibited": f"Prohibited: {prohibited}.",
    }
    order = FEATURED_IMAGE_POLICY.get(
        "prompt_order",
        ["purpose", "topic", "main_subject", "composition", "text", "style", "prohibited"],
    )
    return "\n".join(
        f"{index}) {sections[key]}"
        for index, key in enumerate(order, 1)
        if key in sections
    )

class DesignerAgent:
    """
    [생활정보 24] 대표 이미지 엔진
    - 기본: 짧은 커버 카피 + 하나의 중심 장면을 사용하는 현대적 에디토리얼 커버
    - 공연 예외: 별도 검토된 공식 포스터/홍보 이미지를 원본 비율 보존형으로 재구성
    - 생성 장면 실패: 전체 SEO 제목을 반복하지 않는 미니멀 커버로 폴백
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
        별도 검토된 공연 포스터만 공식 이미지 경로를 사용하고 나머지는 에디토리얼 커버로 통일.
        curated 안의 이미지 주소나 자체 검토 표식은 출처 검증으로 취급하지 않는다.
        """
        search_target = title

        # 공연/콘서트는 검토된 공식 포스터가 있을 때만 원본 보존형 커버를 사용한다.
        if category_key == "concert" or any(w in search_target for w in ["콘서트", "티켓", "예매", "뮤지컬", "페스티벌"]):
            if reviewed_poster_url and reviewed_poster_url.startswith(("https://", "http://")):
                return 4
        return 5

    def _canvas_size(self) -> tuple[int, int]:
        canvas = FEATURED_IMAGE_POLICY["canvas"]
        return int(canvas.get("width", 1200)), int(canvas.get("height", 675))

    def _generated_scene(self, prompt: str) -> Image.Image:
        if not self.client:
            raise RuntimeError("image generation client unavailable")
        from google.genai import types

        model = os.getenv(
            "BLOGUITO_IMAGE_MODEL",
            FEATURED_IMAGE_POLICY["generation"].get("default_model", "gemini-3.1-flash-image"),
        )
        image_size = FEATURED_IMAGE_POLICY["generation"].get("image_size", "1K")
        result = self.client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                image_config=types.ImageConfig(aspect_ratio="16:9", image_size=image_size),
            ),
        )
        for part in getattr(result, "parts", None) or []:
            if getattr(part, "inline_data", None) is None:
                continue
            image = part.as_image()
            if image is not None:
                return image.convert("RGB")
        raise RuntimeError("image generation returned no image part")

    def _vision_review_cover(
        self,
        image: Image.Image,
        *,
        title: str,
        primary_text: str | None,
        secondary_text: str | None,
        source_kind: str,
    ) -> tuple[bool, list[str]]:
        """Review nondeterministic visual output before it can become a featured image."""
        if not self.client:
            return False, ["vision_review_unavailable"]

        from google.genai import types

        review_policy = FEATURED_IMAGE_POLICY.get("visual_review", {})
        model = os.getenv(
            "BLOGUITO_IMAGE_REVIEW_MODEL",
            review_policy.get("default_model", "gemini-3.5-flash"),
        )
        checks = ", ".join(
            str(item).replace("_", " ") for item in FEATURED_IMAGE_POLICY.get("review_checks", [])
        )
        regenerate = ", ".join(
            str(item).replace("_", " ") for item in FEATURED_IMAGE_POLICY.get("regenerate_on", [])
        )
        expected_text = [text for text in [primary_text, secondary_text] if text]
        if source_kind == "official_poster":
            context = (
                "This is a separately verified official concert/promotional image recomposed by fit and background extension. "
                f"The expected article/performance identity is '{title}'. Verify that the visible artist/show identity is consistent with the core artist or performance named there; "
                "ignore SEO helper words such as booking/how-to wording or dates that an official poster may omit. Fail a generic ticket-vendor/share preview or a visibly different artist/show. "
                "Original poster typography is allowed. Fail if a face, full head, chin, performer identity, or important performance title "
                "has been destructively cropped or obscured, or if the recomposition looks broken. Do not fail merely because the official poster contains text."
            )
        else:
            context = (
                f"This is a generated editorial cover for '{title}'. The only intended visible Korean overlay text is {expected_text!r}. "
                "Fail if the generated scene contains additional readable words, fake logos, watermarks, malformed UI text, or if the main subject is unclear."
            )
        prompt = (
            "Review this WordPress featured image strictly. "
            + context
            + f" Check: {checks}. Severe regenerate conditions: {regenerate}. "
            "Also check that the image feels modern, minimal and editorial rather than an old banner or flyer, and that it remains understandable as a small mobile thumbnail. "
            "Return JSON only in this form: {\"pass\": true|false, \"issues\": [\"short issue\"]}."
        )
        try:
            response = self.client.models.generate_content(
                model=model,
                contents=[prompt, image],
                config=types.GenerateContentConfig(response_mime_type="application/json"),
            )
            payload = json.loads((getattr(response, "text", "") or "").strip())
            passed = payload.get("pass") is True
            issues = [str(issue)[:160] for issue in payload.get("issues", []) if str(issue).strip()]
            return passed, issues
        except Exception as exc:
            return False, [f"vision_review_error:{type(exc).__name__}"]

    @staticmethod
    def _fit_without_subject_crop(image: Image.Image, width: int, height: int) -> Image.Image:
        """Fit an image to the cover while preserving the full foreground composition."""
        if image.size == (width, height):
            return image.copy()
        background = ImageOps.fit(image, (width, height), method=Image.Resampling.LANCZOS)
        background = background.filter(ImageFilter.GaussianBlur(radius=20))
        foreground = ImageOps.contain(image, (width, height), method=Image.Resampling.LANCZOS)
        x = (width - foreground.width) // 2
        y = (height - foreground.height) // 2
        background.paste(foreground, (x, y))
        return background

    def _overlay_cover_copy(
        self,
        image: Image.Image,
        primary_text: str,
        secondary_text: str | None,
    ) -> Image.Image:
        width, height = image.size
        base = image.convert("RGBA")

        # A soft left scrim preserves photographic/illustrative context while making
        # Korean typography readable without a banner box.
        scrim = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        sdraw = ImageDraw.Draw(scrim)
        scrim_end = int(width * 0.58)
        for x in range(scrim_end):
            ratio = x / max(scrim_end - 1, 1)
            alpha = int(238 * (1 - ratio) ** 1.7)
            sdraw.line([(x, 0), (x, height)], fill=(248, 252, 252, alpha))
        base = Image.alpha_composite(base, scrim)
        draw = ImageDraw.Draw(base)

        safe_margin = float(
            FEATURED_IMAGE_POLICY.get("composition", {}).get("safe_margin_percent", 8)
        ) / 100.0
        left = int(round(width * safe_margin))
        text_width_chars = max(10, min(16, int(FEATURED_IMAGE_POLICY["text"].get("primary_max_chars", 22))))
        lines = split_title(primary_text, max_first_line=text_width_chars)
        longest = max(map(len, lines)) if lines else 1
        font_size = 72 if longest <= 8 else 62 if longest <= 12 else 52
        if len(lines) > 1:
            font_size = min(font_size, 56)
        title_font = _load_display_font(font_size)
        subtitle_font = _load_font(29, bold=True)

        total_title_h = len(lines) * (font_size + 8)
        subtitle_h = 48 if secondary_text else 0
        start_y = max(70, (height - total_title_h - subtitle_h) // 2 - 15)
        colors = [(13, 70, 145, 255), (0, 132, 96, 255)]
        for index, line in enumerate(lines):
            draw.text(
                (left, start_y + index * (font_size + 8)),
                line,
                font=title_font,
                fill=colors[min(index, len(colors) - 1)],
            )

        if secondary_text:
            subtitle_y = start_y + total_title_h + 18
            draw.text(
                (left + 2, subtitle_y),
                secondary_text,
                font=subtitle_font,
                fill=(30, 72, 110, 255),
            )
        return base.convert("RGB")

    def _render_minimal_fallback(
        self,
        primary_text: str,
        secondary_text: str | None,
        profile: str,
        output_path: Path,
    ):
        """Network/API-safe fallback using short cover copy and one abstract focal object."""
        width, height = self._canvas_size()
        image = Image.new("RGB", (width, height), (244, 250, 249))
        draw = ImageDraw.Draw(image)

        # One large contemporary focal object on the right; the shape changes enough
        # to communicate the broad topic without turning into an icon collage.
        # Keep the fallback focal scene inside the same 8% critical-content
        # margin required for generated covers. 0.72 leaves enough room for
        # even the widest fallback subject on a 1200px canvas.
        cx, cy = int(width * 0.72), int(height * 0.50)
        if profile == "concert":
            draw.rounded_rectangle([cx - 210, cy - 190, cx + 210, cy + 190], radius=44, fill=(24, 31, 58))
            draw.ellipse([cx - 82, cy - 82, cx + 82, cy + 82], fill=(241, 178, 73))
        elif profile == "price_compare":
            draw.rounded_rectangle([cx - 170, cy - 220, cx + 170, cy + 220], radius=32, fill=(255, 255, 255), outline=(204, 220, 220), width=4)
            for offset in (-90, -20, 50):
                draw.rounded_rectangle([cx - 105, cy + offset, cx + 90, cy + offset + 18], radius=9, fill=(204, 222, 222))
            draw.rounded_rectangle([cx + 30, cy + 105, cx + 210, cy + 215], radius=24, fill=(34, 144, 112))
        elif profile == "life_admin":
            # A single coherent home + digital-application scene, echoing the
            # successful move-in cover without copying its artwork.
            house_x, house_y = cx - 10, cy - 155
            draw.polygon(
                [(house_x - 165, house_y + 75), (house_x, house_y - 50), (house_x + 165, house_y + 75)],
                fill=(204, 225, 233),
            )
            draw.rounded_rectangle(
                [house_x - 135, house_y + 55, house_x + 135, house_y + 235],
                radius=14,
                fill=(249, 252, 251),
                outline=(181, 208, 218),
                width=4,
            )
            draw.rounded_rectangle([cx - 185, cy - 35, cx + 135, cy + 165], radius=22, fill=(224, 237, 244), outline=(144, 181, 201), width=4)
            draw.rounded_rectangle([cx - 150, cy - 5, cx + 100, cy + 112], radius=14, fill=(255, 255, 255))
            draw.rounded_rectangle([cx - 82, cy + 18, cx + 38, cy + 88], radius=14, fill=(218, 239, 233))
            draw.rounded_rectangle([cx + 100, cy + 80, cx + 225, cy + 195], radius=18, fill=(255, 255, 255), outline=(193, 215, 219), width=3)
            draw.ellipse([cx + 154, cy + 120, cx + 224, cy + 190], fill=(38, 181, 132))
        elif profile == "welfare":
            draw.rounded_rectangle([cx - 155, cy - 230, cx + 155, cy + 230], radius=46, fill=(230, 241, 245), outline=(174, 204, 216), width=4)
            draw.rounded_rectangle([cx - 120, cy - 175, cx + 120, cy + 128], radius=24, fill=(255, 255, 255))
            draw.ellipse([cx - 48, cy - 92, cx + 48, cy + 4], fill=(216, 235, 230))
            draw.rounded_rectangle([cx - 78, cy + 32, cx + 78, cy + 67], radius=17, fill=(38, 181, 132))
        else:
            draw.rounded_rectangle([cx - 235, cy - 165, cx + 155, cy + 165], radius=28, fill=(233, 242, 248), outline=(176, 204, 220), width=4)
            draw.rounded_rectangle([cx - 190, cy - 120, cx + 110, cy + 72], radius=18, fill=(255, 255, 255))
            draw.rounded_rectangle([cx - 120, cy - 58, cx + 42, cy + 42], radius=18, fill=(224, 241, 238))
            draw.ellipse([cx + 78, cy + 42, cx + 198, cy + 162], fill=(38, 181, 132))

        final = self._overlay_cover_copy(image, primary_text, secondary_text)
        final.save(output_path, "JPEG", quality=96)

    def _render_editorial_cover(
        self,
        title: str,
        keyword: str,
        category_key: str,
        category_name: str,
        output_path: Path,
    ):
        primary_text, secondary_text = derive_cover_copy(title, keyword)
        prompt = build_editorial_cover_prompt(
            title,
            keyword,
            category_key,
            category_name,
            primary_text,
            secondary_text,
        )
        profile = _cover_profile(title, category_key, category_name)
        max_attempts = max(1, int(FEATURED_IMAGE_POLICY["generation"].get("max_generation_attempts", 2)))
        review_issues: list[str] = []
        for attempt in range(1, max_attempts + 1):
            attempt_prompt = prompt
            if review_issues:
                attempt_prompt += "\nPrevious attempt review issues to correct: " + "; ".join(review_issues)
            try:
                generated = self._generated_scene(attempt_prompt)
                width, height = self._canvas_size()
                generated = self._fit_without_subject_crop(generated, width, height)
                final = self._overlay_cover_copy(generated, primary_text, secondary_text)
                passed, review_issues = self._vision_review_cover(
                    final,
                    title=title,
                    primary_text=primary_text,
                    secondary_text=secondary_text,
                    source_kind="generated_scene",
                )
                if passed:
                    final.save(output_path, "JPEG", quality=96)
                    print(f"[DesignerAgent] 🖼️ 현대적 에디토리얼 커버 생성·검수 완료: {output_path}")
                    return
                print(f"[DesignerAgent] ⚠️ 이미지 품질 검수 실패 {attempt}/{max_attempts}: {review_issues}")
            except Exception as e:
                print(f"[DesignerAgent] ⚠️ 장면 생성 실패 ({e}) -> 미니멀 에디토리얼 커버로 폴백")
                break

        self._render_minimal_fallback(primary_text, secondary_text, profile, output_path)

    # =========================================================================
    # 공연 예외: 검토된 공식 포스터 원본 보존형 재구성
    # =========================================================================
    def _render_hybrid_poster(
        self,
        poster_url: str,
        title: str,
        category_name: str,
        curated: dict | None,
        output_path: Path,
    ):
        """공식 포스터를 자르지 않고 16:9 커버 안에 재구성한다.

        공식 홍보물 자체의 공연명, 인물, 로고와 분위기를 보존하기 위해 블로그 제목이나
        브랜드 배지를 추가로 덮지 않는다. 빈 영역은 같은 원본을 흐림 확장한 배경으로 채운다.
        """
        width, height = self._canvas_size()
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

        base.save(output_path, "JPEG", quality=95)
        print(f"[DesignerAgent] 🎤 공식 공연 이미지 원본 보존형 커버 생성 완료: {output_path}")

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
        기본은 현대적 에디토리얼 커버를 만든다. 독립 검토한 공연 공식 이미지 주소를
        별도 인자로 전달한 경우에만 포스터를 사용하며 실패 시 같은 에디토리얼 커버로 폴백한다.
        """
        output_path = _new_generated_cover_path(title)
        try:
            mode = self.select_mode(category_key, curated, title, keyword, reviewed_poster_url)
            poster_url = reviewed_poster_url

            print(f"[DesignerAgent] 🎨 대표 이미지 자동 라우팅: [모드 {mode}] 선정 (주제: '{title[:20]}...', 카테고리: {category_name})")

            # 1. 모드 4: 하이브리드 포스터
            if mode == 4 and poster_url:
                try:
                    self._render_hybrid_poster(poster_url, title, category_name, curated, output_path)
                    with Image.open(output_path) as poster_cover:
                        passed, issues = self._vision_review_cover(
                            poster_cover.convert("RGB"),
                            title=title,
                            primary_text=None,
                            secondary_text=None,
                            source_kind="official_poster",
                        )
                    if passed:
                        return output_path
                    print(f"[DesignerAgent] ⚠️ 공식 공연 이미지 품질 검수 실패: {issues} -> 에디토리얼 커버로 폴백")
                except Exception as e:
                    print(f"[DesignerAgent] ⚠️ 공식 공연 이미지 재구성 실패 ({e}) -> 에디토리얼 커버로 폴백")

            self._render_editorial_cover(title, keyword, category_key, category_name, output_path)
            return output_path
        except Exception:
            cleanup_generated_cover(output_path)
            raise
