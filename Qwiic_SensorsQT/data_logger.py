import logging
import logging.handlers
import os
import shutil
import datetime
from PyQt5.QtCore import QObject, pyqtSignal
import csv
import sys # Import sys for console output

class DataLogger(QObject):
    """
    Manages logging sensor data to CSV files, debug messages to a separate log,
    and archiving old sensor data logs.
    Communicates status updates back to the GUI via a PyQt signal.
    """
    status_message_signal = pyqtSignal(str, str)  # message, color ('info', 'warning', 'danger')

    def __init__(self, log_path, archive_path, debug_log_path, archive_enabled, initial_log_settings, debug_to_console_enabled, debug_log_level):
        super().__init__()
        self._log_path_internal = log_path
        self._archive_path_internal = archive_path
        self._debug_log_path_internal = debug_log_path
        self._archive_enabled_internal = archive_enabled
        self._log_settings_internal = initial_log_settings
        self._debug_to_console_enabled = debug_to_console_enabled # New: control console output
        self._debug_log_level = debug_log_level # New: control console/file log level

        # Ensure directories exist
        os.makedirs(self._log_path_internal, exist_ok=True)
        os.makedirs(self._archive_path_internal, exist_ok=True)
        os.makedirs(os.path.dirname(self._debug_log_path_internal), exist_ok=True) # Ensure debug log directory exists

        # Setup main logger (for sensor data) and debug logger
        self.sensor_logger = self._setup_sensor_logger()
        # Initialize debug_logger here. _setup_debug_logger will return the logger instance.
        self.debug_logger = self._setup_debug_logger()
        self.debug_logger.info("DataLogger initialized.")

        self._active_log_file_handles = {} # {sensor_name: {'file_obj': file_object, 'writer': csv.writer}}
        self.last_archive_time = datetime.datetime.now() # Track last archive time
        self.archive_interval_hours = 24 # Default archive interval

        # Open log files for currently enabled sensors
        self._open_initial_log_files()

    def _setup_sensor_logger(self):
        """Initializes the main logger for sensor data (not currently used for direct logging here, but kept for structure)."""
        logger = logging.getLogger("sensor_data_logger")
        logger.setLevel(logging.INFO)
        # Clear existing handlers to prevent duplicates
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
        # File logging for sensor data is now handled directly by CSV writers in log_sensor_data
        return logger

    def _setup_debug_logger(self):
        """
        Sets up a dedicated logger for debug/info messages, with both file and optional console output.
        This is called internally and by update_logging_configuration.
        """
        debug_logger = logging.getLogger("debug_logger")
        # Ensure the logger does not propagate to the root logger which might have its own console handlers
        debug_logger.propagate = False
        
        # Determine numeric log level
        numeric_level = getattr(logging, self._debug_log_level.upper(), logging.INFO)
        debug_logger.setLevel(numeric_level)

        # Clear existing handlers to prevent duplicates when settings are updated
        for handler in list(debug_logger.handlers):
            debug_logger.removeHandler(handler)
            # Do not use self.debug_logger here as it might not be initialized yet
            # Use print for debugging setup issues or the newly created logger directly
            print(f"DEBUG: Removed existing handler: {handler}")


        # File handler for debug logs
        try:
            file_handler = logging.handlers.RotatingFileHandler(
                self._debug_log_path_internal,
                maxBytes=10*1024*1024, # 10 MB
                backupCount=5
            )
            file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s'))
            debug_logger.addHandler(file_handler)
            print(f"DEBUG: Added file handler to debug_logger: {self._debug_log_path_internal}")


        except Exception as e:
            self.status_message_signal.emit(f"Error setting up debug log file: {e}", 'danger')
            print(f"ERROR: Error setting up debug log file: {e}") # Fallback print for errors during setup

        # Console handler (if enabled)
        if self._debug_to_console_enabled:
            try:
                console_handler = logging.StreamHandler(sys.stdout)
                console_handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
                debug_logger.addHandler(console_handler)
                print("DEBUG: Added console handler to debug_logger.")
            except Exception as e:
                self.status_message_signal.emit(f"Error setting up debug console output: {e}", 'danger')
                print(f"ERROR: Error setting up debug console output: {e}") # Fallback print
        else:
            print("DEBUG: Console output for debug_logger is disabled.")

        return debug_logger

    def _open_log_file(self, sensor_name):
        """Opens or reopens a CSV log file for a given sensor."""
        log_dir = os.path.join(self._log_path_internal, sensor_name)
        os.makedirs(log_dir, exist_ok=True)
        today_str = datetime.datetime.now().strftime("%Y-%m-%d")
        file_path = os.path.join(log_dir, f"{sensor_name}_{today_str}.csv")

        # Close existing handle if it's for the same sensor (e.g., if date changed)
        if sensor_name in self._active_log_file_handles:
            existing_file_path = self._active_log_file_handles[sensor_name]['file_obj'].name
            if existing_file_path != file_path:
                self._active_log_file_handles[sensor_name]['file_obj'].close()
                self.debug_logger.info(f"Closed old CSV file for {sensor_name} due to date change.")
            else:
                # File is already open and correct, no need to reopen
                self.debug_logger.debug(f"CSV file for {sensor_name} is already open and current.")
                return


        file_exists = os.path.exists(file_path)
        mode = 'a' if file_exists else 'w'
        try:
            f = open(file_path, mode, newline='')
            writer = csv.writer(f)

            if not file_exists:
                # Write header if new file
                if sensor_name == 'bme280':
                    writer.writerow(['timestamp', 'temperature_c', 'humidity', 'pressure_pa', 'altitude_m', 'temperature_f', 'dewpoint_c', 'dewpoint_f'])
                elif sensor_name == 'sgp40':
                    writer.writerow(['timestamp', 'voc_index'])
                elif sensor_name == 'shtc3':
                    writer.writerow(['timestamp', 'temperature_c', 'humidity'])
                elif sensor_name == 'proximity':
                    writer.writerow(['timestamp', 'proximity', 'ambient_light', 'white_light'])
                self.debug_logger.info(f"Created new CSV for {sensor_name} at {file_path}")
            else:
                self.debug_logger.info(f"Appending to existing CSV for {sensor_name} at {file_path}")

            self._active_log_file_handles[sensor_name] = {'file_obj': f, 'writer': writer}
        except Exception as e:
            self.status_message_signal.emit(f"Error opening/creating log file for {sensor_name}: {e}", 'danger')
            self.debug_logger.error(f"Error opening/creating log file for {sensor_name}: {e}")
            if sensor_name in self._active_log_file_handles:
                del self._active_log_file_handles[sensor_name] # Remove invalid entry

    def _open_initial_log_files(self):
        """Opens log files for sensors marked for logging in initial settings."""
        self.debug_logger.info("Opening initial log files based on settings.")
        for sensor_name, enabled in self._log_settings_internal.items():
            if enabled:
                self._open_log_file(sensor_name)

    def log_sensor_data(self, sensor_readings):
        """
        Logs sensor data to appropriate CSV files based on enabled settings.
        Handles missing sensor data gracefully.
        """
        timestamp_str = datetime.datetime.now().isoformat()
        
        for sensor_name, enabled in self._log_settings_internal.items():
            if enabled:
                file_info = self._active_log_file_handles.get(sensor_name)
                if not file_info:
                    # Try to open the file if it's not already open (e.g., if a new sensor was enabled)
                    self._open_log_file(sensor_name)
                    file_info = self._active_log_file_handles.get(sensor_name) # Try again

                if file_info:
                    writer = file_info['writer']
                    data = sensor_readings.get(sensor_name, {})
                    
                    row = [timestamp_str]
                    if sensor_name == 'bme280':
                        row.extend([
                            data.get('temp_c', 'N/A'),
                            data.get('humidity', 'N/A'),
                            data.get('pressure', 'N/A'), # Raw pressure in Pa
                            data.get('altitude', 'N/A'),
                            data.get('temp_f', 'N/A'),
                            data.get('dewpoint_c', 'N/A'),
                            data.get('dewpoint_f', 'N/A')
                        ])
                    elif sensor_name == 'sgp40':
                        row.append(data.get('voc_index', 'N/A'))
                    elif sensor_name == 'shtc3':
                        row.extend([
                            data.get('temperature', 'N/A'),
                            data.get('humidity', 'N/A')
                        ])
                    elif sensor_name == 'proximity':
                        row.extend([
                            data.get('proximity', 'N/A'),
                            data.get('ambient_light', 'N/A'),
                            data.get('white_light', 'N/A')
                        ])
                    
                    try:
                        writer.writerow(row)
                        file_info['file_obj'].flush() # Ensure data is written to disk immediately
                        # self.debug_logger.debug(f"Logged data for {sensor_name}: {row}") # Too verbose for general use
                    except Exception as e:
                        self.status_message_signal.emit(f"Error writing data to CSV for {sensor_name}: {e}", 'danger')
                        self.debug_logger.error(f"Error writing data to CSV for {sensor_name}: {e}")
                else:
                    self.debug_logger.warning(f"Could not log data for {sensor_name}: File handle not available.")

        self.check_and_archive_auto() # Check for archiving after logging data

    def archive_logs(self):
        """Archives all current log files by moving them to the archive directory."""
        self.debug_logger.info("Initiating log archiving.")
        self.status_message_signal.emit("Archiving sensor logs...", 'info')

        archive_timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        destination_dir = os.path.join(self._archive_path_internal, f"archive_{archive_timestamp}")
        os.makedirs(destination_dir, exist_ok=True)

        for sensor_name in list(self._active_log_file_handles.keys()):
            file_info = self._active_log_file_handles[sensor_name]
            try:
                # Close the file before moving it
                file_info['file_obj'].close()
                original_path = file_info['file_obj'].name
                
                # Construct new file path in the archive
                file_name = os.path.basename(original_path)
                archive_file_path = os.path.join(destination_dir, file_name)

                shutil.move(original_path, archive_file_path)
                self.debug_logger.info(f"Archived {original_path} to {archive_file_path}")
                # Remove from active handles
                del self._active_log_file_handles[sensor_name]
            except Exception as e:
                self.status_message_signal.emit(f"Error archiving log file for {sensor_name}: {e}", 'danger')
                self.debug_logger.error(f"Error archiving log file for {sensor_name}: {e}")
            finally:
                del self._active_log_file_handles[sensor_name] # Ensure it's removed even if close fails
        
        self.last_archive_time = datetime.datetime.now()
        self.status_message_signal.emit(f"Logs archived to {destination_dir}", 'success')
        self.debug_logger.info(f"Log archiving completed to {destination_dir}.")
        
        # Re-open log files after archiving to continue logging
        self._open_initial_log_files()

    def update_logging_configuration(self, new_log_path, new_archive_path, new_debug_log_path, new_archive_enabled, new_log_settings, new_debug_to_console_enabled, new_debug_log_level):
        """Updates the logging configuration and re-applies it."""
        self.debug_logger.info("Updating logging configuration...")
        
        # Close all currently open log files before changing paths
        self.close_all_log_files()

        self._log_path_internal = new_log_path
        self._archive_path_internal = new_archive_path
        self._debug_log_path_internal = new_debug_log_path
        self._archive_enabled_internal = new_archive_enabled
        self._log_settings_internal = new_log_settings
        self._debug_to_console_enabled = new_debug_to_console_enabled
        self._debug_log_level = new_debug_log_level
        
        # Re-setup debug logger to apply new paths and console settings
        # The existing debug_logger needs to be updated with the new level and handlers.
        # Calling _setup_debug_logger again will clear old handlers and add new ones based on current settings.
        self.debug_logger = self._setup_debug_logger()
        self.debug_logger.info("Debug logger re-configured with new settings.")

        # Ensure directories exist for the new paths
        os.makedirs(self._log_path_internal, exist_ok=True)
        os.makedirs(self._archive_path_internal, exist_ok=True)
        os.makedirs(os.path.dirname(self._debug_log_path_internal), exist_ok=True)

        # Re-open log files for currently enabled sensors based on new settings
        self._open_initial_log_files()

        self.status_message_signal.emit(f"Log path updated to: {new_log_path}", 'info')
        self.status_message_signal.emit(f"Archive path updated to: {new_archive_path}", 'info')
        self.status_message_signal.emit(f"Debug log path updated to: {new_debug_log_path}", 'info')
        self.status_message_signal.emit(f"Archiving {'enabled' if new_archive_enabled else 'disabled'}.", 'info')
        self.status_message_signal.emit(f"Debug console output: {'Enabled' if new_debug_to_console_enabled else 'Disabled'} at {new_debug_log_level} level.", 'info')
        self.status_message_signal.emit("Logging configuration updated.", 'info')
        self.debug_logger.info(f"Logging configuration updated by GUI to path: {new_log_path}, archiving to: {new_archive_path}, debug log: {new_debug_log_path}, enabled: {new_archive_enabled}, console_debug: {new_debug_to_console_enabled}, debug_level: {new_debug_log_level}")

    def check_and_archive_auto(self):
        """Checks if automatic archiving is due and triggers it."""
        if self._archive_enabled_internal and (datetime.datetime.now() - self.last_archive_time).total_seconds() > self.archive_interval_hours * 3600:
            self.debug_logger.info(f"Initiating automatic log archive after {self.archive_interval_hours} hours.")
            self.archive_logs()

    def close_all_log_files(self):
        """Explicitly closes all open CSV log file handles."""
        self.debug_logger.info("Closing all active CSV file handles for shutdown.")
        for sensor_name, file_info in list(self._active_log_file_handles.items()):
            try:
                file_info['file_obj'].close()
                self.debug_logger.debug(f"Closed CSV file for {sensor_name}")
            except Exception as e:
                self.debug_logger.error(f"Error closing CSV file for {sensor_name}: {e}")
            finally:
                del self._active_log_file_handles[sensor_name] # Ensure it's removed even if close fails
