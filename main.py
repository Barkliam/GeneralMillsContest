import logging
import os
import time
from datetime import datetime, time as dt_time

import schedule

from address_tracker import get_real_address, get_dummy_address
from form_filler import submit_form

# Configuration for scheduling
START_TIME = "05:00"  # Start time in HH:MM format
END_TIME = "09:00"  # End time in HH:MM format
INTERVAL = 5  # Interval between attempts in minutes

# Global flag to stop all tasks when winner is found
winner_found = False


def setup_logging() -> logging.Logger:
    """Setup logging to file and console with proper configuration."""
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Clear any existing handlers to avoid duplicates
    logger.handlers.clear()

    # Date-based log file
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    log_filename = os.path.join(log_dir, f"{datetime.today().date()}.log")

    # Insert clear break if file already exists
    if os.path.exists(log_filename):
        with open(log_filename, "a", encoding="utf-8") as f:
            f.write("\n" + "=" * 60 + f"\n=== NEW SESSION STARTED: {datetime.now()} ===\n" + "=" * 60 + "\n")

    # File handler
    file_handler = logging.FileHandler(log_filename, encoding="utf-8")
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

    return logger


def is_within_schedule() -> bool:
    """Check if current time is within the scheduled time range."""
    now = datetime.now().time()
    start_time = dt_time.fromisoformat(START_TIME)
    end_time = dt_time.fromisoformat(END_TIME)

    # Handle cases where end time is next day (e.g., 22:00 to 06:00)
    if start_time <= end_time:
        return start_time <= now <= end_time
    else:
        return now >= start_time or now <= end_time


def form_submission_job(logger: logging.Logger) -> None:
    """Job function that runs form submission with time checking."""
    global winner_found

    # Check if we've already found a winner
    if winner_found:
        logger.info("Winner already found. Skipping submission.")
        return

    if not is_within_schedule():
        logger.info(f"Current time is outside scheduled hours ({START_TIME} - {END_TIME}). Skipping submission.")
        return

    logger.info("Running scheduled form submission...")

    try:
        # First attempt with dummy data to check if we might win
        logger.info("Testing with dummy address to check winner status...")
        is_potential_winner = submit_form(get_dummy_address(), real_submission=False, save_screenshot=False)

        if is_potential_winner:
            logger.info("Winner detected. Attempting submission with real address...")
            try:
                schedule.clear()
                real_address = get_real_address()
                actual_winner = submit_form(real_address, real_submission=True, save_screenshot=True, reuse_driver=True)
                if actual_winner:
                    logger.info("🎉 CONFIRMED WINNER WITH REAL SUBMISSION! 🎉")
                    logger.info("Setting winner flag to stop all future submissions...")
                    winner_found = True
                    logger.info("All scheduled jobs cleared due to winner confirmation.")
                else:
                    logger.info("Real submission not a winner. Waiting 20 minutes before trying again...")
                    time.sleep(20 * 60)  # Pause 20 minutes
                    # Retry one more real submission
                    logger.info("Retrying real submission after 20-minute wait...")
                    actual_winner = submit_form(real_address, real_submission=True, save_screenshot=True)
                    if actual_winner:
                        logger.info("🎉 WINNER ON SECOND REAL SUBMISSION! 🎉")
                        winner_found = True
                        logger.info("All scheduled jobs cleared due to winner confirmation.")
                    else:
                        logger.info("Second real submission also not a winner. All scheduled jobs cleared.")
                        os._exit(0)  # Forceful exit of the script

            except FileNotFoundError as e:
                logger.error(f"No real addresses available: {e}")
            except Exception as e:
                logger.error(f"Error during real submission: {e}", exc_info=True)
        else:
            logger.info("Not a winner this time, closing browser.")

    except FileNotFoundError as e:
        logger.error(f"Required files not found: {e}")
    except Exception as e:
        logger.error(f"Unexpected error during form submission: {e}", exc_info=True)


def schedule_jobs(logger: logging.Logger) -> int:
    logger.info(f"Scheduling form submission jobs every {INTERVAL} minutes between {START_TIME} and {END_TIME}")

    # Clear any existing jobs
    schedule.clear()

    # Schedule the job to run every set interval minutes
    # Pass logger to the job function
    schedule.every(INTERVAL).minutes.do(form_submission_job, logger)

    logger.info(f"Scheduled job: Every {INTERVAL} minutes")
    return len(schedule.jobs)


def validate_time_format(time_str: str) -> bool:
    """Validate that time string is in HH:MM format."""
    try:
        dt_time.fromisoformat(time_str)
        return True
    except ValueError:
        return False


def main() -> None:
    """Main function to run the contest submission scheduler."""
    global winner_found

    # Setup logging first
    logger = setup_logging()

    # Validate configuration
    if not validate_time_format(START_TIME):
        logger.error(f"Invalid START_TIME format: {START_TIME}. Expected HH:MM format.")
        return

    if not validate_time_format(END_TIME):
        logger.error(f"Invalid END_TIME format: {END_TIME}. Expected HH:MM format.")
        return

    if INTERVAL <= 0:
        logger.error(f"Invalid INTERVAL: {INTERVAL}. Must be greater than 0.")
        return

    logger.info("Starting contest submission scheduler...")
    logger.info(f"Schedule configured: {START_TIME} to {END_TIME}, every {INTERVAL} minutes")

    # Schedule the jobs
    try:
        job_count = schedule_jobs(logger)

        if job_count == 0:
            logger.warning("No scheduled jobs found. Exiting.")
            return

        logger.info(f"Scheduler started with {job_count} job(s). Press Ctrl+C to stop.")

        # Main scheduler loop
        while True:
            # Check if winner has been found
            if winner_found:
                logger.info("Winner found! Stopping scheduler...")
                break

            schedule.run_pending()
            time.sleep(30)  # Check every 30 seconds for pending jobs

    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user (Ctrl+C).")
    except Exception as e:
        logger.error(f"Unexpected error in main scheduler loop: {e}", exc_info=True)
    finally:
        schedule.clear()
        if winner_found:
            logger.info("Scheduler shutdown complete - Winner was found!")
        else:
            logger.info("All scheduled jobs cleared. Scheduler shutdown complete.")


if __name__ == "__main__":
    main()