import logging
import os
import time
import sys

logger = logging.getLogger(__name__)

try:
    from moviepy.editor import ImageClip, AudioFileClip, concatenate_audioclips
    MOVIEPY_AVAILABLE = True
    logger.info("moviepy berhasil diimport")
except ImportError as e:
    try:
        from moviepy import ImageClip, AudioFileClip, concatenate_audioclips
        MOVIEPY_AVAILABLE = True
        logger.info("moviepy berhasil diimport (alternatif)")
    except ImportError as e2:
        MOVIEPY_AVAILABLE = False
        logger.error(f"moviepy tidak tersedia: {e2}")
except Exception as e:
    MOVIEPY_AVAILABLE = False
    logger.error(f"Gagal import moviepy: {e}")

from image_generator import THEME_COLORS, ImageGenerator


def _get_title(content):
    return ImageGenerator._get_title(content)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
AUDIO_DIR = os.path.join(os.path.dirname(__file__), "audio")

TARGET_WIDTH = 720
TARGET_HEIGHT = 1280
DEFAULT_FPS = 12
DEFAULT_DURATION = 15


def _resize_image_to_vertical(image_path, target_width=TARGET_WIDTH, target_height=TARGET_HEIGHT):
    from PIL import Image
    img = Image.open(image_path)
    img = img.convert("RGB")

    target_ratio = target_width / target_height
    img_ratio = img.width / img.height

    if img_ratio > target_ratio:
        new_height = target_height
        new_width = int(target_height * img_ratio)
    else:
        new_width = target_width
        new_height = int(target_width / img_ratio)

    img_resized = img.resize((new_width, new_height), Image.LANCZOS)

    left = (new_width - target_width) // 2
    top = (new_height - target_height) // 2
    right = left + target_width
    bottom = top + target_height
    img_cropped = img_resized.crop((left, top, right, bottom))

    return img_cropped


class ReelsGenerator:
    def __init__(self, width=TARGET_WIDTH, height=TARGET_HEIGHT):
        self.width = width
        self.height = height
        self._image_gen = None
        self._fonts_initialized = False

    def _ensure_fonts(self):
        if self._fonts_initialized:
            return
        self._image_gen = ImageGenerator()
        self.font_title = self._image_gen.font_title
        self.font_body = self._image_gen.font_body
        self.font_small = self._image_gen.font_small
        self._fonts_initialized = True

    def __getattr__(self, name):
        if name in ("font_title", "font_body", "font_small"):
            self._ensure_fonts()
            return getattr(self, name)
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

    def generate_from_image(self, image_path, duration=DEFAULT_DURATION, audio_type="bismillah", caption=""):
        if not MOVIEPY_AVAILABLE:
            raise ImportError("moviepy tidak tersedia. Install dengan: pip install moviepy")

        logger.info(f"Generating Reels from image: {image_path}")
        logger.info(f"Duration: {duration}s, audio: {audio_type}")

        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image not found: {image_path}")

        img = _resize_image_to_vertical(image_path, self.width, self.height)
        logger.info(f"Image resized to: {img.size}")

        import numpy as np
        img_array = np.array(img)
        logger.info(f"Image array shape: {img_array.shape}")

        fps = DEFAULT_FPS
        logger.info(f"Creating static video clip (fps={fps}, duration={duration}s)...")

        video = ImageClip(img_array, duration=duration)
        audio = None

        audio_path = os.path.join(AUDIO_DIR, "bismillah.mp3")
        if audio_type == "bismillah" and os.path.exists(audio_path):
            try:
                logger.info("Adding Bismillah audio...")
                audio = AudioFileClip(audio_path)
                if audio.duration < duration:
                    loops = int(duration / audio.duration) + 1
                    audio_clips = [audio] * loops
                    audio = concatenate_audioclips(audio_clips)
                try:
                    audio = audio.subclipped(0, duration)
                except AttributeError:
                    audio = audio.subclip(0, duration)
                try:
                    video = video.with_audio(audio)
                except AttributeError:
                    video = video.set_audio(audio)
                logger.info("Audio added successfully")
            except Exception as e:
                logger.warning(f"Failed to add audio: {e}")
                audio = None
        else:
            logger.info("No audio added")

        os.makedirs(OUTPUT_DIR, exist_ok=True)
        output_path = os.path.join(OUTPUT_DIR, f"reels_{int(time.time())}.mp4")
        logger.info(f"Saving video to: {output_path}")

        video.write_videofile(
            output_path,
            fps=fps,
            codec='libx264',
            audio_codec='aac',
            logger=None,
            preset='ultrafast',
            threads=1
        )

        try:
            video.close()
        except Exception:
            pass
        if audio is not None:
            try:
                audio.close()
            except Exception:
                pass
        del img_array
        import gc
        gc.collect()

        logger.info(f"Video saved: {output_path}")
        return output_path

    def generate(self, content, duration=DEFAULT_DURATION, audio_type="bismillah"):
        if not MOVIEPY_AVAILABLE:
            raise ImportError("moviepy tidak tersedia. Install dengan: pip install moviepy")

        from image_generator import ImageGenerator

        logger.info("Step 1: Generating post image first...")
        image_gen = ImageGenerator(
            width=1080,
            height=1080,
            instagram_username=content.get("_instagram_username", "@tadabbur.quran")
        )

        image_filename = f"reels_source_{int(time.time())}.png"
        image_path = image_gen.generate(content, image_filename)
        logger.info(f"Post image generated: {image_path}")

        reels_duration = min(DEFAULT_DURATION, duration)
        logger.info(f"Step 2: Converting to Reels video ({reels_duration}s)...")

        try:
            output_path = self.generate_from_image(
                image_path,
                duration=reels_duration,
                audio_type=audio_type,
                caption=content.get("caption", "")
            )
            return output_path
        finally:
            try:
                if os.path.exists(image_path):
                    os.remove(image_path)
                    logger.info(f"Cleaned up source image: {image_path}")
            except Exception as e:
                logger.warning(f"Failed to clean up image: {e}")
            import gc
            gc.collect()
