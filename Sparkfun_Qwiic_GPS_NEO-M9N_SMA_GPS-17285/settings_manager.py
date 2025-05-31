# settings_manager.py

import os
import json
import ttkbootstrap as ttk # For theme application
from config import (
    DEFAULT_PORT, DEFAULT_BAUDRATE, SETTINGS_FILE, LOG_DIR, TRIP_LOG_DIR,
    LOG_FILE_MAX_BYTES, LOG_FILE_BACKUP_COUNT, MAX_LOG_AGE_DAYS
)

class SettingsManager:
    """Manages application settings loading and saving."""
    def __init__(self, filename=SETTINGS_FILE, logger=None):
        self.filename = filename
        self.logger = logger # Store the logger instance
        self.settings = self._load_default_settings()
        self.load_settings()

    def _load_default_settings(self):
        """Returns default settings."""
        return {
            "port": DEFAULT_PORT,
            "baudrate": DEFAULT_BAUDRATE,
            "theme": "darkly",
            "log_nmea": False,
            "log_json": False,
            "log_csv": False,
            "display_nmea_console": False, # New setting for NMEA console display
            "log_directory": LOG_DIR, # Default log directory
            "trip_log_directory": TRIP_LOG_DIR, # New setting for trip log directory
            "log_max_bytes_mb": LOG_FILE_MAX_BYTES / (1024 * 1024), # Default max log file size in MB
            "log_backup_count": LOG_FILE_BACKUP_COUNT, # Default number of log backups
            "max_log_age_days": MAX_LOG_AGE_DAYS, # Default max log age in days
            "trip_history": [], # New setting for storing trip history
            "console_output_enabled": True, # New setting for console output control
            "console_output_to_file_enabled": True, # New setting for console output to file
            "geofences": [], # Ensure geofences are initialized
            "speed_noise_threshold_mps": 0.05, # NEW: Configurable speed noise threshold
            "unit_preference": "metric", # NEW: "metric" or "imperial"
            "offline_mode_active": False, # NEW: Offline mode toggle
            "offline_log_filepath": "" # NEW: Path to offline log file
        }

    def _log_message(self, level, message):
        """Helper to log messages using the provided logger or fallback to print."""
        if self.logger:
            if level == "debug":
                self.logger.log_debug(message)
            elif level == "info":
                self.logger.log_info(message)
            elif level == "warning":
                self.logger.log_warning(message)
            elif level == "error":
                self.logger.log_error(message)
        else:
            print(f"{level.upper()}: {message}") # Fallback if logger isn't ready

    def load_settings(self):
        """Loads settings from file."""
        self._log_message("debug", f"Attempting to load settings from: {self.filename}")
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r') as f:
                    loaded_settings = json.load(f)
                    # Update settings with loaded values, but keep defaults for new keys
                    for key, default_value in self._load_default_settings().items():
                        if key not in loaded_settings:
                            loaded_settings[key] = default_value
                    self.settings.update(loaded_settings)
                self._log_message("debug", "Successfully loaded settings.")
                # Apply theme immediately after loading
                if 'theme' in self.settings:
                    try:
                        ttk.Style(theme=self.settings['theme'])
                        self._log_message("debug", f"Successfully loaded theme: {self.settings['theme']}")
                    except Exception as e:
                        self._log_message("warning", f"Could not apply theme '{self.settings['theme']}': {e}. Using default.")
                        self.settings['theme'] = 'darkly' # Fallback to a safe default
                        ttk.Style(theme=self.settings['theme'])
            except json.JSONDecodeError as e:
                self._log_message("error", f"Could not decode settings file: {e}. Using default settings.")
            except Exception as e:
                self._log_message("error", f"An unexpected error occurred loading settings: {e}. Using default settings.")
        else:
            self._log_message("debug", "Settings file not found. Using default settings.")
        self.save_settings() # Save defaults if file didn't exist or was corrupted

    def get(self, key):
        """Gets a setting value."""
        return self.settings.get(key)

    def set(self, key, value):
        """Sets a setting value."""
        self.settings[key] = value

    def save_settings(self):
        """Saves current settings to file."""
        self._log_message("debug", f"Attempting to save settings to: {self.filename}")
        try:
            with open(self.filename, 'w') as f:
                json.dump(self.settings, f, indent=4)
            self._log_message("debug", "Successfully saved settings.")
        except IOError as e:
            self._log_message("error", f"Could not write settings file: {e}")
        except Exception as e:
            self._log_message("error", f"An unexpected error occurred saving settings: {e}")
