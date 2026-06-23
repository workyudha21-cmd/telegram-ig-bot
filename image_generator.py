from PIL import Image, ImageDraw, ImageFont
import os
import random
import textwrap
import time
import urllib.request

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
except ImportError:
    arabic_reshaper = None
    get_display = None

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
FONT_DIR = os.path.join(os.path.dirname(__file__), "fonts")

_LATIN_FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Arial.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    os.path.join(FONT_DIR, "NotoSans-Regular.ttf"),
]

_LATIN_FONT_URL = (
    "https://github.com/notofonts/noto-fonts/raw/main/"
    "hinted/ttf/NotoSans/NotoSans-Regular.ttf"
)

_ARABIC_FONT_CANDIDATES = [
    os.path.join(FONT_DIR, "NotoNaskhArabic-Regular.ttf"),
    "/System/Library/Fonts/Supplemental/NotoNaskhArabic-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf",
]

_ARABIC_FONT_URL = (
    "https://github.com/notofonts/noto-fonts/raw/main/"
    "hinted/ttf/NotoNaskhArabic/NotoNaskhArabic-Regular.ttf"
)

_FONT_CACHE = {}


def _find_font(candidates, download_url, filename):
    if filename in _FONT_CACHE:
        return _FONT_CACHE[filename]
    for path in candidates:
        if os.path.exists(path):
            _FONT_CACHE[filename] = path
            return path
    os.makedirs(FONT_DIR, exist_ok=True)
    dest = os.path.join(FONT_DIR, filename)
    if not os.path.exists(dest):
        try:
            urllib.request.urlretrieve(download_url, dest)
        except (OSError, urllib.error.URLError):
            return None
    if os.path.exists(dest):
        _FONT_CACHE[filename] = dest
    return dest if os.path.exists(dest) else None


THEME_COLORS = {
    "keimanan": ("#0d3b3b", "#1a5f5f", "#d4af37"),
    "motivasi": ("#1a2a4a", "#2d4a6f", "#e8c547"),
    "muhasabah": ("#2c241b", "#4a3b2a", "#c9a86c"),
    "akhlak": ("#1e3d2f", "#2f5e48", "#f0e6d2"),
    "keluarga": ("#3d1e2e", "#5c2f45", "#f4c2c2"),
    "doa": ("#1f2d40", "#34495e", "#d4af37"),
    "dzikir": ("#2d1b4e", "#4a2d7a", "#e6d5f5"),
}


_ARABIC_RESHAPER = None


def _get_arabic_reshaper():
    global _ARABIC_RESHAPER
    if _ARABIC_RESHAPER is None and arabic_reshaper:
        try:
            _ARABIC_RESHAPER = arabic_reshaper.ArabicReshaper(
                configuration={"delete_harakat": False, "support_ligatures": True}
            )
        except Exception:
            _ARABIC_RESHAPER = False
    return _ARABIC_RESHAPER if _ARABIC_RESHAPER else None


class ImageGenerator:
    def __init__(self, width=1080, height=1080, instagram_username="", show_title=True, show_arabic=False):
        self.width = width
        self.height = height
        self.instagram_username = instagram_username.strip().lstrip("@")
        self.show_title = show_title
        self.show_arabic = show_arabic
        self._init_fonts()

    def _init_fonts(self):
        latin_path = _find_font(_LATIN_FONT_CANDIDATES, _LATIN_FONT_URL, "NotoSans-Regular.ttf")
        arabic_path = _find_font(_ARABIC_FONT_CANDIDATES, _ARABIC_FONT_URL, "NotoNaskhArabic-Regular.ttf")

        self.font_title = ImageFont.truetype(latin_path, 52) if latin_path else ImageFont.load_default()
        self.font_body = ImageFont.truetype(latin_path, 56) if latin_path else ImageFont.load_default()
        self.font_tafsir = ImageFont.truetype(latin_path, 38) if latin_path else ImageFont.load_default()
        self.font_footer = ImageFont.truetype(latin_path, 34) if latin_path else ImageFont.load_default()
        self.font_small = ImageFont.truetype(latin_path, 30) if latin_path else ImageFont.load_default()
        self.font_arabic = ImageFont.truetype(arabic_path, 72) if arabic_path else None
        self.font_arabic_large = ImageFont.truetype(arabic_path, 110) if arabic_path else None

    def _render_arabic(self, text, font=None):
        if not text or not self.font_arabic or not arabic_reshaper or not get_display:
            return None, None
        f = font or self.font_arabic
        reshaper = _get_arabic_reshaper()
        if reshaper:
            reshaped = reshaper.reshape(text)
        else:
            reshaped = text
        bidi_text = get_display(reshaped)
        return bidi_text, f

    def _wrap_arabic(self, text, font, max_width):
        if not text or not self.font_arabic or not arabic_reshaper or not get_display:
            return []
        reshaper = _get_arabic_reshaper()
        if not reshaper:
            return [text]
        reshaped = reshaper.reshape(text)
        words = reshaped.split(" ")
        if len(words) <= 1:
            chunks = []
            current = ""
            for ch in reshaped:
                test = current + ch
                test_visual = get_display(test)
                tbbox = font.getbbox(test_visual) if hasattr(font, "getbbox") else font.getsize(test_visual)
                if tbbox[2] - tbbox[0] > max_width and current:
                    chunks.append(get_display(current))
                    current = ch
                else:
                    current = test
            if current:
                chunks.append(get_display(current))
            return chunks
        lines = []
        current = ""
        for word in words:
            test = (current + " " + word) if current else word
            test_visual = get_display(test)
            tbbox = font.getbbox(test_visual) if hasattr(font, "getbbox") else font.getsize(test_visual)
            if tbbox[2] - tbbox[0] > max_width and current:
                lines.append(get_display(current))
                current = word
            else:
                current = test
        if current:
            lines.append(get_display(current))
        return lines

    @staticmethod
    def _get_title(content):
        t = content.get("type", "quran")
        if t == "hadith":
            book = (content.get("book") or content.get("surah", "")).strip()
            if book.lower().startswith("hr."):
                book = book[3:].strip()
            number = content.get("hadith_number") or content.get("ayat", "")
            book_lower = book.lower()
            has_kitab_prefix = any(book_lower.startswith(p) for p in ("shahih ", "sunan ", "musnad ", "muwatha "))
            prefix = "" if has_kitab_prefix else "HR. "
            if number:
                return f"{prefix}{book} No. {number}" if book else f"HR. No. {number}"
            return f"{prefix}{book}" if book else "HR."
        if t in ("dua", "dzikir"):
            source = content.get("source") or content.get("surah", "")
            return source if source else "Dzikir"
        surah = content.get("surah", "")
        ayat = content.get("ayat", "")
        return f"QS. {surah} : {ayat}"

    def _draw_frame(self, draw, margin, accent):
        padding = 24
        draw.rectangle(
            [(margin - padding, margin - padding), (self.width - margin + padding, self.height - margin + padding)],
            outline=accent,
            width=4,
        )
        draw.rectangle(
            [(margin - padding - 12, margin - padding - 12), (self.width - margin + padding + 12, self.height - margin + padding + 12)],
            outline=accent,
            width=1,
        )

    def _text_height(self, text, font):
        bbox = font.getbbox(text) if hasattr(font, "getbbox") else font.getsize(text)
        return bbox[3] - bbox[1]

    def _line_height(self, text, font):
        bbox = font.getbbox(text) if hasattr(font, "getbbox") else font.getsize(text)
        return bbox[3] - bbox[1] + 16

    def _arabic_line_height(self, text, font):
        bbox = font.getbbox(text) if hasattr(font, "getbbox") else font.getsize(text)
        return bbox[3] - bbox[1] + 8

    def _pick_body_font(self, text, max_w, max_height_ratio=0.32):
        for size in [56, 50, 44, 38]:
            font = self._load_font(size)
            lines = self._wrap_text(f'"{text}"', font, max_w)
            total_h = sum(self._line_height(line, font) for line in lines)
            if total_h <= self.height * max_height_ratio:
                return font
        return self.font_small

    def _load_font(self, size):
        latin_path = _find_font(_LATIN_FONT_CANDIDATES, _LATIN_FONT_URL, "NotoSans-Regular.ttf")
        return ImageFont.truetype(latin_path, size) if latin_path else ImageFont.load_default()

    def _wrap_text(self, text, font, max_width):
        lines = []
        for line in text.split("\n"):
            bbox = font.getbbox(line) if hasattr(font, "getbbox") else font.getsize(line)
            if bbox[2] - bbox[0] <= max_width:
                lines.append(line)
            else:
                chars_per_line = max(1, int(len(line) * max_width / (bbox[2] - bbox[0])))
                wrapped = textwrap.fill(line, width=chars_per_line)
                lines.extend(wrapped.split("\n"))
        return lines

    def _create_canvas(self, content):
        theme = content.get("theme", "motivasi")
        bg_colors = THEME_COLORS.get(theme, THEME_COLORS["motivasi"])
        bg_top, bg_bottom, accent = bg_colors
        top = Image.new("RGB", (self.width, self.height), bg_top)
        bot = Image.new("RGB", (self.width, self.height), bg_bottom)
        grad = Image.linear_gradient("L").resize((self.width, self.height))
        img = Image.composite(bot, top, grad)
        draw = ImageDraw.Draw(img)
        return img, draw, accent

    def _draw_text_centered(self, draw, text, y, font, fill, anchor="mt"):
        draw.text((self.width // 2, y), text, fill=fill, anchor=anchor, font=font)

    def _draw_multiline_centered(self, draw, lines, y, font, fill, line_gap=16):
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            x = (self.width - (bbox[2] - bbox[0])) // 2
            draw.text((x, y), line, fill=fill, font=font)
            y += (bbox[3] - bbox[1]) + line_gap
        return y

    def generate(self, content, output_filename="post.png", layout=None):
        if layout is None:
            layout = random.randrange(3)
        img, draw, accent = self._create_canvas(content)
        margin = 80
        self._draw_frame(draw, margin, accent)
        max_w = self.width - (margin * 2)

        title_text = self._get_title(content)
        footer_text = f"@{self.instagram_username}" if self.instagram_username else "@tadabbur.quran"

        if layout == 0:
            self._layout_classic(draw, content, title_text, footer_text, margin, max_w, accent)
        elif layout == 1:
            self._layout_arabic_hero(draw, content, title_text, footer_text, margin, max_w, accent)
        else:
            self._layout_minimal(draw, content, title_text, footer_text, margin, max_w, accent)

        os.makedirs(OUTPUT_DIR, exist_ok=True)
        path = os.path.join(OUTPUT_DIR, output_filename)
        img.save(path, quality=95)

        caption_arabic = content.get("arabic", "")
        image_arabic_raw = getattr(self, "_last_arabic_raw", "")
        if caption_arabic and image_arabic_raw and caption_arabic != image_arabic_raw:
            import logging
            logging.getLogger(__name__).warning(
                "Caption/Image Arabic mismatch: title=%s caption=%r image=%r",
                title_text, caption_arabic[:60], image_arabic_raw[:60],
            )

        return path

    def _layout_classic(self, draw, content, title_text, footer_text, margin, max_w, accent):
        translation = content.get("translation", "")
        arabic_raw = content.get("arabic", "")

        font_body = self._pick_body_font(translation, max_w)

        title_h = self._text_height(title_text, self.font_title) if self.show_title else 0
        footer_h = self._text_height(footer_text, self.font_footer)

        translation_lines = self._wrap_text(f'"{translation}"', font_body, max_w)
        translation_h = sum(self._line_height(line, font_body) for line in translation_lines)

        arabic_lines = []
        arabic_h = 0
        arabic_font_used = None
        if self.show_arabic and arabic_raw and self.font_arabic:
            arabic_path = _find_font(_ARABIC_FONT_CANDIDATES, _ARABIC_FONT_URL, "NotoNaskhArabic-Regular.ttf")
            if arabic_path:
                for size in [56, 48, 40, 36, 32, 28, 24]:
                    font_try = ImageFont.truetype(arabic_path, size)
                    wrapped = self._wrap_arabic(arabic_raw, font_try, max_w)
                    total_ar = sum(self._arabic_line_height(line, font_try) for line in wrapped)
                    avail = self.height - title_h - translation_h - footer_h - 120
                    if total_ar <= avail:
                        arabic_lines = wrapped
                        arabic_h = total_ar
                        arabic_font_used = font_try
                        break
                if not arabic_lines:
                    arabic_font_used = ImageFont.truetype(arabic_path, 24)
                    arabic_lines = self._wrap_arabic(arabic_raw, arabic_font_used, max_w)
                    arabic_h = sum(self._arabic_line_height(line, arabic_font_used) for line in arabic_lines)

        gap = 50
        sections = []
        if self.show_title:
            sections.append(("title", title_h))
        if self.show_arabic:
            sections.append(("arabic", arabic_h))
        sections.append(("translation", translation_h))
        sections.append(("footer", footer_h))

        total_h = sum(s[1] for s in sections) + gap * (len(sections) - 1)
        y = (self.height - total_h) // 2
        if y < margin:
            y = margin

        for section_type, section_h in sections:
            if section_type == "title":
                self._draw_text_centered(draw, title_text, y, self.font_title, accent)
                y += section_h + gap
            elif section_type == "arabic":
                for line in arabic_lines:
                    bbox = draw.textbbox((0, 0), line, font=arabic_font_used)
                    x = (self.width - (bbox[2] - bbox[0])) // 2
                    draw.text((x, y), line, fill="#f8f9fa", font=arabic_font_used)
                    y += self._arabic_line_height(line, arabic_font_used)
                y += gap
            elif section_type == "translation":
                y = self._draw_multiline_centered(draw, translation_lines, y, font_body, "#f8f9fa")
                y += gap
            elif section_type == "footer":
                footer_y = y
                if footer_y + footer_h > self.height - margin:
                    footer_y = self.height - margin - footer_h
                self._draw_text_centered(draw, footer_text, footer_y, self.font_footer, accent, anchor="mt")

        self._last_arabic_lines = list(arabic_lines)
        self._last_arabic_raw = arabic_raw if self.show_arabic else ""

    def _layout_arabic_hero(self, draw, content, title_text, footer_text, margin, max_w, accent):
        arabic_raw = content.get("arabic", "")
        translation = content.get("translation", "")

        if not self.show_arabic or not arabic_raw or not self.font_arabic:
            return self._layout_classic(draw, content, title_text, footer_text, margin, max_w, accent)

        arabic_path = _find_font(_ARABIC_FONT_CANDIDATES, _ARABIC_FONT_URL, "NotoNaskhArabic-Regular.ttf")
        if not arabic_path:
            return self._layout_classic(draw, content, title_text, footer_text, margin, max_w, accent)

        font_body = self._pick_body_font(translation, max_w, max_height_ratio=0.22)
        trans_lines = self._wrap_text(f'"{translation}"', font_body, max_w)
        trans_total = sum(self._line_height(line, font_body) for line in trans_lines)

        title_h = self._text_height(title_text, self.font_title) if self.show_title else 0
        footer_h = self._text_height(footer_text, self.font_footer)
        gap = 50

        arabic_lines = []
        arabic_total_h = 0
        chosen_size = None
        for size in [56, 48, 40, 36, 32, 28, 24]:
            font_try = ImageFont.truetype(arabic_path, size)
            wrapped = self._wrap_arabic(arabic_raw, font_try, max_w)
            total_ar = sum(self._arabic_line_height(line, font_try) for line in wrapped)
            total_h = title_h + gap + total_ar + gap + trans_total + gap + footer_h
            if total_h <= self.height - 2 * margin and wrapped and len(wrapped) <= 7:
                arabic_lines = wrapped
                arabic_total_h = total_ar
                chosen_size = size
                break

        if not arabic_lines or chosen_size is None:
            return self._layout_classic(draw, content, title_text, footer_text, margin, max_w, accent)

        font_try = ImageFont.truetype(arabic_path, chosen_size)
        total_h = title_h + gap + arabic_total_h + gap + trans_total + gap + footer_h
        y = (self.height - total_h) // 2
        if y < margin:
            y = margin

        if self.show_title:
            self._draw_text_centered(draw, title_text, y, self.font_title, accent)
            y += title_h + gap

        for line in arabic_lines:
            bbox = draw.textbbox((0, 0), line, font=font_try)
            x = (self.width - (bbox[2] - bbox[0])) // 2
            draw.text((x, y), line, fill="#f8f9fa", font=font_try)
            y += self._arabic_line_height(line, font_try)
        self._last_arabic_lines = list(arabic_lines)
        self._last_arabic_raw = arabic_raw
        y += gap

        y = self._draw_multiline_centered(draw, trans_lines, y, font_body, "#e9ecef")
        y += gap

        footer_y = y
        if footer_y + footer_h > self.height - margin:
            footer_y = self.height - margin - footer_h
        self._draw_text_centered(draw, footer_text, footer_y, self.font_footer, accent, anchor="mt")

    def _layout_minimal(self, draw, content, title_text, footer_text, margin, max_w, accent):
        translation = content.get("translation", "")

        max_w = self.width - 160
        font_body = self._pick_body_font(translation, max_w, max_height_ratio=0.55)
        trans_lines = self._wrap_text(f'"{translation}"', font_body, max_w)
        trans_h = sum(self._line_height(line, font_body) for line in trans_lines)

        title_h = self._text_height(title_text, self.font_title) if self.show_title else 0
        footer_h = self._text_height(footer_text, self.font_footer)
        gap = 50

        total_h = title_h + gap + trans_h + gap + footer_h
        y = (self.height - total_h) // 2
        if y < margin:
            y = margin

        if self.show_title:
            self._draw_text_centered(draw, title_text, y, self.font_title, accent)
            y += title_h + gap

        y = self._draw_multiline_centered(draw, trans_lines, y, font_body, "#f8f9fa")
        y += gap

        footer_y = y
        if footer_y + footer_h > self.height - margin:
            footer_y = self.height - margin - footer_h
        self._draw_text_centered(draw, footer_text, footer_y, self.font_footer, accent, anchor="mt")

        self._last_arabic_lines = []
        self._last_arabic_raw = content.get("arabic", "") if self.show_arabic else ""

    def generate_carousel(self, content, prefix="carousel"):
        paths = []
        timestamp = int(time.time())

        for slide_idx in range(1, 4):
            img, draw, accent = self._create_canvas(content)
            margin = 80
            self._draw_frame(draw, margin, accent)

            slide_label = f"{slide_idx}/3"
            footer_text = f"@{self.instagram_username}" if self.instagram_username else "@tadabbur.quran"

            if slide_idx == 1:
                self._draw_text_centered(draw, slide_label, 60, self.font_small, accent, anchor="mt")
                self._draw_text_centered(draw, "Tadabbur", 240, self.font_title, accent, anchor="mt")
                if self.show_title:
                    title = self._get_title(content)
                    title_lines = self._wrap_text(title, self.font_title, self.width - 2 * margin)
                    y = 360
                    for line in title_lines:
                        self._draw_text_centered(draw, line, y, self.font_title, "#f8f9fa", anchor="mt")
                        y += self._line_height(line, self.font_title)
                self._draw_text_centered(draw, "Swipe untuk membaca", self.height - 200, self.font_footer, accent, anchor="mt")

            elif slide_idx == 2:
                self._draw_text_centered(draw, slide_label, 60, self.font_small, accent, anchor="mt")
                if self.show_title:
                    title = self._get_title(content)
                    self._draw_text_centered(draw, title, 130, self.font_title, accent, anchor="mt")
                    y = 230
                else:
                    self._draw_text_centered(draw, "Ayat:", 130, self.font_title, accent, anchor="mt")
                    y = 230

                arabic_raw = content.get("arabic", "")
                if self.show_arabic and arabic_raw and self.font_arabic:
                    arabic_path = _find_font(_ARABIC_FONT_CANDIDATES, _ARABIC_FONT_URL, "NotoNaskhArabic-Regular.ttf")
                    if arabic_path:
                        for size in [56, 48, 40, 36, 32, 28, 24]:
                            font_try = ImageFont.truetype(arabic_path, size)
                            wrapped = self._wrap_arabic(arabic_raw, font_try, self.width - 2 * margin)
                            total_ar = sum(self._arabic_line_height(line, font_try) for line in wrapped)
                            avail = self.height - y - 130
                            if total_ar <= avail:
                                break
                        for line in wrapped:
                            bbox = draw.textbbox((0, 0), line, font=font_try)
                            x = (self.width - (bbox[2] - bbox[0])) // 2
                            draw.text((x, y), line, fill="#f8f9fa", font=font_try)
                            y += self._arabic_line_height(line, font_try)
                else:
                    translation = content.get("translation", "")
                    max_w = self.width - 2 * margin
                    font_body = self._pick_body_font(translation, max_w, max_height_ratio=0.45)
                    trans_lines = self._wrap_text(f'"{translation}"', font_body, max_w)
                    avail = self.height - y - 130
                    while len(trans_lines) > 1 and sum(self._line_height(l, font_body) for l in trans_lines) > avail:
                        font_body = ImageFont.truetype(_find_font(_LATIN_FONT_CANDIDATES, _LATIN_FONT_URL, "NotoSans-Regular.ttf"), font_body.size - 2) if font_body.size > 24 else font_body
                        trans_lines = self._wrap_text(f'"{translation}"', font_body, max_w)
                    self._draw_multiline_centered(draw, trans_lines, y, font_body, "#f8f9fa")

            else:
                self._draw_text_centered(draw, slide_label, 60, self.font_small, accent, anchor="mt")
                if self.show_arabic:
                    self._draw_text_centered(draw, "Artinya:", 150, self.font_title, accent, anchor="mt")
                else:
                    self._draw_text_centered(draw, "Renungan:", 150, self.font_title, accent, anchor="mt")
                body_text = content.get("translation", "") if self.show_arabic else (content.get("explanation") or content.get("tafsir", "") or content.get("translation", ""))
                max_w = self.width - 2 * margin
                font_body = self._pick_body_font(body_text, max_w, max_height_ratio=0.55)
                trans_lines = self._wrap_text(f'"{body_text}"', font_body, max_w)
                trans_h = sum(self._line_height(line, font_body) for line in trans_lines)
                y = (self.height - trans_h) // 2 - 40
                self._draw_multiline_centered(draw, trans_lines, y, font_body, "#f8f9fa")

            self._draw_text_centered(draw, footer_text, self.height - 70, self.font_footer, accent, anchor="mb")

            os.makedirs(OUTPUT_DIR, exist_ok=True)
            path = os.path.join(OUTPUT_DIR, f"{prefix}_{timestamp}_{slide_idx}.png")
            img.save(path, quality=95)
            paths.append(path)

        return paths

    def generate_story(self, content, output_filename="story.png"):
        story_w, story_h = 1080, 1920
        theme = content.get("theme", "motivasi")
        bg_colors = THEME_COLORS.get(theme, THEME_COLORS["motivasi"])
        bg_top, bg_bottom, accent = bg_colors
        top = Image.new("RGB", (story_w, story_h), bg_top)
        bot = Image.new("RGB", (story_w, story_h), bg_bottom)
        grad = Image.linear_gradient("L").resize((story_w, story_h))
        img = Image.composite(bot, top, grad)
        draw = ImageDraw.Draw(img)

        translation = content.get("translation", "")
        arabic_raw = content.get("arabic", "")
        title_text = self._get_title(content)
        footer_text = f"@{self.instagram_username}" if self.instagram_username else "@tadabbur.quran"
        max_w = story_w - 120

        title_h = self._text_height(title_text, self.font_title) if self.show_title else 0
        footer_h = self._text_height(footer_text, self.font_footer)
        margin = 100

        font_story_body = self._load_font(60)
        trans_lines = self._wrap_text(f'"{translation}"', font_story_body, max_w)
        trans_h = sum(self._line_height(line, font_story_body) for line in trans_lines)

        arabic_lines = []
        arabic_h = 0
        arabic_font_used = None
        if self.show_arabic and arabic_raw and self.font_arabic:
            arabic_path = _find_font(_ARABIC_FONT_CANDIDATES, _ARABIC_FONT_URL, "NotoNaskhArabic-Regular.ttf")
            if arabic_path:
                for size in [80, 72, 64, 56, 48, 40, 36, 32, 28]:
                    font_try = ImageFont.truetype(arabic_path, size)
                    wrapped = self._wrap_arabic(arabic_raw, font_try, max_w)
                    total_ar = sum(self._arabic_line_height(line, font_try) for line in wrapped)
                    avail = story_h - title_h - trans_h - footer_h - 200
                    if total_ar <= avail and wrapped:
                        arabic_lines = wrapped
                        arabic_h = total_ar
                        arabic_font_used = font_try
                        break
                if not arabic_lines:
                    arabic_font_used = ImageFont.truetype(arabic_path, 28)
                    arabic_lines = self._wrap_arabic(arabic_raw, arabic_font_used, max_w)
                    arabic_h = sum(self._arabic_line_height(line, arabic_font_used) for line in arabic_lines)

        gap = 50
        total_h = title_h + gap + arabic_h + gap + trans_h + gap + footer_h
        y = (story_h - total_h) // 2
        if y < margin:
            y = margin

        if self.show_title:
            self._draw_text_centered(draw, title_text, y, self.font_title, accent, anchor="mt")
            y += title_h + gap

        for line in arabic_lines:
            bbox = draw.textbbox((0, 0), line, font=arabic_font_used)
            x = (story_w - (bbox[2] - bbox[0])) // 2
            draw.text((x, y), line, fill="#f8f9fa", font=arabic_font_used)
            y += self._arabic_line_height(line, arabic_font_used)
        y += gap

        self._draw_multiline_centered(draw, trans_lines, y, font_story_body, "#f8f9fa", line_gap=20)
        footer_y = story_h - 100
        self._draw_text_centered(draw, footer_text, footer_y, self.font_footer, accent, anchor="mt")

        self._last_arabic_lines = list(arabic_lines)
        self._last_arabic_raw = arabic_raw if self.show_arabic else ""

        os.makedirs(OUTPUT_DIR, exist_ok=True)
        path = os.path.join(OUTPUT_DIR, output_filename)
        img.save(path, quality=95)
        return path
