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

# Logging setup - log to both file and console
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

# Create logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
file_handler = logging.FileHandler(os.path.join(LOG_DIR, "form_filler.log"))
file_handler.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)


# TODO separate file reading and writing to separate file and create an instance of it. Then return only the path to be used here. Tell the instance to move the file once the form is submitted
def upload_receipt(driver):
    """Upload a receipt file from the fresh directory and move it to used directory."""
    fresh_dir = "data/receipts/fresh"
    used_dir = "data/receipts/used"

    # Ensure directories exist
    os.makedirs(fresh_dir, exist_ok=True)
    os.makedirs(used_dir, exist_ok=True)

    try:
        receipts = [f for f in os.listdir(fresh_dir) if os.path.isfile(os.path.join(fresh_dir, f))]
        if not receipts:
            error_msg = "No fresh receipts found in directory."
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)

        receipt_file = receipts[0]
        full_path = os.path.abspath(os.path.join(fresh_dir, receipt_file))

        logger.info(f"Attempting to upload receipt: {receipt_file}")

        upload_input = WebDriverWait(driver, 10).until(
            expected_conditions.presence_of_element_located(
                (By.CSS_SELECTOR, "input[type='file'][name='UploadReceipt']"))
        )
        upload_input.send_keys(full_path)
        time.sleep(3)

        # Check for upload error
        error_elements = driver.find_elements(By.CSS_SELECTOR, ".text-danger")
        for elem in error_elements:
            if elem.is_displayed() and elem.text.strip():
                error_msg = f"Upload error for {receipt_file}: {elem.text.strip()}"
                logger.error(error_msg)
                raise Exception(error_msg)

        # Move file after successful upload
        # destination_path = os.path.join(used_dir, receipt_file)
        # shutil.move(full_path, destination_path)
        # logger.info(f"Successfully uploaded and moved: {receipt_file}")

    except FileNotFoundError as e:
        logger.error(f"File not found error: {e}")
        raise
    except Exception as e:
        logger.error(f"Receipt upload failed: {e}")
        raise


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
        logger.info("Firefox driver initialized successfully")
        return driver

    except Exception as e:
        logger.error(f"Failed to initialize Firefox driver: {e}")
        raise


def submit_form(data):
    """Submit the contest entry form with provided data."""
    url = "https://gmfreegroceries.ca/Enter"
    preferred_store = "Walmart"  # Change this to whichever store you want gift cards from

    driver = None
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
        logger.info(f"Selecting preferred store: {preferred_store}")
        driver.find_element(By.ID, "dnn1537PreferredStore").click()
        time.sleep(2)

        # Wait for and click the store option
        store_element = WebDriverWait(driver, 10).until(
            expected_conditions.element_to_be_clickable((By.XPATH, f"//*[contains(text(), '{preferred_store}')]"))
        )
        store_element.click()

        # Upload receipt
        logger.info("Uploading receipt...")
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
        time.sleep(5)

        try:
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
            time.sleep(5)
            # TODO check if url matches  https://gmfreegroceries.ca/Thank-you...
            # otherwise raise error because something went wrong
            logger.info(f"Final URL: {driver.current_url}")
            logger.info("Form submission completed successfully")

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

                # TODO fix this to explain error if this error element exists
                upload_error_element = driver.find_element(By.CSS_SELECTOR, "strong.error")
                if (upload_error_element):
                    raise Exception(f"Form submission failed: image was deleted before form was submitted")

            except NoSuchElementException:
                logger.error("No specific error message found")
                raise Exception("Form submission failed - timeout waiting for results")

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
        error_msg = f"Unexpected error during form submission: {e}"
        logger.error(error_msg)
        raise Exception(error_msg)
    finally:
        if driver:
            try:
                driver.quit()
                logger.info("WebDriver session closed")
            except Exception as e:
                logger.warning(f"Error closing WebDriver: {e}")
