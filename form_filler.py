import os
import shutil
import tempfile
import time
import logging
from telnetlib import EC


from selenium import webdriver
from selenium.webdriver import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.common.action_chains import ActionChains

import time

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

#TODO only move the receipt if the form submission was successful
def upload_receipt(driver):
    fresh_dir = "data/receipts/fresh"
    used_dir = "data/receipts/used"

    receipts = [f for f in os.listdir(fresh_dir) if os.path.isfile(os.path.join(fresh_dir, f))]
    if not receipts:
        logging.error("No fresh receipts found.")
        raise FileNotFoundError("No fresh receipts found.")

    receipt_file = receipts[0]
    full_path = os.path.abspath(os.path.join(fresh_dir, receipt_file))

    #upload_input = driver.find_element(By.CSS_SELECTOR, "input[type='file'][name='UploadReceipt']")
    #upload_input.send_keys(full_path)
    for cookie in driver.get_cookies():
        print(f"{cookie['name']} = {cookie['value']}")
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

    # Move file after successful upload
    shutil.move(full_path, os.path.join(used_dir, receipt_file))
    logging.info(f"Successfully uploaded and moved: {receipt_file}")

def get_chrome_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--start-maximized")
    options.add_argument("--autoplay-policy=no-user-gesture-required")

    # ✅ Use a fresh temporary user data dir for this session
    temp_user_data_dir = tempfile.mkdtemp()
    options.add_argument(f"--user-data-dir={temp_user_data_dir}")
    options.add_argument("--disable-features=SameSiteByDefaultCookies,CookiesWithoutSameSiteMustBeSecure")
    options.add_experimental_option("prefs", {
        "profile.default_content_setting_values.cookies": 1,
        "profile.block_third_party_cookies": False
    })
    # Disable headless during debug
    # options.add_argument("--headless=new")

    return webdriver.Chrome(options=options)

def select_preferred_store(driver, preferred_store=None):
    # Step 1: Find and click the input to trigger dropdown
    input_el = find_element_endswith_id(driver, "PreferredStore")
    input_el.click()
    time.sleep(0.5)  # Let the dropdown populate



    # Step 2: Wait for the first suggestion to appear
    wait = WebDriverWait(driver, 5)
    first_option = wait.until(
        expected_conditions.element_to_be_clickable((By.CSS_SELECTOR, "#dnn1537PreferredStore_dropdown .angucomplete-row"))
    )

    # Step 3: Click the first option
    first_option.click()
    time.sleep(0.3)

def submit_form(data):
    url = "https://gmfreegroceries.ca/Enter"
    preferred_store = "Walmart" #Change this to whichever store you want to giftcards from
    options = webdriver.ChromeOptions()
    #options.add_argument("--headless")
    driver = get_chrome_driver()
    try:
        driver.get(url)
        print(driver.execute_script("return document.cookie"))
        time.sleep(5)

        find_element_endswith_id(driver, "FirstName").send_keys(data['FirstName'])
        find_element_endswith_id(driver, "LastName").send_keys(data['LastName'])
        find_element_endswith_id(driver, "Address").send_keys(data['StreetNumber'])
        find_element_endswith_id(driver, "Unit").send_keys(data.get('Unit', ''))
        find_element_endswith_id(driver, "City").send_keys(data['City'])

        province_select = Select(find_element_endswith_id(driver, "Province"))
        province_select.select_by_visible_text(data['Province'])

        find_element_endswith_id(driver, "PostalCode").send_keys(data['PostalCode'])
        find_element_endswith_id(driver, "Email").send_keys(data['Email'])
        find_element_endswith_id(driver, "Phone").send_keys(data['Phone'])
        find_element_endswith_id(driver, "Birthdate").send_keys(data['Birthdate'])

        select_preferred_store(driver, preferred_store)

        upload_receipt(driver)

        agree_checkbox = find_element_endswith_id(driver, "Agree")
        if not agree_checkbox.is_selected():
            agree_checkbox.click()

        submit_btn = find_element_endswith_id(driver, "Continue")
        if submit_btn.is_enabled():
            driver.execute_script("arguments[0].click();", submit_btn)
            logging.info("Form submitted.")
            time.sleep(5)

            #TODO check here if the page has changed or if it is still on the form

            result = check_result_video(driver)
            logging.info(f"Result video detected: {result}")
        else:
            logging.warning("Submit button is disabled. Form not submitted.")

    except Exception as e:
        logging.exception(f"Form submission failed: {e}")
        raise
    finally:
        driver.quit()


def check_result_video(driver):
    try:
        # Wait for video element to appear (adjust timeout as needed)
        video_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "video.winningvideo"))
        )
        # Find the first <source> tag inside the <video> tag
        source = video_element.find_element(By.TAG_NAME, "source")
        src = source.get_attribute("src")

        if "winner/2025winner_EN.mp4" in src:
            logging.info("🎉 Submission successful — WINNING video detected!")
            return "winner"
        elif "nonwinner/2025nonwinner_EN.mp4" in src:
            logging.info("Submission completed — non-winning result.")
            return "non-winner"
        else:
            logging.warning(f"Unexpected video source: {src}")
            return "unknown"
    except Exception as e:
        logging.exception(f"Could not find result video: {e}")
        return "error"