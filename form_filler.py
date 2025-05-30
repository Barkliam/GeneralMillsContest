import logging
import os
import tempfile
import time
from datetime import datetime

import requests
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.wait import WebDriverWait

# Logging setup
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(
    filename=os.path.join(LOG_DIR, "form_filler.log"),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)


def find_element_endswith_id(driver, suffix):
    elems = driver.find_elements(By.CSS_SELECTOR, f"[id$='{suffix}']")
    if not elems:
        raise NoSuchElementException(f"Element with ID suffix '{suffix}' not found.")
    return elems[0]


def manual_receipt_upload(driver, receipt_path):
    upload_url = "https://gmfreegroceries.ca/DesktopModules/DnnSharp/ActionForm/UploadFile.ashx"
    params = {
        "_portalId": "7",
        "openMode": "Always",
        "_tabId": "388",
        "_aliasid": "41",
        "_mid": "1537",
        "language": "en-CA",
        "fieldid": "655"
    }

    # Extract cookies from Selenium driver
    selenium_cookies = driver.get_cookies()
    session = requests.Session()
    for cookie in selenium_cookies:
        session.cookies.set(cookie['name'], cookie['value'])

    # Grab token from page
    token_element = driver.find_element(By.NAME, "__RequestVerificationToken")
    request_verification_token = token_element.get_attribute("value")

    headers = {
        "User-Agent": driver.execute_script("return navigator.userAgent;"),
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": "https://gmfreegroceries.ca",
        "Referer": "https://gmfreegroceries.ca/Enter",
        "RequestVerificationToken": request_verification_token,
        "ModuleId": "1537",
        "TabId": "388",
    }

    with open(receipt_path, "rb") as f:
        files = {
            'file': (os.path.basename(receipt_path), f, 'application/octet-stream')
        }

        response = session.post(upload_url, headers=headers, params=params, files=files)

    # Check if it worked
    if response.status_code == 200 and "success" in response.text.lower():
        logging.info("Manual upload successful.")
    else:
        logging.error(f"Manual upload failed. Status: {response.status_code}, Response: {response.text}")
        raise Exception("Manual upload failed.")


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
    try:
        driver.get(url)
        print(driver.execute_script("return document.cookie"))
        time.sleep(5)

        driver.find_element(By.ID, "dnn1537FirstName").send_keys(data['FirstName'])
        find_element_endswith_id(driver, "FirstName").send_keys(data['FirstName'])
        driver.find_element(By.ID, "dnn1537LastName").send_keys(data['LastName'])
        driver.find_element(By.ID, "dnn1537Address").send_keys(data['StreetNumber'])
        driver.find_element(By.ID, "dnn1537Unit").send_keys(data.get('Unit', ''))
        driver.find_element(By.ID, "dnn1537City").send_keys(data['City'])
        Select(driver.find_element(By.ID, "dnn1537Province")).select_by_visible_text(data['Province'])
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

        agree_checkbox = find_element_endswith_id(driver, "Agree")
        if not agree_checkbox.is_selected():
            agree_checkbox.click()

        submit_btn = find_element_endswith_id(driver, "Continue")
        if submit_btn.is_enabled():
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
                    print("WINNER")

                elif "2025nonwinner" in poster_url:
                    print("not winner")

                else:
                    print("error, unknown video found" + poster_url)

                learn_more_button.click()
                time.sleep(5)
                print(driver.current_url)

                # TODO implement moving uploaded file
                # Move file after successful upload
                # shutil.move(full_path, os.path.join(used_dir, receipt_file))
                # logging.info(f"Successfully uploaded and moved: {receipt_file}")
            except Exception as e:

                error_element = driver.find_element(By.CLASS_NAME, "jq-toast-wrap")
                if (error_element):
                    print("Error submitting form: " + error_element.text)

        else:
            logging.warning("Submit button is disabled. Form not submitted.")

    except Exception as e:
        logging.exception(f"Form submission failed: {e}")
        raise
    finally:
        driver.quit()
