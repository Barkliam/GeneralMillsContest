import csv
import logging
import os

# Conditional import for file locking
if os.name == 'nt':  # Windows
    import msvcrt
else:  # POSIX (Linux, macOS)
    import fcntl
from datetime import datetime

# Logging setup
logging.basicConfig(
    filename="logs/address_tracker.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s"
)

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
        logging.error(f"CSV file not found at {CSV_PATH}")
        raise FileNotFoundError(f"CSV file not found at {CSV_PATH}")

    today = datetime.today().date()
    updated_rows = []
    selected_address = None

    try:
        with LockedFile(CSV_PATH, "r+") as csvfile:
            reader = csv.DictReader(csvfile)
            fieldnames = reader.fieldnames
            rows = list(reader)

            for row in rows:
                usage_count = int(row.get("TimesUsed", 0))
                last_used = row.get("LastUsedDate", "")
                last_used_date = datetime.strptime(last_used, "%Y-%m-%d").date() if last_used else None

                if selected_address is None and usage_count < MAX_USES and last_used_date != today:
                    # Select this address
                    row["TimesUsed"] = str(usage_count + 1)
                    row["LastUsedDate"] = today.isoformat()
                    selected_address = row
                    logging.info(f"Selected address: {row['Email']} (used {usage_count + 1} times)")

                updated_rows.append(row)

            if selected_address is None:
                logging.warning("No available address to use.")
                raise Exception("No available address to use. All have reached max usage or were used today.")

            # Write updates back to file
            csvfile.seek(0)
            csvfile.truncate()
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(updated_rows)

        return selected_address

    except Exception as e:
        logging.error(f"Failed to get address: {e}", exc_info=True)
        raise
