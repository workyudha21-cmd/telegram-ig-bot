import os
import time
from PIL import Image, ImageDraw, ImageFont
import numpy as np

try:
    from moviepy.editor import ImageSequenceClip, AudioFileClip, concatenate_audioclips
    MOVIEPY_AVAILABLE = True
    print("moviepy berhasil diimport")
except ImportError as e:
    MOVIEPY_AVAILABLE = False
    print(f"ERROR: moviepy tidak tersedia: {e}")
except Exception as e:
    MOVIEPY_AVAILABLE = False
    print(f"ERROR: Gagal import moviepy: {e}")

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
AUDIO_DIR = os.path.join(os.path.dirname(__file__), "audio")
FONT_DIR = os.path.join(os.path.dirname(__file__), "fonts")

THEME_COLORS = {
    "keimanan": ("#0d3b3b", "#1a5f5f", "#d4af37"),
    "motivasi": ("#1a2a4a", "#2d4a6f", "#e8c547"),
    "muhasabah": ("#2c241b", "#4a3b2a", "#c9a86c"),
    "akhlak": ("#1e3d2f", "#2f5e48", "#f0e6d2"),
    "keluarga": ("#3d1e2e", "#5c2f45", "#f4c2c2"),
    "doa": ("#1f2d40", "#34495e", "#d4af37"),
    "dzikir": ("#2d1b4e", "#4a2d7a", "#e6d5f5"),
}

_LATIN_FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Arial.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    os.path.join(FONT_DIR, "NotoSans-Regular.ttf"),
]

_ARABIC_FONT_CANDIDATES = [
    os.path.join(FONT_DIR, "NotoNaskhArabic-Regular.ttf"),
    "/System/Library/Fonts/Supplemental/NotoNaskhArabic-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf",
]

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
except ImportError:
    arabic_reshaper = None
    get_display = None


def _find_font(candidates):
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def _get_title(content):
    t = content.get("type", "quran")
    if t == "hadith":
        book = content.get("book", "")
        number = content.get("hadith_number", "")
        return f"HR. {book} No. {number}" if number else f"HR. {book}"
    surah = content.get("surah", "")
    ayat = content.get("ayat", "")
    return f"QS. {surah} : {ayat}"


class ReelsGenerator:
    def __init__(self, width=1080, height=1920):
        self.width = width
        self.height = height
        self._init_fonts()

    def _init_fonts(self):
        latin_path = _find_font(_LATIN_FONT_CANDIDATES)
        arabic_path = _find_font(_ARABIC_FONT_CANDIDATES)

        if latin_path:
            self.font_title = ImageFont.truetype(latin_path, 72)
            self.font_body = ImageFont.truetype(latin_path, 56)
            self.font_small = ImageFont.truetype(latin_path, 40)
            self.font_footer = ImageFont.truetype(latin_path, 36)
        else:
            self.font_title = ImageFont.load_default()
            self.font_body = ImageFont.load_default()
            self.font_small = ImageFont.load_default()
            self.font_footer = ImageFont.load_default()

        if arabic_path:
            self.font_arabic = ImageFont.truetype(arabic_path, 90)
        else:
            self.font_arabic = None

    def _hex_to_rgb(self, hex_color):
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    def _create_gradient_bg(self, bg_top, bg_bottom):
        top = Image.new("RGB", (self.width, self.height), bg_top)
        bot = Image.new("RGB", (self.width, self.height), bg_bottom)
        grad = Image.linear_gradient("L").resize((self.width, self.height))
        return Image.composite(bot, top, grad)

    def _draw_frame(self, draw, accent):
        margin = 60
        padding = 20
        draw.rectangle(
            [(margin - padding, margin - padding), (self.width - margin + padding, self.height - margin + padding)],
            outline=accent,
            width=3,
        )

    def _render_arabic_text(self, text):
        if not text or not self.font_arabic or not arabic_reshaper or not get_display:
            return None
        reshaper = arabic_reshaper.ArabicReshaper(
            configuration={"delete_harakat": False, "support_ligatures": True}
        )
        reshaped = reshaper.reshape(text)
        return get_display(reshaped)

    def _wrap_text(self, text, font, max_width):
        lines = []
        for line in text.split("\n"):
            bbox = font.getbbox(line) if hasattr(font, "getbbox") else font.getsize(line)
            if bbox[2] - bbox[0] <= max_width:
                lines.append(line)
            else:
                words = line.split()
                current = ""
                for word in words:
                    test = (current + " " + word) if current else word
                    bbox = font.getbbox(test) if hasattr(font, "getbbox") else font.getsize(test)
                    if bbox[2] - bbox[0] > max_width and current:
                        lines.append(current)
                        current = word
                    else:
                        current = test
                if current:
                    lines.append(current)
        return lines

    def _create_opening_frame(self, content, alpha=1.0):
        theme = content.get("theme", "motivasi")
        bg_colors = THEME_COLORS.get(theme, THEME_COLORS["motivasi"])
        bg_top, bg_bottom, accent = bg_colors

        img = self._create_gradient_bg(bg_top, bg_bottom)
        draw = ImageDraw.Draw(img)
        self._draw_frame(draw, accent)

        text = "Tadabbur Hari Ini"
        bbox = draw.textbbox((0, 0), text, font=self.font_title)
        x = (self.width - (bbox[2] - bbox[0])) // 2
        y = (self.height - (bbox[3] - bbox[1])) // 2

        alpha_int = int(alpha * 255)
        draw.text((x, y), text, fill=accent, font=self.font_title)

        subtitle = "🌙 Renungan Islami"
        bbox_sub = draw.textbbox((0, 0), subtitle, font=self.font_small)
        x_sub = (self.width - (bbox_sub[2] - bbox_sub[0])) // 2
        draw.text((x_sub, y + 100), subtitle, fill="#f8f9fa", font=self.font_small)

        return img

    def _create_arabic_frame(self, content, scale=1.0):
        theme = content.get("theme", "motivasi")
        bg_colors = THEME_COLORS.get(theme, THEME_COLORS["motivasi"])
        bg_top, bg_bottom, accent = bg_colors

        img = self._create_gradient_bg(bg_top, bg_bottom)
        draw = ImageDraw.Draw(img)
        self._draw_frame(draw, accent)

        arabic_text = content.get("arabic", "")
        rendered = self._render_arabic_text(arabic_text)

        if rendered and self.font_arabic:
            font_size = int(90 * scale)
            arabic_path = _find_font(_ARABIC_FONT_CANDIDATES)
            if arabic_path:
                font = ImageFont.truetype(arabic_path, font_size)
            else:
                font = self.font_arabic

            lines = self._wrap_text(rendered, font, self.width - 160)
            total_height = sum(font.getbbox(l)[3] - font.getbbox(l)[1] + 20 for l in lines)
            y = (self.height - total_height) // 2

            for line in lines:
                bbox = draw.textbbox((0, 0), line, font=font)
                x = (self.width - (bbox[2] - bbox[0])) // 2
                draw.text((x, y), line, fill="#f8f9fa", font=font)
                y += (bbox[3] - bbox[1]) + 20

        return img

    def _create_translation_frame(self, content, alpha=1.0):
        theme = content.get("theme", "motivasi")
        bg_colors = THEME_COLORS.get(theme, THEME_COLORS["motivasi"])
        bg_top, bg_bottom, accent = bg_colors

        img = self._create_gradient_bg(bg_top, bg_bottom)
        draw = ImageDraw.Draw(img)
        self._draw_frame(draw, accent)

        translation = content.get("translation", "")
        title = _get_title(content)

        bbox_title = draw.textbbox((0, 0), title, font=self.font_small)
        x_title = (self.width - (bbox_title[2] - bbox_title[0])) // 2
        draw.text((x_title, 200), title, fill=accent, font=self.font_small)

        lines = self._wrap_text(f'"{translation}"', self.font_body, self.width - 160)
        total_height = sum(self.font_body.getbbox(l)[3] - self.font_body.getbbox(l)[1] + 20 for l in lines)
        y = (self.height - total_height) // 2

        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=self.font_body)
            x = (self.width - (bbox[2] - bbox[0])) // 2
            draw.text((x, y), line, fill="#f8f9fa", font=self.font_body)
            y += (bbox[3] - bbox[1]) + 20

        return img

    def _create_closing_frame(self, content):
        theme = content.get("theme", "motivasi")
        bg_colors = THEME_COLORS.get(theme, THEME_COLORS["motivasi"])
        bg_top, bg_bottom, accent = bg_colors

        img = self._create_gradient_bg(bg_top, bg_bottom)
        draw = ImageDraw.Draw(img)
        self._draw_frame(draw, accent)

        title = _get_title(content)
        explanation = content.get("explanation", "")[:100]

        lines_text = [
            title,
            "",
            explanation + "..." if len(content.get("explanation", "")) > 100 else explanation,
            "",
            "Follow untuk tadabbur harian",
            "Like & Share jika bermanfaat",
        ]

        y = 400
        for line in lines_text:
            if not line:
                y += 40
                continue
            bbox = draw.textbbox((0, 0), line, font=self.font_small)
            x = (self.width - (bbox[2] - bbox[0])) // 2
            draw.text((x, y), line, fill="#f8f9fa", font=self.font_small)
            y += 60

        footer = "@tadabbur.quran"
        bbox_footer = draw.textbbox((0, 0), footer, font=self.font_footer)
        x_footer = (self.width - (bbox_footer[2] - bbox_footer[0])) // 2
        draw.text((x_footer, self.height - 150), footer, fill=accent, font=self.font_footer)

        return img

    def generate(self, content, duration=30, audio_type="bismillah"):
        if not MOVIEPY_AVAILABLE:
            raise ImportError("moviepy tidak tersedia. Install dengan: pip install moviepy")

        fps = 30
        frames = []

        opening_duration = 3
        arabic_duration = 12
        translation_duration = 10
        closing_duration = 5

        total = opening_duration + arabic_duration + translation_duration + closing_duration
        if duration < total:
            ratio = duration / total
            opening_duration = max(1, int(opening_duration * ratio))
            arabic_duration = max(3, int(arabic_duration * ratio))
            translation_duration = max(3, int(translation_duration * ratio))
            closing_duration = max(2, int(closing_duration * ratio))

        for i in range(opening_duration * fps):
            alpha = min(1.0, i / (fps * 1))
            frame = self._create_opening_frame(content, alpha)
            frames.append(np.array(frame))

        for i in range(arabic_duration * fps):
            scale = 1.0 + (i / (arabic_duration * fps)) * 0.05
            frame = self._create_arabic_frame(content, scale)
            frames.append(np.array(frame))

        for i in range(translation_duration * fps):
            alpha = min(1.0, i / (fps * 1))
            frame = self._create_translation_frame(content, alpha)
            frames.append(np.array(frame))

        for i in range(closing_duration * fps):
            frame = self._create_closing_frame(content)
            frames.append(np.array(frame))

        video = ImageSequenceClip(frames, fps=fps)

        audio_path = os.path.join(AUDIO_DIR, "bismillah.mp3")
        if audio_type == "bismillah" and os.path.exists(audio_path):
            try:
                audio = AudioFileClip(audio_path)
                actual_duration = len(frames) / fps
                if audio.duration < actual_duration:
                    loops = int(actual_duration / audio.duration) + 1
                    audio_clips = [audio] * loops
                    audio = concatenate_audioclips(audio_clips)
                audio = audio.subclip(0, actual_duration)
                video = video.set_audio(audio)
            except Exception as e:
                print(f"Warning: Gagal menambah audio: {e}")

        os.makedirs(OUTPUT_DIR, exist_ok=True)
        output_path = os.path.join(OUTPUT_DIR, f"reels_{int(time.time())}.mp4")
        video.write_videofile(output_path, fps=fps, codec='libx264', audio_codec='aac', logger=None)

        return output_path
