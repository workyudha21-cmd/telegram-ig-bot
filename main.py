import atexit
import fcntl
import json
import logging
import logging.handlers
import os
import signal
import sys
import threading
import time

import requests
import schedule

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
LOG_FILE = os.path.join(LOG_DIR, "bot.log")
SCHEDULE_PATH = os.path.join(os.path.dirname(__file__), "data", "schedule.json")
CLEANUP_MAX_AGE = 7 * 24 * 3600  # 7 hari


def load_schedule():
    if os.path.exists(SCHEDULE_PATH):
        try:
            with open(SCHEDULE_PATH, "r") as f:
                data = json.load(f)
                return data.get("times", AUTO_POST_SCHEDULE.split(","))
        except (OSError, json.JSONDecodeError):
            pass
    return AUTO_POST_SCHEDULE.split(",")


def save_schedule(times):
    os.makedirs(os.path.dirname(SCHEDULE_PATH), exist_ok=True)
    with open(SCHEDULE_PATH, "w") as f:
        json.dump({"times": times}, f, indent=2)

from config import (
    TELEGRAM_BOT_TOKEN,
    INSTAGRAM_USERNAME,
    INSTAGRAM_PASSWORD,
    INSTAGRAM_PROXY,
    NEWS_API_KEY,
    GEMINI_API_KEY,
    ALLOWED_USER_IDS,
    AUTO_POST_SCHEDULE,
    CONTENT_CALENDAR,
)
from content_generator import ContentGenerator
from image_generator import ImageGenerator
from instagram_uploader import InstagramUploader
from telegram_bot import TelegramBot
from trending_content_generator import TrendingContentGenerator

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(),
    ],
)

logger = logging.getLogger(__name__)

os.makedirs(LOG_DIR, exist_ok=True)
_file_handler = logging.handlers.RotatingFileHandler(
    LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
)
_file_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
_file_handler.setLevel(logging.INFO)
logger.addHandler(_file_handler)


def _notify_admin(text):
    if not ALLOWED_USER_IDS:
        return
    for uid in ALLOWED_USER_IDS:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            requests.post(url, json={"chat_id": uid, "text": text}, timeout=10)
        except requests.exceptions.RequestException as e:
            logger.warning(f"Gagal kirim notifikasi ke {uid}: {e}")


def _append_history(entry, max_entries=500):
    history_path = os.path.join(os.path.dirname(__file__), "data", "history.json")
    lock_path = history_path + ".lock"
    os.makedirs(os.path.dirname(history_path), exist_ok=True)
    with open(lock_path, "w") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        try:
            if os.path.exists(history_path):
                with open(history_path, "r") as f:
                    history = json.load(f)
            else:
                history = []
            history.append(entry)
            with open(history_path, "w") as f:
                json.dump(history[-max_entries:], f, indent=2)
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)


def auto_post(content_gen, image_gen, ig_uploader, calendar_map=None):
    theme = content_gen.get_today_theme(calendar_map)
    if theme:
        logger.info(f"Menjalankan auto-post (tema hari ini: {theme})...")
    else:
        logger.info("Menjalankan auto-post (random)...")

    max_retries = 3
    last_error = "Unknown error"
    for attempt in range(1, max_retries + 1):
        try:
            content = content_gen.get_random(theme=theme)
            content_gen.mark_generated(content)
            path = image_gen.generate(content, f"auto_{int(time.time())}.png")
            ok, msg = ig_uploader.upload_photo(path, content["caption"])
            logger.info(f"Auto-post: {msg}")
            if ok:
                try:
                    _append_history({
                        "surah": content["surah"],
                        "ayat": content["ayat"],
                        "theme": content["theme"],
                        "type": content.get("type", "quran"),
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    })
                except (OSError, json.JSONDecodeError) as e:
                    logger.warning(f"Gagal menulis history: {e}")
                return True
            else:
                last_error = msg
            if attempt < max_retries:
                wait = 30 * attempt
                logger.warning(f"Auto-post gagal (percobaan {attempt}/{max_retries}), coba lagi dalam {wait}s...")
                time.sleep(wait)
        except Exception as e:
            last_error = str(e)
            logger.error(f"Auto-post error (percobaan {attempt}/{max_retries}): {e}")
            if attempt < max_retries:
                time.sleep(30 * attempt)
    _notify_admin(f"⚠️ Auto-post gagal setelah {max_retries} percobaan: {last_error}")
    logger.error("Auto-post gagal setelah semua percobaan.")
    return False


def cleanup_output(interval=3600):
    while True:
        now = time.time()
        removed = 0
        if os.path.isdir(OUTPUT_DIR):
            for fname in os.listdir(OUTPUT_DIR):
                fpath = os.path.join(OUTPUT_DIR, fname)
                if os.path.isfile(fpath) and now - os.path.getmtime(fpath) > CLEANUP_MAX_AGE:
                    os.remove(fpath)
                    removed += 1
        lock_dir = os.path.join(os.path.dirname(__file__), "data")
        if os.path.isdir(lock_dir):
            for fname in os.listdir(lock_dir):
                if fname.endswith(".lock"):
                    fpath = os.path.join(lock_dir, fname)
                    if now - os.path.getmtime(fpath) > CLEANUP_MAX_AGE:
                        os.remove(fpath)
                        removed += 1
        if removed:
            logger.info(f"Cleanup: {removed} file lama dihapus")
        time.sleep(interval)


def run_scheduler(content_gen, image_gen, ig_uploader, calendar_map=None):
    last_schedule_hash = None
    while True:
        current_times = load_schedule()
        current_hash = tuple(sorted(current_times))
        if current_hash != last_schedule_hash:
            schedule.clear()
            for t in current_times:
                t = t.strip()
                if t:
                    schedule.every().day.at(t).do(auto_post, content_gen, image_gen, ig_uploader, calendar_map)
                    logger.info(f"Auto-post dijadwalkan setiap {t}")
            last_schedule_hash = current_hash
        schedule.run_pending()
        time.sleep(30)


def main():
    logger.info("Memulai Telegram IG Bot...")

    if TELEGRAM_BOT_TOKEN in (None, "YOUR_TELEGRAM_BOT_TOKEN"):
        logger.error(
            "TELEGRAM_BOT_TOKEN belum diatur! "
            "Set environment variable atau edit config.py"
        )
        return

    content_gen = ContentGenerator()
    image_gen = ImageGenerator(instagram_username=INSTAGRAM_USERNAME)
    ig_uploader = InstagramUploader(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD, INSTAGRAM_PROXY)
    atexit.register(ig_uploader.logout)
    trending_content_gen = None
    if NEWS_API_KEY and GEMINI_API_KEY:
        trending_content_gen = TrendingContentGenerator(NEWS_API_KEY, GEMINI_API_KEY, content_gen=content_gen)
    else:
        logger.warning("NEWS_API_KEY atau GEMINI_API_KEY tidak diatur. Fitur /trending nonaktif.")

    def shutdown(signum, frame):
        logger.info("Menerima sinyal shutdown...")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    bot = TelegramBot(
        token=TELEGRAM_BOT_TOKEN,
        content_gen=content_gen,
        image_gen=image_gen,
        ig_uploader=ig_uploader,
        allowed_user_ids=ALLOWED_USER_IDS,
        trending_content_gen=trending_content_gen,
    )

    scheduler_thread = threading.Thread(
        target=run_scheduler,
        args=(content_gen, image_gen, ig_uploader, CONTENT_CALENDAR),
        daemon=True,
    )
    scheduler_thread.start()

    cleanup_thread = threading.Thread(
        target=cleanup_output,
        daemon=True,
    )
    cleanup_thread.start()

    bot.run()


if __name__ == "__main__":
    main()
