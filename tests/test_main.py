import json
import os
import tempfile
import unittest

from main import validate_config, load_schedule, save_schedule, convert_local_to_utc


class TestValidateConfig(unittest.TestCase):
    def test_valid_config(self):
        errors = validate_config()
        self.assertIsInstance(errors, list)


class TestSchedule(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.schedule_path = os.path.join(self.test_dir, "schedule.json")

    def tearDown(self):
        if os.path.exists(self.schedule_path):
            os.remove(self.schedule_path)
        if os.path.exists(self.test_dir):
            os.rmdir(self.test_dir)

    def test_save_and_load_schedule(self):
        times = ["08:00", "12:00", "19:00"]
        save_schedule(times)
        loaded = load_schedule()
        self.assertEqual(loaded, times)


class TestTimezoneConversion(unittest.TestCase):
    def test_convert_jakarta_to_utc(self):
        result = convert_local_to_utc("08:00", "Asia/Jakarta")
        self.assertEqual(result, "01:00")

    def test_convert_makassar_to_utc(self):
        result = convert_local_to_utc("08:00", "Asia/Makassar")
        self.assertEqual(result, "00:00")

    def test_convert_jayapura_to_utc(self):
        result = convert_local_to_utc("08:00", "Asia/Jayapura")
        self.assertEqual(result, "23:00")

    def test_invalid_timezone(self):
        result = convert_local_to_utc("08:00", "Invalid/Timezone")
        self.assertEqual(result, "08:00")

    def test_invalid_time_format(self):
        result = convert_local_to_utc("invalid", "Asia/Jakarta")
        self.assertEqual(result, "invalid")


if __name__ == "__main__":
    unittest.main()
