import datetime
import fcntl
import json
import os
import random
import threading
from typing import Dict, List, Optional, Set, Tuple, Any

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
DEFAULT_DATA_PATHS = [
    os.path.join(DATA_DIR, "quran_content.json"),
    os.path.join(DATA_DIR, "hadith_content.json"),
    os.path.join(DATA_DIR, "dua_content.json"),
    os.path.join(DATA_DIR, "dzikir_content.json"),
]
GENERATED_PATH = os.path.join(DATA_DIR, "generated.json")
GENERATED_MAX_ENTRIES = 2000


def _key(verse: Dict[str, Any]) -> Tuple[str, ...]:
    t = verse.get("type", "quran")
    if t == "hadith":
        return (t, str(verse.get("book", "")), str(verse.get("hadith_number", "")))
    if t in ("dua", "dzikir"):
        return (t, str(verse.get("source", "")), str(verse.get("arabic", ""))[:64])
    return (t, str(verse.get("surah", "")), str(verse.get("ayat", "")))


_OPENERS = [
    "",
    "Renungan pagi ini 🌅\n\n",
    "📖 Tadabbur singkat\n\n",
    "🤲 Semoga menjadi pengingat\n\n",
    "💎 Hikmah hari ini\n\n",
]

_CLOSERS = [
    "",
    "\n\nSemoga bermanfaat. Bagikan jika kamu suka 🤲",
    "\n\nFollow untuk tadabbur harian 🌙",
    "\n\nJangan lupa like dan share jika bermanfaat 🤲",
    "\n\nIkuti kami untuk konten Islami setiap hari 📖",
    "\n\n📩 Tag teman yang perlu membaca ini!",
    "\n\n💾 Save untuk dibaca ulang di waktu luang",
    "\n\n🔁 Share rezeki pahala ini ke orang lain",
]

_REFLECTIVE_QUESTIONS = [
    "🤔 Bagaimana ayat ini menyentuh hatimu hari ini?",
    "💭 Apa hikmah yang bisa kamu ambil dari ayat ini?",
    "📝 Sudahkah kamu mengamalkan pesan ini dalam hidupmu?",
    "🤲 Yuk share agar orang lain juga mendapat manfaatnya!",
    "💡 Ayat ini mengingatkan kita tentang... apa menurutmu?",
    "🌙 Ceritakan di kolom komentar, ayat apa favoritmu?",
    "📖 Renungkan: apa yang bisa kamu mulai hari ini?",
    "🤍 Save postingan ini untuk dibaca ulang saat kamu butuh.",
]

_HASHTAG_SETS = [
    "#quran #islam #muslim #tadabbur #motivasiislami",
    "#alquran #hadist #sabda #dakwah #quoteislami",
    "#islamicquote #muslimah #muslimindonesia #sunnah #rasulullah",
    "#tafsir #pengajian #ngaji #ilmu #sedekah",
    "#sabar #syukur #ikhlas #tawakal #rezeki",
    "#keluarga #muslim #parenting #akhlak #ibadah",
    "#fyp #fypislami #reelsislami #dakwahislam #viral",
]

_HASHTAG_BRANDED = "#tadabbur #islam #muslim #indonesia"
_HASHTAG_ENGAGEMENT = "#share #save #komen"


def _get_title(verse: Dict[str, Any]) -> str:
    t = verse.get("type", "quran")
    if t == "hadith":
        book = (verse.get("book", "") or "").strip()
        if book.lower().startswith("hr."):
            book = book[3:].strip()
        number = verse.get("hadith_number", "")
        book_lower = book.lower()
        has_kitab_prefix = any(book_lower.startswith(p) for p in ("shahih ", "sunan ", "musnad ", "muwatha "))
        prefix = "" if has_kitab_prefix else "HR. "
        if number:
            return f"{prefix}{book} No. {number}" if book else f"HR. No. {number}"
        return f"{prefix}{book}" if book else "HR."
    if t in ("dua", "dzikir"):
        return verse.get("source", "Dzikir")
    surah = verse.get("surah", "")
    ayat = verse.get("ayat", "")
    return f"QS. {surah} : {ayat}"


def _build_hashtags(theme: str) -> str:
    base = random.choice(_HASHTAG_SETS)
    themed = f"#{theme}"
    if random.random() < 0.4:
        engagement = _HASHTAG_ENGAGEMENT
    else:
        engagement = ""
    return f"{themed} {base} {_HASHTAG_BRANDED} {engagement}".strip()


def _caption_formal(content: Dict[str, Any]) -> str:
    arabic = content["arabic"]
    translation = content["translation"]
    title = _get_title(content)
    explanation = content.get("explanation") or content.get("tafsir", "")
    theme = content.get("theme", "islam")
    hashtags = _build_hashtags(theme)

    return (
        f"📖 {title}\n\n"
        f"{arabic}\n\n"
        f"Artinya: \"{translation}\"\n\n"
        f"Tafsir:\n{explanation}\n\n"
        f"Semoga kita dapat mengamalkan pesan yang terkandung di dalamnya.\n\n"
        f"{hashtags}"
    )


def _caption_casual(content: Dict[str, Any]) -> str:
    arabic = content["arabic"]
    translation = content["translation"]
    title = _get_title(content)
    theme = content.get("theme", "islam")
    hashtags = _build_hashtags(theme)

    return (
        f"✨ {title}\n\n"
        f"{arabic}\n\n"
        f"\"{translation}\"\n\n"
        f"Keren banget kan? Yuk share ke teman-teman yang butuh motivasi! 🤲\n\n"
        f"Save postingan ini buat dibaca lagi nanti ya! 💾\n\n"
        f"{hashtags}"
    )


def _caption_storytelling(content):
    arabic = content["arabic"]
    translation = content["translation"]
    title = _get_title(content)
    explanation = content.get("explanation") or content.get("tafsir", "")
    theme = content.get("theme", "islam")
    hashtags = _build_hashtags(theme)

    return (
        f"🌙 Pagi ini, saat kita memulai hari...\n\n"
        f"Ada satu pesan yang ingin aku bagikan:\n\n"
        f"{arabic}\n\n"
        f"\"{translation}\"\n\n"
        f"— {title}\n\n"
        f"Renungan:\n{explanation}\n\n"
        f"Semoga pesan ini bisa menjadi pengingat bagi kita semua. 🤍\n\n"
        f"{hashtags}"
    )


def _random_caption(content):
    opener = random.choice(_OPENERS)
    closer = random.choice(_CLOSERS)
    question = random.choice(_REFLECTIVE_QUESTIONS)

    arabic = content["arabic"]
    translation = content["translation"]
    title = _get_title(content)
    explanation = content.get("explanation") or content.get("tafsir", "")
    theme = content.get("theme", "islam")
    hashtags = _build_hashtags(theme)

    return (
        f"{opener}"
        f"{arabic}\n\n"
        f"\"{translation}\"\n\n"
        f"— {title}\n\n"
        f"{explanation}"
        f"{closer}"
        f"\n\n{question}"
        f"\n\n{hashtags}"
    )


CAPTION_STYLES = {
    "random": _random_caption,
    "formal": _caption_formal,
    "casual": _caption_casual,
    "storytelling": _caption_storytelling,
}


class ContentGenerator:
    def __init__(self, data_paths=None, caption_style="random"):
        self._lock = threading.Lock()
        self.caption_style = caption_style
        paths = data_paths or DEFAULT_DATA_PATHS
        self.verses = []
        for path in paths:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    self.verses.extend(json.load(f))
        self.generated_keys = self._load_generated()

    def _load_generated(self):
        if not os.path.exists(GENERATED_PATH):
            return set()
        try:
            with open(GENERATED_PATH, "r", encoding="utf-8") as f:
                fcntl.flock(f, fcntl.LOCK_SH)
                try:
                    return set(tuple(x) for x in json.load(f))
                finally:
                    fcntl.flock(f, fcntl.LOCK_UN)
        except (json.JSONDecodeError, OSError):
            return set()

    def _save_generated(self):
        os.makedirs(os.path.dirname(GENERATED_PATH), exist_ok=True)
        lock_path = GENERATED_PATH + ".lock"
        with open(lock_path, "w") as lock_file:
            fcntl.flock(lock_file, fcntl.LOCK_EX)
            try:
                with open(GENERATED_PATH, "w", encoding="utf-8") as f:
                    json.dump(list(self.generated_keys), f, indent=2)
            finally:
                fcntl.flock(lock_file, fcntl.LOCK_UN)

    def mark_generated(self, content):
        with self._lock:
            key = _key(content)
            self.generated_keys.add(key)
            if len(self.generated_keys) > GENERATED_MAX_ENTRIES:
                keys_list = list(self.generated_keys)
                self.generated_keys = set(keys_list[-GENERATED_MAX_ENTRIES // 2:])
            self._save_generated()

    def reset_generated(self):
        with self._lock:
            self.generated_keys = set()
            if os.path.exists(GENERATED_PATH):
                os.remove(GENERATED_PATH)

    def list_themes(self):
        themes = set(v["theme"] for v in self.verses)
        return sorted(themes)

    def list_caption_styles(self):
        return list(CAPTION_STYLES.keys())

    def set_caption_style(self, style):
        if style in CAPTION_STYLES:
            self.caption_style = style
            return True
        return False

    def search(self, query, limit=5):
        query_lower = query.lower()
        results = []
        for v in self.verses:
            translation = (v.get("translation") or "").lower()
            explanation = (v.get("explanation") or v.get("tafsir") or "").lower()
            surah = (v.get("surah") or "").lower()
            book = (v.get("book") or "").lower()
            narrator = (v.get("narrator") or "").lower()
            if (query_lower in translation or query_lower in explanation or
                    query_lower in surah or query_lower in book or query_lower in narrator):
                results.append(v)
                if len(results) >= limit:
                    break
        return results

    @staticmethod
    def get_today_theme(calendar_map=None):
        if calendar_map:
            weekday = datetime.datetime.today().weekday()
            if weekday < len(calendar_map):
                return calendar_map[weekday]
        return None

    def get_random(self, theme=None):
        with self._lock:
            pool = self.verses
            if theme:
                pool = [v for v in self.verses if v.get("theme") == theme]
            available = [v for v in pool if _key(v) not in self.generated_keys]
            if not available:
                if theme:
                    available = [v for v in self.verses if _key(v) not in self.generated_keys]
                if not available:
                    self.reset_generated()
                    available = [v for v in pool if _key(v) not in self.generated_keys]
                    if not available and theme:
                        available = [v for v in self.verses if _key(v) not in self.generated_keys]
            verse = random.choice(available)
            return self._format(verse)

    def _format(self, verse):
        caption_fn = CAPTION_STYLES.get(self.caption_style, _random_caption)
        caption = caption_fn(verse)

        result = {
            "caption": caption,
            "arabic": verse.get("arabic", ""),
            "translation": verse.get("translation", ""),
            "explanation": verse.get("explanation") or verse.get("tafsir", ""),
            "theme": verse.get("theme", ""),
            "type": verse.get("type", "quran"),
            "source": verse.get("source", ""),
        }

        if verse.get("type") == "hadith":
            result["book"] = verse.get("book", "")
            result["hadith_number"] = verse.get("hadith_number", "")
            result["narrator"] = verse.get("narrator", "")
            result["surah"] = verse.get("book", "")
            result["ayat"] = verse.get("hadith_number", "")
        elif verse.get("type") in ("dua", "dzikir"):
            result["surah"] = ""
            result["ayat"] = ""
        else:
            result["surah"] = verse.get("surah", "")
            result["ayat"] = verse.get("ayat", "")
            result["tafsir"] = result["explanation"]

        return result
