import os
import unittest
import tempfile
import csv
from unittest.mock import patch
from address_tracker import get_address, CSV_PATH, MAX_USES

class TestAddressTracker(unittest.TestCase):

    def setUp(self):
        # Create temporary CSV file
        self.temp_csv = tempfile.NamedTemporaryFile(delete=False, mode="w+", newline='', encoding="utf-8")
        self.fieldnames = ["Email", "TimesUsed", "LastUsedDate"]
        self.writer = csv.DictWriter(self.temp_csv, fieldnames=self.fieldnames)
        self.writer.writeheader()
        self.writer.writerow({"Email": "test@example.com", "TimesUsed": "0", "LastUsedDate": ""})
        self.temp_csv.seek(0)

        patcher = patch("address_tracker.CSV_PATH", self.temp_csv.name)
        self.addCleanup(patcher.stop)
        self.mock_csv_path = patcher.start()

    def tearDown(self):
        self.temp_csv.close()
        os.unlink(self.temp_csv.name)

    def test_get_address_success(self):
        result = get_address()
        self.assertEqual(result["Email"], "test@example.com")
        self.assertEqual(result["TimesUsed"], "1")

    def test_get_address_no_csv(self):
        with patch("address_tracker.CSV_PATH", "nonexistent.csv"):
            with self.assertRaises(FileNotFoundError):
                get_address()

    def test_all_addresses_used(self):
        # Overwrite file with only addresses that are all used up
        self.temp_csv.seek(0)
        self.temp_csv.truncate()  # Clear the file before rewriting
        self.writer.writeheader()
        self.writer.writerow({"Email": "used@example.com", "TimesUsed": str(MAX_USES), "LastUsedDate": ""})
        self.temp_csv.flush()

        with self.assertRaises(Exception) as cm:
            get_address()
        self.assertIn("No available address", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
