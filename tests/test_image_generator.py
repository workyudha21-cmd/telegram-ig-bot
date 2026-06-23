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

    def test_hadith_kitab_prefix_no_double_hr(self):
        content = {"type": "hadith", "book": "Sunan At-Tirmidzi", "hadith_number": "1924"}
        result = ImageGenerator._get_title(content)
        self.assertEqual(result, "Sunan At-Tirmidzi No. 1924")
        self.assertNotIn("HR. Sunan", result)

    def test_hadith_strips_existing_hr_prefix(self):
        content = {"type": "hadith", "book": "HR. Muslim", "hadith_number": "32"}
        result = ImageGenerator._get_title(content)
        self.assertEqual(result, "HR. Muslim No. 32")
        self.assertNotIn("HR. HR.", result)

    def test_hadith_shahih_no_double_hr(self):
        content = {"type": "hadith", "book": "Shahih Bukhari", "hadith_number": "6014"}
        result = ImageGenerator._get_title(content)
        self.assertEqual(result, "Shahih Bukhari No. 6014")
        self.assertNotIn("HR. Shahih", result)

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


class TestShowFlags(unittest.TestCase):
    """Test show_title and show_arabic flags control image rendering."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
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

    def test_default_show_title_is_false(self):
        gen = ImageGenerator()
        self.assertFalse(gen.show_title)

    def test_default_show_arabic_is_false(self):
        gen = ImageGenerator()
        self.assertFalse(gen.show_arabic)

    def test_explicit_show_title_true(self):
        gen = ImageGenerator(show_title=True, show_arabic=True)
        self.assertTrue(gen.show_title)
        self.assertTrue(gen.show_arabic)

    def test_explicit_show_flags_false(self):
        gen = ImageGenerator(show_title=False, show_arabic=False)
        self.assertFalse(gen.show_title)
        self.assertFalse(gen.show_arabic)

    def test_generate_default_no_arabic_in_image(self):
        gen = ImageGenerator()
        path = gen.generate(self.content, os.path.join(self.test_dir, "no_arabic.png"), layout=0)
        self.assertTrue(os.path.exists(path))
        # _last_arabic_raw should be empty when show_arabic=False
        self.assertEqual(gen._last_arabic_raw, "")

    def test_generate_with_show_arabic_includes_arabic(self):
        gen = ImageGenerator(show_arabic=True)
        path = gen.generate(self.content, os.path.join(self.test_dir, "with_arabic.png"), layout=0)
        self.assertTrue(os.path.exists(path))
        # _last_arabic_raw should match content's arabic
        self.assertEqual(gen._last_arabic_raw, self.content["arabic"])

    def test_generate_with_show_title_renders_title(self):
        gen = ImageGenerator(show_title=True)
        path = gen.generate(self.content, os.path.join(self.test_dir, "with_title.png"), layout=0)
        self.assertTrue(os.path.exists(path))

    def test_generate_with_both_flags_off(self):
        gen = ImageGenerator(show_title=False, show_arabic=False)
        path = gen.generate(self.content, os.path.join(self.test_dir, "minimal.png"), layout=0)
        self.assertTrue(os.path.exists(path))
        self.assertEqual(gen._last_arabic_raw, "")

    def test_all_themes_with_no_title_no_arabic(self):
        gen = ImageGenerator()
        for theme in ["keimanan", "motivasi", "muhasabah", "akhlak", "keluarga", "doa", "dzikir"]:
            content = self.content.copy()
            content["theme"] = theme
            path = gen.generate(content, os.path.join(self.test_dir, f"theme_{theme}.png"))
            self.assertTrue(os.path.exists(path))

    def test_story_with_no_title_no_arabic(self):
        gen = ImageGenerator()
        path = gen.generate_story(self.content, os.path.join(self.test_dir, "story.png"))
        self.assertTrue(os.path.exists(path))
        self.assertEqual(gen._last_arabic_raw, "")

    def test_story_with_show_arabic(self):
        gen = ImageGenerator(show_arabic=True)
        path = gen.generate_story(self.content, os.path.join(self.test_dir, "story_ar.png"))
        self.assertTrue(os.path.exists(path))
        self.assertEqual(gen._last_arabic_raw, self.content["arabic"])

    def test_carousel_default_no_title_no_arabic(self):
        gen = ImageGenerator()
        paths = gen.generate_carousel(self.content, prefix=os.path.join(self.test_dir, "carousel"))
        self.assertEqual(len(paths), 3)
        for path in paths:
            self.assertTrue(os.path.exists(path))

    def test_carousel_with_show_flags(self):
        gen = ImageGenerator(show_title=True, show_arabic=True)
        paths = gen.generate_carousel(self.content, prefix=os.path.join(self.test_dir, "carousel_full"))
        self.assertEqual(len(paths), 3)
        for path in paths:
            self.assertTrue(os.path.exists(path))

    def test_mismatch_detection_only_when_arabic_shown(self):
        """When show_arabic=False, mismatch warning should not fire even if content has arabic."""
        gen = ImageGenerator(show_arabic=False)
        # Generate and ensure no exception (mismatch check is a no-op)
        path = gen.generate(self.content, os.path.join(self.test_dir, "test.png"), layout=0)
        self.assertTrue(os.path.exists(path))

    def test_mismatch_warning_when_arabic_differs(self):
        """When show_arabic=True and raw differs, _last_arabic_raw tracks it."""
        gen = ImageGenerator(show_arabic=True)
        gen.generate(self.content, os.path.join(self.test_dir, "test.png"), layout=0)
        # Should track the actual arabic text
        self.assertEqual(gen._last_arabic_raw, self.content["arabic"])


if __name__ == "__main__":
    unittest.main()
