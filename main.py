import logging
import os
import time
from datetime import datetime

import schedule

from config import REAL_ADDRESS_CSV_PATH, DUMMY_ADDRESS_CSV_PATH, MAX_USES_PER_ADDRESS, PREFERRED_STORE, CONTEST_URL, \
    SCHEDULED_SUBMISSION_TIMES
from address_tracker import get_real_address
from form_filler import submit_form

# Setup logging to file and console
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Date-based log file
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)
log_filename = os.path.join(log_dir, f"{datetime.today().date()}.log")

# Insert clear break if file already exists
if os.path.exists(log_filename):
    with open(log_filename, "a", encoding="utf-8") as f:
        f.write("\n" + "=" * 60 + f"\n=== NEW SESSION STARTED: {datetime.now()} ===\n" + "=" * 60 + "\n")

# File handler
file_handler = logging.FileHandler(log_filename)
file_handler.setLevel(logging.INFO)
file_formatter = logging.Formatter("%(asctime)s %(levelname)s: %(message)s")
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter("%(asctime)s %(levelname)s: %(message)s")
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)


def form_submission_job():
    logging.info("Running scheduled form submission...")
    try:
        data = get_real_address()
        if data:
            submit_form(data)
            logging.info("Submission completed successfully.")
        else:
            logging.warning("No address data returned.")
    except Exception as e:
        logging.error(f"Error during form submission: {e}", exc_info=True)


def main():
    logging.info("Starting contest submission scheduler...")

    #form_submission_job()  # uncomment to enter immediately

    for time_str in SCHEDULED_SUBMISSION_TIMES:
        schedule.every().day.at(time_str).do(form_submission_job)

    if not schedule.jobs:
        logging.info("No scheduled jobs found. Exiting.")
        return

    try:
        while True:
            schedule.run_pending()
            time.sleep(5)
    except KeyboardInterrupt:
        logging.info("Scheduler stopped by user.")


if __name__ == "__main__":
    main()
