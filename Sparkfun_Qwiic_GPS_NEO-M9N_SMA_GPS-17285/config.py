# config.py

import os
import logging

# Define the base directory for logs and settings relative to the script's location
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(SCRIPT_DIR, "logs")
TRIP_LOG_DIR = os.path.join(LOG_DIR, "trips") # New directory for trip-specific logs
SETTINGS_FILE = os.path.join(SCRIPT_DIR, "settings.json")
MAP_HTML_FILE = os.path.join(SCRIPT_DIR, "map.html") # HTML file for Folium map

# Define log levels for the application
LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL
}

# Logging configuration
LOG_FILE_MAX_BYTES = 10 * 1024 * 1024 # 10 MB
LOG_FILE_BACKUP_COUNT = 5
LOG_FILE_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
MAX_LOG_AGE_DAYS = 30 # Delete logs older than 30 days

# Disk space monitoring
MIN_DISK_SPACE_MB = 500 # Minimum free disk space before warning (in MB)

# GPS Data Handling
DATA_FETCH_INTERVAL_MS = 200 # Milliseconds between fetching new GPS data

# NMEA Console
MAX_NMEA_LINES_DISPLAY = 1000 # Maximum lines to display in the NMEA console

# Trend Data Plotting
MAX_TREND_DATA_POINTS = 500 # Maximum data points to keep for trend plots

# Default settings for the application
DEFAULT_SETTINGS = {
    "serial_port": "", # This was changed to "port" in settings_manager
    "baud_rate": 115200, # This was changed to "baudrate" in settings_manager
    "log_level": "INFO",
    "max_log_size_mb": 10, # Corresponds to LOG_FILE_MAX_BYTES
    "max_log_files": 5, # Corresponds to LOG_FILE_BACKUP_COUNT
    "auto_scroll_console": True, # Not directly used yet, but good to have
    "auto_connect": False, # Not directly used yet
    "map_zoom": 15,
    "map_tile_provider": "OpenStreetMap", # Not directly used yet
    "log_nmea": False, # Default for NMEA logging
    "log_json": False, # Default for JSONL logging
    "log_csv": False,  # Default for CSV logging
    "display_nmea_console": False, # Default for NMEA console display
    "console_output_enabled": True, # New: Enable/disable console (stdout) output
    "console_output_to_file_enabled": True, # New: Enable/disable console output to file
    "log_directory": LOG_DIR, # Default log directory
    "trip_log_directory": TRIP_LOG_DIR, # Default trip log directory
    "log_max_bytes_mb": LOG_FILE_MAX_BYTES / (1024 * 1024), # Default max log file size in MB
    "log_backup_count": LOG_FILE_BACKUP_COUNT, # Default log backup count
    "max_log_age_days": MAX_LOG_AGE_DAYS, # Default max log age in days
    "unit_preference": "metric", # "metric" or "imperial"
    "offline_mode_active": False, # New: Default to live mode
    "offline_log_filepath": "", # New: Path to the log file for offline playback
    "geofences": [], # List to store geofence configurations
    "trip_history": [], # List to store summaries of completed trips
    "speed_noise_threshold_mps": 0.5, # New: Speed below this (m/s) is considered 0 for analysis
    "hard_braking_threshold_mps2": -3.0, # New: Acceleration threshold for hard braking (m/s^2)
    "sharp_cornering_threshold_deg_per_sec": 20.0 # New: Angular velocity threshold for sharp cornering (deg/s)
}

# Default serial port and baudrate (used if not found in settings)
DEFAULT_PORT = "COM1" if os.name == 'nt' else "/dev/ttyACM0"
DEFAULT_BAUDRATE = 115200

# Driving Analysis Thresholds (moved from gps_dashboard_app.py)
HARD_BRAKING_THRESHOLD_MPS2 = -3.0  # m/s^2 (e.g., -3 m/s^2 means deceleration of 3 m/s^2)
SHARP_CORNERING_THRESHOLD_DEG_PER_SEC = 20.0 # degrees per second
