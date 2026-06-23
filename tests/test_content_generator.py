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

    def test_hadith_with_kitab_prefix_no_double_hr(self):
        """Sunan/Shahih/Musnad/Muwatha prefix should not get extra HR."""
        verse = {"type": "hadith", "book": "Sunan At-Tirmidzi", "hadith_number": "1924"}
        result = _get_title(verse)
        self.assertEqual(result, "Sunan At-Tirmidzi No. 1924")
        self.assertNotIn("HR. Sunan", result)

    def test_hadith_strips_existing_hr_prefix(self):
        """Backward compat: book with HR. prefix should not duplicate."""
        verse = {"type": "hadith", "book": "HR. Muslim", "hadith_number": "32"}
        result = _get_title(verse)
        self.assertEqual(result, "HR. Muslim No. 32")
        self.assertNotIn("HR. HR.", result)

    def test_hadith_shahih_bukhari(self):
        verse = {"type": "hadith", "book": "Shahih Bukhari", "hadith_number": "6014"}
        result = _get_title(verse)
        self.assertEqual(result, "Shahih Bukhari No. 6014")
        self.assertNotIn("HR. Shahih", result)

    def test_hadith_no_book_no_number(self):
        verse = {"type": "hadith"}
        result = _get_title(verse)
        self.assertEqual(result, "HR.")

    def test_default_type(self):
        verse = {"surah": "Al-Baqarah", "ayat": "255"}
        result = _get_title(verse)
        self.assertEqual(result, "QS. Al-Baqarah : 255")

    def test_dua_uses_source_field(self):
        from content_generator import _key
        verse = {"type": "dua", "source": "QS. Al-Furqan: 74", "arabic": "رَبَّنَا"}
        result = _get_title(verse)
        self.assertEqual(result, "QS. Al-Furqan: 74")

    def test_dzikir_uses_source_field(self):
        from content_generator import _key
        verse = {"type": "dzikir", "source": "HR. Bukhari & Muslim", "arabic": "سُبْحَانَ"}
        result = _get_title(verse)
        self.assertEqual(result, "HR. Bukhari & Muslim")


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

    def test_returns_exactly_five_tags(self):
        """Instagram allows max 30 tags but cleaner to use 5."""
        for _ in range(20):
            result = _build_hashtags("keluarga")
            tags = result.split()
            self.assertEqual(len(tags), 5, f"Expected 5 tags, got {len(tags)}: {result}")

    def test_five_tags_for_each_theme(self):
        for theme in ["keimanan", "motivasi", "muhasabah", "akhlak", "keluarga", "doa", "dzikir"]:
            for _ in range(5):
                result = _build_hashtags(theme)
                tags = result.split()
                self.assertEqual(len(tags), 5, f"Theme {theme}: got {len(tags)} tags")

    def test_no_duplicate_tags(self):
        for _ in range(20):
            result = _build_hashtags("keluarga")
            tags = result.split()
            self.assertEqual(len(tags), len(set(tags)), f"Duplicate tags: {result}")

    def test_first_tag_is_theme(self):
        result = _build_hashtags("keluarga")
        self.assertTrue(result.startswith("#keluarga"), f"Theme not first: {result}")

    def test_caption_has_five_hashtags(self):
        """End-to-end: caption styles should produce 5 hashtags in the last line."""
        for style in ["random", "formal", "casual", "storytelling"]:
            gen = ContentGenerator(caption_style=style)
            gen.reset_generated()
            content = gen.get_random(theme="keluarga")
            last_line = content["caption"].strip().split("\n")[-1]
            self.assertEqual(len(last_line.split()), 5, f"Style {style}: last line = {last_line}")


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


class TestKey(unittest.TestCase):
    """Test _key() correctly identifies unique entries per type."""

    def test_quran_key_uses_surah_ayat(self):
        from content_generator import _key
        v1 = {"type": "quran", "surah": "Al-Fatihah", "ayat": 1}
        v2 = {"type": "quran", "surah": "Al-Fatihah", "ayat": 2}
        self.assertNotEqual(_key(v1), _key(v2))

    def test_hadith_key_uses_book_number(self):
        from content_generator import _key
        v1 = {"type": "hadith", "book": "Bukhari", "hadith_number": "1"}
        v2 = {"type": "hadith", "book": "Bukhari", "hadith_number": "2"}
        self.assertNotEqual(_key(v1), _key(v2))

    def test_dua_key_uses_source_and_arabic(self):
        from content_generator import _key
        v1 = {"type": "dua", "source": "QS. Al-Baqarah: 201", "arabic": "رَبَّنَا آتِنَا"}
        v2 = {"type": "dua", "source": "QS. Al-Baqarah: 201", "arabic": "رَبَّنَا اغْفِرْ"}
        self.assertNotEqual(_key(v1), _key(v2))

    def test_dzikir_key_uses_source_and_arabic(self):
        from content_generator import _key
        v1 = {"type": "dzikir", "source": "HR. Bukhari", "arabic": "سُبْحَانَ اللَّهِ"}
        v2 = {"type": "dzikir", "source": "HR. Muslim", "arabic": "سُبْحَانَ اللَّهِ"}
        self.assertNotEqual(_key(v1), _key(v2))

    def test_different_types_produce_different_keys(self):
        from content_generator import _key
        quran = {"type": "quran", "surah": "Al-Fatihah", "ayat": 1}
        dua = {"type": "dua", "source": "QS. Al-Fatihah: 1", "arabic": "test"}
        self.assertNotEqual(_key(quran), _key(dua))


class TestFormatDuaDzikir(unittest.TestCase):
    """Test _format() preserves source field and handles dua/dzikir correctly."""

    def setUp(self):
        self.gen = ContentGenerator(caption_style="formal")

    def test_dua_preserves_source_field(self):
        verse = {
            "type": "dua",
            "source": "QS. Al-Furqan: 74",
            "arabic": "رَبَّنَا هَبْ لَنَا",
            "translation": "Ya Tuhan kami, anugerahkanlah",
            "explanation": "Doa keluarga",
            "theme": "keluarga",
        }
        result = self.gen._format(verse)
        self.assertEqual(result["source"], "QS. Al-Furqan: 74")

    def test_dzikir_preserves_source_field(self):
        verse = {
            "type": "dzikir",
            "source": "HR. Bukhari & Muslim",
            "arabic": "سُبْحَانَ اللَّهِ",
            "translation": "Maha Suci Allah",
            "explanation": "Dzikir ringan",
            "theme": "dzikir",
        }
        result = self.gen._format(verse)
        self.assertEqual(result["source"], "HR. Bukhari & Muslim")

    def test_quran_result_has_empty_source(self):
        verse = {
            "type": "quran",
            "surah": "Al-Fatihah",
            "ayat": 1,
            "arabic": "بِسْمِ اللَّهِ",
            "translation": "Dengan nama Allah",
            "tafsir": "Pembuka",
            "theme": "keimanan",
        }
        result = self.gen._format(verse)
        self.assertEqual(result["source"], "")

    def test_dua_has_empty_surah_ayat(self):
        verse = {
            "type": "dua",
            "source": "QS. Al-Furqan: 74",
            "arabic": "رَبَّنَا",
            "translation": "Ya Tuhan",
            "explanation": "Doa",
            "theme": "keluarga",
        }
        result = self.gen._format(verse)
        self.assertEqual(result["surah"], "")
        self.assertEqual(result["ayat"], "")

    def test_dzikir_has_empty_surah_ayat(self):
        verse = {
            "type": "dzikir",
            "source": "HR. Muslim",
            "arabic": "سُبْحَانَ",
            "translation": "Maha Suci",
            "explanation": "Dzikir",
            "theme": "dzikir",
        }
        result = self.gen._format(verse)
        self.assertEqual(result["surah"], "")
        self.assertEqual(result["ayat"], "")

    def test_quran_has_surah_ayat(self):
        verse = {
            "type": "quran",
            "surah": "Al-Baqarah",
            "ayat": 255,
            "arabic": "ٱللَّهُ",
            "translation": "Allah",
            "tafsir": "Ayat Kursi",
            "theme": "keimanan",
        }
        result = self.gen._format(verse)
        self.assertEqual(result["surah"], "Al-Baqarah")
        self.assertEqual(result["ayat"], 255)

    def test_hadith_uses_book_as_surah(self):
        verse = {
            "type": "hadith",
            "book": "Bukhari",
            "hadith_number": "6014",
            "narrator": "Abu Hurairah",
            "arabic": "مَنْ كَانَ",
            "translation": "Barangsiapa",
            "explanation": "Hadits",
            "theme": "akhlak",
        }
        result = self.gen._format(verse)
        self.assertEqual(result["surah"], "Bukhari")
        self.assertEqual(result["ayat"], "6014")
        self.assertEqual(result["source"], "")

    def test_caption_arabic_matches_verse_arabic(self):
        """Caption and image use same arabic text - critical for sync."""
        verse = {
            "type": "dua",
            "source": "QS. Al-Furqan: 74",
            "arabic": "رَبَّنَا هَبْ لَنَا مِنْ أَزْوَاجِنَا",
            "translation": "Ya Tuhan kami",
            "explanation": "Doa keluarga",
            "theme": "keluarga",
        }
        result = self.gen._format(verse)
        self.assertIn(verse["arabic"], result["caption"])
        self.assertEqual(result["arabic"], verse["arabic"])
        self.assertEqual(result["translation"], verse["translation"])


if __name__ == "__main__":
    unittest.main()
