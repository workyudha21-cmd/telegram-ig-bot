import json
import logging
import os
import re
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from trending_content_generator import TrendingContentGenerator

logger = logging.getLogger(__name__)

HISTORY_PATH = os.path.join(os.path.dirname(__file__), "data", "history.json")
SCHEDULE_PATH = os.path.join(os.path.dirname(__file__), "data", "schedule.json")

BANTUAN_TEXT = (
    "📖 Bantuan:\n\n"
    "/post - Langsung posting konten random ke Instagram\n"
    "/post_theme - Pilih tema lalu posting\n"
    "/preview - Lihat konten sebelum diposting\n"
    "/trending - Post berdasarkan berita trending\n"
    "/post_story - Post story ke Instagram\n"
    "/carousel - Buat carousel 3 slide untuk Instagram\n"
    "/search <kata> - Cari konten berdasarkan kata kunci\n"
    "/set_schedule <jam> - Ubah jadwal auto-post (contoh: /set_schedule 07:00,12:00,19:00)\n"
    "/reset_generated - Reset konten yang sudah diposting\n"
    "/history - Lihat riwayat post terakhir\n"
    "/stats - Statistik bot\n"
    "/jadwal - Info jadwal posting otomatis\n"
    "/themes - Daftar tema konten\n"
    "/menu - Menu utama\n"
    "/bantuan - Pesan ini"
)


def _unique_filename(suffix=".png"):
    return f"{int(time.time() * 1000)}_{suffix}"

THEME_NAMES = {
    "keimanan": "Keimanan",
    "motivasi": "Motivasi",
    "muhasabah": "Muhasabah",
    "akhlak": "Akhlak",
    "keluarga": "Keluarga",
    "doa": "Doa",
}


def _main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔥 Post Berdasarkan Trending", callback_data="menu_trending")],
        [InlineKeyboardButton("🎲 Post Random ke IG", callback_data="menu_post")],
        [InlineKeyboardButton("🎨 Post by Tema", callback_data="menu_post_theme")],
        [InlineKeyboardButton("👁 Preview Konten", callback_data="menu_preview")],
        [InlineKeyboardButton("📜 Carousel (3 Slide)", callback_data="menu_carousel")],
        [InlineKeyboardButton("📖 Post ke Story", callback_data="menu_story")],
        [InlineKeyboardButton("📊 Statistik", callback_data="menu_stats")],
        [InlineKeyboardButton("📜 Riwayat Post", callback_data="menu_history")],
        [InlineKeyboardButton("📅 Jadwal Otomatis", callback_data="menu_jadwal")],
        [InlineKeyboardButton("📚 Daftar Tema", callback_data="menu_themes")],
        [InlineKeyboardButton("❓ Bantuan", callback_data="menu_bantuan")],
    ])


def _confirm_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Post ke IG", callback_data="confirm_post"),
            InlineKeyboardButton("🔄 Coba lain", callback_data="retry_preview"),
        ]
    ])


def _story_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📖 Post ke Story juga", callback_data="post_story"),
            InlineKeyboardButton("✅ Selesai", callback_data="story_done"),
        ]
    ])


def _theme_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(name, callback_data=f"theme_{key}")]
        for key, name in THEME_NAMES.items()
    ])


class TelegramBot:
    def __init__(self, token, content_gen, image_gen, ig_uploader, allowed_user_ids=None, trending_content_gen=None):
        self.token = token
        self.content_gen = content_gen
        self.image_gen = image_gen
        self.ig_uploader = ig_uploader
        self.trending_content_gen = trending_content_gen
        self.allowed_user_ids = allowed_user_ids or []
        self._app = None

    def _is_allowed(self, user_id):
        if not self.allowed_user_ids:
            return True
        return user_id in self.allowed_user_ids

    def _generate(self, context, theme=None, trending=False, suffix="post.png"):
        if trending:
            content = self.trending_content_gen.generate()
        elif theme:
            content = self.content_gen.get_random(theme=theme)
        else:
            content = self.content_gen.get_random()
        self.content_gen.mark_generated(content)
        path = self.image_gen.generate(content, _unique_filename(suffix))
        context.user_data["preview_content"] = content
        context.user_data["preview_path"] = path
        return content, path

    def _upload_with_retry(self, upload_fn, max_retries=3):
        last_error = "Unknown error"
        for attempt in range(1, max_retries + 1):
            ok, msg = upload_fn()
            if ok:
                return True, msg
            last_error = msg
            if attempt < max_retries:
                time.sleep(3 * attempt)
        return False, last_error

    def _format_stats_text(self):
        total_available = len(self.content_gen.verses)
        if not os.path.exists(HISTORY_PATH):
            return (
                f"📊 *Statistik Bot*\n\n"
                f"Total konten: {total_available}\n"
                f"Post sukses: 0"
            )
        with open(HISTORY_PATH, "r") as f:
            data = json.load(f)
        total_post = len(data)
        by_theme = {}
        by_type = {}
        for item in data:
            t = item.get("theme", "?")
            by_theme[t] = by_theme.get(t, 0) + 1
            tp = item.get("type", "quran")
            by_type[tp] = by_type.get(tp, 0) + 1
        theme_lines = "\n".join(f"• {k}: {v}" for k, v in sorted(by_theme.items()))
        type_lines = "\n".join(f"• {k}: {v}" for k, v in sorted(by_type.items()))
        return (
            f"📊 *Statistik Bot*\n\n"
            f"*Konten Tersedia:* {total_available}\n"
            f"*Total Post:* {total_post}\n"
            f"*Per Tema:*\n{theme_lines}\n\n"
            f"*Per Sumber:*\n{type_lines}"
        )

    def _format_history_text(self):
        if not os.path.exists(HISTORY_PATH):
            return None
        with open(HISTORY_PATH, "r") as f:
            data = json.load(f)
        if not data:
            return None
        lines = ["📜 *Riwayat Post Terakhir:*\n"]
        for item in data[-10:]:
            lines.append(
                f"• {item.get('surah', '?')}:{item.get('ayat', '?')} "
                f"({item.get('theme', '?')}) "
                f"— {item.get('timestamp', '?')}"
            )
        return "\n".join(lines)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_allowed(update.effective_user.id):
            await update.message.reply_text("Maaf, kamu tidak memiliki akses.")
            return
        await update.message.reply_text(
            "Assalamu'alaikum! 🌙\n\n"
            "Aku adalah bot pembuat konten Islami untuk Instagram.\n\n"
            "Ketik pesan apa saja atau pilih menu di bawah ini:",
            reply_markup=_main_menu_keyboard(),
        )

    async def any_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_allowed(update.effective_user.id):
            return
        await update.message.reply_text(
            "📋 Pilih menu di bawah ini:",
            reply_markup=_main_menu_keyboard(),
        )

    async def menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_allowed(update.effective_user.id):
            return
        await update.message.reply_text(
            "📋 Menu utama:\n\nPilih aksi yang ingin dilakukan:",
            reply_markup=_main_menu_keyboard(),
        )

    async def post(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_allowed(update.effective_user.id):
            return
        msg = await update.message.reply_text("⏳ Membuat konten...")
        try:
            content, path = self._generate(context)
            with open(path, "rb") as f:
                await update.message.reply_photo(f, caption=content["caption"])
            ok, result = self._upload_with_retry(
                lambda: self.ig_uploader.upload_photo(path, content["caption"])
            )
            status = "✅ " + result if ok else "❌ " + result
            if ok:
                context.user_data["story_content"] = content
                await msg.edit_text(status, reply_markup=_story_keyboard())
            else:
                await msg.edit_text(status)
        except (OSError, ValueError) as e:
            await msg.edit_text(f"❌ Error: {str(e)}")

    async def post_theme(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_allowed(update.effective_user.id):
            return
        await update.message.reply_text("Pilih tema:", reply_markup=_theme_keyboard())

    async def theme_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        theme = query.data.replace("theme_", "")
        msg = await query.edit_message_text(f"⏳ Membuat konten tema: {THEME_NAMES.get(theme, theme)}...")
        try:
            content, path = self._generate(context, theme=theme, suffix=f"{theme}.png")
            with open(path, "rb") as f:
                await query.message.reply_photo(f, caption=content["caption"])
            ok, result = self._upload_with_retry(
                lambda: self.ig_uploader.upload_photo(path, content["caption"])
            )
            status = "✅ " + result if ok else "❌ " + result
            await msg.edit_text(status)
        except (OSError, ValueError) as e:
            await msg.edit_text(f"❌ Error: {str(e)}")

    async def preview(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_allowed(update.effective_user.id):
            return
        msg = await update.message.reply_text("⏳ Membuat preview...")
        try:
            content, path = self._generate(context, suffix="preview.png")
            with open(path, "rb") as f:
                await update.message.reply_photo(
                    f, caption=content["caption"], reply_markup=_confirm_keyboard()
                )
            await msg.delete()
        except Exception as e:
            await msg.edit_text(f"❌ Error: {str(e)}")

    async def preview_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        if query.data == "confirm_post":
            content = context.user_data.get("preview_content")
            if not content:
                await query.answer("❌ Session expired. Coba /preview lagi.", show_alert=True)
                return
            await query.message.delete()
            msg = await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="⏳ Mengupload ke Instagram..."
            )
            path = context.user_data.get("preview_path")
            if not path:
                path = self.image_gen.generate(content, "upload.png")
            ok, result = self.ig_uploader.upload_photo(path, content["caption"])
            status = "✅ " + result if ok else "❌ " + result
            await msg.edit_text(status)
        elif query.data == "retry_preview":
            await query.message.delete()
            try:
                content, path = self._generate(context, suffix="preview.png")
                with open(path, "rb") as f:
                    await query.message.reply_photo(
                        f, caption=content["caption"], reply_markup=_confirm_keyboard()
                    )
            except Exception as e:
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text=f"❌ Error: {str(e)}"
                )

    async def trending(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_allowed(update.effective_user.id):
            return
        if not self.trending_content_gen:
            await update.message.reply_text(
                "❌ Fitur trending belum diatur. Tambahkan NEWS_API_KEY dan GEMINI_API_KEY di file .env"
            )
            return
        msg = await update.message.reply_text("⏳ Mencari berita trending dan membuat konten...")
        try:
            content, path = self._generate(context, trending=True, suffix="trending.png")
            with open(path, "rb") as f:
                await update.message.reply_photo(
                    f, caption=content["caption"], reply_markup=_confirm_keyboard()
                )
            await msg.delete()
        except Exception as e:
            await msg.edit_text(f"❌ Error: {str(e)}")

    async def jadwal(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_allowed(update.effective_user.id):
            return
        current_times = []
        if os.path.exists(SCHEDULE_PATH):
            try:
                with open(SCHEDULE_PATH, "r") as f:
                    data = json.load(f)
                    current_times = data.get("times", [])
            except (OSError, json.JSONDecodeError):
                pass
        if not current_times:
            from config import AUTO_POST_SCHEDULE
            current_times = [t.strip() for t in AUTO_POST_SCHEDULE.split(",")]
        schedule_text = ", ".join(current_times)
        await update.message.reply_text(
            f"📅 Jadwal posting otomatis saat ini:\n{schedule_text}\n\n"
            f"Untuk mengubah, gunakan:\n/set_schedule 07:00,12:00,19:00"
        )

    async def themes(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_allowed(update.effective_user.id):
            return
        themes_list = self.content_gen.list_themes()
        text = "📚 Tema yang tersedia:\n\n"
        for t in themes_list:
            name = THEME_NAMES.get(t, t)
            text += f"• {name}\n"
        await update.message.reply_text(text)

    async def bantuan(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_allowed(update.effective_user.id):
            return
        await update.message.reply_text(BANTUAN_TEXT)

    async def search(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_allowed(update.effective_user.id):
            return
        query = " ".join(context.args) if context.args else ""
        if not query:
            await update.message.reply_text("Usage: /search <kata kunci>\nContoh: /search sabar")
            return
        results = self.content_gen.search(query, limit=5)
        if not results:
            await update.message.reply_text(f"Tidak ditemukan konten untuk: {query}")
            return
        lines = [f"🔍 Hasil pencarian: *{query}*\n"]
        for v in results:
            title = v.get("surah", "?")
            if v.get("type") == "hadith":
                title = f"HR. {v.get('book', '?')} No. {v.get('hadith_number', '?')}"
            translation = (v.get("translation") or "")[:80]
            lines.append(f"• *{title}* — {translation}...")
        await update.message.reply_text("\n".join(lines))

    async def reset_generated(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_allowed(update.effective_user.id):
            return
        self.content_gen.reset_generated()
        await update.message.reply_text("✅ Daftar konten yang sudah diposting berhasil direset.")

    async def set_schedule(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_allowed(update.effective_user.id):
            return
        schedule_str = " ".join(context.args) if context.args else ""
        if not schedule_str:
            await update.message.reply_text(
                "Usage: /set_schedule <jam1,jam2,...>\n"
                "Contoh: /set_schedule 07:00,12:00,19:00\n"
                "Gunakan /jadwal untuk melihat jadwal saat ini."
            )
            return
        times = [t.strip() for t in schedule_str.split(",") if t.strip()]
        for t in times:
            if not re.match(r"^\d{2}:\d{2}$", t):
                await update.message.reply_text(f"❌ Format jam salah: {t}\nGunakan format HH:MM (contoh: 07:00)")
                return
        os.makedirs(os.path.dirname(SCHEDULE_PATH), exist_ok=True)
        with open(SCHEDULE_PATH, "w") as f:
            json.dump({"times": times}, f, indent=2)
        await update.message.reply_text(
            f"✅ Jadwal auto-post berhasil diubah!\n"
            f"Jadwal baru: {', '.join(times)}\n\n"
            f"Perubahan akan aktif dalam 30 detik."
        )

    async def history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_allowed(update.effective_user.id):
            return
        try:
            text = self._format_history_text()
            if not text:
                await update.message.reply_text("Belum ada riwayat post.")
                return
            await update.message.reply_text(text)
        except (json.JSONDecodeError, OSError) as e:
            await update.message.reply_text(f"❌ Gagal membaca riwayat: {e}")

    async def notify_admin(self, text):
        if not self._app:
            logger.warning("Tidak bisa kirim notifikasi: bot belum berjalan.")
            return
        for uid in self.allowed_user_ids:
            try:
                await self._app.bot.send_message(chat_id=uid, text=text)
            except Exception as e:
                logger.warning(f"Gagal kirim notifikasi ke {uid}: {e}")

    async def _post_story(self, update_or_query, context, content=None, msg=None):
        if not content:
            content = context.user_data.get("story_content")
        if not content:
            content = context.user_data.get("preview_content")
        if not content:
            text = "❌ Tidak ada konten untuk story. Buat konten dulu."
            if msg:
                await msg.edit_text(text)
            else:
                await update_or_query.message.reply_text(text)
            return
        story_path = self.image_gen.generate_story(content, f"story_{int(time.time())}.png")
        ok, result = self.ig_uploader.upload_story(story_path)
        status = "📖 " + result if ok else "❌ " + result
        if msg:
            await msg.edit_text(status)
        else:
            await update_or_query.message.reply_text(status)

    async def story_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        if query.data == "post_story":
            await query.edit_message_text("⏳ Mengupload ke Story...")
            content = context.user_data.get("story_content") or context.user_data.get("preview_content")
            if not content:
                await query.edit_message_text("❌ Session expired. Buat konten dulu.")
                return
            story_path = self.image_gen.generate_story(content, f"story_{int(time.time())}.png")
            ok, result = self.ig_uploader.upload_story(story_path)
            status = "📖 " + result if ok else "❌ " + result
            await query.edit_message_text(status)
        elif query.data == "story_done":
            await query.message.delete()

    async def post_story(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_allowed(update.effective_user.id):
            return
        msg = await update.message.reply_text("⏳ Membuat story...")
        try:
            content, _ = self._generate(context, suffix="story.png")
            story_path = self.image_gen.generate_story(content, f"story_{int(time.time())}.png")
            with open(story_path, "rb") as f:
                await update.message.reply_photo(f, caption="📖 Preview story")
            ok, result = self._upload_with_retry(
                lambda: self.ig_uploader.upload_story(story_path)
            )
            status = "📖 " + result if ok else "❌ " + result
            await msg.edit_text(status)
        except (OSError, ValueError) as e:
            await msg.edit_text(f"❌ Error: {str(e)}")

    async def carousel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_allowed(update.effective_user.id):
            return
        msg = await update.message.reply_text("⏳ Membuat carousel (3 slide)...")
        try:
            content, _ = self._generate(context, suffix="carousel.png")
            paths = self.image_gen.generate_carousel(content, prefix=f"carousel_{update.effective_user.id}")

            files = []
            media_group = []
            try:
                for i, p in enumerate(paths):
                    f = open(p, "rb")
                    files.append(f)
                    media_group.append(InputMediaPhoto(f, caption=f"📖 Slide {i+1}/3" if i == 0 else None))
                await update.message.reply_media_group(media_group)
            finally:
                for f in files:
                    f.close()

            keyboard = [
                [
                    InlineKeyboardButton("✅ Upload ke IG (Album)", callback_data="carousel_upload"),
                    InlineKeyboardButton("❌ Batal", callback_data="carousel_cancel"),
                ]
            ]
            context.user_data["carousel_paths"] = paths
            context.user_data["carousel_content"] = content
            await msg.edit_text("✅ Carousel siap! Mau upload ke Instagram?", reply_markup=InlineKeyboardMarkup(keyboard))
        except Exception as e:
            await msg.edit_text(f"❌ Error: {str(e)}")

    async def carousel_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        if query.data == "carousel_upload":
            paths = context.user_data.get("carousel_paths")
            content = context.user_data.get("carousel_content")
            if not paths or not content:
                await query.edit_message_text("❌ Session expired. Coba /carousel lagi.")
                return
            await query.edit_message_text("⏳ Uploading album ke Instagram...")
            ok, result = self.ig_uploader.upload_album(paths, content["caption"])
            status = "✅ " + result if ok else "❌ " + result
            await query.edit_message_text(status)
        elif query.data == "carousel_cancel":
            await query.message.delete()

    async def stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_allowed(update.effective_user.id):
            return
        try:
            text = self._format_stats_text()
            await update.message.reply_text(text)
        except (json.JSONDecodeError, OSError) as e:
            await update.message.reply_text(f"❌ Gagal baca statistik: {e}")

    async def menu_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        if not self._is_allowed(update.effective_user.id):
            return

        if query.data == "menu_post":
            msg = await query.message.reply_text("⏳ Membuat konten...")
            try:
                content, path = self._generate(context)
                with open(path, "rb") as f:
                    await query.message.reply_photo(f, caption=content["caption"])
                ok, result = self.ig_uploader.upload_photo(path, content["caption"])
                status = "✅ " + result if ok else "❌ " + result
                await msg.edit_text(status)
            except Exception as e:
                await msg.edit_text(f"❌ Error: {str(e)}")

        elif query.data == "menu_trending":
            if not self.trending_content_gen:
                await query.answer("❌ Fitur trending belum diatur.", show_alert=True)
                return
            msg = await query.message.reply_text("⏳ Mencari berita trending dan membuat konten...")
            try:
                content, path = self._generate(context, trending=True, suffix="trending.png")
                with open(path, "rb") as f:
                    await query.message.reply_photo(
                        f, caption=content["caption"], reply_markup=_confirm_keyboard()
                    )
                await msg.delete()
            except Exception as e:
                await msg.edit_text(f"❌ Error: {str(e)}")

        elif query.data == "menu_post_theme":
            await query.edit_message_text("Pilih tema:", reply_markup=_theme_keyboard())

        elif query.data == "menu_preview":
            msg = await query.message.reply_text("⏳ Membuat preview...")
            try:
                content, path = self._generate(context, suffix="preview.png")
                with open(path, "rb") as f:
                    await query.message.reply_photo(
                        f, caption=content["caption"], reply_markup=_confirm_keyboard()
                    )
                await msg.delete()
            except Exception as e:
                await msg.edit_text(f"❌ Error: {str(e)}")

        elif query.data == "menu_carousel":
            msg = await query.message.reply_text("⏳ Membuat carousel (3 slide)...")
            try:
                content, _ = self._generate(context, suffix="carousel.png")
                paths = self.image_gen.generate_carousel(content, prefix=f"carousel_{query.from_user.id}")

                files = []
                media_group = []
                try:
                    for i, p in enumerate(paths):
                        f = open(p, "rb")
                        files.append(f)
                        media_group.append(InputMediaPhoto(f, caption=f"Slide {i+1}/3" if i == 0 else None))
                    await query.message.reply_media_group(media_group)
                finally:
                    for f in files:
                        f.close()

                keyboard = [
                    [
                        InlineKeyboardButton("Upload ke IG (Album)", callback_data="carousel_upload"),
                        InlineKeyboardButton("Batal", callback_data="carousel_cancel"),
                    ]
                ]
                context.user_data["carousel_paths"] = paths
                context.user_data["carousel_content"] = content
                await msg.edit_text("Carousel siap! Mau upload ke Instagram?", reply_markup=InlineKeyboardMarkup(keyboard))
            except Exception as e:
                await msg.edit_text(f"❌ Error: {str(e)}")

        elif query.data == "menu_story":
            msg = await query.message.reply_text("⏳ Membuat story...")
            try:
                content, _ = self._generate(context, suffix="story.png")
                story_path = self.image_gen.generate_story(content, f"story_{int(time.time())}.png")
                with open(story_path, "rb") as f:
                    await query.message.reply_photo(f, caption="Preview story")
                ok, result = self.ig_uploader.upload_story(story_path)
                status = "📖 " + result if ok else "❌ " + result
                await msg.edit_text(status)
            except Exception as e:
                await msg.edit_text(f"❌ Error: {str(e)}")

        elif query.data == "menu_stats":
            try:
                text = self._format_stats_text()
                await query.edit_message_text(text, reply_markup=_main_menu_keyboard(), parse_mode="Markdown")
            except (json.JSONDecodeError, OSError) as e:
                await query.edit_message_text(f"❌ Error: {e}", reply_markup=_main_menu_keyboard())

        elif query.data == "menu_history":
            try:
                text = self._format_history_text()
                if not text:
                    await query.edit_message_text("Belum ada riwayat post.", reply_markup=_main_menu_keyboard())
                    return
                await query.edit_message_text(text, reply_markup=_main_menu_keyboard(), parse_mode="Markdown")
            except (json.JSONDecodeError, OSError) as e:
                await query.edit_message_text(f"❌ Error: {e}", reply_markup=_main_menu_keyboard())

        elif query.data == "menu_jadwal":
            current_times = []
            if os.path.exists(SCHEDULE_PATH):
                try:
                    with open(SCHEDULE_PATH, "r") as f:
                        data = json.load(f)
                        current_times = data.get("times", [])
                except (OSError, json.JSONDecodeError):
                    pass
            if not current_times:
                from config import AUTO_POST_SCHEDULE
                current_times = [t.strip() for t in AUTO_POST_SCHEDULE.split(",")]
            schedule_text = ", ".join(current_times)
            await query.edit_message_text(
                f"📅 Jadwal posting otomatis saat ini:\n{schedule_text}\n\n"
                f"Untuk mengubah, gunakan:\n/set_schedule 07:00,12:00,19:00",
                reply_markup=_main_menu_keyboard(),
            )

        elif query.data == "menu_themes":
            themes_list = self.content_gen.list_themes()
            text = "📚 Tema yang tersedia:\n\n"
            for t in themes_list:
                name = THEME_NAMES.get(t, t)
                text += f"• {name}\n"
            await query.edit_message_text(text, reply_markup=_main_menu_keyboard())

        elif query.data == "menu_bantuan":
            await query.edit_message_text(
                BANTUAN_TEXT,
                reply_markup=_main_menu_keyboard(),
            )

    def run(self):
        self._app = Application.builder().token(self.token).build()

        self._app.add_handler(CommandHandler("start", self.start))
        self._app.add_handler(CommandHandler("menu", self.menu))
        self._app.add_handler(CommandHandler("post", self.post))
        self._app.add_handler(CommandHandler("post_theme", self.post_theme))
        self._app.add_handler(CommandHandler("preview", self.preview))
        self._app.add_handler(CommandHandler("trending", self.trending))
        self._app.add_handler(CommandHandler("post_story", self.post_story))
        self._app.add_handler(CommandHandler("carousel", self.carousel))
        self._app.add_handler(CommandHandler("history", self.history))
        self._app.add_handler(CommandHandler("stats", self.stats))
        self._app.add_handler(CommandHandler("jadwal", self.jadwal))
        self._app.add_handler(CommandHandler("themes", self.themes))
        self._app.add_handler(CommandHandler("bantuan", self.bantuan))
        self._app.add_handler(CommandHandler("search", self.search))
        self._app.add_handler(CommandHandler("reset_generated", self.reset_generated))
        self._app.add_handler(CommandHandler("set_schedule", self.set_schedule))

        self._app.add_handler(CallbackQueryHandler(self.theme_callback, pattern="^theme_"))
        self._app.add_handler(CallbackQueryHandler(self.preview_callback, pattern="^(confirm_post|retry_preview)$"))
        self._app.add_handler(CallbackQueryHandler(self.story_callback, pattern="^(post_story|story_done)$"))
        self._app.add_handler(CallbackQueryHandler(self.carousel_callback, pattern="^(carousel_upload|carousel_cancel)$"))
        self._app.add_handler(CallbackQueryHandler(self.menu_callback, pattern="^menu_"))

        self._app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.any_message))

        logger.info("Bot started polling...")
        self._app.run_polling(allowed_updates=Update.ALL_TYPES)
