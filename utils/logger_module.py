# logger_module.py

import os
import datetime

class SystemLogger:
    def __init__(self, admin_log_dir="logs/admin", user_log_dir="logs/user"):
        self.admin_log_dir = admin_log_dir
        self.user_log_dir = user_log_dir

        # Ensure directories exist
        os.makedirs(self.admin_log_dir, exist_ok=True)
        os.makedirs(self.user_log_dir, exist_ok=True)

    def info(self, message):
        """Log info level message."""
        self.log_user("SYSTEM", message, True)

    def error(self, message):
        """Log error level message."""
        self.log_user("SYSTEM", message, False)

    def exception(self, message):
        """Log exception with message."""
        self.error(f"Exception: {message}")

    def _get_timestamp(self):
        """
        Format: day/month/year-hours:minutes:seconds:milliseconds
        """
        now = datetime.datetime.now()
        return now.strftime("%d/%m/%Y-%H:%M:%S:%f")

    def log_admin(self, username, action, success=True, message=None):
        """
        Log admin actions with optional message.
        """
        timestamp = self._get_timestamp()
        status = "SUCCESS" if success else "FAIL"
        log_entry = f"[{timestamp}] [ADMIN={username}] [ACTION={action}] [STATUS={status}]"
        if message:
            log_entry += f" [MESSAGE={message}]"
        log_entry += "\n"

        filename = os.path.join(self.admin_log_dir, "admin_log.txt")
        with open(filename, "a") as f:
            f.write(log_entry)

    def log_user(self, user_info, action, success=True):
        timestamp = self._get_timestamp()
        status = "SUCCESS" if success else "FAIL"
        filename = os.path.join(self.user_log_dir, "user_log.txt")
        with open(filename, "a") as f:
            f.write(f"[{timestamp}] [USER={user_info}] [ACTION={action}] [STATUS={status}]\n")

    def log_trip(self, trip_number, details):
        """
        For writing trip-level info.
        'details' could be a dict or string.
        """
        timestamp = self._get_timestamp()
        filename = os.path.join(self.user_log_dir, "trip_log.txt")
        with open(filename, "a") as f:
            f.write(f"\n=== TRIP #{trip_number} ({timestamp}) ===\n")
            f.write(f"{details}\n")
            f.write("====================================\n")
