import os
import tempfile
import time
import unittest
from unittest.mock import MagicMock

from telegram_bot import TelegramBot


def _make_bot():
    return TelegramBot(
        token="test",
        content_gen=MagicMock(),
        image_gen=MagicMock(),
        ig_uploader=MagicMock(),
        allowed_user_ids=[1, 2, 3],
        trending_content_gen=None,
        reels_gen=None,
    )


class TestRateLimit(unittest.TestCase):
    def test_first_action_allowed(self):
        bot = _make_bot()
        allowed, retry = bot._check_rate_limit(1)
        self.assertTrue(allowed)
        self.assertEqual(retry, 0)

    def test_under_limit_allowed(self):
        bot = _make_bot()
        for _ in range(TelegramBot.RATE_LIMIT_MAX_ACTIONS - 1):
            allowed, _ = bot._check_rate_limit(1)
            self.assertTrue(allowed)

    def test_at_limit_blocked(self):
        bot = _make_bot()
        for _ in range(TelegramBot.RATE_LIMIT_MAX_ACTIONS):
            bot._check_rate_limit(1)
        allowed, retry = bot._check_rate_limit(1)
        self.assertFalse(allowed)
        self.assertGreater(retry, 0)
        self.assertLessEqual(retry, TelegramBot.RATE_LIMIT_WINDOW_SECONDS + 1)

    def test_per_user_isolation(self):
        bot = _make_bot()
        for _ in range(TelegramBot.RATE_LIMIT_MAX_ACTIONS):
            bot._check_rate_limit(1)
        allowed_user2, _ = bot._check_rate_limit(2)
        self.assertTrue(allowed_user2)

    def test_window_expiry_resets(self):
        bot = _make_bot()
        old_ts = time.time() - (TelegramBot.RATE_LIMIT_WINDOW_SECONDS + 10)
        bot._user_action_log[1] = [old_ts] * TelegramBot.RATE_LIMIT_MAX_ACTIONS
        allowed, _ = bot._check_rate_limit(1)
        self.assertTrue(allowed)


class TestIsAllowed(unittest.TestCase):
    def test_allowed_user(self):
        bot = _make_bot()
        self.assertTrue(bot._is_allowed(1))

    def test_blocked_user(self):
        bot = _make_bot()
        self.assertFalse(bot._is_allowed(999))

    def test_empty_allowlist_allows_all(self):
        bot = TelegramBot("t", MagicMock(), MagicMock(), MagicMock(), allowed_user_ids=[])
        self.assertTrue(bot._is_allowed(42))


if __name__ == "__main__":
    unittest.main()
