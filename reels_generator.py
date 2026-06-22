import os
import time
import sys
from PIL import Image, ImageDraw, ImageFont
import numpy as np

print(f"reels_generator.py dimuat dari: {__file__}")
print(f"Python version: {sys.version}")

try:
    import moviepy
    print(f"moviepy version: {moviepy.__version__}")
    print(f"moviepy location: {moviepy.__file__}")
    from moviepy.editor import ImageSequenceClip, AudioFileClip, concatenate_audioclips
    MOVIEPY_AVAILABLE = True
    print("moviepy.editor berhasil diimport")
except ImportError as e:
    try:
        print(f"moviepy.editor gagal, mencoba import langsung: {e}")
        from moviepy import ImageSequenceClip, AudioFileClip, concatenate_audioclips
        MOVIEPY_AVAILABLE = True
        print("moviepy berhasil diimport (alternatif)")
    except ImportError as e2:
        MOVIEPY_AVAILABLE = False
        print(f"ERROR: moviepy tidak tersedia: {e}, {e2}")
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
    def __init__(self, width=720, height=1280):
        self.width = width
        self.height = height
        self._init_fonts()

    def _init_fonts(self):
        latin_path = _find_font(_LATIN_FONT_CANDIDATES)
        arabic_path = _find_font(_ARABIC_FONT_CANDIDATES)

        scale = self.width / 1080.0

        if latin_path:
            self.font_title = ImageFont.truetype(latin_path, int(72 * scale * 1.4))
            self.font_body = ImageFont.truetype(latin_path, int(56 * scale * 1.4))
            self.font_small = ImageFont.truetype(latin_path, int(40 * scale * 1.4))
            self.font_footer = ImageFont.truetype(latin_path, int(36 * scale * 1.4))
            self.font_arabic_title = ImageFont.truetype(latin_path, int(48 * scale * 1.4))
        else:
            self.font_title = ImageFont.load_default()
            self.font_body = ImageFont.load_default()
            self.font_small = ImageFont.load_default()
            self.font_footer = ImageFont.load_default()
            self.font_arabic_title = ImageFont.load_default()

        if arabic_path:
            self.font_arabic = ImageFont.truetype(arabic_path, int(120 * scale * 1.4))
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
        margin = int(40 * (self.width / 1080.0))
        padding = int(15 * (self.width / 1080.0))
        line_width = max(2, int(3 * (self.width / 1080.0)))
        draw.rectangle(
            [(margin - padding, margin - padding), (self.width - margin + padding, self.height - margin + padding)],
            outline=accent,
            width=line_width,
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

    def _wrap_arabic_text(self, text, font, max_width):
        if not text or not self.font_arabic:
            return [text] if text else []

        rendered = self._render_arabic_text(text)
        if not rendered:
            return [text] if text else []

        chars = list(rendered)
        lines = []
        current = ""

        for ch in chars:
            test = current + ch
            bbox = font.getbbox(test) if hasattr(font, "getbbox") else font.getsize(test)
            if bbox[2] - bbox[0] > max_width and current:
                lines.append(current)
                current = ch
            else:
                current = test

        if current:
            lines.append(current)

        return lines

    def _get_line_height(self, font):
        bbox = font.getbbox("Ay") if hasattr(font, "getbbox") else font.getsize("Ay")
        return int((bbox[3] - bbox[1]) * 1.4)

    def _create_opening_frame(self, content, alpha=1.0):
        theme = content.get("theme", "motivasi")
        bg_colors = THEME_COLORS.get(theme, THEME_COLORS["motivasi"])
        bg_top, bg_bottom, accent = bg_colors

        img = self._create_gradient_bg(bg_top, bg_bottom)
        draw = ImageDraw.Draw(img)
        self._draw_frame(draw, accent)

        icon = "🌙"
        icon_bbox = draw.textbbox((0, 0), icon, font=self.font_title)
        icon_x = (self.width - (icon_bbox[2] - icon_bbox[0])) // 2
        icon_y = self.height // 3
        draw.text((icon_x, icon_y), icon, fill=accent, font=self.font_title)

        title = "Tadabbur"
        title_bbox = draw.textbbox((0, 0), title, font=self.font_title)
        title_x = (self.width - (title_bbox[2] - title_bbox[0])) // 2
        title_y = icon_y + self._get_line_height(self.font_title) + 30
        draw.text((title_x, title_y), title, fill="#f8f9fa", font=self.font_title)

        subtitle = "Hari Ini"
        sub_bbox = draw.textbbox((0, 0), subtitle, font=self.font_arabic_title)
        sub_x = (self.width - (sub_bbox[2] - sub_bbox[0])) // 2
        sub_y = title_y + self._get_line_height(self.font_title) + 20
        draw.text((sub_x, sub_y), subtitle, fill=accent, font=self.font_arabic_title)

        footer = "📖 Renungan Islami"
        footer_y = self.height - 200
        footer_bbox = draw.textbbox((0, 0), footer, font=self.font_small)
        footer_x = (self.width - (footer_bbox[2] - footer_bbox[0])) // 2
        draw.text((footer_x, footer_y), footer, fill="#f8f9fa", font=self.font_small)

        return img

    def _create_arabic_frame(self, content, scale=1.0):
        theme = content.get("theme", "motivasi")
        bg_colors = THEME_COLORS.get(theme, THEME_COLORS["motivasi"])
        bg_top, bg_bottom, accent = bg_colors

        img = self._create_gradient_bg(bg_top, bg_bottom)
        draw = ImageDraw.Draw(img)
        self._draw_frame(draw, accent)

        title = _get_title(content)
        title_bbox = draw.textbbox((0, 0), title, font=self.font_small)
        title_x = (self.width - (title_bbox[2] - title_bbox[0])) // 2
        title_y = int(80 * (self.height / 1920.0))
        draw.text((title_x, title_y), title, fill=accent, font=self.font_small)

        arabic_text = content.get("arabic", "")
        if arabic_text and self.font_arabic:
            max_text_width = int(self.width * 0.85)
            font_size = int(60 * (self.width / 720.0) * scale)
            font_size = max(40, min(font_size, 100))

            arabic_path = _find_font(_ARABIC_FONT_CANDIDATES)
            if arabic_path:
                font = ImageFont.truetype(arabic_path, font_size)
            else:
                font = self.font_arabic

            lines = self._wrap_arabic_text(arabic_text, font, max_text_width)

            line_height = int(font_size * 1.5)
            total_height = line_height * len(lines)
            y = (self.height - total_height) // 2

            for line in lines:
                bbox = draw.textbbox((0, 0), line, font=font)
                x = (self.width - (bbox[2] - bbox[0])) // 2
                draw.text((x, y), line, fill="#f8f9fa", font=font)
                y += line_height

        return img

    def _create_translation_frame(self, content, alpha=1.0):
        theme = content.get("theme", "motivasi")
        bg_colors = THEME_COLORS.get(theme, THEME_COLORS["motivasi"])
        bg_top, bg_bottom, accent = bg_colors

        img = self._create_gradient_bg(bg_top, bg_bottom)
        draw = ImageDraw.Draw(img)
        self._draw_frame(draw, accent)

        title = _get_title(content)
        title_bbox = draw.textbbox((0, 0), title, font=self.font_small)
        title_x = (self.width - (title_bbox[2] - title_bbox[0])) // 2
        title_y = int(100 * (self.height / 1920.0))
        draw.text((title_x, title_y), title, fill=accent, font=self.font_small)

        label = "Artinya:"
        label_bbox = draw.textbbox((0, 0), label, font=self.font_arabic_title)
        label_x = (self.width - (label_bbox[2] - label_bbox[0])) // 2
        label_y = title_y + 80
        draw.text((label_x, label_y), label, fill=accent, font=self.font_arabic_title)

        translation = content.get("translation", "")
        max_text_width = int(self.width * 0.85)
        lines = self._wrap_text(f'"{translation}"', self.font_body, max_text_width)

        line_height = self._get_line_height(self.font_body)
        total_height = line_height * len(lines)
        y = (self.height - total_height) // 2 + 50

        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=self.font_body)
            x = (self.width - (bbox[2] - bbox[0])) // 2
            draw.text((x, y), line, fill="#f8f9fa", font=self.font_body)
            y += line_height

        return img

    def _create_closing_frame(self, content):
        theme = content.get("theme", "motivasi")
        bg_colors = THEME_COLORS.get(theme, THEME_COLORS["motivasi"])
        bg_top, bg_bottom, accent = bg_colors

        img = self._create_gradient_bg(bg_top, bg_bottom)
        draw = ImageDraw.Draw(img)
        self._draw_frame(draw, accent)

        title = _get_title(content)
        title_bbox = draw.textbbox((0, 0), title, font=self.font_arabic_title)
        title_x = (self.width - (title_bbox[2] - title_bbox[0])) // 2
        title_y = int(200 * (self.height / 1920.0))
        draw.text((title_x, title_y), title, fill=accent, font=self.font_arabic_title)

        explanation = content.get("explanation", "")
        if explanation:
            max_explanation_length = 150
            if len(explanation) > max_explanation_length:
                explanation = explanation[:max_explanation_length] + "..."

            max_text_width = int(self.width * 0.85)
            lines = self._wrap_text(explanation, self.font_small, max_text_width)

            line_height = self._get_line_height(self.font_small)
            total_height = line_height * len(lines)
            y = title_y + 100

            for line in lines:
                bbox = draw.textbbox((0, 0), line, font=self.font_small)
                x = (self.width - (bbox[2] - bbox[0])) // 2
                draw.text((x, y), line, fill="#f8f9fa", font=self.font_small)
                y += line_height

        cta = "Follow untuk tadabbur harian"
        cta_bbox = draw.textbbox((0, 0), cta, font=self.font_arabic_title)
        cta_x = (self.width - (cta_bbox[2] - cta_bbox[0])) // 2
        cta_y = self.height - 280
        draw.text((cta_x, cta_y), cta, fill=accent, font=self.font_arabic_title)

        footer = "Like & Share 🤲"
        footer_bbox = draw.textbbox((0, 0), footer, font=self.font_small)
        footer_x = (self.width - (footer_bbox[2] - footer_bbox[0])) // 2
        footer_y = cta_y + 80
        draw.text((footer_x, footer_y), footer, fill="#f8f9fa", font=self.font_small)

        return img

        return img

    def generate(self, content, duration=30, audio_type="bismillah"):
        print(f"ReelsGenerator.generate() dipanggil dengan duration={duration}")
        if not MOVIEPY_AVAILABLE:
            print("ERROR: MOVIEPY_AVAILABLE is False")
            raise ImportError("moviepy tidak tersedia. Install dengan: pip install moviepy")

        fps = 10
        target_width = 720
        target_height = 1280
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

        total_frames = (opening_duration + arabic_duration + translation_duration + closing_duration) * fps
        print(f"Membuat {total_frames} frames @ {target_width}x{target_height}...")

        original_width = self.width
        original_height = self.height
        self.width = target_width
        self.height = target_height

        try:
            frame_count = 0
            for i in range(opening_duration * fps):
                alpha = min(1.0, i / (fps * 1))
                frame = self._create_opening_frame(content, alpha)
                frames.append(np.array(frame))
                frame_count += 1
            print(f"Opening frames: {frame_count}")

            for i in range(arabic_duration * fps):
                scale = 1.0 + (i / (arabic_duration * fps)) * 0.05
                frame = self._create_arabic_frame(content, scale)
                frames.append(np.array(frame))
                frame_count += 1
            print(f"Setelah Arabic: {frame_count}")

            for i in range(translation_duration * fps):
                alpha = min(1.0, i / (fps * 1))
                frame = self._create_translation_frame(content, alpha)
                frames.append(np.array(frame))
                frame_count += 1
            print(f"Setelah Translation: {frame_count}")

            for i in range(closing_duration * fps):
                frame = self._create_closing_frame(content)
                frames.append(np.array(frame))
                frame_count += 1
            print(f"Total frames: {frame_count}")
        finally:
            self.width = original_width
            self.height = original_height

        print("Membuat video dari frames...")
        video = ImageSequenceClip(frames, fps=fps)

        audio_path = os.path.join(AUDIO_DIR, "bismillah.mp3")
        if audio_type == "bismillah" and os.path.exists(audio_path):
            try:
                print("Menambah audio Bismillah...")
                audio = AudioFileClip(audio_path)
                actual_duration = len(frames) / fps
                if audio.duration < actual_duration:
                    loops = int(actual_duration / audio.duration) + 1
                    audio_clips = [audio] * loops
                    audio = concatenate_audioclips(audio_clips)
                try:
                    audio = audio.subclipped(0, actual_duration)
                except AttributeError:
                    audio = audio.subclip(0, actual_duration)
                try:
                    video = video.with_audio(audio)
                except AttributeError:
                    video = video.set_audio(audio)
                print("Audio berhasil ditambahkan")
            except Exception as e:
                print(f"Warning: Gagal menambah audio: {e}")

        os.makedirs(OUTPUT_DIR, exist_ok=True)
        output_path = os.path.join(OUTPUT_DIR, f"reels_{int(time.time())}.mp4")
        print(f"Menyimpan video ke: {output_path}")
        video.write_videofile(
            output_path,
            fps=fps,
            codec='libx264',
            audio_codec='aac',
            logger=None,
            preset='ultrafast',
            threads=1
        )
        print(f"Video berhasil disimpan: {output_path}")

        video.close()
        try:
            audio.close()
        except Exception:
            pass
        frames.clear()

        return output_path
