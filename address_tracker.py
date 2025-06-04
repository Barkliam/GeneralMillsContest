import csv
import logging
import os

# Conditional import for file locking
if os.name == 'nt':  # Windows
    import msvcrt
else:  # POSIX (Linux, macOS)
    import fcntl
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

REAL_ADDRESS_CSV_PATH = "data/real_addresses.csv"
DUMMY_ADDRESS_CSV_PATH = "data/dummy_addresses.csv"
MAX_USES = 10


class LockedFile:
    def __init__(self, path, mode):
        self.path = path
        self.mode = mode
        self.file = None

    def __enter__(self):
        self.file = open(self.path, self.mode, newline='', encoding='utf-8')
        if os.name == "nt":
            msvcrt.locking(self.file.fileno(), msvcrt.LK_LOCK, 1)
        else:
            fcntl.flock(self.file, fcntl.LOCK_EX)
        return self.file

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.file:
            if os.name == "nt":
                self.file.seek(0)
                msvcrt.locking(self.file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(self.file, fcntl.LOCK_UN)
            self.file.close()


def get_real_address():
    logger.info("attempting to get real address...")
    if not os.path.exists(REAL_ADDRESS_CSV_PATH):
        logger.error(f"CSV file not found at {REAL_ADDRESS_CSV_PATH}")
        raise FileNotFoundError(f"CSV file not found at {REAL_ADDRESS_CSV_PATH}")

    now = datetime.now()
    twenty_four_hours_ago = now - timedelta(hours=24)
    updated_rows = []
    selected_address = None

    try:
        with LockedFile(REAL_ADDRESS_CSV_PATH, "r+") as csvfile:
            reader = csv.DictReader(csvfile)
            fieldnames = reader.fieldnames
            rows = list(reader)

            for row in rows:
                usage_count = int(row.get("TimesUsed", 0))
                last_used_datetime = datetime.fromisoformat(row.get("LastUsedDateTime", ""))

                if selected_address is None and usage_count < MAX_USES and last_used_datetime < twenty_four_hours_ago:
                    # Select this address
                    row["TimesUsed"] = str(usage_count + 1)
                    row["LastUsedDateTime"] = now.isoformat()
                    selected_address = row
                    logger.info(f"Selected address: {row.get('Email', 'unknown')} (used {usage_count + 1} times)")

                updated_rows.append(row)

            if selected_address is None:
                logger.warning("No available real address to use.")
                raise Exception(
                    "No available real address to use. All have reached max usage or were used within the last 24 hours.")

            # Write updates back to file
            csvfile.seek(0)
            csvfile.truncate()
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(updated_rows)

        return selected_address

    except Exception as e:
        logger.error(f"Failed to get address: {e}", exc_info=True)
        raise


def get_dummy_address():
    logger.info("attempting to get dummy address...")

    if not os.path.exists(DUMMY_ADDRESS_CSV_PATH):
        logger.error(f"Dummy CSV file not found at {DUMMY_ADDRESS_CSV_PATH}")
        raise FileNotFoundError(f"Dummy CSV file not found at {DUMMY_ADDRESS_CSV_PATH}")

    try:
        with open(DUMMY_ADDRESS_CSV_PATH, 'r', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            rows = list(reader)

            if not rows:
                logger.warning("Dummy CSV file is empty")
                raise Exception("Dummy CSV file is empty")

            # Find the address with the oldest LastUsedDateTime
            oldest_address = None
            oldest_datetime = None

            for row in rows:
                try:
                    last_used_str = row.get("LastUsedDateTime", "")
                    if not last_used_str:
                        oldest_address = row
                        break

                    last_used_datetime = datetime.fromisoformat(last_used_str)
                    if oldest_datetime is None or last_used_datetime < oldest_datetime:
                        oldest_datetime = last_used_datetime
                        oldest_address = row

                except ValueError as ve:
                    logger.info(
                        f"Invalid datetime format for row with email {row.get('Email', 'unknown')}: {ve} - treating as infinitely old")
                    oldest_address = row
                    break

            if oldest_address is None:
                raise Exception("No valid dummy address found")

            logger.info(
                f"Selected dummy address: {oldest_address.get('Email', 'unknown')} with LastUsedDateTime: {oldest_datetime}")
            return oldest_address

    except Exception as e:
        logger.error(f"Failed to get dummy address: {e}", exc_info=True)
        raise