import unittest
from unittest.mock import patch
from main import form_submission_job

class TestMain(unittest.TestCase):

    @patch("main.submit_form")
    @patch("main.get_address")
    def test_form_submission_success(self, mock_get_address, mock_submit_form):
        mock_get_address.return_value = {"Email": "mock@example.com"}
        form_submission_job()
        mock_submit_form.assert_called_once()

    @patch("main.submit_form", side_effect=Exception("Form error"))
    @patch("main.get_address", return_value={"Email": "mock@example.com"})
    def test_form_submission_failure(self, mock_get_address, mock_submit_form):
        form_submission_job()  # Should log error, not crash

    @patch("main.get_address", return_value=None)
    def test_form_submission_no_data(self, mock_get_address):
        form_submission_job()  # Should log warning, not crash

if __name__ == "__main__":
    unittest.main()
