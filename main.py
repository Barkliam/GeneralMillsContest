import logging
import time

import schedule

from address_tracker import get_address
from form_filler import submit_form

# Setup logging to file and console
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# File handler
file_handler = logging.FileHandler("logs/main.log")
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
        data = get_address()
        if data:
            submit_form(data)
            logging.info("Submission completed successfully.")
        else:
            logging.warning("No address data returned.")
    except Exception as e:
        logging.error(f"Error during form submission: {e}", exc_info=True)


def main():
    logging.info("Starting contest submission scheduler...")

    form_submission_job()
    # Schedule job at 6:00, 7:00, and 8:00
    # schedule.every().day.at("06:00").do(form_submission_job)
    # schedule.every().day.at("07:00").do(form_submission_job)
    # schedule.every().day.at("08:00").do(form_submission_job)

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
