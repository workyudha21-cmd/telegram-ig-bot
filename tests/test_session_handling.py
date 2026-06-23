import time
import unittest
from unittest.mock import MagicMock, patch

from instagrapi.exceptions import LoginRequired, ClientError, ChallengeError

from instagram_uploader import InstagramUploader


def _make_uploader(callback=None):
    with patch("instagram_uploader.Client") as mock_client:
        mock_client.return_value = MagicMock()
        uploader = InstagramUploader("user", "pass", proxy="", on_login_failure=callback)
    return uploader


class TestIsSessionExpiredError(unittest.TestCase):
    def setUp(self):
        self.uploader = _make_uploader()

    def test_login_required_is_expired(self):
        self.assertTrue(self.uploader._is_session_expired_error(LoginRequired()))

    def test_session_expired_message(self):
        err = ClientError("Session expired")
        self.assertTrue(self.uploader._is_session_expired_error(err))

    def test_session_invalid_message(self):
        err = ClientError("session is invalid, please login again")
        self.assertTrue(self.uploader._is_session_expired_error(err))

    def test_challenge_message(self):
        err = ClientError("challenge required")
        self.assertTrue(self.uploader._is_session_expired_error(err))

    def test_unrelated_error_not_expired(self):
        err = ClientError("Network timeout")
        self.assertFalse(self.uploader._is_session_expired_error(err))

    def test_generic_exception_not_expired(self):
        self.assertFalse(self.uploader._is_session_expired_error(ValueError("boom")))


class TestNotifyLoginFailure(unittest.TestCase):
    def setUp(self):
        self.uploader = _make_uploader()

    def test_callback_invoked(self):
        called = []
        self.uploader.on_login_failure = lambda r: called.append(r)
        self.uploader._notify_login_failure("Login gagal: bad password")
        self.assertEqual(called, ["Login gagal: bad password"])

    def test_debounce_within_window(self):
        called = []
        self.uploader.on_login_failure = lambda r: called.append(r)
        self.uploader._last_login_alert_ts = time.time()
        self.uploader._notify_login_failure("first")
        self.uploader._notify_login_failure("second")
        self.assertEqual(called, [])

    def test_callback_exception_swallowed(self):
        def bad_cb(_):
            raise RuntimeError("boom")
        self.uploader.on_login_failure = bad_cb
        try:
            self.uploader._notify_login_failure("test")
        except Exception:
            self.fail("_notify_login_failure should not propagate callback errors")

    def test_no_callback_no_crash(self):
        self.uploader.on_login_failure = None
        self.uploader._notify_login_failure("test")


class TestUploadWithSessionRetry(unittest.TestCase):
    def setUp(self):
        self.uploader = _make_uploader()
        self.uploader.logged_in = True

    def test_success_no_retry(self):
        self.uploader._ensure_login = MagicMock(return_value=(True, "OK"))
        self.uploader._is_session_expired_error = MagicMock(return_value=False)
        call_count = [0]
        def _do():
            call_count[0] += 1
            return True, "uploaded"
        ok, msg = self.uploader._upload_with_session_retry(_do, "Photo", max_retries=2)
        self.assertTrue(ok)
        self.assertEqual(msg, "uploaded")
        self.assertEqual(call_count[0], 1)

    def test_session_expired_triggers_relogin(self):
        self.uploader._ensure_login = MagicMock(return_value=(True, "OK"))
        self.uploader._is_session_expired_error = MagicMock(return_value=True)
        self.uploader._notify_login_failure = MagicMock()
        results = [ClientError("Session expired"), (True, "ok second try")]
        def _do():
            r = results.pop(0)
            if isinstance(r, Exception):
                raise r
            return r
        ok, msg = self.uploader._upload_with_session_retry(_do, "Photo", max_retries=1)
        self.assertTrue(ok)
        self.assertEqual(msg, "ok second try")
        self.assertEqual(self.uploader.logged_in, False)

    def test_unrelated_error_not_retried(self):
        self.uploader._ensure_login = MagicMock(return_value=(True, "OK"))
        call_count = [0]
        def _do():
            call_count[0] += 1
            raise ClientError("Network timeout")
        ok, msg = self.uploader._upload_with_session_retry(_do, "Photo", max_retries=3)
        self.assertFalse(ok)
        self.assertIn("Network timeout", msg)
        self.assertEqual(call_count[0], 1)

    def test_login_failure_short_circuits(self):
        self.uploader._ensure_login = MagicMock(return_value=(False, "auth bad"))
        called = [False]
        def _do():
            called[0] = True
            return True, "should not happen"
        ok, msg = self.uploader._upload_with_session_retry(_do, "Photo")
        self.assertFalse(ok)
        self.assertEqual(msg, "auth bad")
        self.assertFalse(called[0])


if __name__ == "__main__":
    unittest.main()
