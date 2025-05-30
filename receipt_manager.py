import logging
import os
import shutil

logger = logging.getLogger(__name__)


class ReceiptManager:
    def __init__(self, fresh_dir: str = "data/receipts/fresh", used_dir: str = "data/receipts/used"):
        self.current_receipt = None
        self.fresh_dir = fresh_dir
        self.used_dir = used_dir

        # Ensure directories exist
        os.makedirs(self.fresh_dir, exist_ok=True)
        os.makedirs(self.used_dir, exist_ok=True)

        logger.info(f"ReceiptManager initialized - Fresh: {self.fresh_dir}, Used: {self.used_dir}")

    def get_next_receipt(self) -> str:
        receipts = [f for f in os.listdir(self.fresh_dir) if os.path.isfile(os.path.join(self.fresh_dir, f))]
        if not receipts:
            raise FileNotFoundError(f"No fresh receipts found in directory. ({self.fresh_dir})")

        receipt_file = receipts[0]
        self.current_receipt = receipt_file
        return os.path.abspath(os.path.join(self.fresh_dir, receipt_file))

    def move_current_receipt_to_used(self) -> None:
        if not self.current_receipt:
            error_msg = "No current receipt to move."
            raise Exception(error_msg)

        current_path = os.path.abspath(os.path.join(self.fresh_dir, self.current_receipt));
        destination_path = os.path.join(self.used_dir, self.current_receipt)
        shutil.move(current_path, destination_path)
        logger.info(f"Moved: {self.current_receipt}  --->  {destination_path}")
