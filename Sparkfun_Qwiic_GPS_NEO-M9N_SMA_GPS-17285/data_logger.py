# data_logger.py

import os
import logging
import logging.handlers
import queue
import json
import csv
import shutil
import sys
from datetime import datetime, timedelta

# Import constants from config.py
from config import (
    LOG_DIR, TRIP_LOG_DIR, LOG_FILE_MAX_BYTES, LOG_FILE_BACKUP_COUNT,
    LOG_FILE_FORMAT, MIN_DISK_SPACE_MB, MAX_LOG_AGE_DAYS
)
from utils import format_coord, format_value

class DataLogger:
    """Handles logging of GPS data to various formats and console output."""
    def __init__(self, log_dir, max_bytes, backup_count, max_age_days, settings_manager=None):
        self.log_dir = log_dir
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self.max_age_days = max_age_days
        self.settings_manager = settings_manager # Store settings_manager

        os.makedirs(self.log_dir, exist_ok=True)
        # Ensure trip log directory exists
        os.makedirs(TRIP_LOG_DIR, exist_ok=True)

        self.queue = queue.Queue() # Queue for status messages

        # Setup a dedicated logger for console output FIRST
        self.console_logger = logging.getLogger('console_logger')
        self.console_logger.setLevel(logging.DEBUG) # Lowest level to capture all
        self.console_logger.propagate = False # Prevent messages from going to root logger

        # Initialize file loggers to None; they will be set up when settings are loaded
        self.nmea_logger = None
        self.json_logger = None
        self.csv_file = None
        self.csv_writer = None

        # Set up handlers based on initial settings (or defaults)
        self._setup_console_handler()
        self._setup_file_handlers() # Call this to set up file handlers based on settings

        # Log initialization messages using the console_logger
        self.log_debug(f"DataLogger initialized. Log directory: {self.log_dir}")
        self.log_debug(f"Max log bytes: {self.max_bytes}, Backup count: {self.backup_count}, Max age days: {self.max_age_days}")
        self.log_debug(f"Settings Manager provided: {settings_manager is not None}")

    def _setup_console_handler(self):
        """Sets up or reconfigures the console handler based on settings."""
        # Remove existing console handlers to prevent duplicates
        for handler in list(self.console_logger.handlers):
            if isinstance(handler, logging.StreamHandler):
                self.console_logger.removeHandler(handler)
                handler.close()

        if self.settings_manager and not self.settings_manager.get("console_output_enabled"):
            self.log_debug("Console output disabled by settings.")
            return

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(logging.Formatter(LOG_FILE_FORMAT))
        self.console_logger.addHandler(console_handler)
        self.log_debug("Console output handler set up.")

        # Also manage file output for console logs
        self._setup_console_file_handler()


    def _setup_console_file_handler(self):
        """Sets up or reconfigures the console output to file handler."""
        # Remove existing file handlers for the console_logger
        for handler in list(self.console_logger.handlers):
            if isinstance(handler, logging.handlers.RotatingFileHandler) and handler.baseFilename.endswith('console.log'):
                self.console_logger.removeHandler(handler)
                handler.close()

        if self.settings_manager and not self.settings_manager.get("console_output_to_file_enabled"):
            self.log_debug("Console output to file disabled by settings.")
            return

        console_file_path = os.path.join(self.log_dir, "console.log")
        console_file_handler = logging.handlers.RotatingFileHandler(
            console_file_path,
            maxBytes=self.max_bytes,
            backupCount=self.backup_count
        )
        console_file_handler.setFormatter(logging.Formatter(LOG_FILE_FORMAT))
        self.console_logger.addHandler(console_file_handler)
        self.log_debug(f"Console output to file handler set up at: {console_file_path}")


    def _setup_file_handlers(self):
        """Sets up or reconfigures the NMEA and JSON file handlers based on settings."""
        # Close existing handlers if they exist
        if self.nmea_logger:
            for handler in list(self.nmea_logger.handlers):
                self.nmea_logger.removeHandler(handler)
                handler.close()
            self.nmea_logger = None # Reset to None after closing

        if self.json_logger:
            for handler in list(self.json_logger.handlers):
                self.json_logger.removeHandler(handler)
                handler.close()
            self.json_logger = None # Reset to None after closing

        if self.csv_file and not self.csv_file.closed:
            self.csv_file.close()
            self.csv_file = None
            self.csv_writer = None

        # Re-create handlers based on current settings
        if self.settings_manager:
            if self.settings_manager.get("log_nmea"):
                nmea_log_path = os.path.join(self.log_dir, "nmea_log.txt")
                self.nmea_logger = logging.getLogger('nmea_logger')
                self.nmea_logger.setLevel(logging.INFO)
                self.nmea_logger.propagate = False # Prevent messages from going to root logger
                nmea_handler = logging.handlers.RotatingFileHandler(
                    nmea_log_path,
                    maxBytes=self.max_bytes,
                    backupCount=self.backup_count
                )
                nmea_handler.setFormatter(logging.Formatter('%(message)s')) # Raw NMEA
                self.nmea_logger.addHandler(nmea_handler)
                self.log_debug(f"NMEA file logging enabled at: {nmea_log_path}")
            else:
                self.log_debug("NMEA file logging disabled by settings.")

            if self.settings_manager.get("log_json"):
                json_log_path = os.path.join(self.log_dir, "gps_data.jsonl")
                self.json_logger = logging.getLogger('json_logger')
                self.json_logger.setLevel(logging.INFO)
                self.json_logger.propagate = False # Prevent messages from going to root logger
                json_handler = logging.handlers.RotatingFileHandler(
                    json_log_path,
                    maxBytes=self.max_bytes,
                    backupCount=self.backup_count
                )
                json_handler.setFormatter(logging.Formatter('%(message)s')) # Raw JSON line
                self.json_logger.addHandler(json_handler)
                self.log_debug(f"JSONL file logging enabled at: {json_log_path}")
            else:
                self.log_debug("JSONL file logging disabled by settings.")

            if self.settings_manager.get("log_csv"):
                csv_log_path = os.path.join(self.log_dir, "gps_data.csv")
                try:
                    # Check if file exists and is empty to write header
                    file_exists = os.path.exists(csv_log_path)
                    is_empty = not file_exists or os.stat(csv_log_path).st_size == 0

                    self.csv_file = open(csv_log_path, 'a', newline='') # Open in append mode
                    self.csv_writer = csv.writer(self.csv_file)
                    if is_empty:
                        # Define a comprehensive header based on potential GPS data fields
                        header = [
                            "Timestamp", "Latitude", "Longitude", "Altitude (MSL)",
                            "Speed (m/s)", "Heading (deg)", "Num SV", "Fix Type",
                            "Horizontal Accuracy (m)", "Vertical Accuracy (m)",
                            "PDOP", "HDOP", "VDOP",
                            "HP Latitude", "HP Longitude", "HP Height (m)",
                            "Carrier Solution", "Differential Age", "RTK Age", "RTK Ratio"
                        ]
                        self.csv_writer.writerow(header)
                        self.csv_file.flush() # Ensure header is written immediately
                        self.log_debug("CSV header written.")
                    self.log_debug(f"CSV file logging enabled at: {csv_log_path}")
                except Exception as e:
                    self.log_error(f"Failed to set up CSV logging: {e}")
                    self.csv_file = None
                    self.csv_writer = None
            else:
                self.log_debug("CSV file logging disabled by settings.")
        else:
            self.log_debug("No settings manager provided, file logging handlers not configured.")


    def log_nmea(self, message):
        """Logs raw NMEA data to a file if enabled."""
        if self.nmea_logger:
            self.nmea_logger.info(message.strip())

    def log_json(self, data):
        """Logs GPS data as a JSON line to a file if enabled."""
        if self.json_logger:
            # Add timestamp to the JSON data
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "data": data
            }
            self.json_logger.info(json.dumps(log_entry))

    def log_csv(self, data):
        """Logs GPS data to a CSV file if enabled."""
        if self.csv_writer and self.csv_file:
            timestamp = datetime.now().isoformat()
            
            # Ensure gSpeed is in m/s for CSV logging
            speed_mps = data.get('gSpeed', float('nan'))
            # The speed from ublox_gps is mm/s, so if it's a large number, assume mm/s and convert
            # This heuristic is used because the source of 'data' can be live (mm/s) or playback (m/s)
            if speed_mps > 1000: # Assuming typical speeds won't exceed 1000 m/s
                speed_mps /= 1000.0

            row = [
                timestamp,
                format_coord(data.get('lat', float('nan'))),
                format_coord(data.get('lon', float('nan'))),
                format_value(data.get('hMSL', float('nan'))),
                format_value(speed_mps, 2), # Log speed in m/s
                format_value(data.get('headMot', float('nan'))),
                data.get('numSV', 'N/A'),
                data.get('fixType', 'N/A'),
                format_value(data.get('hAcc', float('nan'))),
                format_value(data.get('vAcc', float('nan'))),
                format_value(data.get('pDOP', float('nan'))),
                format_value(data.get('hDOP', float('nan'))),
                format_value(data.get('vDOP', float('nan'))),
                format_coord(data.get('hp_lat', float('nan'))),
                format_coord(data.get('hp_lon', float('nan'))),
                format_value(data.get('hp_height', float('nan'))),
                data.get('carrSoln', 'N/A'),
                format_value(data.get('diffAge', float('nan'))),
                format_value(data.get('rtkAge', float('nan'))),
                format_value(data.get('rtkRatio', float('nan')))
            ]
            self.csv_writer.writerow(row)
            self.csv_file.flush() # Ensure data is written to disk immediately

    def check_disk_space(self):
        """Checks available disk space and logs a warning if it's low."""
        try:
            total, used, free = shutil.disk_usage(self.log_dir)
            free_mb = free / (1024 * 1024)
            if free_mb < MIN_DISK_SPACE_MB:
                self.log_warning(f"Low disk space alert! Only {free_mb:.2f} MB free in {self.log_dir}")
                self.queue.put(f"WARNING: Low disk space! Only {free_mb:.2f} MB free.")
            else:
                self.log_debug(f"Disk space check: {free_mb:.2f} MB free in {self.log_dir}")
        except Exception as e:
            self.log_error(f"Could not check disk space for {self.log_dir}: {e}")

    def clean_old_logs(self):
        """Deletes log files older than max_age_days."""
        now = datetime.now()
        # Clean main log directory
        self._clean_directory(self.log_dir, now)
        # Clean trip log directory
        self._clean_directory(TRIP_LOG_DIR, now)

    def _clean_directory(self, directory_path, now):
        """Helper to clean old files in a specified directory."""
        if not os.path.exists(directory_path):
            self.log_debug(f"Directory for cleaning does not exist: {directory_path}")
            return

        self.log_debug(f"Cleaning old log files in: {directory_path}")
        for filename in os.listdir(directory_path):
            filepath = os.path.join(directory_path, filename)
            if os.path.isfile(filepath):
                file_mod_time = datetime.fromtimestamp(os.path.getmtime(filepath))
                if (now - file_mod_time).days > self.max_age_days:
                    try:
                        self.log_debug(f"Deleted old log file: {filename}")
                        os.remove(filepath)
                    except Exception as e:
                        self.log_error(f"Could not delete old log file {filename}: {e}")

    def close(self):
        """Closes all log file handlers."""
        self.log_debug("Closing all DataLogger handlers.")
        # Close NMEA logger handlers
        if self.nmea_logger:
            for handler in list(self.nmea_logger.handlers):
                self.nmea_logger.removeHandler(handler)
                handler.close()
            self.nmea_logger = None # Reset to None after closing
            self.log_debug("NMEA logger handlers closed.")

        # Close JSON logger handlers
        if self.json_logger:
            for handler in list(self.json_logger.handlers):
                self.json_logger.removeHandler(handler)
                handler.close()
            self.json_logger = None # Reset to None after closing
            self.log_debug("JSON logger handlers closed.")

        # Close CSV file
        if self.csv_file and not self.csv_file.closed:
            self.csv_file.close()
            self.csv_file = None
            self.csv_writer = None
            self.log_debug("CSV file closed.")

        # Close console logger handlers (both stream and file)
        for handler in list(self.console_logger.handlers):
            self.console_logger.removeHandler(handler)
            handler.close()
        self.log_debug("Console logger handlers closed.")


    # Methods for logging to console (and console file if enabled)
    def log_info(self, message):
        self.console_logger.info(message)
        self.queue.put(message) # Also push to status queue for UI

    def log_debug(self, message):
        self.console_logger.debug(message)

    def log_warning(self, message):
        self.console_logger.warning(message)
        self.queue.put(f"WARNING: {message}") # Also push to status queue for UI

    def log_error(self, message, exc_info=False):
        self.console_logger.error(message, exc_info=exc_info)
        self.queue.put(f"ERROR: {message}") # Also push to status queue for UI

    def log_critical(self, message, exc_info=False):
        self.console_logger.critical(message, exc_info=exc_info)
        self.queue.put(f"CRITICAL: {message}") # Also push to status queue for UI
