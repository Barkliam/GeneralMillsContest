import logging
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

from receipt_manager import ReceiptManager

receipt_manager = ReceiptManager()
logger = logging.getLogger(__name__)


def upload_receipt(driver):
    receipt_path = receipt_manager.get_next_receipt()
    upload_input = WebDriverWait(driver, 10).until(
        expected_conditions.presence_of_element_located(
            (By.CSS_SELECTOR, "input[type='file'][name='UploadReceipt']"))
    )
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


def submit_form(data):
    """Submit the contest entry form with provided data."""
    url = "https://gmfreegroceries.ca/Enter"
    preferred_store = "Walmart"  # Change this to whichever store you want gift cards from

    driver = None
    form_submitted_successfully = False

    try:
        driver = get_firefox_driver()
        logger.info(f"Navigating to: {url}")
        driver.get(url)

        # Log cookies for debugging
        logger.debug(f"Cookies: {driver.execute_script('return document.cookie')}")
        time.sleep(5)

        # Fill form fields
        logger.info("Filling form fields...")

        # Personal information
        driver.find_element(By.ID, "dnn1537FirstName").send_keys(data['FirstName'])
        driver.find_element(By.ID, "dnn1537LastName").send_keys(data['LastName'])
        driver.find_element(By.ID, "dnn1537Address").send_keys(data['StreetNumber'])
        driver.find_element(By.ID, "dnn1537Unit").send_keys(data.get('Unit', ''))
        driver.find_element(By.ID, "dnn1537City").send_keys(data['City'])

        province_select = Select(driver.find_element(By.ID, "dnn1537Province"))
        province_select.select_by_visible_text(data['Province'])

        raw_postal_code = data['PostalCode'].replace(" ", "").upper()
        formatted_postal_code = f"{raw_postal_code[:3]} {raw_postal_code[3:]}"
        driver.find_element(By.ID, "dnn1537PostalCode").send_keys(formatted_postal_code)

        driver.find_element(By.ID, "dnn1537Email").send_keys(data['Email'])
        driver.find_element(By.ID, "dnn1537Phone").send_keys(data['Phone'])

        raw_birthdate = data['Birthdate']  # e.g., "2001-03-01"
        parsed_date = datetime.strptime(raw_birthdate, "%Y-%m-%d")
        formatted_date = parsed_date.strftime("%d/%m/%Y")  # "01/03/2001"
        driver.find_element(By.ID, "dnn1537Birthdate").send_keys(formatted_date)

        # Select preferred store
        driver.find_element(By.ID, "dnn1537PreferredStore").click()
        time.sleep(5)

        # Wait for and click the store option
        store_element = WebDriverWait(driver, 10).until(
            expected_conditions.element_to_be_clickable((By.XPATH, f"//*[contains(text(), '{preferred_store}')]"))
        )
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
            raise Exception(error_msg)

        logger.info("Submitting form...")
        driver.execute_script("arguments[0].click();", submit_btn)
        time.sleep(2)

        try:
            logger.info("Watching Video...")
            learn_more_button = WebDriverWait(driver, 25).until(
                expected_conditions.element_to_be_clickable((By.XPATH, "//button[text()='LEARN MORE']"))
            )

            # Check if winner or not by video matching
            try:
                video_element = driver.find_element(By.CSS_SELECTOR, "video.winningvideo")
                poster_url = video_element.get_attribute('poster')

                if "2025winner" in poster_url:
                    logger.info("🎉 WINNER! 🎉")
                elif "2025nonwinner" in poster_url:
                    logger.info("Not a winner this time")
                else:
                    logger.warning(f"Unknown video found: {poster_url}")

            except NoSuchElementException:
                logger.warning("Could not find video element to determine win status")

            # Click learn more button
            learn_more_button.click()
            time.sleep(6)

            if not driver.current_url.startswith("https://gmfreegroceries.ca/Thank-you"):
                error_msg = f"Unexpected final URL. Expected: https://gmfreegroceries.ca/Thank-you*, Got: {driver.current_url}"
                logger.error(error_msg)
                raise Exception(error_msg)

            logger.info("Successfully clicked on 'LEARN MORE' button")
            form_submitted_successfully = True

        except TimeoutException:
            logger.error("Timeout waiting for results page")

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
        logger.error(e)
        raise Exception(e)
    finally:
        # Move receipt to used directory only if form was submitted successfully
        if form_submitted_successfully:
            try:
                receipt_manager.move_current_receipt_to_used()
            except Exception as e:
                logger.warning(f"Failed to move receipt to used directory: {e}")
        if driver:
            try:
                driver.quit()
                logger.info("WebDriver session closed")
            except Exception as e:
                logger.warning(f"Error closing WebDriver: {e}")
