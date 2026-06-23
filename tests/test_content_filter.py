import json
import os
import tempfile
import time
import unittest
from datetime import datetime, timedelta

import content_generator
from content_generator import ContentGenerator


VERSE_1 = {
    "type": "quran", "surah": "Al-Baqarah", "ayat": "1",
    "arabic": "...", "translation": "...", "explanation": "...",
    "theme": "keimanan",
}
VERSE_2 = {
    "type": "quran", "surah": "Al-Baqarah", "ayat": "2",
    "arabic": "...", "translation": "...", "explanation": "...",
    "theme": "motivasi",
}
VERSE_3 = {
    "type": "quran", "surah": "Ali Imran", "ayat": "1",
    "arabic": "...", "translation": "...", "explanation": "...",
    "theme": "akhlak",
}

TEST_VERSES = [VERSE_1, VERSE_2, VERSE_3]


class _IsolatedContentGen(ContentGenerator):
    """ContentGenerator that ignores on-disk data files for unit tests."""
    pass


def _write_history(path, items):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(items, f)


def _now_ts(days_ago=0, hours_ago=0):
    dt = datetime.now() - timedelta(days=days_ago, hours=hours_ago)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


class TestLoadRecentKeys(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.history = os.path.join(self.tmpdir, "history.json")
        import content_generator
        self._orig_history = content_generator.HISTORY_PATH
        content_generator.HISTORY_PATH = self.history

    def tearDown(self):
        import content_generator
        content_generator.HISTORY_PATH = self._orig_history
        if os.path.exists(self.history):
            os.remove(self.history)
        os.rmdir(self.tmpdir)

    def test_no_history_file(self):
        keys = ContentGenerator._load_recent_keys(days=30)
        self.assertEqual(keys, set())

    def test_zero_days_returns_empty(self):
        _write_history(self.history, [{
            "type": "quran", "surah": "Al-Baqarah", "ayat": "1",
            "theme": "x", "timestamp": _now_ts(days_ago=0),
        }])
        keys = ContentGenerator._load_recent_keys(days=0)
        self.assertEqual(keys, set())

    def test_recent_post_filtered(self):
        _write_history(self.history, [
            {"type": "quran", "surah": "Al-Baqarah", "ayat": "1", "theme": "x", "timestamp": _now_ts(days_ago=1)},
            {"type": "quran", "surah": "Al-Baqarah", "ayat": "2", "theme": "x", "timestamp": _now_ts(days_ago=5)},
        ])
        keys = ContentGenerator._load_recent_keys(days=30)
        self.assertIn(("quran", "Al-Baqarah", "1"), keys)
        self.assertIn(("quran", "Al-Baqarah", "2"), keys)
        self.assertEqual(len(keys), 2)

    def test_old_post_outside_window(self):
        _write_history(self.history, [
            {"type": "quran", "surah": "Al-Baqarah", "ayat": "1", "theme": "x", "timestamp": _now_ts(days_ago=60)},
        ])
        keys = ContentGenerator._load_recent_keys(days=30)
        self.assertEqual(keys, set())

    def test_invalid_timestamp_skipped(self):
        _write_history(self.history, [
            {"type": "quran", "surah": "Al-Baqarah", "ayat": "1", "theme": "x", "timestamp": "bogus"},
        ])
        keys = ContentGenerator._load_recent_keys(days=30)
        self.assertEqual(keys, set())

    def test_empty_surah_ayat_skipped(self):
        _write_history(self.history, [
            {"type": "dua", "surah": "", "ayat": "", "theme": "x", "timestamp": _now_ts(days_ago=1)},
        ])
        keys = ContentGenerator._load_recent_keys(days=30)
        self.assertEqual(keys, set())


class TestGetRandomWithExcludeRecent(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.history = os.path.join(self.tmpdir, "history.json")
        self.gen = _IsolatedContentGen(caption_style="formal")
        self.gen.verses = list(TEST_VERSES)
        self.gen.generated_keys = set()
        self._orig_history_path = content_generator.HISTORY_PATH
        content_generator.HISTORY_PATH = self.history

    def tearDown(self):
        content_generator.HISTORY_PATH = self._orig_history_path
        if os.path.exists(self.history):
            os.remove(self.history)
        os.rmdir(self.tmpdir)

    def test_exclude_recent_skips_posted(self):
        _write_history(self.history, [
            {"type": "quran", "surah": "Al-Baqarah", "ayat": "1", "theme": "keimanan", "timestamp": _now_ts(days_ago=2)},
        ])
        seen = set()
        for _ in range(20):
            v = self.gen.get_random(exclude_recent_days=30)
            seen.add((v["surah"], v["ayat"]))
        self.assertNotIn(("Al-Baqarah", "1"), seen)
        self.assertIn(("Al-Baqarah", "2"), seen)
        self.assertIn(("Ali Imran", "1"), seen)

    def test_exclude_recent_zero_no_filter(self):
        _write_history(self.history, [
            {"type": "quran", "surah": "Al-Baqarah", "ayat": "1", "theme": "keimanan", "timestamp": _now_ts(days_ago=2)},
        ])
        v = self.gen.get_random(exclude_recent_days=0)
        self.assertIn((v["surah"], v["ayat"]), {("Al-Baqarah", "1"), ("Al-Baqarah", "2"), ("Ali Imran", "1")})

    def test_exclude_recent_old_posting_outside_window(self):
        _write_history(self.history, [
            {"type": "quran", "surah": "Al-Baqarah", "ayat": "1", "theme": "keimanan", "timestamp": _now_ts(days_ago=45)},
        ])
        seen = set()
        for _ in range(20):
            v = self.gen.get_random(exclude_recent_days=30)
            seen.add((v["surah"], v["ayat"]))
        self.assertIn(("Al-Baqarah", "1"), seen)


class TestCleanupStaleLocks(unittest.TestCase):
    def test_removes_old_lock(self):
        tmpdir = tempfile.mkdtemp()
        old_lock = os.path.join(tmpdir, "test.lock")
        with open(old_lock, "w") as f:
            f.write("")
        old_time = time.time() - 7200
        os.utime(old_lock, (old_time, old_time))
        removed = ContentGenerator.cleanup_stale_locks(data_dir=tmpdir, max_age_seconds=3600)
        self.assertEqual(removed, 1)
        self.assertFalse(os.path.exists(old_lock))
        os.rmdir(tmpdir)

    def test_keeps_fresh_lock(self):
        tmpdir = tempfile.mkdtemp()
        fresh_lock = os.path.join(tmpdir, "test.lock")
        with open(fresh_lock, "w") as f:
            f.write("")
        removed = ContentGenerator.cleanup_stale_locks(data_dir=tmpdir, max_age_seconds=3600)
        self.assertEqual(removed, 0)
        self.assertTrue(os.path.exists(fresh_lock))
        os.remove(fresh_lock)
        os.rmdir(tmpdir)

    def test_ignores_non_lock_files(self):
        tmpdir = tempfile.mkdtemp()
        old_file = os.path.join(tmpdir, "test.json")
        with open(old_file, "w") as f:
            f.write("{}")
        old_time = time.time() - 7200
        os.utime(old_file, (old_time, old_time))
        removed = ContentGenerator.cleanup_stale_locks(data_dir=tmpdir, max_age_seconds=3600)
        self.assertEqual(removed, 0)
        self.assertTrue(os.path.exists(old_file))
        os.remove(old_file)
        os.rmdir(tmpdir)


if __name__ == "__main__":
    unittest.main()
