import json
import os
import tempfile
import unittest

from content_generator import ContentGenerator, _get_title, _build_hashtags, _random_caption, CAPTION_STYLES


class TestGetTitle(unittest.TestCase):
    def test_quran_content(self):
        verse = {"type": "quran", "surah": "Al-Fatihah", "ayat": "1"}
        result = _get_title(verse)
        self.assertEqual(result, "QS. Al-Fatihah : 1")

    def test_hadith_content(self):
        verse = {"type": "hadith", "book": "Bukhari", "hadith_number": "123"}
        result = _get_title(verse)
        self.assertEqual(result, "HR. Bukhari No. 123")

    def test_hadith_no_number(self):
        verse = {"type": "hadith", "book": "Muslim"}
        result = _get_title(verse)
        self.assertEqual(result, "HR. Muslim")

    def test_default_type(self):
        verse = {"surah": "Al-Baqarah", "ayat": "255"}
        result = _get_title(verse)
        self.assertEqual(result, "QS. Al-Baqarah : 255")


class TestBuildHashtags(unittest.TestCase):
    def test_returns_string(self):
        result = _build_hashtags("motivasi")
        self.assertIsInstance(result, str)

    def test_contains_theme(self):
        result = _build_hashtags("sabar")
        self.assertIn("#sabar", result)

    def test_contains_base_hashtags(self):
        result = _build_hashtags("islam")
        self.assertIn("#islam", result)


class TestCaptionStyles(unittest.TestCase):
    def setUp(self):
        self.content = {
            "arabic": "بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ",
            "translation": "Dengan nama Allah Yang Maha Pengasih lagi Maha Penyayang.",
            "explanation": "Pembuka Al-Fatihah.",
            "surah": "Al-Fatihah",
            "ayat": "1",
            "theme": "keimanan",
            "type": "quran",
        }

    def test_random_caption(self):
        result = _random_caption(self.content)
        self.assertIn(self.content["arabic"], result)
        self.assertIn(self.content["translation"], result)

    def test_all_styles_exist(self):
        self.assertIn("random", CAPTION_STYLES)
        self.assertIn("formal", CAPTION_STYLES)
        self.assertIn("casual", CAPTION_STYLES)
        self.assertIn("storytelling", CAPTION_STYLES)

    def test_formal_caption(self):
        fn = CAPTION_STYLES["formal"]
        result = fn(self.content)
        self.assertIn("Artinya:", result)

    def test_casual_caption(self):
        fn = CAPTION_STYLES["casual"]
        result = fn(self.content)
        self.assertIn("Keren banget", result)

    def test_storytelling_caption(self):
        fn = CAPTION_STYLES["storytelling"]
        result = fn(self.content)
        self.assertIn("Pagi ini", result)


class TestContentGenerator(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.test_dir, "test_content.json")
        self.test_data = [
            {
                "arabic": "آيَةٌ",
                "translation": "Ayat test",
                "explanation": "Penjelasan test",
                "surah": "Test",
                "ayat": "1",
                "theme": "motivasi",
                "type": "quran",
            },
            {
                "arabic": "آيَةٌ 2",
                "translation": "Ayat test 2",
                "explanation": "Penjelasan test 2",
                "surah": "Test",
                "ayat": "2",
                "theme": "akhlak",
                "type": "quran",
            },
        ]
        with open(self.test_file, "w", encoding="utf-8") as f:
            json.dump(self.test_data, f)

        self.generated_path = os.path.join(self.test_dir, "generated.json")
        self._original_generated_path = None

    def tearDown(self):
        if os.path.exists(self.test_file):
            os.remove(self.test_file)
        if os.path.exists(self.generated_path):
            os.remove(self.generated_path)
        if os.path.exists(self.test_dir):
            os.rmdir(self.test_dir)

    def test_load_content(self):
        gen = ContentGenerator(data_paths=[self.test_file])
        self.assertEqual(len(gen.verses), 2)

    def test_list_themes(self):
        gen = ContentGenerator(data_paths=[self.test_file])
        themes = gen.list_themes()
        self.assertIn("motivasi", themes)
        self.assertIn("akhlak", themes)

    def test_search(self):
        gen = ContentGenerator(data_paths=[self.test_file])
        results = gen.search("Ayat test")
        self.assertEqual(len(results), 2)

    def test_search_limit(self):
        gen = ContentGenerator(data_paths=[self.test_file])
        results = gen.search("Ayat test", limit=1)
        self.assertEqual(len(results), 1)

    def test_get_random(self):
        gen = ContentGenerator(data_paths=[self.test_file])
        content = gen.get_random()
        self.assertIn("arabic", content)
        self.assertIn("translation", content)
        self.assertIn("caption", content)

    def test_get_random_with_theme(self):
        gen = ContentGenerator(data_paths=[self.test_file])
        content = gen.get_random(theme="motivasi")
        self.assertEqual(content["theme"], "motivasi")

    def test_mark_generated(self):
        gen = ContentGenerator(data_paths=[self.test_file])
        gen.reset_generated()
        content = gen.get_random()
        gen.mark_generated(content)
        self.assertEqual(len(gen.generated_keys), 1)

    def test_reset_generated(self):
        gen = ContentGenerator(data_paths=[self.test_file])
        content = gen.get_random()
        gen.mark_generated(content)
        gen.reset_generated()
        self.assertEqual(len(gen.generated_keys), 0)

    def test_caption_style(self):
        gen = ContentGenerator(data_paths=[self.test_file], caption_style="formal")
        self.assertEqual(gen.caption_style, "formal")

    def test_set_caption_style(self):
        gen = ContentGenerator(data_paths=[self.test_file])
        result = gen.set_caption_style("casual")
        self.assertTrue(result)
        self.assertEqual(gen.caption_style, "casual")

    def test_set_invalid_caption_style(self):
        gen = ContentGenerator(data_paths=[self.test_file])
        result = gen.set_caption_style("invalid")
        self.assertFalse(result)

    def test_list_caption_styles(self):
        gen = ContentGenerator(data_paths=[self.test_file])
        styles = gen.list_caption_styles()
        self.assertIn("random", styles)
        self.assertIn("formal", styles)


if __name__ == "__main__":
    unittest.main()
