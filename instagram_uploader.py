import json
import logging
import os
import time
from instagrapi import Client
from instagrapi.exceptions import LoginRequired, ClientError, ChallengeError

logger = logging.getLogger(__name__)

SESSION_DIR = os.path.join(os.path.dirname(__file__), "data")


class InstagramUploader:
    def __init__(self, username, password, proxy=""):
        self.username = username
        self.password = password
        self.client = Client()
        self.client.request_timeout = 60
        self.client.delay_range = [3, 8]
        if proxy:
            self.client.set_proxy(proxy)
            logger.info(f"Menggunakan proxy: {proxy}")
        self.logged_in = False
        self._load_session()

    def _session_path(self):
        safe = "".join(c for c in self.username if c.isalnum() or c in "._-")
        return os.path.join(SESSION_DIR, f"ig_session_{safe}.json")

    def _load_session(self):
        path = self._session_path()
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    settings = json.load(f)
                self.client.set_settings(settings)
                self.logged_in = True
                logger.info("Session Instagram dimuat dari file.")
            except (OSError, json.JSONDecodeError) as e:
                logger.warning(f"Gagal memuat session: {e}")

    def _save_session(self):
        os.makedirs(SESSION_DIR, exist_ok=True)
        try:
            settings = self.client.get_settings()
            with open(self._session_path(), "w") as f:
                json.dump(settings, f, indent=2)
            logger.info("Session Instagram disimpan ke file.")
        except OSError as e:
            logger.warning(f"Gagal menyimpan session: {e}")

    def _handle_challenge(self, username, choice=None):
        try:
            logger.info(f"Challenge diperlukan untuk {username}")
            self.client.challenge_resolve(self.client.last_json)
            return choice if choice is not None else "0"
        except json.JSONDecodeError:
            logger.error(
                "Instagram meminta verifikasi manual. "
                "Silakan login dari browser/HP terlebih dahulu, selesaikan verifikasi, "
                "lalu coba lagi."
            )
            return "0"
        except (ClientError, OSError) as e:
            logger.warning(f"Gagal resolve challenge: {e}")
            return "0"

    def login(self):
        try:
            self.client.challenge_code_handler = self._handle_challenge
            self.client.login(self.username, self.password)
            self.logged_in = True
            self._save_session()
            time.sleep(5)
            return True, "Login berhasil"
        except LoginRequired:
            try:
                self.client.relogin()
                self.logged_in = True
                self._save_session()
                time.sleep(5)
                return True, "Relogin berhasil"
            except (ClientError, ChallengeError) as e:
                return False, f"Login gagal: {str(e)}"
        except ChallengeError as e:
            return False, f"Challenge diperlukan: {str(e)}"
        except json.JSONDecodeError:
            self.logged_in = False
            return False, (
                "Login gagal: Instagram meminta verifikasi manual. "
                "Silakan login dari browser/HP terlebih dahulu, selesaikan verifikasi, "
                "lalu tunggu beberapa jam sebelum mencoba lagi."
            )
        except (ClientError, OSError) as e:
            return False, f"Login gagal: {str(e)}"

    def upload_photo(self, image_path, caption):
        if not self.logged_in:
            ok, msg = self.login()
            if not ok:
                return False, msg
        try:
            result = self.client.photo_upload(image_path, caption)
            media_id = str(getattr(result, 'id', '0'))
            if media_id in ('0', 'None', ''):
                return False, "Upload dilaporkan sukses tapi media tidak ditemukan. Mungkin kena shadowban."
            time.sleep(3)
            return True, f"Berhasil diupload! Media ID: {media_id}"
        except (ClientError, OSError) as e:
            return False, f"Upload gagal: {str(e)}"

    def upload_story(self, image_path):
        if not self.logged_in:
            ok, msg = self.login()
            if not ok:
                return False, msg
        try:
            result = self.client.photo_upload_to_story(image_path)
            story_id = str(getattr(result, 'id', '0'))
            if story_id in ('0', 'None', ''):
                return False, "Story dilaporkan sukses tapi tidak ditemukan."
            time.sleep(2)
            return True, f"Story berhasil! ID: {story_id}"
        except (ClientError, OSError) as e:
            return False, f"Story gagal: {str(e)}"

    def upload_album(self, image_paths, caption):
        if not self.logged_in:
            ok, msg = self.login()
            if not ok:
                return False, msg
        if not image_paths or len(image_paths) < 2:
            return False, "Album minimal 2 gambar."
        try:
            result = self.client.album_upload(image_paths, caption)
            media_id = str(getattr(result, 'id', '0'))
            if media_id in ('0', 'None', ''):
                return False, "Album dilaporkan sukses tapi tidak ditemukan."
            time.sleep(3)
            return True, f"Album berhasil! ID: {media_id} ({len(image_paths)} slide)"
        except (ClientError, OSError) as e:
            return False, f"Album gagal: {str(e)}"

    def upload_reel(self, video_path, caption):
        if not self.logged_in:
            ok, msg = self.login()
            if not ok:
                return False, msg
        try:
            result = self.client.clip_upload(video_path, caption)
            media_id = str(getattr(result, 'id', '0'))
            if media_id in ('0', 'None', ''):
                return False, "Reels dilaporkan sukses tapi tidak ditemukan."
            time.sleep(3)
            return True, f"Reels berhasil! ID: {media_id}"
        except (ClientError, OSError) as e:
            return False, f"Reels gagal: {str(e)}"

    def logout(self):
        try:
            self.client.logout()
            self.logged_in = False
        except (ClientError, OSError):
            pass
