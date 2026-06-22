import os
import tempfile
import unittest

from reels_generator import ReelsGenerator, MOVIEPY_AVAILABLE


class TestReelsGenerator(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.gen = ReelsGenerator(width=1080, height=1920)
        self.content = {
            "arabic": "بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ",
            "translation": "Dengan nama Allah Yang Maha Pengasih lagi Maha Penyayang.",
            "explanation": "Pembuka Al-Fatihah.",
            "surah": "Al-Fatihah",
            "ayat": "1",
            "theme": "keimanan",
            "type": "quran",
        }

    def tearDown(self):
        import shutil
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    @unittest.skipUnless(MOVIEPY_AVAILABLE, "moviepy tidak tersedia")
    def test_generate_reels(self):
        """Test generate Reels 30 detik"""
        video_path = self.gen.generate(self.content, duration=30)
        self.assertTrue(os.path.exists(video_path))
        self.assertTrue(video_path.endswith('.mp4'))

    @unittest.skipUnless(MOVIEPY_AVAILABLE, "moviepy tidak tersedia")
    def test_generate_with_audio(self):
        """Test generate Reels dengan audio Bismillah"""
        video_path = self.gen.generate(self.content, duration=30, audio_type="bismillah")
        self.assertTrue(os.path.exists(video_path))

    @unittest.skipUnless(MOVIEPY_AVAILABLE, "moviepy tidak tersedia")
    def test_generate_without_audio(self):
        """Test generate Reels tanpa audio"""
        video_path = self.gen.generate(self.content, duration=30, audio_type="none")
        self.assertTrue(os.path.exists(video_path))

    def test_get_title_quran(self):
        """Test judul untuk konten Quran"""
        from reels_generator import _get_title
        title = _get_title(self.content)
        self.assertEqual(title, "QS. Al-Fatihah : 1")

    def test_get_title_hadith(self):
        """Test judul untuk konten Hadith"""
        from reels_generator import _get_title
        content = {
            "type": "hadith",
            "book": "Bukhari",
            "hadith_number": "123",
        }
        title = _get_title(content)
        self.assertEqual(title, "HR. Bukhari No. 123")

    def test_theme_colors(self):
        """Test tema warna tersedia"""
        from reels_generator import THEME_COLORS
        themes = ["keimanan", "motivasi", "muhasabah", "akhlak", "keluarga", "doa", "dzikir"]
        for theme in themes:
            self.assertIn(theme, THEME_COLORS)

    def test_init_fonts(self):
        """Test inisialisasi font"""
        self.assertIsNotNone(self.gen.font_title)
        self.assertIsNotNone(self.gen.font_body)
        self.assertIsNotNone(self.gen.font_small)


if __name__ == "__main__":
    unittest.main()
