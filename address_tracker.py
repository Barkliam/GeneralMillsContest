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


def is_empty_row(row):
    """Check if a CSV row is completely empty (all values are empty strings or None)"""
    if not row:
        return True
    return all(not value or not str(value).strip() for value in row.values())


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
                # Skip completely empty rows
                if is_empty_row(row):
                    logger.debug("Skipping empty row in addresses CSV")
                    continue

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

    now = datetime.now()

    try:
        with LockedFile(DUMMY_ADDRESS_CSV_PATH, "r+") as csvfile:
            reader = csv.DictReader(csvfile)
            fieldnames = reader.fieldnames
            rows = list(reader)

            # Filter out completely empty rows
            non_empty_rows = []
            for row in rows:
                if not is_empty_row(row):
                    non_empty_rows.append(row)
                else:
                    logger.debug("Skipping empty row in dummy addresses CSV")

            if not non_empty_rows:
                raise Exception("Dummy CSV file contains no valid (non-empty) rows")

            # Find the address with the oldest LastUsedDateTime
            oldest_address = None
            oldest_datetime = None
            oldest_index = -1

            for i, row in enumerate(non_empty_rows):
                try:
                    last_used_str = row.get("LastUsedDateTime", "")
                    if not last_used_str:
                        oldest_address = row
                        oldest_index = i
                        break

                    last_used_datetime = datetime.fromisoformat(last_used_str)
                    if oldest_datetime is None or last_used_datetime < oldest_datetime:
                        oldest_datetime = last_used_datetime
                        oldest_address = row
                        oldest_index = i

                except ValueError as ve:
                    logger.info(
                        f"Invalid datetime format for row with email {row.get('Email', 'unknown')}: {ve} - treating as infinitely old")
                    oldest_address = row
                    oldest_index = i
                    break

            if oldest_address is None:
                raise Exception("No valid dummy address found")

            # Update the LastUsedDateTime for the selected address
            non_empty_rows[oldest_index]["LastUsedDateTime"] = now.isoformat()

            # Write updates back to file (only non-empty rows)
            csvfile.seek(0)
            csvfile.truncate()
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(non_empty_rows)

            logger.info(
                f"Selected dummy address: {oldest_address.get('Email', 'unknown')} with previous LastUsedDateTime: {oldest_datetime}, updated to: {now.isoformat()}")

            return oldest_address

    except Exception as e:
        logger.error(f"Failed to get dummy address: {e}", exc_info=True)
        raise