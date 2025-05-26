import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
from form_filler import upload_receipt

# Helper function reused from form_filler.py
def find_element_endswith_id(driver, endswith):
    return driver.find_element(By.CSS_SELECTOR, f"[id$='{endswith}']")

class TestFormFiller(unittest.TestCase):

    def setUp(self):
        # Create a temporary Chrome user profile to avoid conflicts
        self.temp_profile = tempfile.TemporaryDirectory()

        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument(f"--user-data-dir={self.temp_profile.name}")

        self.driver = webdriver.Chrome(options=chrome_options)

        # Load the form from a local HTML snapshot
        form_path = os.path.abspath("data/form_test.html")
        self.driver.get(f"file://{form_path}")

    def tearDown(self):
        self.driver.quit()
        self.temp_profile.cleanup()

    def test_fill_and_submit_form(self):
        driver = self.driver

        # Fill form fields
        find_element_endswith_id(driver, "FirstName").send_keys("Alice")
        find_element_endswith_id(driver, "LastName").send_keys("Smith")
        find_element_endswith_id(driver, "Address").send_keys("123 Maple St")
        find_element_endswith_id(driver, "Unit").send_keys("2A")
        find_element_endswith_id(driver, "City").send_keys("Toronto")

        province_select = Select(find_element_endswith_id(driver, "Province"))
        province_select.select_by_visible_text("Ontario")

        find_element_endswith_id(driver, "PostalCode").send_keys("M5H 2N2")
        find_element_endswith_id(driver, "Email").send_keys("alice@example.com")
        find_element_endswith_id(driver, "Phone").send_keys("4161234567")
        find_element_endswith_id(driver, "Birthdate").send_keys("1980-01-01")

        store_select = Select(find_element_endswith_id(driver, "PreferredStore"))
        store_select.select_by_visible_text("Metro")

        # Upload a test receipt
        test_receipt = os.path.abspath("data/receipts/fresh/test_receipt.jpg")
        upload_input = driver.find_element(By.CSS_SELECTOR, "input[type='file'][name='UploadReceipt']")
        upload_input.send_keys(test_receipt)

        # Agree to terms
        agree_checkbox = find_element_endswith_id(driver, "Agree")
        if not agree_checkbox.is_selected():
            agree_checkbox.click()

        # Check submit button
        submit_btn = find_element_endswith_id(driver, "Continue")
        self.assertTrue(submit_btn.is_enabled())

        print("✅ Form filled and ready for submission (simulation only).")

    @patch("form_filler.os.listdir")
    @patch("form_filler.shutil.move")
    def test_upload_receipt_success(self, mock_move, mock_listdir):
        mock_driver = MagicMock()
        mock_input = MagicMock()

        mock_driver.find_element.return_value = mock_input
        mock_listdir.return_value = ["receipt.jpg"]

        with patch("form_filler.os.path.isfile", return_value=True), \
             patch("form_filler.os.path.abspath", side_effect=lambda x: f"/abs/{x}"):
            upload_receipt(mock_driver)

        mock_input.send_keys.assert_called_once_with("/abs/data/receipts/fresh/receipt.jpg")
        mock_move.assert_called_once()

    def test_parse_uploaded_file_error(self):
        # Load saved HTML snapshot simulating an upload error
        html_path = "tests/form_page_snapshot.html"
        with open(html_path, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f, "html.parser")

        error_span = soup.select_one(".file-table strong.error.text-danger")
        self.assertIsNotNone(error_span)
        self.assertIn("File is too large", error_span.text.strip())


if __name__ == "__main__":
    unittest.main()
