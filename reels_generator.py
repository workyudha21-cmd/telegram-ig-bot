import os
import time
import sys

try:
    from moviepy.editor import ImageClip, AudioFileClip, concatenate_audioclips
    MOVIEPY_AVAILABLE = True
    print("moviepy berhasil diimport")
except ImportError as e:
    try:
        from moviepy import ImageClip, AudioFileClip, concatenate_audioclips
        MOVIEPY_AVAILABLE = True
        print("moviepy berhasil diimport (alternatif)")
    except ImportError as e2:
        MOVIEPY_AVAILABLE = False
        print(f"ERROR: moviepy tidak tersedia: {e2}")
except Exception as e:
    MOVIEPY_AVAILABLE = False
    print(f"ERROR: Gagal import moviepy: {e}")

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
AUDIO_DIR = os.path.join(os.path.dirname(__file__), "audio")

TARGET_WIDTH = 720
TARGET_HEIGHT = 1280


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


def _apply_ken_burns(img, duration, fps, zoom_factor=1.15):
    import numpy as np
    from PIL import Image

    total_frames = int(duration * fps)
    frames = []

    base_width, base_height = img.size

    for i in range(total_frames):
        progress = i / max(1, total_frames - 1)
        scale = 1.0 + (zoom_factor - 1.0) * progress

        new_width = int(base_width * scale)
        new_height = int(base_height * scale)

        img_scaled = img.resize((new_width, new_height), Image.LANCZOS)

        left = (new_width - base_width) // 2
        top = (new_height - base_height) // 2
        right = left + base_width
        bottom = top + base_height
        img_frame = img_scaled.crop((left, top, right, bottom))

        frames.append(img_frame)

    return frames


class ReelsGenerator:
    def __init__(self, width=TARGET_WIDTH, height=TARGET_HEIGHT):
        self.width = width
        self.height = height

    def generate_from_image(self, image_path, duration=15, audio_type="bismillah", caption=""):
        if not MOVIEPY_AVAILABLE:
            raise ImportError("moviepy tidak tersedia. Install dengan: pip install moviepy")

        print(f"Generating Reels from image: {image_path}")
        print(f"Duration: {duration}s, audio: {audio_type}")

        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image not found: {image_path}")

        img = _resize_image_to_vertical(image_path, self.width, self.height)
        print(f"Image resized to: {img.size}")

        fps = 24
        frames = _apply_ken_burns(img, duration, fps, zoom_factor=1.12)
        print(f"Generated {len(frames)} frames with Ken Burns effect")

        import numpy as np
        frame_arrays = [np.array(f) for f in frames]

        print("Creating video clip...")
        video = ImageClip(frame_arrays[0], duration=duration)
        if len(frame_arrays) > 1:
            video = ImageClip(frame_arrays, duration=duration)

        audio_path = os.path.join(AUDIO_DIR, "bismillah.mp3")
        if audio_type == "bismillah" and os.path.exists(audio_path):
            try:
                print("Adding Bismillah audio...")
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
                print("Audio added successfully")
            except Exception as e:
                print(f"Warning: Failed to add audio: {e}")
        else:
            print("No audio added")

        os.makedirs(OUTPUT_DIR, exist_ok=True)
        output_path = os.path.join(OUTPUT_DIR, f"reels_{int(time.time())}.mp4")
        print(f"Saving video to: {output_path}")

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
        try:
            audio.close()
        except Exception:
            pass

        print(f"Video saved: {output_path}")
        return output_path

    def generate(self, content, duration=30, audio_type="bismillah"):
        if not MOVIEPY_AVAILABLE:
            raise ImportError("moviepy tidak tersedia. Install dengan: pip install moviepy")

        from image_generator import ImageGenerator

        print("Step 1: Generating post image first...")
        image_gen = ImageGenerator(
            width=1080,
            height=1080,
            instagram_username=content.get("_instagram_username", "@tadabbur.quran")
        )

        image_filename = f"reels_source_{int(time.time())}.png"
        image_path = image_gen.generate(content, image_filename)
        print(f"Post image generated: {image_path}")

        reels_duration = min(15, duration)
        print(f"Step 2: Converting to Reels video ({reels_duration}s)...")

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
                    print(f"Cleaned up source image: {image_path}")
            except Exception as e:
                print(f"Warning: Failed to clean up image: {e}")
