import json
import logging
import os
import random
import re
import requests

from content_generator import ContentGenerator, _get_title

logger = logging.getLogger(__name__)

NEWS_API_URL = "https://newsapi.org/v2/top-headlines"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"

THEME_NAMES = {
    "keimanan": "keimanan",
    "motivasi": "motivasi",
    "muhasabah": "muhasabah",
    "akhlak": "akhlak",
    "keluarga": "keluarga",
    "doa": "doa",
    "dzikir": "dzikir",
}


def _clean_gemini_text(text):
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


class TrendingContentGenerator:
    def __init__(self, news_api_key, gemini_api_key, content_gen=None):
        self.news_api_key = news_api_key
        self.gemini_api_key = gemini_api_key
        self.content_gen = content_gen or ContentGenerator()

    def fetch_trending_news(self, country="id", page_size=5):
        if not self.news_api_key:
            return None
        try:
            params = {
                "country": country,
                "pageSize": page_size,
                "apiKey": self.news_api_key,
            }
            response = requests.get(NEWS_API_URL, params=params, timeout=20)
            response.raise_for_status()
            data = response.json()
            articles = data.get("articles", [])
            if not articles:
                return None
            article = random.choice(articles[:page_size])
            return {
                "title": article.get("title", ""),
                "description": article.get("description", ""),
                "source": article.get("source", {}).get("name", ""),
                "url": article.get("url", ""),
            }
        except requests.exceptions.RequestException as e:
            logger.warning(f"Gagal mengambil berita: {e}")
            return None

    def _generate_with_gemini(self, prompt):
        if not self.gemini_api_key:
            return None
        try:
            url = f"{GEMINI_API_URL}?key={self.gemini_api_key}"
            payload = {
                "contents": [
                    {
                        "parts": [{"text": prompt}]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.7,
                    "maxOutputTokens": 1024,
                },
            }
            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            return _clean_gemini_text(text)
        except (requests.exceptions.RequestException, KeyError, json.JSONDecodeError) as e:
            logger.warning(f"Gagal generate dengan Gemini: {e}")
            return None

    def _build_prompt(self, news):
        title = news.get("title", "")
        description = news.get("description", "")
        themes_text = ", ".join(THEME_NAMES.keys())
        return (
            f"Kamu adalah asisten konten Islami. Berikut berita terkini di Indonesia:\n"
            f"Judul: {title}\n"
            f"Deskripsi: {description}\n\n"
            f"Berdasarkan berita tersebut, buatkan refleksi Islami yang relevan. "
            f"Pilih satu tema dari daftar berikut: {themes_text}. "
            f"Jawab dalam format JSON dengan key: theme, reflection, hashtag. "
            f"Reflection harus singkat (2-3 kalimat), menenangkan, dan mengaitkan berita dengan ajaran Islam. "
            f"Hashtag berisi 3-5 tag relevan (contoh: #islam #berita #motivasi).\n\n"
            f"Contoh output:\n"
            f'{{"theme": "sabar", "reflection": "Dalam situasi sulit, Islam mengajarkan kita untuk tetap sabar ...", "hashtag": "#sabar #islam #indonesia"}}'
        )

    def generate(self):
        news = self.fetch_trending_news()
        if not news:
            logger.info("Tidak ada berita trending, fallback ke konten random.")
            content = self.content_gen.get_random()
            return content

        raw = self._generate_with_gemini(self._build_prompt(news))
        if not raw:
            logger.info("Gemini tidak merespons, fallback ke konten random.")
            content = self.content_gen.get_random()
            return content

        try:
            ai_result = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning(f"Gemini tidak mengembalikan JSON valid: {raw}")
            content = self.content_gen.get_random()
            return content

        theme = ai_result.get("theme", "motivasi")
        reflection = ai_result.get("reflection", "")
        hashtag = ai_result.get("hashtag", "#islam #quran #indonesia")

        if theme not in THEME_NAMES:
            theme = "motivasi"

        content = self.content_gen.get_random(theme=theme)
        self.content_gen.mark_generated(content)

        title = _get_title(content)
        news_caption = (
            f"📰 Isu terkini: {news['title']}\n\n"
            f"{content['arabic']}\n\n"
            f"\"{content['translation']}\"\n\n"
            f"— {title}\n\n"
            f"💡 Refleksi: {reflection}\n\n"
            f"{hashtag} #quran #islam #quote"
        )

        content["caption"] = news_caption
        content["news_title"] = news["title"]
        content["news_source"] = news["source"]
        content["news_url"] = news["url"]
        content["reflection"] = reflection
        content["trending_hashtag"] = hashtag

        return content
