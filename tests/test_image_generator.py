import os
import tempfile
import unittest

from image_generator import ImageGenerator


class TestImageGenerator(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.gen = ImageGenerator(width=1080, height=1080, instagram_username="test")
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

    def test_generate_creates_file(self):
        output_path = os.path.join(self.test_dir, "test.png")
        result = self.gen.generate(self.content, output_path)
        self.assertTrue(os.path.exists(result))

    def test_generate_returns_path(self):
        output_path = os.path.join(self.test_dir, "test.png")
        result = self.gen.generate(self.content, output_path)
        self.assertEqual(result, output_path)

    def test_generate_with_layout(self):
        output_path = os.path.join(self.test_dir, "test_layout.png")
        result = self.gen.generate(self.content, output_path, layout=0)
        self.assertTrue(os.path.exists(result))

    def test_generate_all_layouts(self):
        for layout in [0, 1, 2]:
            output_path = os.path.join(self.test_dir, f"test_{layout}.png")
            result = self.gen.generate(self.content, output_path, layout=layout)
            self.assertTrue(os.path.exists(result))

    def test_generate_carousel(self):
        paths = self.gen.generate_carousel(self.content, prefix="test_carousel")
        self.assertEqual(len(paths), 3)
        for path in paths:
            self.assertTrue(os.path.exists(path))

    def test_generate_story(self):
        output_path = os.path.join(self.test_dir, "story.png")
        result = self.gen.generate_story(self.content, output_path)
        self.assertTrue(os.path.exists(result))

    def test_theme_colors(self):
        for theme in ["keimanan", "motivasi", "muhasabah", "akhlak", "keluarga", "doa", "dzikir"]:
            content = self.content.copy()
            content["theme"] = theme
            output_path = os.path.join(self.test_dir, f"theme_{theme}.png")
            result = self.gen.generate(content, output_path)
            self.assertTrue(os.path.exists(result))


class TestImageGeneratorTitle(unittest.TestCase):
    """Test _get_title() in image_generator handles all content types."""

    def test_quran_title(self):
        content = {"type": "quran", "surah": "Al-Fatihah", "ayat": "1"}
        result = ImageGenerator._get_title(content)
        self.assertEqual(result, "QS. Al-Fatihah : 1")

    def test_hadith_title_with_number(self):
        content = {"type": "hadith", "book": "Bukhari", "hadith_number": "123"}
        result = ImageGenerator._get_title(content)
        self.assertEqual(result, "HR. Bukhari No. 123")

    def test_hadith_title_without_number(self):
        content = {"type": "hadith", "book": "Muslim"}
        result = ImageGenerator._get_title(content)
        self.assertEqual(result, "HR. Muslim")

    def test_dua_uses_source(self):
        content = {"type": "dua", "source": "QS. Al-Furqan: 74"}
        result = ImageGenerator._get_title(content)
        self.assertEqual(result, "QS. Al-Furqan: 74")

    def test_dzikir_uses_source(self):
        content = {"type": "dzikir", "source": "HR. Bukhari & Muslim"}
        result = ImageGenerator._get_title(content)
        self.assertEqual(result, "HR. Bukhari & Muslim")

    def test_dua_falls_back_to_surah(self):
        content = {"type": "dua", "surah": "QS. Thaha: 25"}
        result = ImageGenerator._get_title(content)
        self.assertEqual(result, "QS. Thaha: 25")


if __name__ == "__main__":
    unittest.main()
