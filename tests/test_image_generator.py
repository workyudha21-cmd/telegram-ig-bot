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


if __name__ == "__main__":
    unittest.main()
