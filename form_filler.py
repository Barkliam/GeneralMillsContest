import logging
import os
import tempfile
import time
from datetime import datetime

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.wait import WebDriverWait

#TODO log to file but also print to console
# Logging setup
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(
    filename=os.path.join(LOG_DIR, "form_filler.log"),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# TODO separate this into separate file
def upload_receipt(driver):
    fresh_dir = "data/receipts/fresh"
    used_dir = "data/receipts/used"

    receipts = [f for f in os.listdir(fresh_dir) if os.path.isfile(os.path.join(fresh_dir, f))]
    if not receipts:
        logging.error("No fresh receipts found.")
        raise FileNotFoundError("No fresh receipts found.")

    receipt_file = receipts[0]
    full_path = os.path.abspath(os.path.join(fresh_dir, receipt_file))

    # upload_input = driver.find_element(By.CSS_SELECTOR, "input[type='file'][name='UploadReceipt']")
    # upload_input.send_keys(full_path)
    upload_input = WebDriverWait(driver, 10).until(
        expected_conditions.presence_of_element_located((By.CSS_SELECTOR, "input[type='file'][name='UploadReceipt']"))
    )
    upload_input.send_keys(full_path)
    time.sleep(3)

    # TODO implement moving uploaded file
    # Move file after successful upload
    # shutil.move(full_path, os.path.join(used_dir, receipt_file))
    # logging.info(f"Successfully uploaded and moved: {receipt_file}")

    # Check for upload error
    error_elements = driver.find_elements(By.CSS_SELECTOR, ".text-danger")
    for elem in error_elements:
        if elem.is_displayed() and elem.text.strip():
            logging.error(f"Upload error for {receipt_file}: {elem.text.strip()}")
            raise Exception(f"Receipt upload failed: {elem.text.strip()}")


def get_firefox_driver():
    options = FirefoxOptions()
    # options.add_argument("--headless")  # Uncomment to run headless

    # Create a temporary Firefox profile
    profile_path = tempfile.mkdtemp()
    profile = webdriver.FirefoxProfile(profile_path)

    # Optional: enable autoplay, disable prompts
    profile.set_preference("media.autoplay.default", 0)
    profile.set_preference("media.autoplay.allow-muted", True)
    profile.set_preference("dom.webnotifications.enabled", False)

    return webdriver.Firefox(options=options)


def submit_form(data):
    url = "https://gmfreegroceries.ca/Enter"
    preferred_store = "Walmart"  # Change this to whichever store you want to giftcards from
    options = webdriver.ChromeOptions()
    # options.add_argument("--headless")
    driver = get_firefox_driver()
    #TODO fix error handling here so that all errors throw exception with info what went wrong to be logged.
    try:
        driver.get(url)
        print(driver.execute_script("return document.cookie"))
        time.sleep(5)

        driver.find_element(By.ID, "dnn1537FirstName").send_keys(data['FirstName'])
        driver.find_element(By.ID, "dnn1537LastName").send_keys(data['LastName'])
        driver.find_element(By.ID, "dnn1537Address").send_keys(data['StreetNumber'])
        driver.find_element(By.ID, "dnn1537Unit").send_keys(data.get('Unit', ''))
        driver.find_element(By.ID, "dnn1537City").send_keys(data['City'])
        Select(driver.find_element(By.ID, "dnn1537Province")).select_by_visible_text(data['Province'])

        #TODO add a space in the middle of postal code if there is not one.
        #(e.g. "K1R6E9" -> "K1R 6E9")
        driver.find_element(By.ID, "dnn1537PostalCode").send_keys(data['PostalCode'])
        driver.find_element(By.ID, "dnn1537Email").send_keys(data['Email'])
        driver.find_element(By.ID, "dnn1537Phone").send_keys(data['Phone'])

        raw_birthdate = data['Birthdate']  # e.g., "2001-03-01"
        parsed_date = datetime.strptime(raw_birthdate, "%Y-%m-%d")
        formatted_date = parsed_date.strftime("%d/%m/%Y")  # "01/03/2001"
        driver.find_element(By.ID, "dnn1537Birthdate").send_keys(formatted_date)

        driver.find_element(By.ID, "dnn1537PreferredStore").click()
        time.sleep(4)
        driver.find_element(By.XPATH, "//*[contains(text(), 'Walmart')]").click()

        upload_receipt(driver)

        driver.find_element(By.ID, "dnn1537Agree").click()

        submit_btn = driver.find_element(By.ID, "dnn1537Continue")

        if not submit_btn.is_enabled():
            raise Exception("Submit button is disabled. Form not submitted.")

        driver.execute_script("arguments[0].click();", submit_btn)
        logging.info("Form submitted.")
        time.sleep(100)

        print(driver.current_url)
        try:
            learn_more_button = WebDriverWait(driver, 100).until(
                expected_conditions.presence_of_element_located((By.XPATH, "//button[text()='LEARN MORE']"))
            )

            video_element = driver.find_element(By.CSS_SELECTOR, "video.winningvideo")
            poster_url = video_element.get_attribute('poster')
            if "2025winner" in poster_url:
                logging.info("WINNER")

            elif "2025nonwinner" in poster_url:
                logging.info("not winner")

            else:
                logging.info("error, unknown video found" + poster_url)

            learn_more_button.click()
            time.sleep(5)
            logging.info(driver.current_url)


        except Exception as e:

            error_element = driver.find_element(By.CLASS_NAME, "jq-toast-wrap")
            if (error_element):
                logging.info("Error submitting form: " + error_element.text)



    except Exception as e:
        logging.exception(f"Form submission failed: {e}")
        raise
    finally:
        driver.quit()
