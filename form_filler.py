import logging
import os
import tempfile
import time
from datetime import datetime

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.wait import WebDriverWait
from dateutil import parser

from config import PREFERRED_STORE, CONTEST_URL
from receipt_manager import ReceiptManager

receipt_manager = ReceiptManager()
logger = logging.getLogger(__name__)


def upload_receipt(driver):
    """Upload receipt file to the form."""
    receipt_path = receipt_manager.get_next_receipt()
    upload_input = WebDriverWait(driver, 10).until(
        expected_conditions.presence_of_element_located((By.CSS_SELECTOR, "input[type='file'][name='UploadReceipt']")))
    upload_input.send_keys(receipt_path)
    logger.info(f"Uploading receipt: {receipt_path}")
    time.sleep(3)


def get_firefox_driver():
    """Create and configure Firefox WebDriver instance."""
    try:
        options = FirefoxOptions()
        # options.add_argument("--headless")  # Uncomment to run headless

        # Create a temporary Firefox profile
        profile_path = tempfile.mkdtemp()
        profile = webdriver.FirefoxProfile(profile_path)

        # Configure profile preferences
        profile.set_preference("media.autoplay.default", 0)
        profile.set_preference("media.autoplay.allow-muted", True)
        profile.set_preference("dom.webnotifications.enabled", False)

        driver = webdriver.Firefox(options=options)
        return driver

    except Exception as e:
        logger.error(f"Failed to initialize Firefox driver: {e}")
        raise


def save_screenshot_with_timestamp(driver: webdriver.Firefox, prefix: str = "screenshot"):
    """Save a screenshot with timestamp."""
    try:
        # Create screenshots directory if it doesn't exist
        screenshot_dir = "screenshots"
        os.makedirs(screenshot_dir, exist_ok=True)

        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{prefix}_{timestamp}.png"
        filepath = os.path.join(screenshot_dir, filename)

        # Save screenshot
        success = driver.save_screenshot(filepath)
        if success:
            logger.info(f"Screenshot saved: {filepath}")
        else:
            raise ValueError()

    except Exception as e:
        logger.warning(f"Failed to save screenshot: {e}")


def submit_form(data):
    """Submit the contest entry form with provided data."""
    driver = None
    form_submitted_successfully = False
    is_winner = False

    try:
        driver = get_firefox_driver()
        logger.info(f"Navigating to: {CONTEST_URL}")
        driver.get(CONTEST_URL)

        # Wait for page to load completely
        WebDriverWait(driver, 25).until(expected_conditions.presence_of_element_located((By.ID, "dnn1537FirstName")))

        # Fill form fields
        logger.info("Filling form fields...")
        time.sleep(3)

        # delete cookie banner
        driver.execute_script("""
            let banner = document.querySelector('.cc-window');
            if (banner) banner.remove();
        """)

        # Personal information
        driver.find_element(By.ID, "dnn1537FirstName").send_keys(data['FirstName'])
        driver.find_element(By.ID, "dnn1537LastName").send_keys(data['LastName'])
        driver.find_element(By.ID, "dnn1537Address").send_keys(data['StreetNumber'])
        driver.find_element(By.ID, "dnn1537Unit").send_keys(data.get('Unit', ''))
        driver.find_element(By.ID, "dnn1537City").send_keys(data['City'])

        province_select = Select(driver.find_element(By.ID, "dnn1537Province"))
        province_select.select_by_visible_text(data['Province'])

        # Format postal code properly (add space if missing)
        raw_postal_code = data['PostalCode'].replace(" ", "").upper()
        formatted_postal_code = f"{raw_postal_code[:3]} {raw_postal_code[3:]}"
        driver.find_element(By.ID, "dnn1537PostalCode").send_keys(formatted_postal_code)

        driver.find_element(By.ID, "dnn1537Email").send_keys(data['Email'])

        phone_field = driver.find_element(By.ID, "dnn1537Phone")
        phone_number = data['Phone']
        for char in phone_number:
            phone_field.send_keys(char)
            time.sleep(0.1)


        # Format birthdate
        raw_birthdate = data['Birthdate']  # e.g., "2001-03-01" or "1/4/1969"
        parsed_date = parser.parse(raw_birthdate)
        formatted_date = parsed_date.strftime("%d/%m/%Y")  # "01/03/2001"
        driver.find_element(By.ID, "dnn1537Birthdate").send_keys(formatted_date)

        # Select preferred store
        driver.find_element(By.ID, "dnn1537PreferredStore").click()
        time.sleep(5)

        # Wait for and click the store option
        store_element = WebDriverWait(driver, 10).until(
            expected_conditions.element_to_be_clickable((By.XPATH, f"//*[contains(text(), '{PREFERRED_STORE}')]")))
        store_element.click()

        # Upload receipt
        upload_receipt(driver)

        # Agree to terms
        agree_checkbox = driver.find_element(By.ID, "dnn1537Agree")
        if not agree_checkbox.is_selected():
            agree_checkbox.click()

        # Submit form
        submit_btn = driver.find_element(By.ID, "dnn1537Continue")

        if not submit_btn.is_enabled():
            error_msg = "Submit button is disabled. Form cannot be submitted."
            logger.error(error_msg)
            save_screenshot_with_timestamp(driver, "submit button disabled")
            raise Exception(error_msg)

        logger.info("Submitting form...")
        driver.execute_script("arguments[0].click();", submit_btn)
        time.sleep(3)

        # Handle post-submission flow
        try:
            logger.info("Watching Video...")

            # Wait for button to appear after video
            button_element = WebDriverWait(driver, 30).until(expected_conditions.element_to_be_clickable(
                (By.XPATH, "//button[contains(text(), 'NEXT STEPS') or contains(text(), 'LEARN MORE')]")))

            # Check button text to determine winner status
            button_text = button_element.text.strip().upper()

            if "NEXT STEPS" in button_text:
                logger.info("🎉 WINNER! 🎉")
                is_winner = True
            elif "LEARN MORE" in button_text:
                logger.info("Not a winner this time")
                is_winner = False
            else:
                logger.warning(f"Unknown button text found after watching video: {button_text}")
                save_screenshot_with_timestamp(driver, "error")
                is_winner = False

            screenshot_prefix = "winner" if is_winner else "non_winner"
            save_screenshot_with_timestamp(driver, screenshot_prefix)

            logger.info(f"Clicking '{button_text}' button...")
            button_element.click()
            time.sleep(45)

            # Commented out URL verification because we don't know what the winning URL is
            # if not driver.current_url.startswith("https://gmfreegroceries.ca/Thank-you"):
            # error_msg = f"Unexpected final URL. Expected: https://gmfreegroceries.ca/Thank-you*, Got: {driver.current_url}"
            # save_screenshot_with_timestamp(driver, "error")
            # logger.error(error_msg)
            # raise Exception(error_msg)

            logger.info(f"Successfully clicked on '{button_text}' button")
            save_screenshot_with_timestamp(driver, "Winner_Next_Steps_Page")
            form_submitted_successfully = True

        except TimeoutException:
            logger.error("Timeout waiting for results page")
            save_screenshot_with_timestamp(driver, "error")

            # Check for error messages
            try:
                error_elements = driver.find_elements(By.CLASS_NAME, "jq-toast-wrap")
                for error_element in error_elements:
                    if error_element.is_displayed():
                        error_text = error_element.text.strip()
                        if error_text:
                            logger.error(f"Form submission error: {error_text}")
                            raise Exception(f"Form submission failed: {error_text}")

            except NoSuchElementException:
                logger.error("No specific error message found")
                raise Exception("Form submission failed - timeout waiting for results")

            # Check for receipt deletion error
            try:
                if driver.find_element(By.CSS_SELECTOR, "strong.error").is_displayed():
                    raise Exception("Receipt file was deleted before form was submitted")
            except NoSuchElementException:
                pass

    except TimeoutException as e:
        error_msg = f"Timeout error during form submission: {e}"
        logger.error(error_msg)
        raise Exception(error_msg)
    except NoSuchElementException as e:
        error_msg = f"Element not found during form submission: {e}"
        logger.error(error_msg)
        raise Exception(error_msg)
    except WebDriverException as e:
        error_msg = f"WebDriver error during form submission: {e}"
        logger.error(error_msg)
        raise Exception(error_msg)
    except Exception as e:
        logger.error(f"Unexpected error during form submission: {e}")
        raise Exception(e)
    finally:
        # Move receipt to used directory only if form was submitted successfully
        if form_submitted_successfully:
            try:
                receipt_manager.move_current_receipt_to_used()
                logger.info("Receipt moved to used directory")
            except Exception as e:
                logger.warning(f"Failed to move receipt to used directory: {e}")

        if driver:
            try:
                driver.quit()
                logger.info("WebDriver session closed")
            except Exception as e:
                logger.warning(f"Error closing WebDriver: {e}")

        return is_winner
