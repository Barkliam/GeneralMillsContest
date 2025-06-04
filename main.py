import logging
import os
import time
from datetime import datetime, time as dt_time

import schedule

from address_tracker import get_real_address, get_dummy_address
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

# Configuration for scheduling
START_TIME = "06:00"  # Start time in HH:MM format
END_TIME = "08:00"  # End time in HH:MM format
INTERVAL = 5  # Interval between attempts in minutes


def is_within_schedule():
    """Check if current time is within the scheduled time range."""
    now = datetime.now().time()
    start_time = dt_time.fromisoformat(START_TIME)
    end_time = dt_time.fromisoformat(END_TIME)

    # Handle cases where end time is next day (e.g., 22:00 to 06:00)
    if start_time <= end_time:
        return start_time <= now <= end_time
    else:
        return now >= start_time or now <= end_time


def form_submission_job():
    """Job function that runs form submission with time checking."""
    if not is_within_schedule():
        logging.info(f"Current time is outside scheduled hours ({START_TIME} - {END_TIME}). Skipping submission.")
        return

    logging.info("Running scheduled form submission...")
    try:
        if submit_form(get_dummy_address()):
            logging.info("Attempting to submit with real address.")
            submit_form(get_real_address(), True, True)
        else:
            logging.info("Not a winner this time, exiting.")
    except Exception as e:
        logging.error(f"Error during form submission: {e}", exc_info=True)


def schedule_jobs():
    logging.info(f"Scheduling form submission jobs every {INTERVAL} minutes between {START_TIME} and {END_TIME}")

    # Clear any existing jobs
    schedule.clear()

    # Schedule the job to run every set interval minutes
    schedule.every(INTERVAL).minutes.do(form_submission_job)

    return len(schedule.jobs)


def main():
    logging.info("Starting contest submission scheduler...")

    # Schedule the jobs
    job_count = schedule_jobs()

    if job_count == 0:
        logging.info("No scheduled jobs found. Exiting.")
        return

    logging.info(f"Scheduler started with {job_count} job(s). Press Ctrl+C to stop.")

    try:
        while True:
            schedule.run_pending()
            time.sleep(30)  # Check every 30 seconds for pending jobs
    except KeyboardInterrupt:
        logging.info("Scheduler stopped by user.")
    finally:
        schedule.clear()
        logging.info("All scheduled jobs cleared.")


if __name__ == "__main__":
    main()
