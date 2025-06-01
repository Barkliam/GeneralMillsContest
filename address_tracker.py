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

CSV_PATH = "data/addresses.csv"
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


def get_address():
    if not os.path.exists(CSV_PATH):
        logger.error(f"CSV file not found at {CSV_PATH}")
        raise FileNotFoundError(f"CSV file not found at {CSV_PATH}")

    now = datetime.now()
    twenty_four_hours_ago = now - timedelta(hours=24)
    updated_rows = []
    selected_address = None

    try:
        with LockedFile(CSV_PATH, "r+") as csvfile:
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
                logger.warning("No available address to use.")
                raise Exception(
                    "No available address to use. All have reached max usage or were used within the last 24 hours.")

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