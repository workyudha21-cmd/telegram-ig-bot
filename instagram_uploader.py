import json
import logging
import os
import time
from typing import Callable, Optional, Tuple
from instagrapi import Client
from instagrapi.exceptions import LoginRequired, ClientError, ChallengeError

logger = logging.getLogger(__name__)

SESSION_DIR = os.path.join(os.path.dirname(__file__), "data")


class InstagramUploader:
    def __init__(self, username, password, proxy="", on_login_failure: Optional[Callable[[str], None]] = None):
        self.username = username
        self.password = password
        self.client = Client()
        self.client.request_timeout = 60
        self.client.delay_range = [3, 8]
        if proxy:
            self.client.set_proxy(proxy)
            logger.info(f"Menggunakan proxy: {proxy}")
        self.logged_in = False
        self.on_login_failure = on_login_failure
        self._last_login_alert_ts = 0.0
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
                self._notify_login_failure(f"Relogin gagal: {e}")
                return False, f"Login gagal: {str(e)}"
        except ChallengeError as e:
            self._notify_login_failure(f"Challenge diperlukan: {e}")
            return False, f"Challenge diperlukan: {str(e)}"
        except json.JSONDecodeError:
            self.logged_in = False
            self._notify_login_failure(
                "Instagram meminta verifikasi manual. Selesaikan via browser/app, lalu tunggu beberapa jam."
            )
            return False, (
                "Login gagal: Instagram meminta verifikasi manual. "
                "Silakan login dari browser/HP terlebih dahulu, selesaikan verifikasi, "
                "lalu tunggu beberapa jam sebelum mencoba lagi."
            )
        except (ClientError, OSError) as e:
            self._notify_login_failure(f"Login gagal: {e}")
            return False, f"Login gagal: {str(e)}"

    def _ensure_login(self) -> Tuple[bool, str]:
        if self.logged_in:
            return True, "OK"
        return self.login()

    def _notify_login_failure(self, reason: str):
        now = time.time()
        if now - self._last_login_alert_ts < 1800:
            return
        self._last_login_alert_ts = now
        logger.error(f"[IG-AUTH] {reason}")
        if self.on_login_failure:
            try:
                self.on_login_failure(reason)
            except Exception as e:
                logger.warning(f"on_login_failure callback error: {e}")

    def _is_session_expired_error(self, err: Exception) -> bool:
        msg = str(err).lower()
        return (
            isinstance(err, LoginRequired)
            or "login_required" in msg
            or "session" in msg and ("expired" in msg or "invalid" in msg)
            or "challenge" in msg
        )

    def _upload_with_session_retry(self, upload_callable, op_name: str, max_retries: int = 1):
        for attempt in range(max_retries + 1):
            ok, msg = self._ensure_login()
            if not ok:
                return False, msg
            try:
                return upload_callable()
            except (ClientError, OSError) as e:
                if attempt < max_retries and self._is_session_expired_error(e):
                    logger.warning(f"{op_name}: session expired, attempting re-login...")
                    self.logged_in = False
                    continue
                return False, f"{op_name} gagal: {str(e)}"

    def upload_photo(self, image_path, caption):
        def _do():
            result = self.client.photo_upload(image_path, caption)
            media_id = str(getattr(result, 'id', '0'))
            if media_id in ('0', 'None', ''):
                return False, "Upload dilaporkan sukses tapi media tidak ditemukan. Mungkin kena shadowban."
            time.sleep(3)
            return True, f"Berhasil diupload! Media ID: {media_id}"
        return self._upload_with_session_retry(_do, "Photo")

    def upload_story(self, image_path):
        def _do():
            result = self.client.photo_upload_to_story(image_path)
            story_id = str(getattr(result, 'id', '0'))
            if story_id in ('0', 'None', ''):
                return False, "Story dilaporkan sukses tapi tidak ditemukan."
            time.sleep(2)
            return True, f"Story berhasil! ID: {story_id}"
        return self._upload_with_session_retry(_do, "Story")

    def upload_album(self, image_paths, caption):
        if not image_paths or len(image_paths) < 2:
            return False, "Album minimal 2 gambar."

        def _do():
            result = self.client.album_upload(image_paths, caption)
            media_id = str(getattr(result, 'id', '0'))
            if media_id in ('0', 'None', ''):
                return False, "Album dilaporkan sukses tapi tidak ditemukan."
            time.sleep(3)
            return True, f"Album berhasil! ID: {media_id} ({len(image_paths)} slide)"
        return self._upload_with_session_retry(_do, "Album")

    def upload_reel(self, video_path, caption):
        def _do():
            result = self.client.clip_upload(video_path, caption)
            media_id = str(getattr(result, 'id', '0'))
            if media_id in ('0', 'None', ''):
                return False, "Reels dilaporkan sukses tapi tidak ditemukan."
            time.sleep(3)
            return True, f"Reels berhasil! ID: {media_id}"
        return self._upload_with_session_retry(_do, "Reels")

    def logout(self):
        try:
            self.client.logout()
            self.logged_in = False
        except (ClientError, OSError):
            pass
