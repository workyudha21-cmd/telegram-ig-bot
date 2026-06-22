import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME", "YOUR_INSTAGRAM_USERNAME")
INSTAGRAM_PASSWORD = os.getenv("INSTAGRAM_PASSWORD", "YOUR_INSTAGRAM_PASSWORD")
INSTAGRAM_PROXY = os.getenv("INSTAGRAM_PROXY", "")

NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

AUTO_POST_SCHEDULE = os.getenv("AUTO_POST_SCHEDULE", "08:00,20:00")
TIMEZONE = os.getenv("TIMEZONE", "Asia/Jakarta")
CAPTION_STYLE = os.getenv("CAPTION_STYLE", "random")

ALLOWED_USER_IDS = [int(id) for id in os.getenv("ALLOWED_USER_IDS", "").split(",") if id.strip()]

_CONTENT_CALENDAR_DEFAULT = "motivasi,akhlak,keimanan,muhasabah,keluarga,doa,motivasi"
CONTENT_CALENDAR = [t.strip() for t in os.getenv("CONTENT_CALENDAR", _CONTENT_CALENDAR_DEFAULT).split(",") if t.strip()]
