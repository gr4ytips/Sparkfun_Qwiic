import logging
import logging.handlers
import os
import shutil
import datetime
import queue # For communication with the main thread (status messages)

class DataLogger:
    def __init__(self, log_path, archive_path, archive_enabled, initial_log_settings, status_queue):
        self._log_path_internal = log_path
        self._archive_path_internal = archive_path
        self._archive_enabled_internal = archive_enabled
        self._log_settings_internal = initial_log_settings # {sensor_name: bool}
        self.status_queue = status_queue # Queue to send status messages back to GUI

        self.logger = self._setup_logger()
        self._active_log_handlers = {} # {sensor_name: handler_instance}
        self.last_archive_time = datetime.datetime.now() # Track last archive time
        self.archive_interval_hours = 24 # Default archive interval (24 hours)

        # Ensure log and archive directories exist on initialization
        os.makedirs(self._log_path_internal, exist_ok=True)
        os.makedirs(self._archive_path_internal, exist_ok=True)


    def _setup_logger(self):
        """Initializes the main logger and clears any existing handlers."""
        logger = logging.getLogger("sensor_logger")
        logger.setLevel(logging.INFO)
        # Clear existing handlers to prevent duplicates if called multiple times
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
            handler.close() # Important to close file handlers
        self._active_log_handlers = {} # Reset active handlers tracker
        return logger

    def _get_sensor_logger(self, sensor_name):
        """
        Gets or creates a RotatingFileHandler for a specific sensor.
        Manages handlers to avoid duplicates and ensures correct file paths.
        """
        current_log_path = self._log_path_internal
        log_file = os.path.join(current_log_path, f"{sensor_name}.log")

        # Check if a handler for this sensor already exists and is for the correct file
        if sensor_name in self._active_log_handlers:
            existing_handler = self._active_log_handlers[sensor_name]
            if os.path.abspath(existing_handler.baseFilename) == os.path.abspath(log_file):
                return self.logger # Handler is already set up and correct
            else:
                # Path changed, remove old handler
                self.logger.removeHandler(existing_handler)
                existing_handler.close()
                del self._active_log_handlers[sensor_name]

        # Create new handler if it doesn't exist or path changed
        handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=1024 * 1024, backupCount=5
        ) # 1MB max, 5 backups
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self._active_log_handlers[sensor_name] = handler # Store the handler
        return self.logger

    def _check_disk_space(self, required_mb=10):
        """Checks if there's enough free disk space for logging."""
        try:
            current_log_path = self._log_path_internal
            os.makedirs(current_log_path, exist_ok=True) # Ensure directory exists
            total, used, free = shutil.disk_usage(current_log_path)
            free_mb = free / (1024 * 1024)
            if free_mb < required_mb:
                self.logger.warning(f"Low disk space: {free_mb:.2f} MB free in {current_log_path}. Logging might be affected.")
                self.status_queue.put({'type': 'status_message', 'message': f"Low disk space: {free_mb:.2f} MB free in log path.", 'color': 'orange'})
                return False
            return True
        except Exception as e:
            self.logger.error(f"Error checking disk space at {self._log_path_internal}: {e}")
            self.status_queue.put({'type': 'status_message', 'message': f"Disk space check error: {e}", 'color': 'red'})
            return False

    def log_sensor_data(self, sensor_data):
        """Logs the provided sensor data based on current settings."""
        if not self._check_disk_space():
            return # Don't log if disk space is low

        for sensor_name, data in sensor_data.items():
            if self._log_settings_internal.get(sensor_name, False): # Check if logging is enabled for this sensor
                sensor_logger = self._get_sensor_logger(sensor_name)
                sensor_logger.info(f"Sensor: {sensor_name}, Data: {data}")

    def archive_logs(self):
        """Archives all current log files into a timestamped zip archive."""
        if not self._archive_enabled_internal:
            self.logger.info("Log archiving is disabled. Skipping archive.")
            self.status_queue.put({'type': 'status_message', 'message': "Log archiving disabled.", 'color': 'gray'})
            return

        current_log_path = self._log_path_internal
        archive_dest_path = self._archive_path_internal
        
        self.logger.info(f"Attempting to archive logs from {current_log_path} to {archive_dest_path}")
        self.status_queue.put({'type': 'status_message', 'message': "Initiating log archive...", 'color': 'blue'})

        if not os.path.exists(current_log_path):
            self.status_queue.put({'type': 'status_message', 'message': f"Log directory for archiving not found: {current_log_path}", 'color': 'orange'})
            self.logger.warning(f"Log directory for archiving not found: {current_log_path}")
            return
        if not os.path.exists(archive_dest_path):
            try:
                os.makedirs(archive_dest_path, exist_ok=True)
                self.status_queue.put({'type': 'status_message', 'message': f"Archive directory created: {archive_dest_path}", 'color': 'blue'})
                self.logger.info(f"Archive directory created: {archive_dest_path}")
            except Exception as e:
                self.status_queue.put({'type': 'status_message', 'message': f"Failed to create archive directory: {e}", 'color': 'red'})
                self.logger.error(f"Failed to create archive directory {archive_dest_path}: {e}")
                return

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_name = f"sensor_logs_archive_{timestamp}"
        archive_full_path = os.path.join(archive_dest_path, archive_name)

        try:
            # Close all existing log handlers before archiving to ensure files are not locked
            self.logger.info("Closing all log handlers before archiving.")
            for handler in list(self.logger.handlers):
                if isinstance(handler, logging.handlers.RotatingFileHandler):
                    handler.close()
                    self.logger.removeHandler(handler)
            self._active_log_handlers = {} # Clear tracker

            # Create the zip archive
            self.logger.info(f"Creating zip archive: {archive_full_path}.zip")
            shutil.make_archive(archive_full_path, 'zip', current_log_path)
            self.status_queue.put({'type': 'status_message', 'message': f"Logs archived to {archive_full_path}.zip", 'color': 'green'})
            self.logger.info(f"Logs archived to {archive_full_path}.zip")

            self.logger.info("Deleting old log files after successful archiving.")
            for filename in os.listdir(current_log_path):
                file_path = os.path.join(current_log_path, filename)
                if os.path.isfile(file_path) and (filename.endswith('.log') or (filename.startswith("bme280.log.") or filename.startswith("sgp40.log.") or filename.startswith("shtc3.log.") or filename.startswith("proximity.log."))):
                    try:
                        os.remove(file_path)
                        self.logger.info(f"Deleted old log file: {filename}")
                    except Exception as rm_e:
                        self.logger.warning(f"Failed to delete {filename}: {rm_e}")
            self.status_queue.put({'type': 'status_message', 'message': "Old log files cleared.", 'color': 'green'})

            self.logger.info("Re-initializing loggers...")
            self._setup_logger()
            self.last_archive_time = datetime.datetime.now() # Reset archive timer
            self.logger.info("Loggers re-initialized after archiving.")

        except Exception as e:
            self.status_queue.put({'type': 'status_message', 'message': f"Error archiving logs: {e}", 'color': 'red'})
            self.logger.error(f"Error archiving logs: {e}", exc_info=True)
            self.logger.info("Attempting to re-initialize loggers after archiving failure.")
            self._setup_logger()

    def update_config(self, new_log_path, new_archive_path, new_archive_enabled, new_log_settings):
        """Updates the logging configuration."""
        self._log_path_internal = new_log_path
        self._archive_path_internal = new_archive_path
        self._archive_enabled_internal = new_archive_enabled
        self._log_settings_internal = new_log_settings
        
        # Re-setup logger to apply new paths if necessary
        self._setup_logger()

        self.status_queue.put({'type': 'status_message', 'message': f"Log path updated to: {new_log_path}", 'color': 'green'})
        self.status_queue.put({'type': 'status_message', 'message': f"Archive path updated to: {new_archive_path}", 'color': 'green'})
        self.status_queue.put({'type': 'status_message', 'message': f"Archiving {'enabled' if new_archive_enabled else 'disabled'}.", 'color': 'green'})
        self.status_queue.put({'type': 'status_message', 'message': "Logging configuration updated.", 'color': 'info'})
        self.logger.info(f"Logging configuration updated by GUI to path: {new_log_path}, archiving to: {new_archive_path}, enabled: {new_archive_enabled}")

    def check_and_archive_auto(self):
        """Checks if automatic archiving is due and triggers it."""
        if self._archive_enabled_internal and (datetime.datetime.now() - self.last_archive_time).total_seconds() > self.archive_interval_hours * 3600:
            self.logger.info(f"Initiating automatic log archive after {self.archive_interval_hours} hours.")
            self.archive_logs()
