# gps_dashboard_app.py

import tkinter as tk
from tkinter import messagebox, simpledialog, filedialog
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import threading
import time
import os
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from tkhtmlview import HTMLLabel # For embedding HTML (Folium map)
import sys # Import sys for clean exit
import math # Import math for isnan check
from datetime import datetime, timedelta # Import datetime and timedelta
import json # For settings and JSON log files
import csv # For CSV log files
import shutil # For disk space checks
import subprocess # For opening log directory
import numpy as np # Import numpy for plotting data handling
import webbrowser # For opening map in browser
import logging # Import the logging module
import queue # Import the queue module

# Import modularized components
from config import (
    LOG_DIR, TRIP_LOG_DIR, LOG_FILE_MAX_BYTES, LOG_FILE_BACKUP_COUNT,
    MAX_LOG_AGE_DAYS, MIN_DISK_SPACE_MB, MAX_NMEA_LINES_DISPLAY,
    MAX_TREND_DATA_POINTS, MAP_HTML_FILE, HARD_BRAKING_THRESHOLD_MPS2,
    SHARP_CORNERING_THRESHOLD_DEG_PER_SEC, DATA_FETCH_INTERVAL_MS,
    DEFAULT_PORT, DEFAULT_BAUDRATE
)
from utils import format_coord, format_value, haversine_distance
from data_logger import DataLogger
from settings_manager import SettingsManager
from gps_handler import GpsDataHandler, UBLOX_GPS_AVAILABLE # Import UBLOX_GPS_AVAILABLE
from map_generator import LogMapGenerator # Import LogMapGenerator
from playback_manager import OfflinePlaybackManager

class GpsDashboardApp(tk.Tk):
    """Main application window for the GPS Dashboard."""

    # Methods moved to before __init__ to resolve AttributeError
    def _load_geofences_to_tree(self):
        """Loads geofences from the list into the Treeview."""
        self.logger.log_debug("Loading geofences to treeview.")
        for i in self.geofence_tree.get_children():
            self.geofence_tree.delete(i)
        for gf in self.geofences:
            self.geofence_tree.insert("", END, text=gf['name'],
                                      values=(gf['name'], f"{gf['latitude']:.4f}", f"{gf['longitude']:.4f}", f"{gf['radius']:.2f}"))
        self.logger.log_debug(f"Loaded {len(self.geofences)} geofences.")

    def _save_geofences(self):
        """Saves geofences to settings."""
        self.settings_manager.set("geofences", self.geofences)
        self.settings_manager.save_settings()
        self.logger.log_debug("Geofences saved to settings.")

    def _load_geofences_from_settings(self):
        """Loads geofences from settings at startup."""
        self.logger.log_debug("Loading geofences from settings.")
        loaded_geofences = self.settings_manager.get("geofences")
        if loaded_geofences:
            self.geofences = loaded_geofences
            self._load_geofences_to_tree()
            self.logger.log_debug(f"Successfully loaded {len(self.geofences)} geofences from settings.")
        else:
            self.logger.log_debug("No geofences found in settings.")

    def _load_trip_history_to_tree(self):
        """Updates the Trip History tab with saved trip summaries."""
        self.logger.log_debug(f"Trip history update: Populating treeview with {len(self.trip_history)} data points. (This is a debug message)")
        # Clear existing items in the Treeview
        for i in self.trip_history_tree.get_children():
            self.trip_history_tree.delete(i)

        unit_preference = self.settings_manager.get("unit_preference") # Get unit preference

        if not self.trip_history:
            self.trip_history_tree.insert("", END, values=("", "No completed trips yet.", "", "", "", "", "", "", ""))
            self.logger.log_debug("No trip history to display.")
            return

        for trip in self.trip_history:
            # Distance and max speed are already stored in preferred units, just display
            distance_val = trip.get('distance', float('nan'))
            distance_str = f"{distance_val:.2f}" if not math.isnan(distance_val) else "N/A"
            max_speed_val = trip.get('max_speed', float('nan'))
            max_speed_str = f"{max_speed_val:.2f}" if not math.isnan(max_speed_val) else "N/A"
            
            self.trip_history_tree.insert("", END, values=(
                trip.get('start_time', 'N/A'),
                trip.get('end_time', 'N/A'),
                trip.get('duration', 'N/A'),
                distance_str,
                trip.get('distance_unit', 'N/A'),
                max_speed_str,
                trip.get('max_speed_unit', 'N/A'),
                trip.get('csv_path', ''), # Hidden path
                trip.get('jsonl_path', '') # Hidden path
            ))
        self.logger.log_debug("Trip history treeview populated.")

    def __init__(self):
        super().__init__()
        self.withdraw() # Hide the root window initially
        self.logger = None # Initialize logger to None for safety
        self.logger_initialized = False # Flag to track logger initialization

        try:
            # Initialize a temporary DataLogger for early messages
            # This logger will output to console and a temporary file until full settings are loaded.
            self.logger = DataLogger(
                log_dir=LOG_DIR, # Use default log dir for temp logger
                max_bytes=LOG_FILE_MAX_BYTES,
                backup_count=LOG_FILE_BACKUP_COUNT,
                max_age_days=MAX_LOG_AGE_DAYS,
                settings_manager=None # No settings_manager yet for temp logger
            )
            self.logger_initialized = True
            self.logger.log_debug("Temporary DataLogger initialized for early startup messages.")
        except Exception as e:
            print(f"CRITICAL ERROR: Failed to initialize temporary DataLogger. Application cannot proceed: {e}", file=sys.stderr)
            sys.exit(1) # Exit if logger cannot be initialized at all

        self.logger.log_debug("GPS Dashboard App: __init__ started.")

        try:
            # Initialize SettingsManager, passing the temporary logger
            self.settings_manager = SettingsManager(logger=self.logger)
            self.logger.log_debug("SettingsManager initialized.")

            # Now, re-initialize the main DataLogger with the actual settings_manager
            # This will properly set up console and file handlers based on loaded settings.
            # This also ensures that new timestamped log files are created for the main application session.
            if self.logger_initialized: # Only close if it was successfully initialized
                self.logger.close() # Close temporary logger handlers before re-initializing
                self.logger.log_debug("Temporary DataLogger closed.")

            self.logger = DataLogger(
                log_dir=self.settings_manager.get("log_directory"),
                max_bytes=int(self.settings_manager.get("log_max_bytes_mb") * 1024 * 1024),
                backup_count=self.settings_manager.get("log_backup_count"),
                max_age_days=self.settings_manager.get("max_log_age_days"),
                settings_manager=self.settings_manager
            )
            self.logger_initialized = True # Confirm main logger is initialized
            self.logger.log_debug("Main DataLogger re-initialized with settings.")

            # Update the settings manager with the fully configured logger
            self.settings_manager.logger = self.logger
            self.logger.log_debug("SettingsManager logger reference updated.")

            self.title("GPS Dashboard")
            # self.geometry("1000x800") # Removed fixed geometry
            self.protocol("WM_DELETE_WINDOW", self.on_close) # Handle window close event
            self.logger.log_debug("Tkinter root window configured.")

            self.current_gps_data = {}
            self.geofences = []
            self.track_points = [] # Store historical track points for plotting
            self.max_track_points = 500 # Limit number of points for performance
            self.trend_data_history = [] # Stores historical data for trend plots
            self.max_trend_data_points = MAX_TREND_DATA_POINTS
            self.logger.log_debug("Core data structures initialized.")

            # UI Update Throttling
            self.ui_update_throttle_ms = 100  # Update UI at most every 100ms
            self.ui_update_scheduled = False
            self.logger.log_debug("UI update throttling configured.")

            # Variables for storage info display
            self.total_disk_space_var = tk.StringVar(value="N/A")
            self.used_disk_space_var = tk.StringVar(value="N/A")
            self.free_disk_space_var = tk.StringVar(value="N/A")
            self.logger.log_debug("Storage info variables initialized.")

            # --- Trip Logging Variables ---
            self.is_trip_active = False
            self.current_trip_start_time = None # datetime object
            self.current_trip_start_lat_lon = None # (lat, lon) tuple
            self.current_trip_max_speed = 0.0 # m/s (base unit)
            self.current_trip_distance = 0.0 # meters (base unit)
            self.last_lat_lon_for_distance = None # (lat, lon) for distance calculation
            self.trip_csv_file_obj = None # File object for current trip CSV log
            self.trip_csv_writer_obj = None # CSV writer object for current trip
            self.trip_jsonl_file_obj = None # File object for current trip JSONL log
            self.logger.log_debug("Trip logging variables initialized.")

            # Load trip history from settings
            self.trip_history = self.settings_manager.get("trip_history")
            if self.trip_history is None: # Ensure it's a list if not found
                self.trip_history = []
                self.settings_manager.set("trip_history", self.trip_history)
                self.settings_manager.save_settings()
            self.logger.log_debug(f"Trip history loaded with {len(self.trip_history)} entries.")

            # Variables for Trip Metrics Display on Driving Dashboard
            self.trip_duration_var = tk.StringVar(value="Duration: N/A")
            self.trip_distance_var = tk.StringVar(value="Distance: N/A")
            self.trip_max_speed_var = tk.StringVar(value="Max Speed: N/A")
            self.logger.log_debug("Driving dashboard trip metrics variables initialized.")

            # High-Precision Coordinates variables (reused for Driving Dashboard)
            self.hp_lat_var = tk.StringVar(value="N/A")
            self.hp_lon_var = tk.StringVar(value="N/A")
            self.hp_height_var = tk.StringVar(value="N/A")
            self.h_acc_var = tk.StringVar(value="N/A") # Horizontal Accuracy
            self.v_acc_var = tk.StringVar(value="N/A") # Vertical Accuracy
            self.logger.log_debug("High-precision variables initialized.")

            # Port Settings variables (now read-only display)
            self.port_id_var = tk.StringVar(value="N/A")
            self.port_mode_var = tk.StringVar(value="N/A")
            self.port_baudrate_var = tk.StringVar(value="N/A")
            self.in_protocol_var = tk.StringVar(value="N/A")
            self.out_protocol_var = tk.StringVar(value="N/A")
            self.logger.log_debug("Port settings variables initialized.")

            self.protocol_options = { # Still needed for display mapping
                "UBX": 0x01, # UBX only
                "NMEA": 0x02, # NMEA only
                "UBX+NMEA": 0x03, # UBX + NMEA
                "RTCM3": 0x04, # RTCM3 only (for input)
                "UBX+NMEA+RTCM3": 0x07 # Combined (for input)
            }
            self.protocol_map = {v: k for k, v in self.protocol_options.items()} # Reverse map for display
            self.logger.log_debug("Protocol options and map initialized.")

            # Communication Status variables (from MON-COMMS)
            self.comm_errors_var = tk.StringVar(value="N/A")
            self.rx_buf_usage_var = tk.StringVar(value="N/A")
            self.tx_buf_usage_var = tk.StringVar(value="N/A")
            self.logger.log_debug("Communication status variables initialized.")

            # Driving Dashboard variables
            self.dashboard_speed_var = tk.StringVar(value="N/A")
            self.dashboard_altitude_var = tk.StringVar(value="N/A")
            self.dashboard_heading_var = tk.StringVar(value="N/A")
            self.dashboard_num_sv_var = tk.StringVar(value="N/A")
            self.dashboard_fix_type_var = tk.StringVar(value="N/A")
            self.dashboard_hdop_var = tk.StringVar(value="N/A")
            self.dashboard_vdop_var = tk.StringVar(value="N/A")
            self.dashboard_time_var = tk.StringVar(value="N/A") # New: Current Time
            self.dashboard_speed_unit_var = tk.StringVar(value="km/h") # Dynamic speed unit
            self.dashboard_altitude_unit_var = tk.StringVar(value="m MSL") # Dynamic altitude unit
            self.logger.log_debug("Driving dashboard display variables initialized.")


            # Current Position Data variables (Moved here for early initialization)
            self.pos_vars = {}
            pos_labels = ["Latitude:", "Longitude:", "Altitude (MSL):", "Speed:", "Heading (deg):", "Satellites in Use:", "Fix Type:"]
            for text in pos_labels:
                key = text.replace(":", "").replace(" ", "_").replace("(deg)", "deg").lower()
                # Special handling for speed and altitude units
                if "speed" in key:
                    self.pos_vars[key] = tk.StringVar(value="N/A")
                    self.pos_vars[f"{key}_unit"] = tk.StringVar(value="m/s") # Dynamic
                elif "altitude" in key:
                    self.pos_vars[key] = tk.StringVar(value="N/A")
                    self.pos_vars[f"{key}_unit"] = tk.StringVar(value="m") # Dynamic
                else:
                    self.pos_vars[key] = tk.StringVar(value="N/A")
            self.logger.log_debug("Current position variables initialized.")

            # System Information (initialized early)
            self.info_vars = {
                "sw_version": tk.StringVar(value="N/A"),
                "hw_version": tk.StringVar(value="N/A"),
                "gnss_support": tk.StringVar(value="N/A"),
                "rf_antenna_status": tk.StringVar(value="N/A")
            }
            self.logger.log_debug("System information variables initialized.")

            # Communication Status (initialized early)
            self.comm_status_vars = {
                "comm_errors": tk.StringVar(value="N/A"),
                "rx_buffer_usage": tk.StringVar(value="N/A"),
                "tx_buffer_usage": tk.StringVar(value="N/A")
            }
            self.logger.log_debug("Communication status variables initialized.")

            # DOP Data (initialized early)
            self.dop_vars = {
                "pdop": tk.StringVar(value="N/A"),
                "hdop": tk.StringVar(value="N/A"),
                "vdop": tk.StringVar(value="N/A")
            }
            self.logger.log_debug("DOP variables initialized.")

            # Fix Type Mapping
            self.fix_type_map = {
                0: "No Fix",
                1: "Dead Reckoning Only",
                2: "2D Fix",
                3: "3D Fix",
                4: "GPS + Dead Reckoning",
                5: "Time Only Fix"
            }
            # Bootstyle colors for fix type
            self.fix_type_color_map = {
                0: "danger",    # No Fix
                1: "warning",   # Dead Reckoning Only
                2: "warning",   # 2D Fix
                3: "success",   # 3D Fix
                4: "success",   # GPS + Dead Reckoning
                5: "info"       # Time Only Fix
            }
            self.logger.log_debug("Fix type mappings initialized.")

            # --- Offline Playback Variables ---
            self.offline_mode_active_var = tk.BooleanVar(value=self.settings_manager.get("offline_mode_active"))
            self.offline_file_path_var = tk.StringVar(value=self.settings_manager.get("offline_log_filepath"))
            self.playback_speed_var = tk.DoubleVar(value=1.0) # Default 1x speed
            self.playback_status_var = tk.StringVar(value="Stopped")
            self.playback_progress_var = tk.StringVar(value="0%")
            self.logger.log_debug("Offline playback variables initialized.")

            self.live_gps_thread = None
            self.offline_playback_thread = None
            self.stop_live_gps_event = threading.Event()
            self.stop_playback_event = threading.Event()
            self.data_queue = queue.Queue() # Unified queue for both live and offline data
            self.nmea_display_queue = queue.Queue() # For NMEA console display
            self.logger.log_debug("Threading events and queues initialized.")

            # Initialize OfflinePlaybackManager later, after buttons are created in _create_settings_widgets
            self.offline_playback_manager = None 
            self.logger.log_debug("OfflinePlaybackManager placeholder created.")

            # --- Trip Analysis Variables ---
            self.analysis_trip_duration_var = tk.StringVar(value="N/A")
            self.analysis_trip_distance_var = tk.StringVar(value="N/A")
            self.analysis_trip_max_speed_var = tk.StringVar(value="N/A")
            self.analysis_trip_avg_speed_var = tk.StringVar(value="N/A") # New: Average Speed
            self.analysis_hard_braking_events_var = tk.StringVar(value="N/A") # New: Hard Braking Events
            self.analysis_sharp_cornering_events_var = tk.StringVar(value="N/A") # New: Sharp Cornering Events
            self.analysis_map_status_var = tk.StringVar(value="No trip selected for map.")
            self.logger.log_debug("Trip analysis variables initialized.")


            # Configure root window to expand
            self.grid_rowconfigure(0, weight=1)
            self.grid_columnconfigure(0, weight=1)
            self.logger.log_debug("Root window grid configured.")

            self.logger.log_debug("Calling _create_widgets...")
            self._create_widgets() # This will create the buttons for offline playback
            self.logger.log_debug("_create_widgets completed.")
            
            # Now that buttons are created, initialize OfflinePlaybackManager
            self.offline_playback_manager = OfflinePlaybackManager(
                self.data_queue,
                self.stop_playback_event,
                self.logger,
                self.playback_speed_var,
                self.playback_status_var,
                self.playback_progress_var,
                self.play_button, # Pass button references
                self.pause_button,
                self.stop_button
            )
            self.logger.log_debug("OfflinePlaybackManager initialized with button references.")

            # --- Centralize initial data loading after widgets are created ---
            self._load_geofences_from_settings() # This method already calls _load_geofences_to_tree()
            self._load_trip_history_to_tree() # Load trip history into the Treeview
            self.logger.log_debug("Initial data (geofences, trip history) loaded.")
            # ------------------------------------------------------------------
            self._setup_data_sources() # Call the new setup method
            self.logger.log_debug("Data sources setup initiated.")
            self._setup_plot() # This is for the single track plot on the map tab
            self.logger.log_debug("Matplotlib plot setup initiated.")
            self._setup_menu()
            self.logger.log_debug("Application menu setup initiated.")

            self.update_id = None # To store the after() job ID for cancellation
            self.logger.log_debug("UI update ID initialized.")

            # Show the main window after everything is set up
            self.deiconify()
            self.logger.log_debug("Main window deiconified (shown).")

            # Initial update of storage info
            self._update_storage_info()
            self.logger.log_debug("Initial storage info updated.")

            # Load initial offline file if path is saved in settings
            initial_offline_filepath = self.settings_manager.get("offline_log_filepath")
            if initial_offline_filepath and os.path.exists(initial_offline_filepath):
                self.offline_playback_manager.load_file(initial_offline_filepath)
                self.offline_file_path_var.set(os.path.basename(initial_offline_filepath))
                self.logger.log_debug(f"Attempting to load initial offline file: {initial_offline_filepath}")
            else:
                self.offline_file_path_var.set("No file selected.")
                self.play_button.config(state=DISABLED) # Disable play if no file
                self.logger.log_debug("No initial offline file found or path invalid.")

            # Set initial UI state based on offline mode preference
            self._toggle_offline_mode_ui(self.offline_mode_active_var.get())
            self.logger.log_debug("Initial UI state toggled based on offline mode.")

            self.logger.log_debug("GPS Dashboard App: __init__ completed successfully.")

        except Exception as e:
            self.logger.log_critical(f"An error occurred during application initialization: {e}", exc_info=True)
            messagebox.showerror("Initialization Error", f"The application failed to start due to an error: {e}\nCheck logs for details.")
            sys.exit(1) # Ensure the application exits if initialization fails


    def _create_widgets(self,):
        """Creates and arranges all GUI widgets."""
        self.logger.log_debug("Creating main application widgets.")
        try:
            # Create a main canvas to hold all content, allowing for scrolling
            self.main_canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0)
            self.main_canvas.grid(row=0, column=0, sticky="nsew")
            self.logger.log_debug("Main canvas created.")

            self.vsb = ttk.Scrollbar(self, orient="vertical", command=self.main_canvas.yview)
            self.vsb.grid(row=0, column=1, sticky="ns")
            self.hsb = ttk.Scrollbar(self, orient="horizontal", command=self.main_canvas.xview)
            self.hsb.grid(row=1, column=0, sticky="ew")
            self.logger.log_debug("Scrollbars created.")

            self.main_canvas.configure(yscrollcommand=self.vsb.set, xscrollcommand=self.hsb.set)
            self.main_canvas.bind('<Configure>', self._on_canvas_resize) # Bind canvas resize
            self.logger.log_debug("Canvas scroll commands and resize bind configured.")

            # Bind mouse wheel events for cross-platform scrolling
            # Use bind_all to ensure scrolling works regardless of which widget has focus
            self.bind_all("<MouseWheel>", self._on_mouse_wheel) # Windows/macOS
            self.bind_all("<Button-4>", self._on_mouse_wheel)   # Linux scroll up
            self.bind_all("<Button-5>", self._on_mouse_wheel)   # Linux scroll down
            self.logger.log_debug("Mouse wheel events bound.")


            # Create a frame inside the canvas to hold the notebook
            self.main_frame = ttk.Frame(self.main_canvas)
            # Store the item ID returned by create_window
            self.main_frame_canvas_id = self.main_canvas.create_window((0, 0), window=self.main_frame, anchor="nw")
            self.main_frame.bind("<Configure>", self._on_frame_configure) # Bind frame resize to update scrollregion
            self.logger.log_debug("Main frame inside canvas created and configured.")

            # Notebook (tabs) now goes inside main_frame
            self.notebook = ttk.Notebook(self.main_frame)
            self.notebook.pack(pady=10, expand=True, fill=BOTH) # Pack within main_frame
            self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_change)
            self.logger.log_debug("Notebook (tabs) created.")

            # Tab 1: Driving Dashboard (NEW)
            self.driving_dashboard_frame = ttk.Frame(self.notebook, padding=10)
            self.notebook.add(self.driving_dashboard_frame, text="Driving Dashboard")
            self._create_driving_dashboard_widgets(self.driving_dashboard_frame)
            self.logger.log_debug("Driving Dashboard tab created.")

            # Tab 2: GPS Data (shifted from 1 to 2)
            self.gps_data_frame = ttk.Frame(self.notebook, padding=10)
            self.notebook.add(self.gps_data_frame, text="GPS Data")
            self._create_gps_data_widgets(self.gps_data_frame)
            self.logger.log_debug("GPS Data tab created.")

            # Tab 3: Satellite Skyplot (shifted from 2 to 3)
            self.skyplot_frame = ttk.Frame(self.notebook, padding=10)
            self.notebook.add(self.skyplot_frame, text="Satellite Skyplot")
            self._create_skyplot_widgets(self.skyplot_frame) # Corrected call
            self.logger.log_debug("Satellite Skyplot tab created.")

            # Tab 4: Map (shifted from 3 to 4)
            self.map_frame = ttk.Frame(self.notebook, padding=10)
            self.notebook.add(self.map_frame, text="Map")
            self._create_map_widgets(self.map_frame)
            self.logger.log_debug("Map tab created.")

            # Tab 5: Geofencing (shifted from 4 to 5)
            self.geofence_frame = ttk.Frame(self.notebook, padding=10)
            self.notebook.add(self.geofence_frame, text="Geofencing")
            self._create_geofencing_widgets(self.geofence_frame)
            self.logger.log_debug("Geofencing tab created.")

            # Tab 6: NMEA Console (shifted from 5 to 6)
            self.nmea_console_frame = ttk.Frame(self.notebook, padding=10)
            self.notebook.add(self.nmea_console_frame, text="NMEA Console")
            self._create_nmea_console_widgets(self.nmea_console_frame)
            self.logger.log_debug("NMEA Console tab created.")

            # Tab 7: GPS Trend Data Plot (shifted from 6 to 7)
            self.trend_data_frame = ttk.Frame(self.notebook, padding=10)
            self.notebook.add(self.trend_data_frame, text="GPS Trend Data")
            self._create_trend_plot_widgets(self.trend_data_frame)
            self.logger.log_debug("GPS Trend Data tab created.")

            # Tab 8: Travel History (shifted from 7 to 8)
            self.travel_history_frame = ttk.Frame(self.notebook, padding=10)
            self.notebook.add(self.travel_history_frame, text="Travel History")
            self._create_travel_history_widgets(self.travel_history_frame)
            self.logger.log_debug("Travel History tab created.")

            # Tab 9: Trip History (shifted from 8 to 9)
            self.trip_history_frame = ttk.Frame(self.notebook, padding=10)
            self.notebook.add(self.trip_history_frame, text="Trip History")
            self._create_trip_history_widgets(self.trip_history_frame)
            self.logger.log_debug("Trip History tab created.")

            # Tab 10: Trip Analysis (NEW)
            self.trip_analysis_frame = ttk.Frame(self.notebook, padding=10)
            self.notebook.add(self.trip_analysis_frame, text="Trip Analysis")
            self._create_trip_analysis_widgets(self.trip_analysis_frame)
            self.logger.log_debug("Trip Analysis tab created.")

            # Tab 11: Log File Map (shifted from 10 to 11)
            self.log_file_map_frame = ttk.Frame(self.notebook, padding=10)
            self.notebook.add(self.log_file_map_frame, text="Log File Map")
            self._create_log_file_map_widgets(self.log_file_map_frame)
            self.logger.log_debug("Log File Map tab created.")

            # Tab 12: Settings (shifted from 11 to 12)
            self.settings_frame = ttk.Frame(self.notebook, padding=10)
            self.notebook.add(self.settings_frame, text="Settings")
            self._create_settings_widgets(self.settings_frame)
            self.logger.log_debug("Settings tab created.")

            # Status Bar - packed directly into the root window, below the canvas
            self.status_label = ttk.Label(self, text="Initializing...", anchor=W, bootstyle="info")
            self.status_label.grid(row=2, column=0, columnspan=2, sticky="ew", ipady=5) # Placed in grid
            self.logger.log_debug("Status bar created.")

            self.logger.log_debug("All main application widgets created successfully.")
        except Exception as e:
            self.logger.log_critical(f"An error occurred during widget creation: {e}", exc_info=True)
            messagebox.showerror("UI Creation Error", f"Failed to create user interface elements: {e}\nCheck logs for details.")
            sys.exit(1)


    def _on_frame_configure(self, event):
        """Update the scrollregion of the canvas when the main_frame changes size."""
        # This ensures the canvas scrollbars adjust to the actual size of the content
        self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all"))
        self.logger.log_debug("Main frame configured, scrollregion updated.")

    def _on_canvas_resize(self, event):
        """Update the width of the main_frame to match the canvas width."""
        # Use the stored canvas item ID for the main_frame
        self.main_canvas.itemconfig(self.main_frame_canvas_id, width=event.width)
        self.logger.log_debug(f"Canvas resized to width: {event.width}.")

    def _on_mouse_wheel(self, event):
        """Handles mouse wheel scrolling for the main canvas."""
        # Determine scroll direction and amount based on OS
        if sys.platform.startswith('win'):
            # Windows: event.delta is typically 120 per scroll "click"
            self.main_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        elif sys.platform.startswith('linux'):
            # Linux: Button-4 (up) and Button-5 (down)
            if event.num == 4: # Button-4 is scroll up on Linux
                self.main_canvas.yview_scroll(-1, "units")
            elif event.num == 5: # Button-5 is scroll down on Linux
                self.main_canvas.yview_scroll(1, "units")
        elif sys.platform == "darwin": # macOS
            # macOS: event.delta is usually positive for scroll down, negative for scroll up
            self.main_canvas.yview_scroll(int(event.delta), "units")

        # For horizontal scrolling with shift key (common convention)
        if event.state & 0x1: # Check if Shift key is pressed (state 0x1 is Shift)
            if sys.platform.startswith('win'):
                self.main_canvas.xview_scroll(int(-1*(event.delta/120)), "units")
            elif sys.platform.startswith('linux'):
                self.main_canvas.xview_scroll(-1, "units")
            elif sys.platform.startswith('linux'):
                if event.num == 4:
                    self.main_canvas.xview_scroll(-1, "units")
                elif event.num == 5:
                    self.main_canvas.xview_scroll(1, "units")
            elif sys.platform == "darwin":
                self.main_canvas.xview_scroll(int(event.delta), "units")
        self.logger.log_debug("Mouse wheel event processed.")

    def _on_tab_change(self, event):
        """
        Handles tab change events in the notebook.
        This method is called when a user switches between tabs.
        It can be used to trigger updates specific to the newly selected tab.
        """
        selected_tab = self.notebook.tab(self.notebook.select(), "text")
        self.logger.log_debug(f"Tab changed to: {selected_tab}")
        
        # Example: Trigger updates for specific tabs when they become active
        if selected_tab == "Map":
            self._generate_folium_map() # Regenerate map to ensure it's current
        elif selected_tab == "Satellite Skyplot":
            # Ensure skyplot and CNO are drawn if data is available
            if self.current_gps_data:
                self._update_skyplot(self.current_gps_data.get('satellites', []))
                self._update_cno_barchart(self.current_gps_data.get('satellites', []))
        elif selected_tab == "GPS Trend Data":
            self._update_trend_plots()
        elif selected_tab == "Travel History":
            self._update_travel_history_tab()
        elif selected_tab == "Trip History":
            self._update_trip_history_tab() # Ensure trip history is refreshed
        elif selected_tab == "Driving Dashboard":
            if self.current_gps_data:
                self._update_compass(self.current_gps_data.get('headMot', float('nan')))
        # Add more conditions for other tabs as needed

    def _create_driving_dashboard_widgets(self, parent):
        """Widgets for the new Driving Dashboard tab."""
        self.logger.log_debug("Creating Driving Dashboard widgets.")
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=1)
        parent.rowconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)
        parent.rowconfigure(2, weight=1)
        parent.rowconfigure(3, weight=1) # Added row for additional metrics

        colors = self._get_plot_colors()

        # Top Row: Speed and Time
        top_row_frame = ttk.LabelFrame(parent, text="Current Status", padding=5, bootstyle="primary")
        top_row_frame.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=5, pady=5)
        top_row_frame.columnconfigure(0, weight=3) # Speed takes more space
        top_row_frame.columnconfigure(1, weight=1) # Time takes less space

        # Speed Display (Large and Central)
        speed_frame = ttk.LabelFrame(top_row_frame, text="Current Speed", padding=20, bootstyle="success")
        speed_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        speed_frame.columnconfigure(0, weight=1)
        speed_frame.rowconfigure(0, weight=1)

        ttk.Label(speed_frame, textvariable=self.dashboard_speed_var, font=("Helvetica", 72, "bold"),
                  bootstyle="success").grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        # Dynamically set speed unit label
        self.speed_unit_label = ttk.Label(speed_frame, textvariable=self.dashboard_speed_unit_var, font=("Helvetica", 18), bootstyle="success")
        self.speed_unit_label.grid(row=1, column=0, sticky="n")

        # Current Time Display
        time_frame = ttk.LabelFrame(top_row_frame, text="Current Time", padding=10, bootstyle="info")
        time_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        time_frame.columnconfigure(0, weight=1)
        time_frame.rowconfigure(0, weight=1)
        ttk.Label(time_frame, textvariable=self.dashboard_time_var, font=("Helvetica", 24, "bold"),
                  bootstyle="info").grid(row=0, column=0, sticky="nsew", padx=10, pady=10)


        # Middle Row: Compass and Key Metrics
        # Compass Display (Matplotlib)
        compass_frame = ttk.LabelFrame(parent, text="Heading", padding=10, bootstyle="primary")
        compass_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        compass_frame.columnconfigure(0, weight=1)
        compass_frame.rowconfigure(0, weight=1)

        # Changed to a standard rectangular plot for the vehicle-style compass
        self.fig_compass, self.ax_compass = plt.subplots(figsize=(4, 2), facecolor=colors["bg"]) # Smaller height
        self.compass_canvas = FigureCanvasTkAgg(self.fig_compass, master=compass_frame)
        self.compass_canvas_widget = self.compass_canvas.get_tk_widget()
        self.compass_canvas_widget.pack(side=TOP, fill=BOTH, expand=True)

        # Initial draw of the compass (even if N/A)
        self._update_compass(float('nan')) # Draw initial empty compass

        # Other Key Metrics
        metrics_frame = ttk.LabelFrame(parent, text="GPS Metrics", padding=10, bootstyle="info")
        metrics_frame.grid(row=1, column=1, sticky="nsew", padx=5, pady=5)
        metrics_frame.columnconfigure(1, weight=1) # Allow value column to expand

        # Altitude label needs dynamic unit
        self.altitude_label = ttk.Label(metrics_frame, text="Altitude:", font=("TkDefaultFont", 9))
        self.altitude_label.grid(row=0, column=0, sticky="w", pady=0)
        self.altitude_value_label = ttk.Label(metrics_frame, textvariable=self.dashboard_altitude_var, bootstyle="info", font=("TkDefaultFont", 10))
        self.altitude_value_label.grid(row=0, column=1, sticky="ew", pady=0)
        self.altitude_unit_label = ttk.Label(metrics_frame, textvariable=self.dashboard_altitude_unit_var, font=("TkDefaultFont", 9))
        self.altitude_unit_label.grid(row=0, column=2, sticky="w", pady=0) # New column for unit

        labels = [
            ("Heading (Deg):", self.dashboard_heading_var),
            ("Satellites in Use:", self.dashboard_num_sv_var),
            ("Fix Type:", self.dashboard_fix_type_var), # This label's style will be dynamic
            ("HDOP:", self.dashboard_hdop_var),
            ("VDOP:", self.dashboard_vdop_var),
        ]

        for i, (text, var) in enumerate(labels):
            # Reduced font size for labels and pady for minimal spacing
            ttk.Label(metrics_frame, text=text, font=("TkDefaultFont", 9)).grid(row=i+1, column=0, sticky="w", pady=0) # Shifted by 1 due to altitude
            
            # Store reference to the fix type label for dynamic styling
            if text == "Fix Type:":
                self.dashboard_fix_type_label = ttk.Label(metrics_frame, textvariable=var, bootstyle="info", font=("TkDefaultFont", 10))
                self.dashboard_fix_type_label.grid(row=i+1, column=1, sticky="ew", pady=0)
            else:
                ttk.Label(metrics_frame, textvariable=var, bootstyle="info", font=("TkDefaultFont", 10)).grid(row=i+1, column=1, sticky="ew", pady=0)


        # Bottom Row: Coordinates and Accuracy
        coords_accuracy_frame = ttk.LabelFrame(parent, text="Location & Accuracy", padding=5, bootstyle="secondary")
        coords_accuracy_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=5, pady=5)
        coords_accuracy_frame.columnconfigure(0, weight=1)
        coords_accuracy_frame.columnconfigure(1, weight=1)

        # Coordinates
        coord_frame = ttk.LabelFrame(coords_accuracy_frame, text="Coordinates", padding=10, bootstyle="secondary")
        coord_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        coord_frame.columnconfigure(1, weight=1)

        ttk.Label(coord_frame, text="Lat:").grid(row=0, column=0, sticky="w", pady=2)
        ttk.Label(coord_frame, textvariable=self.pos_vars["latitude"], bootstyle="secondary", font=("TkDefaultFont", 10)).grid(row=0, column=1, sticky="ew", pady=2)
        ttk.Label(coord_frame, text="Lon:").grid(row=1, column=0, sticky="w", pady=2)
        ttk.Label(coord_frame, textvariable=self.pos_vars["longitude"], bootstyle="secondary", font=("TkDefaultFont", 10)).grid(row=1, column=1, sticky="ew", pady=2)

        # Accuracy
        accuracy_frame = ttk.LabelFrame(coords_accuracy_frame, text="Accuracy (m)", padding=10, bootstyle="warning")
        accuracy_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        accuracy_frame.columnconfigure(1, weight=1)

        ttk.Label(accuracy_frame, text="Horizontal:").grid(row=0, column=0, sticky="w", pady=2)
        ttk.Label(accuracy_frame, textvariable=self.h_acc_var, bootstyle="warning").grid(row=0, column=1, sticky="ew", pady=2)
        ttk.Label(accuracy_frame, text="Vertical:").grid(row=1, column=0, sticky="w", pady=2)
        ttk.Label(accuracy_frame, textvariable=self.v_acc_var, bootstyle="warning").grid(row=1, column=1, sticky="ew", pady=2)

        # Trip Controls and Metrics
        trip_control_frame = ttk.LabelFrame(parent, text="Trip Controls", padding=10, bootstyle="primary")
        trip_control_frame.grid(row=3, column=0, columnspan=2, sticky="ew", padx=5, pady=5)
        trip_control_frame.columnconfigure(0, weight=1)
        trip_control_frame.columnconfigure(1, weight=1)
        trip_control_frame.columnconfigure(2, weight=1) # For duration, distance, max speed

        # Buttons
        self.start_trip_button = ttk.Button(trip_control_frame, text="Start Trip", command=self._start_trip, bootstyle="success")
        self.start_trip_button.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        self.end_trip_button = ttk.Button(trip_control_frame, text="End Trip", command=self._end_trip, bootstyle="danger", state=DISABLED)
        self.end_trip_button.grid(row=0, column=1, sticky="ew", padx=5, pady=5)

        # Trip Metrics Display
        ttk.Label(trip_control_frame, textvariable=self.trip_duration_var, bootstyle="info").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        ttk.Label(trip_control_frame, textvariable=self.trip_distance_var, bootstyle="info").grid(row=1, column=1, sticky="w", padx=5, pady=2)
        ttk.Label(trip_control_frame, textvariable=self.trip_max_speed_var, bootstyle="info").grid(row=1, column=2, sticky="w", padx=5, pady=2)
        self.logger.log_debug("Driving Dashboard widgets created.")


    def _create_gps_data_widgets(self, parent):
        """Widgets for the GPS Data tab."""
        self.logger.log_debug("Creating GPS Data widgets.")
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=1)
        parent.rowconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)
        parent.rowconfigure(2, weight=1)

        # Current Position Frame
        pos_frame = ttk.LabelFrame(parent, text="Current Position", padding=10, bootstyle="primary")
        pos_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        pos_frame.columnconfigure(1, weight=1)

        labels = ["Latitude:", "Longitude:", "Altitude (MSL):", "Speed:", "Heading (deg):", "Satellites in Use:", "Fix Type:"]
        for i, text in enumerate(labels):
            key = text.replace(":", "").replace(" ", "_").replace("(deg)", "deg").lower()
            ttk.Label(pos_frame, text=text).grid(row=i, column=0, sticky="w", pady=2)
            
            # Special handling for speed and altitude to include dynamic units
            if "speed" in key:
                ttk.Label(pos_frame, textvariable=self.pos_vars[key], bootstyle="info").grid(row=i, column=1, sticky="ew", pady=2)
                ttk.Label(pos_frame, textvariable=self.pos_vars[f"{key}_unit"], bootstyle="info").grid(row=i, column=2, sticky="w", pady=2)
            elif "altitude" in key:
                ttk.Label(pos_frame, textvariable=self.pos_vars[key], bootstyle="info").grid(row=i, column=1, sticky="ew", pady=2)
                ttk.Label(pos_frame, textvariable=self.pos_vars[f"{key}_unit"], bootstyle="info").grid(row=i, column=2, sticky="w", pady=2)
            else:
                ttk.Label(pos_frame, textvariable=self.pos_vars[key], bootstyle="info").grid(row=i, column=1, sticky="ew", pady=2)


        # High-Precision Coordinates Frame
        hp_coords_frame = ttk.LabelFrame(parent, text="High-Precision Coords (RTK)", padding=10, bootstyle="primary")
        hp_coords_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        hp_coords_frame.columnconfigure(1, weight=1)

        ttk.Label(hp_coords_frame, text="HP Latitude:").grid(row=0, column=0, sticky="w", pady=2)
        ttk.Label(hp_coords_frame, textvariable=self.hp_lat_var, bootstyle="info").grid(row=0, column=1, sticky="ew", pady=2)
        ttk.Label(hp_coords_frame, text="HP Longitude:").grid(row=1, column=0, sticky="w", pady=2)
        ttk.Label(hp_coords_frame, textvariable=self.hp_lon_var, bootstyle="info").grid(row=1, column=1, sticky="ew", pady=2)
        ttk.Label(hp_coords_frame, text="HP Height (m):").grid(row=2, column=0, sticky="w", pady=2)
        ttk.Label(hp_coords_frame, textvariable=self.hp_height_var, bootstyle="info").grid(row=2, column=1, sticky="ew", pady=2)
        ttk.Label(hp_coords_frame, text="Horizontal Accuracy (m):").grid(row=3, column=0, sticky="w", pady=2)
        ttk.Label(hp_coords_frame, textvariable=self.h_acc_var, bootstyle="info").grid(row=3, column=1, sticky="ew", pady=2)
        ttk.Label(hp_coords_frame, text="Vertical Accuracy (m):").grid(row=4, column=0, sticky="w", pady=2)
        ttk.Label(hp_coords_frame, textvariable=self.v_acc_var, bootstyle="info").grid(row=4, column=1, sticky="ew", pady=2)


        # DOP Information Frame
        dop_frame = ttk.LabelFrame(parent, text="DOP (Dilution of Precision)", padding=10, bootstyle="primary")
        dop_frame.grid(row=2, column=0, sticky="nsew", padx=5, pady=5)
        dop_frame.columnconfigure(1, weight=1)

        ttk.Label(dop_frame, text="PDOP:").grid(row=0, column=0, sticky="w", pady=2)
        ttk.Label(dop_frame, textvariable=self.dop_vars["pdop"], bootstyle="info").grid(row=0, column=1, sticky="ew", pady=2)
        ttk.Label(dop_frame, text="HDOP:").grid(row=1, column=0, sticky="w", pady=2)
        ttk.Label(dop_frame, textvariable=self.dop_vars["hdop"], bootstyle="info").grid(row=1, column=1, sticky="ew", pady=2)
        ttk.Label(dop_frame, text="VDOP:").grid(row=2, column=0, sticky="w", pady=2)
        ttk.Label(dop_frame, textvariable=self.dop_vars["vdop"], bootstyle="info").grid(row=2, column=1, sticky="ew", pady=2)


        # Satellite Details Frame
        sat_frame = ttk.LabelFrame(parent, text="Satellite Details", padding=10, bootstyle="primary")
        sat_frame.grid(row=0, column=1, rowspan=3, sticky="nsew", padx=5, pady=5)
        sat_frame.columnconfigure(0, weight=1)
        sat_frame.rowconfigure(0, weight=1)

        columns = ("svid", "gnss_id", "cno", "elevation", "azimuth", "used_in_fix", "diff_corr", "sbas_corr")
        self.sat_tree = ttk.Treeview(sat_frame, columns=columns, show="headings", bootstyle="primary")
        self.sat_tree.grid(row=0, column=0, sticky="nsew")

        self.sat_tree.heading("svid", text="SV ID")
        self.sat_tree.heading("gnss_id", text="GNSS ID")
        self.sat_tree.heading("cno", text="CNO")
        self.sat_tree.heading("elevation", text="Elev.")
        self.sat_tree.heading("azimuth", text="Azim.")
        self.sat_tree.heading("used_in_fix", text="Used")
        self.sat_tree.heading("diff_corr", text="Diff. Corr.")
        self.sat_tree.heading("sbas_corr", text="SBAS Corr.")

        self.sat_tree.column("svid", width=50, anchor=CENTER)
        self.sat_tree.column("gnss_id", width=70, anchor=CENTER)
        self.sat_tree.column("cno", width=50, anchor=CENTER)
        self.sat_tree.column("elevation", width=50, anchor=CENTER)
        self.sat_tree.column("azimuth", width=50, anchor=CENTER)
        self.sat_tree.column("used_in_fix", width=50, anchor=CENTER)
        self.sat_tree.column("diff_corr", width=70, anchor=CENTER)
        self.sat_tree.column("sbas_corr", width=70, anchor=CENTER)

        # Add a scrollbar
        scrollbar = ttk.Scrollbar(sat_frame, orient=VERTICAL, command=self.sat_tree.yview)
        self.sat_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.grid(row=0, column=1, sticky="ns")


        # System Information Frame
        sys_info_frame = ttk.LabelFrame(parent, text="System Information", padding=10, bootstyle="primary")
        sys_info_frame.grid(row=3, column=0, columnspan=2, sticky="ew", padx=5, pady=5) # Placed below other frames
        sys_info_frame.columnconfigure(1, weight=1)

        ttk.Label(sys_info_frame, text="Software Version:").grid(row=0, column=0, sticky="w", pady=2)
        ttk.Label(sys_info_frame, textvariable=self.info_vars["sw_version"], bootstyle="info").grid(row=0, column=1, sticky="ew", pady=2)

        ttk.Label(sys_info_frame, text="Hardware Version:").grid(row=1, column=0, sticky="w", pady=2)
        ttk.Label(sys_info_frame, textvariable=self.info_vars["hw_version"], bootstyle="info").grid(row=1, column=1, sticky="ew", pady=2)

        ttk.Label(sys_info_frame, text="GNSS Support:").grid(row=2, column=0, sticky="w", pady=2)
        ttk.Label(sys_info_frame, textvariable=self.info_vars["gnss_support"], bootstyle="info").grid(row=2, column=1, sticky="ew", pady=2)

        ttk.Label(sys_info_frame, text="RF/Antenna Status:").grid(row=3, column=0, sticky="w", pady=2)
        ttk.Label(sys_info_frame, textvariable=self.info_vars["rf_antenna_status"], bootstyle="info").grid(row=3, column=1, sticky="ew", pady=2)

        # Communication Status
        comm_status_frame = ttk.LabelFrame(sys_info_frame, text="Communication Status", padding=10, bootstyle="secondary")
        comm_status_frame.grid(row=4, column=0, columnspan=2, sticky="ew", pady=5)
        comm_status_frame.columnconfigure(1, weight=1)

        ttk.Label(comm_status_frame, text="TX Errors:").grid(row=0, column=0, sticky="w", pady=2)
        ttk.Label(comm_status_frame, textvariable=self.comm_status_vars["comm_errors"], bootstyle="secondary").grid(row=0, column=1, sticky="ew", pady=2)

        ttk.Label(comm_status_frame, text="RX Buffer Usage:").grid(row=1, column=0, sticky="w", pady=2)
        ttk.Label(comm_status_frame, textvariable=self.comm_status_vars["rx_buffer_usage"], bootstyle="secondary").grid(row=1, column=1, sticky="ew", pady=2)

        ttk.Label(comm_status_frame, text="TX Buffer Usage:").grid(row=2, column=0, sticky="w", pady=2)
        ttk.Label(comm_status_frame, textvariable=self.comm_status_vars["tx_buffer_usage"], bootstyle="secondary").grid(row=2, column=1, sticky="ew", pady=2)
        self.logger.log_debug("GPS Data widgets created.")


    def _draw_skyplot_template(self):
        """Draws the static elements of the skyplot."""
        self.logger.log_debug("Drawing skyplot template.")
        colors = self._get_plot_colors()
        ax = self.ax_skyplot
        ax.clear()
        ax.set_theta_zero_location("N")  # North at the top
        ax.set_theta_direction(-1)      # Clockwise
        ax.set_ylim(0, 90)               # Zenith to horizon
        ax.set_yticks(range(0, 91, 30))  # Elevation circles
        ax.set_yticklabels([f"{90-x}°" for x in range(0, 91, 30)]) # Labels for elevation
        ax.set_thetagrids(np.arange(0, 360, 45), ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'], color=colors["text"], fontsize=10)
        ax.set_facecolor(colors["bg"])
        ax.grid(True, color=colors["grid"])
        self.fig_skyplot.tight_layout()
        self.skyplot_canvas.draw_idle()
        self.logger.log_debug("Skyplot template drawn.")

    def _draw_cno_barchart_template(self):
        """Draws the static elements of the CNO bar chart."""
        self.logger.log_debug("Drawing CNO barchart template.")
        colors = self._get_plot_colors()
        ax = self.ax_cno
        ax.clear()
        ax.set_xlabel("CNO (dBHz)", color=colors["text"])
        ax.set_ylabel("SV ID", color=colors["text"])
        ax.set_title("Satellite CNO Levels", color=colors["text"])
        ax.set_xlim(0, 50) # Typical CNO range
        ax.set_facecolor(colors["bg"])
        ax.tick_params(axis='x', colors=colors["text"])
        ax.tick_params(axis='y', colors=colors["text"])
        ax.grid(True, axis='x', color=colors["grid"])
        self.fig_cno.tight_layout()
        self.cno_canvas.draw_idle()
        self.logger.log_debug("CNO barchart template drawn.")

    def _create_skyplot_widgets(self, parent):
        """Widgets for the Satellite Skyplot tab."""
        self.logger.log_debug("Creating Skyplot widgets.")
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=1)
        parent.rowconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        colors = self._get_plot_colors()

        # Skyplot Frame
        skyplot_frame = ttk.LabelFrame(parent, text="Satellite Skyplot", padding=10, bootstyle="primary")
        skyplot_frame.grid(row=0, column=0, sticky="nsew", pady=5, padx=5)
        skyplot_frame.columnconfigure(0, weight=1)
        skyplot_frame.rowconfigure(0, weight=1)

        self.fig_skyplot, self.ax_skyplot = plt.subplots(figsize=(6, 6), subplot_kw={'projection': 'polar'}, facecolor=colors["bg"])
        self.skyplot_canvas = FigureCanvasTkAgg(self.fig_skyplot, master=skyplot_frame)
        self.skyplot_canvas_widget = self.skyplot_canvas.get_tk_widget()
        self.skyplot_canvas_widget.pack(side=TOP, fill=BOTH, expand=True)

        # CNO Bar Chart Frame
        cno_frame = ttk.LabelFrame(parent, text="CNO Levels", padding=10, bootstyle="primary")
        cno_frame.grid(row=0, column=1, sticky="nsew", pady=5, padx=5)
        cno_frame.columnconfigure(0, weight=1)
        cno_frame.rowconfigure(0, weight=1)

        self.fig_cno, self.ax_cno = plt.subplots(figsize=(6, 6), facecolor=colors["bg"])
        self.cno_canvas = FigureCanvasTkAgg(self.fig_cno, master=cno_frame)
        self.cno_canvas_widget = self.cno_canvas.get_tk_widget()
        self.cno_canvas_widget.pack(side=TOP, fill=BOTH, expand=True)

        # Satellite Info Display (similar to GPS Data tab but focused on skyplot context)
        sat_info_frame = ttk.LabelFrame(parent, text="Skyplot Info", padding=10, bootstyle="info")
        sat_info_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=5, padx=5)
        sat_info_frame.columnconfigure(1, weight=1)

        ttk.Label(sat_info_frame, text="Total Satellites:").grid(row=0, column=0, sticky="w", pady=2)
        self.total_sats_var = tk.StringVar(value="N/A")
        ttk.Label(sat_info_frame, textvariable=self.total_sats_var, bootstyle="info").grid(row=0, column=1, sticky="ew", pady=2)

        ttk.Label(sat_info_frame, text="Satellites Used in Fix:").grid(row=1, column=0, sticky="w", pady=2)
        self.sats_in_fix_var = tk.StringVar(value="N/A")
        ttk.Label(sat_info_frame, textvariable=self.sats_in_fix_var, bootstyle="info").grid(row=1, column=1, sticky="ew", pady=2)

        # Initial drawing of empty plots
        self._draw_skyplot_template()
        self._draw_cno_barchart_template()
        self.logger.log_debug("Skyplot widgets created.")


    def _update_skyplot(self, satellites):
        """Updates the satellite skyplot with new data."""
        self.logger.log_debug(f"Skyplot update: Received {len(satellites)} satellites for plotting.")
        colors = self._get_plot_colors()
        ax = self.ax_skyplot
        self._draw_skyplot_template() # Redraw template to clear old points

        sats_used_in_fix = 0
        
        # Plot satellites
        for sat in satellites:
            elev = sat.get('elev')
            azim = sat.get('azim')
            cno = sat.get('cno')
            sv_used = sat.get('flags', {}).get('svUsed')

            if elev is not None and azim is not None and not math.isnan(elev) and not math.isnan(azim):
                # Convert elevation (0-90 from horizon) to radial distance (0-90 from zenith)
                # For polar plot, radial distance is from center (zenith) to edge (horizon)
                r = 90 - elev
                theta = math.radians(azim) # Azimuth in degrees to radians

                marker_color = 'green' if sv_used == 1 else 'orange'
                marker_edge_color = 'black' if sv_used == 1 else 'gray'
                marker_size = 8 + (cno / 5) if cno is not None and not math.isnan(cno) else 8 # Scale size by CNO

                ax.plot(theta, r, 'o', color=marker_color, markeredgecolor=marker_edge_color, markersize=marker_size, alpha=0.8)
                ax.text(theta, r + 5, str(sat['svid']), color=colors["text"], fontsize=8, ha='center', va='center') # Label with SV ID

                if sv_used == 1:
                    sats_used_in_fix += 1

        self.total_sats_var.set(str(len(satellites)))
        self.sats_in_fix_var.set(str(sats_used_in_fix))
        self.skyplot_canvas.draw_idle()
        self.logger.log_debug("Skyplot updated.")

    def _update_cno_barchart(self, satellites):
        """Updates the CNO bar chart with new satellite data."""
        self.logger.log_debug(f"CNO barchart update: Received {len(satellites)} satellites for plotting.")
        colors = self._get_plot_colors()
        self.ax_cno.clear()
        self.ax_cno.set_xlabel("CNO (dBHz)", color=colors["text"])
        self.ax_cno.set_ylabel("SV ID", color=colors["text"]) # Re-apply Y-label
        self.ax_cno.set_title("Satellite CNO Levels", color=colors["text"])
        self.ax_cno.set_xlim(0, 50) # Typical CNO range, adjust if needed
        self.ax_cno.set_facecolor(colors["bg"]) # Ensure facecolor is set on clear
        self.ax_cno.tick_params(axis='x', colors=colors["text"])
        # --- MODIFICATION START ---
        # Reduce font size for y-axis (SV ID) labels to avoid clutter
        self.ax_cno.tick_params(axis='y', colors=colors["text"], labelsize=6) # Reduced labelsize
        # --- MODIFICATION END ---
        self.ax_cno.grid(True, axis='x', color=colors["grid"])

        cno_values = []
        sv_ids = []
        colors_bar = [] # Use a different variable name to avoid conflict with plot_colors

        # Define a mapping for GNSS IDs to single-letter prefixes
        gnss_prefix_map = {
            0: "G",   # GPS
            2: "E",   # Galileo
            3: "C",   # BeiDou
            5: "J",   # QZSS
            6: "R",   # GLONASS
            7: "S"    # SBAS
        }

        # Filter satellites with valid CNO and sort them by CNO for better visualization
        valid_sats = sorted([s for s in satellites if s.get('cno') is not None and not math.isnan(s['cno'])],
                            key=lambda x: x['cno'], reverse=True)

        for sat in valid_sats:
            cno_values.append(sat['cno'])
            # Format SV ID and GNSS ID for display using the new prefix
            gnss_prefix = gnss_prefix_map.get(sat.get('gnssId'), "?") # Use '?' for unknown GNSS ID
            sv_ids.append(f"{gnss_prefix}{sat['svid']}")
            colors_bar.append('green' if sat.get('flags', {}).get('svUsed') == 1 else 'orange') # Green if used, orange if not

        if cno_values:
            # Create horizontal bars
            self.ax_cno.barh(sv_ids, cno_values, color=colors_bar)
            self.ax_cno.set_yticks(np.arange(len(sv_ids)))
            self.ax_cno.set_yticklabels(sv_ids)
            self.ax_cno.invert_yaxis() # Highest CNO at the top

        self.fig_cno.tight_layout()
        self.cno_canvas.draw_idle()
        self.logger.log_debug("CNO barchart updated.")

    def _create_map_widgets(self, parent):
        """Widgets for the Map tab."""
        self.logger.log_debug("Creating Map widgets.")
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        # Frame to hold the message and button
        map_control_frame = ttk.Frame(parent, padding=10)
        map_control_frame.grid(row=0, column=0, sticky="nsew")
        map_control_frame.columnconfigure(0, weight=1)
        map_control_frame.rowconfigure(0, weight=1)
        map_control_frame.rowconfigure(1, weight=1)

        self.map_status_label = ttk.Label(map_control_frame, text="Map will be generated. Click the button below to view it in your browser.",
                                          anchor=CENTER, justify=CENTER, wraplength=400, bootstyle="info")
        self.map_status_label.grid(row=0, column=0, sticky="nsew", pady=10)

        self.open_map_button = ttk.Button(map_control_frame, text="Open Map in Browser", command=self._open_map_in_browser, bootstyle="primary")
        self.open_map_button.grid(row=1, column=0, pady=5)
        self.logger.log_debug("Map widgets created.")


    def _open_map_in_browser(self):
        """Opens the generated Folium map HTML file in the default web browser."""
        map_filepath = os.path.abspath(MAP_HTML_FILE)
        self.logger.log_debug(f"Attempting to open map in browser: {map_filepath}")
        if os.path.exists(map_filepath):
            try:
                webbrowser.open_new_tab(f"file://{map_filepath}")
                self.status_label.config(text="Map opened in browser.", bootstyle="info")
                self.logger.log_info("Map opened in browser.")
            except Exception as e:
                messagebox.showerror("Error", f"Could not open map in browser: {e}")
                self.status_label.config(text=f"ERROR: Could not open map: {e}", bootstyle="danger")
                self.logger.log_error(f"Could not open map in browser: {e}", exc_info=True)
        else:
            self.status_label.config(text="Map file not yet generated. Please wait for GPS data.", bootstyle="warning")
            self.logger.log_warning("Map file not yet generated. Cannot open in browser.")


    def _create_geofencing_widgets(self, parent):
        """Widgets for the Geofencing tab."""
        self.logger.log_debug("Creating Geofencing widgets.")
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        control_frame = ttk.Frame(parent, padding=5)
        control_frame.grid(row=0, column=0, sticky="ew")

        ttk.Button(control_frame, text="Add Geofence", command=self._add_geofence, bootstyle="success").pack(side=LEFT, padx=5)
        ttk.Button(control_frame, text="Edit Geofence", command=self._edit_selected_geofence, bootstyle="info").pack(side=LEFT, padx=5)
        ttk.Button(control_frame, text="Delete Geofence", command=self._delete_selected_geofence, bootstyle="danger").pack(side=LEFT, padx=5)

        # Geofence list Treeview
        columns = ("name", "latitude", "longitude", "radius")
        self.geofence_tree = ttk.Treeview(parent, columns=columns, show="headings", bootstyle="primary")
        self.geofence_tree.grid(row=1, column=0, sticky="nsew", pady=5)

        self.geofence_tree.heading("name", text="Name")
        self.geofence_tree.heading("latitude", text="Latitude")
        self.geofence_tree.heading("longitude", text="Longitude")
        self.geofence_tree.heading("radius", text="Radius (m)")

        self.geofence_tree.column("name", width=150, anchor=W)
        self.geofence_tree.column("latitude", width=100, anchor=CENTER)
        self.geofence_tree.column("longitude", width=100, anchor=CENTER)
        self.geofence_tree.column("radius", width=80, anchor=CENTER)

        # Add a scrollbar
        scrollbar = ttk.Scrollbar(parent, orient=VERTICAL, command=self.geofence_tree.yview)
        self.geofence_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.grid(row=1, column=1, sticky="ns", pady=5)

        # Removed redundant call: self._load_geofences_to_tree()
        # This is now handled by _load_geofences_from_settings() in __init__
        self.logger.log_debug("Geofencing widgets created.")

    def _add_geofence(self):
        """Prompts user for geofence details and adds it, with radius calculated from a second point."""
        self.logger.log_debug("Attempting to add geofence.")
        name = simpledialog.askstring("Add Geofence", "Enter geofence name:")
        if not name:
            self.logger.log_debug("Geofence addition cancelled by user (no name).")
            return

        center_lat = None
        center_lon = None

        # Ask user how to define the geofence center
        choice = messagebox.askyesno("Geofence Center", "Use current GPS location as geofence center?")

        if choice: # User chose to use current GPS location
            if 'lat' in self.current_gps_data and 'lon' in self.current_gps_data and \
               not math.isnan(self.current_gps_data['lat']) and not math.isnan(self.current_gps_data['lon']):
                center_lat = self.current_gps_data['lat']
                center_lon = self.current_gps_data['lon']
                self.logger.log_info(f"Using current GPS location ({center_lat:.6f}, {center_lon:.6f}) as geofence center.")
            else:
                messagebox.showwarning("No GPS Data", "Current GPS data is not available or invalid. Please try again when GPS data is stable, or choose to enter coordinates manually.")
                self.logger.log_warning("Attempted to use current GPS for geofence center, but data was invalid.")
                return
        else: # User chose to manually enter coordinates
            try:
                center_lat = simpledialog.askfloat("Add Geofence", "Enter center latitude:")
                if center_lat is None:
                    self.logger.log_debug("Geofence addition cancelled by user (no center latitude).")
                    return
                center_lon = simpledialog.askfloat("Add Geofence", "Enter center longitude:")
                if center_lon is None:
                    self.logger.log_debug("Geofence addition cancelled by user (no center longitude).")
                    return
            except ValueError:
                messagebox.showerror("Invalid Input", "Please enter valid numbers for center coordinates.")
                self.logger.log_error("Invalid input for geofence center coordinates.", exc_info=True)
                return

        # Now, get the second point to calculate the radius
        try:
            second_point_lat = simpledialog.askfloat("Add Geofence", "Enter latitude of a point on the geofence boundary (to calculate radius):")
            if second_point_lat is None:
                self.logger.log_debug("Geofence addition cancelled by user (no boundary latitude).")
                return
            second_point_lon = simpledialog.askfloat("Add Geofence", "Enter longitude of a point on the geofence boundary (to calculate radius):")
            if second_point_lon is None:
                self.logger.log_debug("Geofence addition cancelled by user (no boundary longitude).")
                return
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter valid numbers for the second point's coordinates.")
            self.logger.log_error("Invalid input for geofence second point coordinates.", exc_info=True)
            return

        # Calculate the radius using Haversine distance
        radius = haversine_distance(center_lat, center_lon, second_point_lat, second_point_lon)
        self.logger.log_info(f"Calculated geofence radius: {radius:.2f} meters.")

        geofence = {"name": name, "latitude": center_lat, "longitude": center_lon, "radius": radius}
        self.geofences.append(geofence)
        self._load_geofences_to_tree()
        self._save_geofences()
        messagebox.showinfo("Geofence Added", f"Geofence '{name}' added with calculated radius of {radius:.2f} meters.")
        self.logger.log_info(f"Geofence '{name}' added with calculated radius of {radius:.2f} meters.")

    def _edit_selected_geofence(self):
        """Edits the selected geofence."""
        self.logger.log_debug("Attempting to edit geofence.")
        selected_item = self.geofence_tree.selection()
        if not selected_item:
            messagebox.showwarning("No Selection", "Please select a geofence to edit.")
            self.logger.log_warning("No geofence selected for editing.")
            return

        item_values = self.geofence_tree.item(selected_item, 'values')
        old_name = item_values[0]
        
        # Find the geofence object
        geofence_to_edit = next((gf for gf in self.geofences if gf['name'] == old_name), None)
        if not geofence_to_edit:
            messagebox.showerror("Error", "Selected geofence not found in data.")
            self.logger.log_error(f"Selected geofence '{old_name}' not found in data for editing.")
            return

        new_name = simpledialog.askstring("Edit Geofence", "Enter new name:", initialvalue=geofence_to_edit['name'])
        if new_name is None:
            self.logger.log_debug("Geofence edit cancelled by user (no new name).")
            return

        try:
            new_latitude = simpledialog.askfloat("Edit Geofence", "Enter new latitude:", initialvalue=geofence_to_edit['latitude'])
            if new_latitude is None:
                self.logger.log_debug("Geofence edit cancelled by user (no new latitude).")
                return
            new_longitude = simpledialog.askfloat("Edit Geofence", "Enter new longitude:", initialvalue=geofence_to_edit['longitude'])
            if new_longitude is None:
                self.logger.log_debug("Geofence edit cancelled by user (no new longitude).")
                return
            new_radius = simpledialog.askfloat("Edit Geofence", "Enter new radius in meters:", initialvalue=geofence_to_edit['radius'])
            if new_radius is None:
                self.logger.log_debug("Geofence edit cancelled by user (no new radius).")
                return
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter valid numbers for coordinates and radius.")
            self.logger.log_error("Invalid input for geofence edit coordinates/radius.", exc_info=True)
            return

        geofence_to_edit.update({
            "name": new_name,
            "latitude": new_latitude,
            "longitude": new_longitude,
            "radius": new_radius
        })
        self._load_geofences_to_tree()
        self._save_geofences()
        messagebox.showinfo("Geofence Edited", f"Geofence '{old_name}' updated to '{new_name}'.")
        self.logger.log_info(f"Geofence '{old_name}' updated to '{new_name}'.")


    def _delete_selected_geofence(self):
        """Deletes the selected geofence."""
        self.logger.log_debug("Attempting to delete geofence.")
        selected_item = self.geofence_tree.selection()
        if not selected_item:
            messagebox.showwarning("No Selection", "Please select a geofence to delete.")
            self.logger.log_warning("No geofence selected for deletion.")
            return

        item_values = self.geofence_tree.item(selected_item, 'values')
        name_to_delete = item_values[0]

        if messagebox.askyesno("Delete Geofence", f"Are you sure you want to delete '{name_to_delete}'?"):
            self.geofences = [gf for gf in self.geofences if gf['name'] != name_to_delete]
            self._load_geofences_to_tree()
            self._save_geofences()
            messagebox.showinfo("Geofence Deleted", f"Geofence '{name_to_delete}' deleted.")
            self.logger.log_info(f"Geofence '{name_to_delete}' deleted.")
        else:
            self.logger.log_debug("Geofence deletion cancelled by user.")

    def _create_nmea_console_widgets(self, parent):
        """Widgets for the NMEA Console tab."""
        self.logger.log_debug("Creating NMEA Console widgets.")
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        nmea_frame = ttk.LabelFrame(parent, text="Raw NMEA Data", padding=10, bootstyle="primary")
        nmea_frame.grid(row=0, column=0, sticky="nsew", pady=5, padx=5)
        nmea_frame.columnconfigure(0, weight=1)
        nmea_frame.rowconfigure(0, weight=1)

        self.nmea_text = tk.Text(nmea_frame, wrap="word", height=20, state="disabled",
                                 font=("TkFixedFont", 10), background="#2b2b2b", foreground="#f0f0f0")
        self.nmea_text.grid(row=0, column=0, sticky="nsew")

        nmea_scrollbar = ttk.Scrollbar(nmea_frame, orient="vertical", command=self.nmea_text.yview)
        nmea_scrollbar.grid(row=0, column=1, sticky="ns")
        self.nmea_text.config(yscrollcommand=nmea_scrollbar.set)
        self.logger.log_debug("NMEA Console widgets created.")


    def _create_trend_plot_widgets(self, parent):
        """Widgets for the GPS Trend Data plot tab."""
        self.logger.log_debug("Creating Trend Plot widgets.")
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        colors = self._get_plot_colors()

        trend_frame = ttk.LabelFrame(parent, text="GPS Parameter Trends Over Time", padding=10, bootstyle="primary")
        trend_frame.grid(row=0, column=0, sticky="nsew", pady=5, padx=5)
        trend_frame.columnconfigure(0, weight=1)
        trend_frame.rowconfigure(0, weight=1)

        # Create a figure with multiple subplots
        self.fig_trend, self.ax_trend = plt.subplots(nrows=4, ncols=2, figsize=(12, 10), facecolor=colors["bg"])
        # Flatten the array of axes for easy iteration
        self.ax_trend_flat = self.ax_trend.flatten()

        # Define titles and y-labels for each subplot
        plot_configs = [
            {"title": "Latitude Trend", "ylabel": "Latitude (deg)"},
            {"title": "Longitude Trend", "ylabel": "Longitude (deg)"},
            {"title": "Altitude (MSL) Trend", "ylabel": "Altitude (m)"},
            {"title": "Speed Trend", "ylabel": "Speed (m/s)"},
            {"title": "Satellites in Use Trend", "ylabel": "Number of SVs"},
            {"title": "PDOP Trend", "ylabel": "PDOP"},
            {"title": "HDOP Trend", "ylabel": "HDOP"},
            {"title": "VDOP Trend", "ylabel": "VDOP"},
        ]

        # Apply configurations to each subplot
        for i, ax in enumerate(self.ax_trend_flat):
            ax.set_title(plot_configs[i]["title"], fontsize=10, color=colors["text"])
            ax.set_ylabel(plot_configs[i]["ylabel"], fontsize=8, color=colors["text"])
            ax.tick_params(axis='both', which='major', labelsize=7, colors=colors["text"])
            ax.set_facecolor(colors["bg"]) # Set facecolor for each subplot
            ax.grid(True, color=colors["grid"])
            if i < len(self.ax_trend_flat) - 2: # Only set xlabel for bottom row plots
                ax.set_xlabel("Time (s)", fontsize=8, color=colors["text"])


        self.fig_trend.tight_layout(pad=3.0) # Adjust padding between subplots

        self.trend_canvas = FigureCanvasTkAgg(self.fig_trend, master=trend_frame)
        self.trend_canvas_widget = self.trend_canvas.get_tk_widget()
        self.trend_canvas_widget.pack(side=TOP, fill=BOTH, expand=True)

        toolbar = NavigationToolbar2Tk(self.trend_canvas, trend_frame)
        toolbar.update()
        self.trend_canvas_widget.pack(side=TOP, fill=BOTH, expand=True)
        self.trend_canvas.draw_idle()
        self.logger.log_debug("Trend Plot widgets created.")

    def _create_travel_history_widgets(self, parent):
        """Widgets for the Travel History tab."""
        self.logger.log_debug("Creating Travel History widgets.")
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        history_frame = ttk.LabelFrame(parent, text="Travel History Log", padding=10, bootstyle="primary")
        history_frame.grid(row=0, column=0, sticky="nsew", pady=5, padx=5)
        history_frame.columnconfigure(0, weight=1)
        history_frame.rowconfigure(0, weight=1)

        columns = ("timestamp", "latitude", "longitude", "speed", "speed_unit") # Added speed_unit column
        self.travel_history_tree = ttk.Treeview(history_frame, columns=columns, show="headings", bootstyle="primary")
        self.travel_history_tree.pack(expand=True, fill=BOTH)

        self.travel_history_tree.heading("timestamp", text="Timestamp")
        self.travel_history_tree.heading("latitude", text="Latitude")
        self.travel_history_tree.heading("longitude", text="Longitude")
        self.travel_history_tree.heading("speed", text="Speed")
        self.travel_history_tree.heading("speed_unit", text="Unit") # New heading

        self.travel_history_tree.column("timestamp", width=150, anchor=CENTER)
        self.travel_history_tree.column("latitude", width=100, anchor=CENTER)
        self.travel_history_tree.column("longitude", width=100, anchor=CENTER)
        self.travel_history_tree.column("speed", width=80, anchor=CENTER)
        self.travel_history_tree.column("speed_unit", width=50, anchor=CENTER) # New column width

        # Add a scrollbar
        scrollbar = ttk.Scrollbar(history_frame, orient=VERTICAL, command=self.travel_history_tree.yview)
        self.travel_history_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=RIGHT, fill=Y)
        self.logger.log_debug("Travel History widgets created.")

    def _create_trip_history_widgets(self, parent):
        """Widgets for the new Trip History tab."""
        self.logger.log_debug("Creating Trip History widgets.")
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        parent.rowconfigure(1, weight=0) # Row for the button

        trip_history_frame = ttk.LabelFrame(parent, text="Completed Trips", padding=10, bootstyle="primary")
        trip_history_frame.grid(row=0, column=0, sticky="nsew", pady=5, padx=5)
        trip_history_frame.columnconfigure(0, weight=1)
        trip_history_frame.rowconfigure(0, weight=1)

        columns = ("start_time", "end_time", "duration", "distance", "distance_unit", "max_speed", "max_speed_unit", "csv_path", "jsonl_path") # Added path columns
        self.trip_history_tree = ttk.Treeview(trip_history_frame, columns=columns, show="headings", bootstyle="primary")
        self.trip_history_tree.pack(expand=True, fill=BOTH)

        self.trip_history_tree.heading("start_time", text="Start Time")
        self.trip_history_tree.heading("end_time", text="End Time")
        self.trip_history_tree.heading("duration", text="Duration")
        self.trip_history_tree.heading("distance", text="Distance")
        self.trip_history_tree.heading("distance_unit", text="Unit") # New heading
        self.trip_history_tree.heading("max_speed", text="Max Speed")
        self.trip_history_tree.heading("max_speed_unit", text="Unit") # New heading
        self.trip_history_tree.heading("csv_path", text="CSV Log (Hidden)") # Hidden column
        self.trip_history_tree.column("csv_path", width=0, stretch=NO) # Make column hidden
        self.trip_history_tree.heading("jsonl_path", text="JSONL Log (Hidden)") # Hidden column
        self.trip_history_tree.column("jsonl_path", width=0, stretch=NO) # Make column hidden


        self.trip_history_tree.column("start_time", width=150, anchor=CENTER)
        self.trip_history_tree.column("end_time", width=150, anchor=CENTER)
        self.trip_history_tree.column("duration", width=100, anchor=CENTER)
        self.trip_history_tree.column("distance", width=80, anchor=CENTER)
        self.trip_history_tree.column("distance_unit", width=50, anchor=CENTER) # New column width
        self.trip_history_tree.column("max_speed", width=80, anchor=CENTER)
        self.trip_history_tree.column("max_speed_unit", width=50, anchor=CENTER) # New column width


        # Add a scrollbar
        scrollbar = ttk.Scrollbar(trip_history_frame, orient=VERTICAL, command=self.trip_history_tree.yview)
        self.trip_history_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=RIGHT, fill=Y)

        # Button to view trip details
        self.view_trip_details_button = ttk.Button(parent, text="View Trip Details", command=self._view_selected_trip_details, bootstyle="info")
        self.view_trip_details_button.grid(row=1, column=0, pady=10)
        self.logger.log_debug("Trip History widgets created.")


    def _create_trip_analysis_widgets(self, parent):
        """Widgets for the new Trip Analysis tab."""
        self.logger.log_debug("Creating Trip Analysis widgets.")
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=1)
        parent.rowconfigure(0, weight=0) # Metrics row
        parent.rowconfigure(1, weight=1) # Map row

        # Metrics Frame
        metrics_frame = ttk.LabelFrame(parent, text="Selected Trip Analysis", padding=10, bootstyle="primary")
        metrics_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=5, pady=5)
        metrics_frame.columnconfigure(1, weight=1) # Allow value column to expand

        ttk.Label(metrics_frame, text="Duration:").grid(row=0, column=0, sticky="w", pady=2)
        ttk.Label(metrics_frame, textvariable=self.analysis_trip_duration_var, bootstyle="info").grid(row=0, column=1, sticky="ew", pady=2)

        ttk.Label(metrics_frame, text="Total Distance:").grid(row=1, column=0, sticky="w", pady=2)
        ttk.Label(metrics_frame, textvariable=self.analysis_trip_distance_var, bootstyle="info").grid(row=1, column=1, sticky="ew", pady=2)

        ttk.Label(metrics_frame, text="Max Speed:").grid(row=2, column=0, sticky="w", pady=2)
        ttk.Label(metrics_frame, textvariable=self.analysis_trip_max_speed_var, bootstyle="info").grid(row=2, column=1, sticky="ew", pady=2)

        ttk.Label(metrics_frame, text="Average Speed:").grid(row=3, column=0, sticky="w", pady=2)
        ttk.Label(metrics_frame, textvariable=self.analysis_trip_avg_speed_var, bootstyle="info").grid(row=3, column=1, sticky="ew", pady=2)

        ttk.Label(metrics_frame, text="Hard Braking Events:").grid(row=4, column=0, sticky="w", pady=2)
        ttk.Label(metrics_frame, textvariable=self.analysis_hard_braking_events_var, bootstyle="warning").grid(row=4, column=1, sticky="ew", pady=2)

        ttk.Label(metrics_frame, text="Sharp Cornering Events:").grid(row=5, column=0, sticky="w", pady=2)
        ttk.Label(metrics_frame, textvariable=self.analysis_sharp_cornering_events_var, bootstyle="warning").grid(row=5, column=1, sticky="ew", pady=2)


        # Map Display Frame for Trip Analysis
        map_frame = ttk.LabelFrame(parent, text="Trip Map", padding=10, bootstyle="primary")
        map_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=5, pady=5)
        map_frame.columnconfigure(0, weight=1)
        map_frame.rowconfigure(0, weight=1)
        map_frame.rowconfigure(1, weight=0) # For the button

        self.analysis_map_status_label = ttk.Label(map_frame, textvariable=self.analysis_map_status_var,
                                                  anchor=CENTER, justify=CENTER, wraplength=400, bootstyle="info")
        self.analysis_map_status_label.grid(row=0, column=0, sticky="nsew", pady=10)

        self.open_analysis_map_button = ttk.Button(map_frame, text="Open Trip Map in Browser", command=self._open_analysis_trip_map, bootstyle="primary", state=DISABLED)
        self.open_analysis_map_button.grid(row=1, column=0, pady=5)

        self.analysis_log_map_generator = LogMapGenerator(self.logger) # Separate instance for analysis maps
        self.current_analysis_map_path = None # To store path of the map generated for analysis
        self.logger.log_debug("Trip Analysis widgets created.")


    def _view_selected_trip_details(self):
        """
        Callback for 'View Trip Details' button.
        Loads the selected trip's log file, analyzes it, and updates the Trip Analysis tab.
        """
        self.logger.log_debug("Attempting to view selected trip details.")
        selected_item = self.trip_history_tree.selection()
        if not selected_item:
            messagebox.showwarning("No Selection", "Please select a trip from the history to view details.")
            self.logger.log_warning("No trip selected for analysis.")
            return

        item_values = self.trip_history_tree.item(selected_item, 'values')
        # Assuming csv_path is at index 7 and jsonl_path at index 8
        csv_path = item_values[7]
        jsonl_path = item_values[8]
        trip_name = f"Trip from {item_values[0]} to {item_values[1]}" # Use start and end time as name

        log_filepath = None
        if os.path.exists(csv_path):
            log_filepath = csv_path
        elif os.path.exists(jsonl_path):
            log_filepath = jsonl_path
        
        if not log_filepath:
            messagebox.showerror("File Not Found", "Log file for the selected trip could not be found.")
            self.logger.log_error(f"Log file not found for selected trip: CSV={csv_path}, JSONL={jsonl_path}")
            self._clear_analysis_metrics()
            self.analysis_map_status_var.set("Log file not found.")
            self.open_analysis_map_button.config(state=DISABLED)
            return

        self.logger.log_info(f"Analyzing trip from log file: {log_filepath}")
        
        # Load and analyze the trip data
        trip_data_points = self._load_trip_data_for_analysis(log_filepath)
        if not trip_data_points:
            messagebox.showwarning("No Data", "No valid data points found in the selected trip log.")
            self.logger.log_warning(f"No valid data points found in {log_filepath} for analysis.")
            self._clear_analysis_metrics()
            self.analysis_map_status_var.set("No valid data points in log file.")
            self.open_analysis_map_button.config(state=DISABLED)
            return

        analysis_results = self._analyze_trip_data(trip_data_points)

        # Update UI with analysis results
        unit_preference = self.settings_manager.get("unit_preference")

        display_distance, distance_unit = self._convert_distance(analysis_results['total_distance'], unit_preference)
        display_max_speed, max_speed_unit = self._convert_speed(analysis_results['max_speed'], unit_preference)
        display_avg_speed, avg_speed_unit = self._convert_speed(analysis_results['average_speed'], unit_preference)

        self.analysis_trip_duration_var.set(analysis_results['duration'])
        self.analysis_trip_distance_var.set(f"{display_distance:.2f} {distance_unit}")
        self.analysis_trip_max_speed_var.set(f"{display_max_speed:.2f} {max_speed_unit}")
        self.analysis_trip_avg_speed_var.set(f"{display_avg_speed:.2f} {avg_speed_unit}")
        self.analysis_hard_braking_events_var.set(str(analysis_results['hard_braking_events']))
        self.analysis_sharp_cornering_events_var.set(str(analysis_results['sharp_cornering_events']))

        # Generate and store the map for the analyzed trip
        coordinates_for_map = [(dp['lat'], dp['lon']) for dp in trip_data_points if not math.isnan(dp['lat']) and not math.isnan(dp['lon'])]
        if coordinates_for_map:
            generated_map_path = self.analysis_log_map_generator.generate_map(coordinates_for_map, map_title=f"Trip Map: {trip_name}")
            if generated_map_path:
                self.current_analysis_map_path = generated_map_path
                self.analysis_map_status_var.set("Trip map generated. Click to open in browser.")
                self.open_analysis_map_button.config(state=NORMAL)
            else:
                self.current_analysis_map_path = None
                self.analysis_map_status_var.set("Failed to generate trip map.")
                self.open_analysis_map_button.config(state=DISABLED)
        else:
            self.current_analysis_map_path = None
            self.analysis_map_status_var.set("No valid coordinates for map generation.")
            self.open_analysis_map_button.config(state=DISABLED)

        # Switch to the Trip Analysis tab
        self.notebook.select(self.trip_analysis_frame)
        self.logger.log_info("Trip analysis displayed.")

    def _clear_analysis_metrics(self):
        """Clears the displayed analysis metrics."""
        self.analysis_trip_duration_var.set("N/A")
        self.analysis_trip_distance_var.set("N/A")
        self.analysis_trip_max_speed_var.set("N/A")
        self.analysis_trip_avg_speed_var.set("N/A")
        self.analysis_hard_braking_events_var.set("N/A")
        self.analysis_sharp_cornering_events_var.set("N/A")
        self.analysis_map_status_var.set("No trip selected for map.")
        self.open_analysis_map_button.config(state=DISABLED)
        self.current_analysis_map_path = None
        self.logger.log_debug("Analysis metrics cleared.")


    def _load_trip_data_for_analysis(self, filepath):
        """Loads GPS data from a specified CSV or JSONL file for analysis."""
        self.logger.log_debug(f"Loading trip data for analysis from: {filepath}")
        file_extension = os.path.splitext(filepath)[1].lower()
        data_points = []
        try:
            if file_extension == '.csv':
                with open(filepath, 'r', newline='') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        dp = {}
                        try:
                            # Timestamp conversion
                            dp['timestamp'] = datetime.fromisoformat(row['Timestamp']).timestamp()
                            # Coordinates
                            dp['lat'] = float(row['Latitude'])
                            dp['lon'] = float(row['Longitude'])
                            # Speed (already in m/s in CSV)
                            dp['gSpeed'] = float(row['Speed (m/s)'])
                            # Heading
                            dp['headMot'] = float(row['Heading (deg)'])
                            data_points.append(dp)
                        except (ValueError, TypeError, KeyError) as e:
                            self.logger.log_warning(f"Skipping invalid row in CSV {filepath} during analysis load: {row} - Error: {e}")
                            continue
            elif file_extension == '.jsonl':
                with open(filepath, 'r') as f:
                    for line in f:
                        try:
                            entry = json.loads(line)
                            if isinstance(entry, dict) and 'data' in entry and isinstance(entry['data'], dict):
                                dp = entry['data'].copy()
                                # Convert timestamp from ISO string to Unix timestamp
                                if 'timestamp' in entry:
                                    dp['timestamp'] = datetime.fromisoformat(entry['timestamp']).timestamp()
                                else:
                                    dp['timestamp'] = float('nan') # Or handle missing timestamp
                                
                                # Ensure speed is in m/s (gSpeed from ublox_gps is mm/s, so convert here)
                                # This logic is duplicated from _process_gps_data, consider centralizing
                                if 'gSpeed' in dp and not math.isnan(dp['gSpeed']):
                                    # Heuristic: if speed is very large, assume mm/s and convert
                                    if dp['gSpeed'] > 1000: # Assuming typical speeds won't exceed 1000 m/s
                                        dp['gSpeed'] /= 1000.0 # Convert mm/s to m/s
                                data_points.append(dp)
                        except (json.JSONDecodeError, ValueError, TypeError) as e:
                            self.logger.log_warning(f"Skipping invalid JSON line in {filepath} during analysis load: {line.strip()} - Error: {e}")
                            continue
            else:
                raise ValueError("Unsupported file type for analysis. Please select a .csv or .jsonl file.")
            
            # Filter out data points with NaN coordinates or speed for analysis
            data_points = [dp for dp in data_points if not math.isnan(dp.get('lat', float('nan'))) and 
                                                      not math.isnan(dp.get('lon', float('nan'))) and
                                                      not math.isnan(dp.get('gSpeed', float('nan'))) and
                                                      not math.isnan(dp.get('timestamp', float('nan')))]
            
            # Sort by timestamp to ensure correct order for calculations
            data_points.sort(key=lambda x: x['timestamp'])
            self.logger.log_debug(f"Loaded {len(data_points)} valid data points for analysis.")
            return data_points
        except Exception as e:
            self.logger.log_error(f"Error loading trip log file {filepath} for analysis: {e}", exc_info=True)
            return []

    def _analyze_trip_data(self, data_points):
        """
        Analyzes a list of GPS data points to calculate trip metrics and driving habits.
        Assumes data_points are sorted by timestamp and contain 'timestamp' (Unix),
        'lat', 'lon', 'gSpeed' (m/s), 'headMot' (degrees).
        """
        self.logger.log_debug(f"Analyzing trip data with {len(data_points)} points.")
        total_distance = 0.0 # meters
        total_speed_sum = 0.0 # m/s
        max_speed = 0.0 # m/s
        hard_braking_events = 0
        sharp_cornering_events = 0
        
        # Filter out zero speed points for average speed calculation
        speed_noise_threshold = self.settings_manager.get("speed_noise_threshold_mps") # Get from settings
        moving_speed_points = [dp['gSpeed'] for dp in data_points if dp['gSpeed'] > speed_noise_threshold]

        if not data_points:
            self.logger.log_debug("No data points for analysis, returning zeroed results.")
            return {
                "total_distance": 0.0,
                "duration": "0:00:00",
                "average_speed": 0.0,
                "max_speed": 0.0,
                "hard_braking_events": 0,
                "sharp_cornering_events": 0
            }

        first_timestamp = data_points[0]['timestamp']
        last_timestamp = data_points[-1]['timestamp']
        duration_seconds = last_timestamp - first_timestamp
        duration_timedelta = timedelta(seconds=duration_seconds)
        duration_str = str(duration_timedelta).split('.')[0]

        prev_dp = None
        for i, dp in enumerate(data_points):
            current_lat = dp['lat']
            current_lon = dp['lon']
            current_speed = dp['gSpeed'] # Already in m/s
            current_heading = dp['headMot']
            current_time = dp['timestamp']

            if current_speed > max_speed:
                max_speed = current_speed

            if prev_dp:
                # Calculate distance
                prev_lat = prev_dp['lat']
                prev_lon = prev_dp['lon']
                total_distance += haversine_distance(prev_lat, prev_lon, current_lat, current_lon)

                # Calculate acceleration for braking detection
                time_diff = current_time - prev_dp['timestamp']
                if time_diff > 0:
                    speed_diff = current_speed - prev_dp['gSpeed']
                    acceleration = speed_diff / time_diff # m/s^2
                    if acceleration < HARD_BRAKING_THRESHOLD_MPS2:
                        hard_braking_events += 1
                        self.logger.log_debug(f"Hard braking detected: Accel={acceleration:.2f} m/s^2 at {datetime.fromtimestamp(current_time).strftime('%H:%M:%S')}")

                    # Calculate angular velocity for cornering detection
                    # Ensure heading is within 0-360 before calculating difference
                    prev_heading = prev_dp['headMot'] % 360
                    current_heading_normalized = current_heading % 360

                    heading_diff = current_heading_normalized - prev_heading
                    # Normalize heading_diff to be between -180 and 180
                    if heading_diff > 180:
                        heading_diff -= 360
                    elif heading_diff < -180:
                        heading_diff += 360
                    
                    # Only check for cornering if moving
                    if current_speed > speed_noise_threshold: # Use speed_noise_threshold
                        angular_velocity_deg_per_sec = abs(heading_diff / time_diff) if time_diff > 0 else 0
                        if angular_velocity_deg_per_sec > SHARP_CORNERING_THRESHOLD_DEG_PER_SEC:
                            sharp_cornering_events += 1
                            self.logger.log_debug(f"Sharp cornering detected: Angular Vel={angular_velocity_deg_per_sec:.2f} deg/s at {datetime.fromtimestamp(current_time).strftime('%H:%M:%S')}")

            prev_dp = dp
        
        average_speed = sum(moving_speed_points) / len(moving_speed_points) if moving_speed_points else 0.0
        self.logger.log_debug(f"Trip analysis complete. Distance: {total_distance:.2f}m, Max Speed: {max_speed:.2f}m/s, Avg Speed: {average_speed:.2f}m/s, Braking Events: {hard_braking_events}, Cornering Events: {sharp_cornering_events}")

        return {
            "total_distance": total_distance,
            "duration": duration_str,
            "average_speed": average_speed,
            "max_speed": max_speed,
            "hard_braking_events": hard_braking_events,
            "sharp_cornering_events": sharp_cornering_events
        }

    def _open_analysis_trip_map(self):
        """Opens the generated map for the analyzed trip in the browser."""
        self.logger.log_debug("Attempting to open analysis trip map.")
        if self.current_analysis_map_path and os.path.exists(self.current_analysis_map_path):
            try:
                webbrowser.open_new_tab(f"file://{os.path.abspath(self.current_analysis_map_path)}")
                self.analysis_map_status_var.set("Trip map opened in browser.")
                self.logger.log_info("Analysis trip map opened in browser.")
            except Exception as e:
                messagebox.showerror("Error", f"Could not open map in browser: {e}")
                self.analysis_map_status_var.set(f"ERROR: Could not open map: {e}")
                self.logger.log_error(f"Could not open analysis trip map in browser: {e}", exc_info=True)
        else:
            messagebox.showwarning("No Map", "No map generated for analysis, or file not found.")
            self.analysis_map_status_var.set("No map to open. Analyze a trip first.")
            self.logger.log_warning("No analysis map to open or file not found.")


    def _create_log_file_map_widgets(self, parent):
        """Widgets for the new Log File Map tab."""
        self.logger.log_debug("Creating Log File Map widgets.")
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=0) # Control row (not expanding)
        parent.rowconfigure(1, weight=1) # Message row (expanding)

        control_frame = ttk.Frame(parent, padding=10)
        control_frame.grid(row=0, column=0, sticky="ew", pady=5)
        control_frame.columnconfigure(0, weight=1) # Label for file path
        control_frame.columnconfigure(1, weight=0) # Browse button
        control_frame.columnconfigure(2, weight=0) # Generate button
        control_frame.columnconfigure(3, weight=0) # Open button

        self.selected_log_file_path_var = tk.StringVar(value="No file selected.")
        ttk.Label(control_frame, textvariable=self.selected_log_file_path_var, bootstyle="info", wraplength=400).grid(row=0, column=0, sticky="w", padx=5, pady=5)

        self.browse_log_file_button = ttk.Button(control_frame, text="Browse Log File", command=self._load_log_file_map_browse, bootstyle="primary")
        self.browse_log_file_button.grid(row=0, column=1, padx=5, pady=5)

        self.generate_log_map_button = ttk.Button(control_frame, text="Generate Map", command=self._generate_log_map_action, bootstyle="success", state=DISABLED)
        self.generate_log_map_button.grid(row=0, column=2, padx=5, pady=5)

        self.open_generated_log_map_button = ttk.Button(control_frame, text="Open Generated Map", command=self._open_generated_log_map, bootstyle="info", state=DISABLED)
        self.open_generated_log_map_button.grid(row=0, column=3, padx=5, pady=5)

        self.log_map_status_label = ttk.Label(parent, text="Select a GPS log file (.csv or .jsonl) and click 'Generate Map'.",
                                              anchor=CENTER, justify=CENTER, wraplength=600, bootstyle="info")
        self.log_map_status_label.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

        self.log_map_generator = LogMapGenerator(self.logger)
        self.loaded_coordinates_for_map = None # To store coordinates after browsing, before generating
        self.logger.log_debug("Log File Map widgets created.")

    def _load_log_file_map_browse(self):
        """Callback for the 'Browse Log File' button in the Log File Map tab."""
        self.logger.log_debug("Browsing for log file for map generation.")
        filepath = filedialog.askopenfilename(
            title="Select GPS Log File",
            initialdir=self.settings_manager.get("log_directory"), # Start in the main log directory
            filetypes=[("GPS Log Files", "*.csv *.jsonl"), ("CSV files", "*.csv"), ("JSONL files", "*.jsonl"), ("All files", "*.*")]
        )
        if filepath:
            self.selected_log_file_path_var.set(os.path.basename(filepath))
            coordinates = self.log_map_generator.load_log_file(filepath)
            if coordinates:
                self.loaded_coordinates_for_map = coordinates
                self.generate_log_map_button.config(state=NORMAL)
                self.open_generated_log_map_button.config(state=DISABLED) # Disable until new map is generated
                self.log_map_status_label.config(text=f"File '{os.path.basename(filepath)}' loaded. Click 'Generate Map' to view.", bootstyle="info")
                self.logger.log_info(f"Log file {filepath} loaded for map generation.")
            else:
                self.loaded_coordinates_for_map = None
                self.generate_log_map_button.config(state=DISABLED)
                self.open_generated_log_map_button.config(state=DISABLED)
                self.log_map_status_label.config(text="Failed to load coordinates from selected file.", bootstyle="danger")
                self.logger.log_warning(f"Failed to load coordinates from {filepath} for map generation.")
        else:
            self.selected_log_file_path_var.set("No file selected.")
            self.loaded_coordinates_for_map = None
            self.generate_log_map_button.config(state=DISABLED)
            self.open_generated_log_map_button.config(state=DISABLED)
            self.log_map_status_label.config(text="Select a GPS log file (.csv or .jsonl) and click 'Generate Map'.", bootstyle="info")
            self.logger.log_debug("Log file selection cancelled for map generation.")


    def _generate_log_map_action(self):
        """Callback for the 'Generate Map' button."""
        self.logger.log_debug("Attempting to generate log map.")
        if self.loaded_coordinates_for_map:
            generated_path = self.log_map_generator.generate_map(self.loaded_coordinates_for_map)
            if generated_path:
                self.open_generated_log_map_button.config(state=NORMAL)
                self.log_map_status_label.config(text=f"Map generated successfully! Click 'Open Generated Map' to view.", bootstyle="success")
                self.logger.log_info(f"Log map generated successfully at: {generated_path}")
            else:
                self.open_generated_log_map_button.config(state="disabled")
                self.log_map_status_label.config(text="Failed to generate map.", bootstyle="danger")
                self.logger.log_error("Failed to generate log map.")
        else:
            messagebox.showwarning("No Data", "Please browse and load a log file first.")
            self.log_map_status_label.config(text="No log file data to generate map. Please browse a file.", bootstyle="warning")
            self.logger.log_warning("No data to generate log map.")

    def _open_generated_log_map(self):
        """Opens the last generated log map in the browser."""
        self.logger.log_debug("Attempting to open generated log map.")
        map_filepath = self.log_map_generator.get_last_generated_map_path()
        if map_filepath and os.path.exists(map_filepath):
            try:
                webbrowser.open_new_tab(f"file://{os.path.abspath(map_filepath)}")
                self.log_map_status_label.config(text="Generated map opened in browser.", bootstyle="info")
                self.logger.log_info("Generated log map opened in browser.")
            except Exception as e:
                messagebox.showerror("Error", f"Could not open map in browser: {e}")
                self.log_map_status_label.config(text=f"ERROR: Could not open map: {e}", bootstyle="danger")
                self.logger.log_error(f"Could not open generated map in browser: {e}", exc_info=True)
        else:
            messagebox.showwarning("No Map", "No map has been generated yet, or the file was moved/deleted.")
            self.log_map_status_label.config(text="No generated map to open.", bootstyle="warning")
            self.logger.log_warning("No generated map to open or file not found.")


    def _create_settings_widgets(self, parent):
        """Creates widgets for the Settings tab, including the offline playback buttons."""
        self.logger.log_debug("Creating Settings widgets.")
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=1) # Add a second column for side-by-side layout

        # GPS Connection Settings (now read-only display)
        gps_settings_frame = ttk.LabelFrame(parent, text="GPS Connection (Read-Only)", padding=10, bootstyle="primary")
        gps_settings_frame.grid(row=0, column=0, sticky="ew", pady=5, padx=5) # Placed in column 0, row 0
        gps_settings_frame.columnconfigure(1, weight=1)

        ttk.Label(gps_settings_frame, text="Serial Port:").grid(row=0, column=0, sticky="w", pady=2)
        self.port_label = ttk.Label(gps_settings_frame, text=self.settings_manager.get("port"), bootstyle="info")
        self.port_label.grid(row=0, column=1, sticky="ew", pady=2)

        ttk.Label(gps_settings_frame, text="Baud Rate:").grid(row=1, column=0, sticky="w", pady=2)
        self.baudrate_label = ttk.Label(gps_settings_frame, text=str(self.settings_manager.get("baudrate")), bootstyle="info")
        self.baudrate_label.grid(row=1, column=1, sticky="ew", pady=2)


        # Port Configuration (now read-only display)
        port_cfg_frame = ttk.LabelFrame(parent, text="Port Configuration (UART1) (Read-Only)", padding=10, bootstyle="primary")
        port_cfg_frame.grid(row=1, column=0, padx=5, pady=5, sticky="ew") # Placed below GPS Connection, still in column 0
        port_cfg_frame.columnconfigure(1, weight=1)

        ttk.Label(port_cfg_frame, text="Port ID:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.port_id_label = ttk.Label(port_cfg_frame, textvariable=self.port_id_var, bootstyle="info")
        self.port_id_label.grid(row=0, column=1, sticky="w", padx=5, pady=2)
        ttk.Label(port_cfg_frame, text="Mode:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        self.port_mode_label = ttk.Label(port_cfg_frame, textvariable=self.port_mode_var, bootstyle="info")
        self.port_mode_label.grid(row=1, column=1, sticky="w", padx=5, pady=2)
        ttk.Label(port_cfg_frame, text="Baud Rate:").grid(row=2, column=0, sticky="w", padx=5, pady=2)
        self.port_baudrate_label = ttk.Label(port_cfg_frame, textvariable=self.port_baudrate_var, bootstyle="info")
        self.port_baudrate_label.grid(row=2, column=1, sticky="w", padx=5, pady=2)
        ttk.Label(port_cfg_frame, text="In Protocols:").grid(row=3, column=0, sticky="w", padx=5, pady=2)
        self.in_protocol_label = ttk.Label(port_cfg_frame, textvariable=self.in_protocol_var, bootstyle="info")
        self.in_protocol_label.grid(row=3, column=1, sticky="w", padx=5, pady=2)
        ttk.Label(port_cfg_frame, text="Out Protocols:").grid(row=4, column=0, sticky="w", pady=2)
        self.out_protocol_label = ttk.Label(port_cfg_frame, textvariable=self.out_protocol_var, bootstyle="info")
        self.out_protocol_label.grid(row=4, column=1, sticky="w", pady=2)


        # Logging Settings
        log_settings_frame = ttk.LabelFrame(parent, text="Logging Options", padding=10, bootstyle="primary")
        log_settings_frame.grid(row=0, column=1, sticky="nsew", pady=5, padx=5, rowspan=2) # Placed in column 1, spanning 2 rows
        log_settings_frame.columnconfigure(1, weight=1) # Allow value column to expand

        self.log_nmea_var = tk.BooleanVar(value=self.settings_manager.get("log_nmea"))
        ttk.Checkbutton(log_settings_frame, text="Log Raw NMEA (to file)", variable=self.log_nmea_var).grid(row=0, column=0, columnspan=2, sticky="w", pady=2)

        self.log_json_var = tk.BooleanVar(value=self.settings_manager.get("log_json"))
        ttk.Checkbutton(log_settings_frame, text="Log GPS Data (JSONL)", variable=self.log_json_var).grid(row=1, column=0, columnspan=2, sticky="w", pady=2)

        self.log_csv_var = tk.BooleanVar(value=self.settings_manager.get("log_csv"))
        ttk.Checkbutton(log_settings_frame, text="Log GPS Data (CSV)", variable=self.log_csv_var).grid(row=2, column=0, columnspan=2, sticky="w", pady=2)

        self.display_nmea_console_var = tk.BooleanVar(value=self.settings_manager.get("display_nmea_console"))
        ttk.Checkbutton(log_settings_frame, text="Display NMEA Console", variable=self.display_nmea_console_var,
                        command=self._apply_display_nmea_console_setting).grid(row=3, column=0, columnspan=2, sticky="w", pady=2)

        self.console_output_enabled_var = tk.BooleanVar(value=self.settings_manager.get("console_output_enabled"))
        ttk.Checkbutton(log_settings_frame, text="Enable Console Output", variable=self.console_output_enabled_var,
                        command=self._apply_console_output_setting).grid(row=4, column=0, columnspan=2, sticky="w", pady=2)

        self.console_output_to_file_enabled_var = tk.BooleanVar(value=self.settings_manager.get("console_output_to_file_enabled"))
        ttk.Checkbutton(log_settings_frame, text="Log Console Output to File", variable=self.console_output_to_file_enabled_var,
                        command=self._apply_console_output_to_file_setting).grid(row=5, column=0, columnspan=2, sticky="w", pady=2)


        ttk.Label(log_settings_frame, text="Main Log Directory:").grid(row=6, column=0, sticky="w", pady=2)
        self.log_dir_var = tk.StringVar(value=self.settings_manager.get("log_directory"))
        self.log_dir_entry = ttk.Entry(log_settings_frame, textvariable=self.log_dir_var)
        self.log_dir_entry.grid(row=6, column=1, sticky="ew", pady=2)
        ttk.Button(log_settings_frame, text="Browse", command=self._browse_log_directory, bootstyle="secondary").grid(row=6, column=2, padx=2, pady=2)
        
        ttk.Label(log_settings_frame, text="Trip Log Directory:").grid(row=7, column=0, sticky="w", pady=2)
        self.trip_log_dir_var = tk.StringVar(value=self.settings_manager.get("trip_log_directory"))
        self.trip_log_dir_entry = ttk.Entry(log_settings_frame, textvariable=self.trip_log_dir_var) 
        self.trip_log_dir_entry.grid(row=7, column=1, sticky="ew", pady=2)
        ttk.Button(log_settings_frame, text="Browse", command=self._browse_trip_log_directory, bootstyle="secondary").grid(row=7, column=2, padx=2, pady=2)


        ttk.Label(log_settings_frame, text="Max Log Size (MB):").grid(row=8, column=0, sticky="w", pady=2)
        self.log_max_bytes_var = tk.DoubleVar(value=self.settings_manager.get("log_max_bytes_mb"))
        self.log_max_bytes_entry = ttk.Entry(log_settings_frame, textvariable=self.log_max_bytes_var)
        self.log_max_bytes_entry.grid(row=8, column=1, sticky="ew", pady=2)

        ttk.Label(log_settings_frame, text="Log Backups:").grid(row=9, column=0, sticky="w", pady=2)
        self.log_backup_count_var = tk.IntVar(value=self.settings_manager.get("log_backup_count"))
        self.log_backup_count_entry = ttk.Entry(log_settings_frame, textvariable=self.log_backup_count_var)
        self.log_backup_count_entry.grid(row=9, column=1, sticky="ew", pady=2)

        ttk.Label(log_settings_frame, text="Max Log Age (Days):").grid(row=10, column=0, sticky="w", pady=2)
        self.max_log_age_var = tk.IntVar(value=self.settings_manager.get("max_log_age_days"))
        self.max_log_age_entry = ttk.Entry(log_settings_frame, textvariable=self.max_log_age_var)
        self.max_log_age_entry.grid(row=10, column=1, sticky="ew", pady=2)

        ttk.Label(log_settings_frame, text="Speed Noise Threshold (m/s):").grid(row=11, column=0, sticky="w", pady=2)
        self.speed_noise_threshold_var = tk.DoubleVar(value=self.settings_manager.get("speed_noise_threshold_mps"))
        self.speed_noise_threshold_entry = ttk.Entry(log_settings_frame, textvariable=self.speed_noise_threshold_var)
        self.speed_noise_threshold_entry.grid(row=11, column=1, sticky="ew", pady=2)


        ttk.Button(log_settings_frame, text="Apply Logging Settings", command=self._apply_logging_settings, bootstyle="success").grid(row=12, column=0, columnspan=3, pady=5)
        ttk.Button(log_settings_frame, text="Open Main Log Directory", command=self._open_log_directory, bootstyle="info").grid(row=13, column=0, columnspan=3, pady=2)
        ttk.Button(log_settings_frame, text="Open Trip Log Directory", command=self._open_trip_log_directory, bootstyle="info").grid(row=14, column=0, columnspan=3, pady=2)


        # Theme Selection
        theme_frame = ttk.LabelFrame(parent, text="Theme", padding=10, bootstyle="primary")
        theme_frame.grid(row=2, column=0, sticky="ew", pady=5, padx=5) # Placed in row 2, column 0

        self.theme_var = tk.StringVar(value=self.settings_manager.get("theme"))
        themes = ttk.Style().theme_names()
        for theme_name in themes:
            ttk.Radiobutton(theme_frame, text=theme_name.capitalize(), variable=self.theme_var, value=theme_name,
                            command=self._apply_theme).pack(anchor=W, pady=1)

        # Unit Preference
        unit_preference_frame = ttk.LabelFrame(parent, text="Unit Preference", padding=10, bootstyle="primary")
        unit_preference_frame.grid(row=2, column=1, sticky="ew", pady=5, padx=5) # Placed in row 2, column 1
        
        self.unit_preference_var = tk.StringVar(value=self.settings_manager.get("unit_preference"))
        
        ttk.Radiobutton(unit_preference_frame, text="Metric (km/h, m, km)", variable=self.unit_preference_var, value="metric",
                        command=self._apply_unit_preference).pack(anchor=W, pady=1)
        ttk.Radiobutton(unit_preference_frame, text="Imperial (mph, ft, miles)", variable=self.unit_preference_var, value="imperial",
                        command=self._apply_unit_preference).pack(anchor=W, pady=1)


        # --- Offline Playback Settings ---
        offline_playback_frame = ttk.LabelFrame(parent, text="Offline Playback", padding=10, bootstyle="primary")
        offline_playback_frame.grid(row=3, column=0, columnspan=2, sticky="ew", pady=5, padx=5) # Placed in row 3, spanning both columns
        offline_playback_frame.columnconfigure(1, weight=1)

        self.offline_mode_checkbox = ttk.Checkbutton(offline_playback_frame, text="Enable Offline Mode",
                                                     variable=self.offline_mode_active_var,
                                                     command=self._handle_offline_mode_toggle)
        self.offline_mode_checkbox.grid(row=0, column=0, columnspan=3, sticky="w", pady=2)

        ttk.Label(offline_playback_frame, text="Log File:").grid(row=1, column=0, sticky="w", pady=2)
        self.offline_file_label = ttk.Label(offline_playback_frame, textvariable=self.offline_file_path_var, bootstyle="info", wraplength=300)
        self.offline_file_label.grid(row=1, column=1, sticky="ew", pady=2)
        self.browse_offline_file_button = ttk.Button(offline_playback_frame, text="Browse", command=self._load_offline_file_action, bootstyle="secondary")
        self.browse_offline_file_button.grid(row=1, column=2, padx=2, pady=2)

        playback_control_frame = ttk.Frame(offline_playback_frame)
        playback_control_frame.grid(row=2, column=0, columnspan=3, sticky="ew", pady=5)
        playback_control_frame.columnconfigure(0, weight=1)
        playback_control_frame.columnconfigure(1, weight=1)
        playback_control_frame.columnconfigure(2, weight=1)

        self.play_button = ttk.Button(playback_control_frame, text="Play", command=lambda: self.offline_playback_manager.start_playback(), bootstyle="success", state=DISABLED)
        self.play_button.grid(row=0, column=0, sticky="ew", padx=5)
        self.pause_button = ttk.Button(playback_control_frame, text="Pause", command=lambda: self.offline_playback_manager.pause_playback(), bootstyle="warning", state=DISABLED)
        self.pause_button.grid(row=0, column=1, sticky="ew", padx=5)
        self.stop_button = ttk.Button(playback_control_frame, text="Stop", command=lambda: self.offline_playback_manager.stop_playback(), bootstyle="danger", state=DISABLED)
        self.stop_button.grid(row=0, column=2, sticky="ew", padx=5)

        ttk.Label(offline_playback_frame, text="Playback Speed:").grid(row=3, column=0, sticky="w", pady=2)
        self.speed_slider = ttk.Scale(offline_playback_frame, from_=0.5, to=4.0, orient=HORIZONTAL,
                                      variable=self.playback_speed_var, command=self._update_speed_label)
        self.speed_slider.grid(row=3, column=1, sticky="ew", pady=2)
        self.speed_label = ttk.Label(offline_playback_frame, textvariable=self.playback_speed_var, bootstyle="info")
        self.speed_label.grid(row=3, column=2, sticky="w", padx=5, pady=2)
        self.playback_speed_var.set(1.0) # Set initial value for slider and label

        ttk.Label(offline_playback_frame, text="Progress:").grid(row=4, column=0, sticky="w", pady=2)
        ttk.Label(offline_playback_frame, textvariable=self.playback_progress_var, bootstyle="info").grid(row=4, column=1, columnspan=2, sticky="ew", pady=2)


        # Storage Information
        storage_info_frame = ttk.LabelFrame(parent, text="Storage Information", padding=10, bootstyle="primary")
        storage_info_frame.grid(row=4, column=0, columnspan=2, sticky="ew", pady=5, padx=5) # Placed in row 4, spanning both columns
        storage_info_frame.columnconfigure(1, weight=1)

        ttk.Label(storage_info_frame, text="Total Disk Space:").grid(row=0, column=0, sticky="w", pady=2)
        ttk.Label(storage_info_frame, textvariable=self.total_disk_space_var, bootstyle="info").grid(row=0, column=1, sticky="ew", pady=2)

        ttk.Label(storage_info_frame, text="Used Disk Space:").grid(row=1, column=0, sticky="w", pady=2)
        ttk.Label(storage_info_frame, textvariable=self.used_disk_space_var, bootstyle="info").grid(row=1, column=1, sticky="ew", pady=2)

        ttk.Label(storage_info_frame, text="Free Disk Space:").grid(row=2, column=0, sticky="w", pady=2)
        ttk.Label(storage_info_frame, textvariable=self.free_disk_space_var, bootstyle="info").grid(row=2, column=1, sticky="ew", pady=2)
        self.logger.log_debug("Settings widgets created.")


    def _update_speed_label(self, value):
        """Updates the speed label with the current slider value."""
        self.playback_speed_var.set(f"{float(value):.1f}")
        self.logger.log_debug(f"Playback speed label updated to: {value}")

    def _handle_offline_mode_toggle(self):
        """
        Callback for the 'Enable Offline Mode' checkbox.
        Manages the transition between live GPS and offline playback modes,
        including stopping/starting threads and updating UI button states.
        """
        is_offline = self.offline_mode_active_var.get()
        self.settings_manager.set("offline_mode_active", is_offline)
        self.settings_manager.save_settings()
        self.logger.log_info(f"Offline mode {'enabled' if is_offline else 'disabled'}.")

        if is_offline:
            # If switching TO offline mode:
            # 1. Stop live GPS thread
            self.stop_live_gps_event.set()
            if self.live_gps_thread and self.live_gps_thread.is_alive():
                self.live_gps_thread.join(timeout=1)
            self.logger.log_info("Live GPS thread stopped.")
            
            # 2. Update UI for offline mode (enables offline controls, disables live controls)
            self._toggle_offline_mode_ui(True)
            
            # 3. If a file is already loaded, start playback (or enable play button)
            if self.offline_playback_manager.loaded_data:
                self.offline_playback_manager.start_playback() # Automatically start if data is loaded
                self.logger.log_info("Offline playback started automatically.")
            else:
                self.offline_playback_manager.playback_status_var.set("No file loaded")
                self.logger.log_debug("No offline file loaded, playback not started.")

        else:
            # If switching FROM offline mode:
            # 1. Stop offline playback (this will also update its buttons to 'stopped' state)
            self.offline_playback_manager.stop_playback()
            self.logger.log_info("Offline playback stopped.")
            
            # 2. Update UI for live mode (disables offline controls, enables live controls)
            self._toggle_offline_mode_ui(False)

            # 3. Restart live GPS thread (only if ublox_gps is available)
            self.stop_live_gps_event.clear() # Clear event to allow thread to run
            if UBLOX_GPS_AVAILABLE:
                self.live_gps_thread = threading.Thread(target=self.data_handler.run, daemon=True)
                self.live_gps_thread.start()
                self.logger.log_info("Live GPS thread restarted.")
                # Reset live GPS connection status to trigger re-connection sequence
                self.data_handler.connected = False
                self.data_handler.system_info_fetched = False
            else:
                self.logger.log_warning("Cannot start live GPS thread: ublox_gps library not available.")
                self.status_label.config(text="ERROR: ublox_gps library not available. Live GPS disabled.", bootstyle="danger")


    def _toggle_offline_mode_ui(self, is_offline_mode):
        """
        Enables/disables UI elements based on offline mode status.
        This function is the single source of truth for UI element states
        when switching between live and offline modes.
        """
        self.logger.log_debug(f"Toggling offline mode UI to: {is_offline_mode}")

        # Live GPS related controls
        live_gps_controls = [
            self.port_label, self.baudrate_label, self.port_id_label,
            self.port_mode_label, self.port_baudrate_label, self.in_protocol_label,
            self.out_protocol_label
        ]
        for widget in live_gps_controls:
            widget.config(state=DISABLED if is_offline_mode else NORMAL)
        
        # Trip control buttons (only active in live mode)
        self.start_trip_button.config(state=DISABLED if is_offline_mode else NORMAL)
        # End trip button state depends on both offline mode and if a trip is active
        self.end_trip_button.config(state=DISABLED if is_offline_mode or not self.is_trip_active else NORMAL)


        # Offline playback specific controls (browse file, speed slider)
        offline_playback_controls = [
            self.browse_offline_file_button, self.speed_slider
        ]
        for widget in offline_playback_controls:
            widget.config(state=NORMAL if is_offline_mode else DISABLED)
        
        # Playback control buttons (Play, Pause, Stop)
        if is_offline_mode:
            # If in offline mode, enable/disable based on whether a file is loaded
            if self.offline_playback_manager.loaded_data:
                self.play_button.config(state=NORMAL)
                self.pause_button.config(state=DISABLED)
                self.stop_button.config(state=DISABLED)
            else:
                # No data loaded, all playback buttons disabled
                self.play_button.config(state=DISABLED)
                self.pause_button.config(state=DISABLED)
                self.stop_button.config(state=DISABLED)
        else:
            # If NOT in offline mode, all offline playback controls should be disabled.
            self.play_button.config(state=DISABLED)
            self.pause_button.config(state=DISABLED)
            self.stop_button.config(state=DISABLED)
        self.logger.log_debug("Offline mode UI toggled.")


    def _load_offline_file_action(self):
        """Callback for the 'Browse' button in offline playback settings."""
        self.logger.log_debug("Browsing for offline playback file.")
        filepath = filedialog.askopenfilename(
            title="Select GPS Log File for Playback",
            initialdir=self.settings_manager.get("log_directory"),
            filetypes=[("GPS Log Files", "*.csv *.jsonl"), ("CSV files", "*.csv"), ("JSONL files", "*.jsonl"), ("All files", "*.*")]
        )
        if filepath:
            self.offline_file_path_var.set(os.path.basename(filepath))
            self.settings_manager.set("offline_log_filepath", filepath)
            self.settings_manager.save_settings()
            self.offline_playback_manager.load_file(filepath)
            # Re-enable/disable playback controls based on loaded data
            self._toggle_offline_mode_ui(self.offline_mode_active_var.get())
            self.logger.log_info(f"Offline playback file loaded: {filepath}")
        else:
            self.offline_file_path_var.set("No file selected.")
            self.settings_manager.set("offline_log_filepath", "")
            self.settings_manager.save_settings()
            self.offline_playback_manager.loaded_data = [] # Clear loaded data
            self.offline_playback_manager.total_data_points = 0
            self.offline_playback_manager.playback_status_var.set("No file loaded")
            self.offline_playback_manager.playback_progress_var.set("0%")
            self._toggle_offline_mode_ui(self.offline_mode_active_var.get()) # Update UI state
            self.logger.log_debug("Offline playback file selection cancelled.")


    def _browse_log_directory(self):
        """Opens a directory chooser dialog for the main log path."""
        self.logger.log_debug("Browsing for main log directory.")
        selected_dir = filedialog.askdirectory(initialdir=self.log_dir_var.get())
        if selected_dir:
            self.log_dir_var.set(selected_dir)
            self.logger.log_info(f"Main log directory set to: {selected_dir}")

    def _browse_trip_log_directory(self):
        """Opens a directory chooser dialog for the trip log path."""
        self.logger.log_debug("Browsing for trip log directory.")
        selected_dir = filedialog.askdirectory(initialdir=self.trip_log_dir_var.get())
        if selected_dir:
            self.trip_log_dir_var.set(selected_dir)
            self.logger.log_info(f"Trip log directory set to: {selected_dir}")


    def _apply_logging_settings(self):
        """Applies logging settings."""
        self.logger.log_debug("Applying logging settings.")
        self.settings_manager.set("log_nmea", self.log_nmea_var.get())
        self.settings_manager.set("log_json", self.log_json_var.get())
        self.settings_manager.set("log_csv", self.log_csv_var.get())
        
        # New logging settings
        new_log_dir = self.log_dir_var.get()
        new_trip_log_dir = self.trip_log_dir_var.get() # Get new trip log directory
        new_max_bytes_mb = self.log_max_bytes_var.get()
        new_backup_count = self.log_backup_count_var.get()
        new_max_log_age_days = self.max_log_age_var.get()
        new_speed_noise_threshold = self.speed_noise_threshold_var.get() # Get new threshold

        try:
            new_max_bytes_mb = float(new_max_bytes_mb)
            new_backup_count = int(new_backup_count)
            new_max_log_age_days = int(new_max_log_age_days)
            new_speed_noise_threshold = float(new_speed_noise_threshold) # Convert to float
            if new_max_bytes_mb <= 0 or new_backup_count < 0 or new_max_log_age_days < 0 or new_speed_noise_threshold < 0:
                raise ValueError("Values must be positive or non-negative.")
        except ValueError:
            messagebox.showerror("Invalid Input", "Log settings (size, backups, age, speed threshold) must be valid positive numbers.")
            self.logger.log_error("Invalid input for log settings (size, backups, age, speed threshold).", exc_info=True)
            return

        self.settings_manager.set("log_directory", new_log_dir)
        self.settings_manager.set("trip_log_directory", new_trip_log_dir) # Save new trip log directory
        self.settings_manager.set("log_max_bytes_mb", new_max_bytes_mb)
        self.settings_manager.set("log_backup_count", new_backup_count)
        self.settings_manager.set("max_log_age_days", new_max_log_age_days)
        self.settings_manager.set("speed_noise_threshold_mps", new_speed_noise_threshold) # Save new threshold

        self.settings_manager.save_settings()
        messagebox.showinfo("Settings Applied", "Logging settings applied. Some changes (Log Directory, Max Log Size, Log Backups) may require an application restart to take full effect.")
        self.logger.log_info("Logging settings applied.")

    def _apply_display_nmea_console_setting(self):
        """Applies the NMEA console display setting."""
        self.settings_manager.set("display_nmea_console", self.display_nmea_console_var.get())
        self.settings_manager.save_settings()
        self.logger.log_info(f"NMEA console display {'enabled' if self.display_nmea_console_var.get() else 'disabled'}.")

    def _apply_console_output_setting(self):
        """Applies the console output setting and reconfigures the console logger."""
        self.settings_manager.set("console_output_enabled", self.console_output_enabled_var.get())
        self.settings_manager.save_settings()
        self.logger._setup_console_handler() # Re-setup the console logger based on the new setting
        self.logger.log_info(f"Console output {'enabled' if self.console_output_enabled_var.get() else 'disabled'}.")

    def _apply_console_output_to_file_setting(self):
        """Applies the console output to file setting and reconfigures the console logger."""
        self.settings_manager.set("console_output_to_file_enabled", self.console_output_to_file_enabled_var.get())
        self.settings_manager.save_settings()
        self.logger._setup_console_handler() # Re-setup the console logger based on the new setting
        self.logger.log_info(f"Console output to file {'enabled' if self.console_output_to_file_enabled_var.get() else 'disabled'}.")

    def _apply_unit_preference(self):
        """Applies the selected unit preference and updates the UI."""
        selected_unit = self.unit_preference_var.get()
        self.settings_manager.set("unit_preference", selected_unit)
        self.settings_manager.save_settings()
        self.logger.log_info(f"Unit preference set to: {selected_unit}")
        self.update_ui() # Force UI update to reflect new units

    def _open_log_directory(self):
        """Opens the main log directory in the file explorer using subprocess.run for better error handling."""
        log_path = os.path.abspath(self.settings_manager.get("log_directory"))
        self._open_directory(log_path, "Main Log Directory")

    def _open_trip_log_directory(self):
        """Opens the trip log directory in the file explorer."""
        trip_log_path = os.path.abspath(self.settings_manager.get("trip_log_directory"))
        self._open_directory(trip_log_path, "Trip Log Directory")

    def _open_directory(self, path, name):
        """Helper function to open a directory in the file explorer."""
        self.logger.log_debug(f"Attempting to open directory: {path} ({name})")
        if not os.path.exists(path):
            messagebox.showwarning("Directory Not Found", f"The {name} '{path}' does not exist.")
            self.logger.log_warning(f"{name} '{path}' not found.")
            return
        try:
            if sys.platform.startswith('linux'):
                subprocess.run(["xdg-open", path], check=True)
            elif sys.platform.startswith('win'):
                # On Windows, 'start' command is used, shell=True is necessary
                subprocess.run(["start", "", path], shell=True, check=True)
            elif sys.platform.startswith('darwin'):
                # On macOS, 'open' command is used
                subprocess.run(["open", path], check=True)
            else:
                messagebox.showwarning("Unsupported OS", f"Opening directories is not supported on your OS: {sys.platform}")
                self.logger.log_warning(f"Opening directories not supported on OS: {sys.platform}")
                return

            self.status_label.config(text=f"Opened {name}: {path}", bootstyle="info")
            self.logger.log_info(f"Opened {name}: {path}")
        except FileNotFoundError:
            messagebox.showerror("Error", "Command not found to open directory. Ensure 'xdg-open' (Linux), 'start' (Windows), or 'open' (macOS) is available.")
            self.status_label.config(text="ERROR: Command to open directory not found.", bootstyle="danger")
            self.logger.log_error("Command to open directory not found.", exc_info=True)
        except subprocess.CalledProcessError as e:
            messagebox.showerror("Error", f"Failed to open {name} '{path}': {e}\nStderr: {e.stderr.decode() if e.stderr else 'N/A'}")
            self.status_label.config(text=f"ERROR: Failed to open {name}: {e}", bootstyle="danger")
            self.logger.log_error(f"Failed to open {name}: {e}", exc_info=True)
        except Exception as e:
            messagebox.showerror("Error", f"An unexpected error occurred while trying to open '{path}': {e}")
            self.status_label.config(text=f"ERROR: Unexpected error opening {name}: {e}", bootstyle="danger")
            self.logger.log_error(f"Unexpected error opening {name}: {e}", exc_info=True)

    def _apply_theme(self):
        """Applies the selected ttkbootstrap theme."""
        self.logger.log_debug("Applying theme.")
        selected_theme = self.theme_var.get()
        try:
            ttk.Style(theme=selected_theme)
            self.settings_manager.set("theme", selected_theme)
            self.settings_manager.save_settings()
            # Re-render plots to apply new theme colors
            self.update_ui()
            self.logger.log_info(f"Applied theme: {selected_theme}")
        except Exception as e:
            messagebox.showerror("Theme Error", f"Failed to apply theme '{selected_theme}': {e}")
            self.logger.log_error(f"Failed to apply theme '{selected_theme}': {e}", exc_info=True)

    def _setup_data_sources(self):
        """Sets up both live GPS and offline playback data sources."""
        self.logger.log_debug("Setting up data sources.")
        
        # Check if ublox_gps library is available before initializing GpsDataHandler
        if not UBLOX_GPS_AVAILABLE:
            self.logger.warning("ublox_gps library not available. Live GPS functionality will be disabled.")
            self.status_label.config(text="WARNING: ublox_gps library not found. Live GPS disabled.", bootstyle="warning")
            # Disable live GPS related UI elements if the library is not available
            self.start_trip_button.config(state=DISABLED)
            # You might want to disable other live GPS related UI elements here too
            # e.g., self.connect_button.config(state=DISABLED) if you had one.
            # However, for now, the _toggle_offline_mode_ui handles this based on the offline_mode_active_var.

        self.data_handler = GpsDataHandler(
            self.settings_manager.get("port"),
            self.settings_manager.get("baudrate"),
            self.stop_live_gps_event,
            self.data_queue,
            self.logger,
            self.nmea_display_queue
        )
        self.logger.log_debug("GpsDataHandler instance created.")

        # Start the appropriate data source based on initial settings
        if self.offline_mode_active_var.get():
            self.stop_live_gps_event.set() # Ensure live GPS is stopped
            self.logger.log_info("Starting in offline mode.")
        else:
            self.stop_playback_event.set() # Ensure playback is stopped
            if UBLOX_GPS_AVAILABLE:
                self.live_gps_thread = threading.Thread(target=self.data_handler.run, daemon=True)
                self.live_gps_thread.start()
                self.logger.log_info("Starting in live GPS mode.")
            else:
                self.logger.log_warning("Cannot start live GPS thread: ublox_gps library not available.")
                self.status_label.config(text="ERROR: ublox_gps library not available. Live GPS disabled.", bootstyle="danger")


        self._check_for_gps_data() # Start checking for data from the unified queue
        self.logger.log_debug("Data sources setup complete.")

    def _get_plot_colors(self):
        """Determines appropriate plot background and text colors based on the current theme."""
        current_theme = self.settings_manager.get("theme").lower()
        if "dark" in current_theme or "solar" in current_theme or "cyborg" in current_theme or "superhero" in current_theme:
            return {"bg": "#2b2b2b", "text": "#f0f0f0", "grid": "#444444"} # Dark background, light text
        else:
            return {"bg": "white", "text": "black", "grid": "#cccccc"} # Light background, dark text

    def _setup_plot(self):
        """Initializes the matplotlib plot for track points."""
        self.logger.log_debug("Setting up Matplotlib track plot.")
        colors = self._get_plot_colors()
        self.fig, self.ax = plt.subplots(figsize=(8, 6), facecolor=colors["bg"])
        self.line, = self.ax.plot([], [], 'r-o') # Red line with circles
        self.ax.set_title("GPS Track", color=colors["text"])
        self.ax.set_xlabel("Longitude", color=colors["text"])
        self.ax.set_ylabel("Latitude", color=colors["text"])
        self.ax.set_facecolor(colors["bg"])
        self.ax.tick_params(axis='x', colors=colors["text"])
        self.ax.tick_params(axis='y', colors=colors["text"])
        self.ax.grid(True, color=colors["grid"])

        self.canvas = FigureCanvasTkAgg(self.fig, master=self.map_frame)
        self.canvas_widget = self.canvas.get_tk_widget()
        # self.canvas_widget.pack(side=TOP, fill=BOTH, expand=True) # Initially hidden or packed on map tab

        # toolbar = NavigationToolbar2Tk(self.canvas, self.map_frame)
        # toolbar.update()
        # self.canvas_widget.pack(side=TOP, fill=BOTH, expand=True)
        self.logger.log_debug("Matplotlib track plot setup complete.")

    def _update_plot(self):
        """Updates the matplotlib track plot with new data."""
        self.logger.log_debug("Updating Matplotlib track plot.")
        if self.track_points:
            lats = [p[0] for p in self.track_points]
            lons = [p[1] for p in self.track_points]
            self.line.set_data(lons, lats)
            self.ax.relim()
            self.ax.autoscale_view()
            self.canvas.draw_idle()
            self.logger.log_debug(f"Track plot updated with {len(self.track_points)} points.")

    def _generate_folium_map(self):
        """Generates an HTML map using Folium and updates the HTMLLabel."""
        self.logger.log_debug("Generating Folium map.")
        if not self.track_points:
            # If no track points, try to use current GPS data for initial map center
            if 'lat' in self.current_gps_data and 'lon' in self.current_gps_data and \
               not math.isnan(self.current_gps_data['lat']) and not math.isnan(self.current_gps_data['lon']):
                initial_lat = self.current_gps_data['lat']
                initial_lon = self.current_gps_data['lon']
                self.logger.log_debug(f"Using current GPS data ({initial_lat:.6f}, {initial_lon:.6f}) for initial map center.")
            else:
                initial_lat, initial_lon = 0, 0 # Default to 0,0 if no data yet
                self.map_status_label.config(text="Waiting for GPS data to generate map...", bootstyle="info")
                self.open_map_button.config(state=DISABLED) # Disable button until map is ready
                self.logger.log_debug("No GPS data for map, setting default center.")
                return

        else:
            initial_lat, initial_lon = self.track_points[-1] # Center on last known position
            self.logger.log_debug(f"Using last track point ({initial_lat:.6f}, {initial_lon:.6f}) for map center.")

        # Create a Folium map centered at the last known position
        import folium # Import folium here to ensure it's loaded when needed
        m = folium.Map(location=[initial_lat, initial_lon], zoom_start=15)

        # Add track points as a PolyLine
        if len(self.track_points) > 1:
            folium.PolyLine(self.track_points, color="blue", weight=2.5, opacity=1).add_to(m)
            self.logger.log_debug(f"Added {len(self.track_points)} track points to Folium map.")

        # Add markers for geofences
        for gf in self.geofences:
            folium.Circle(
                location=[gf['latitude'], gf['longitude']],
                radius=gf['radius'],
                color='red',
                fill=True,
                fill_color='red',
                fill_opacity=0.2,
                tooltip=f"{gf['name']} ({gf['radius']}m)"
            ).add_to(m)
            folium.Marker(
                location=[gf['latitude'], gf['longitude']],
                popup=f"Current Position<br>Lat: {gf['latitude']:.4f}<br>Lon: {gf['longitude']:.4f}<br>Radius: {gf['radius']:.2f}m",
                icon=folium.Icon(color="red", icon="info-sign")
            ).add_to(m)
            self.logger.log_debug(f"Added geofence '{gf['name']}' to Folium map.")

        # Add current position marker
        if 'lat' in self.current_gps_data and 'lon' in self.current_gps_data and \
           not math.isnan(self.current_gps_data['lat']) and not math.isnan(self.current_gps_data['lon']):
            current_lat = self.current_gps_data['lat']
            current_lon = self.current_gps_data['lon']
            folium.Marker(
                location=[current_lat, current_lon],
                popup=f"Current Position<br>Lat: {current_lat:.6f}<br>Lon: {current_lon:.6f}",
                icon=folium.Icon(color="green", icon="pushpin")
            ).add_to(m)
            self.logger.log_debug("Added current position marker to Folium map.")

        # Save map to HTML file
        map_filepath = os.path.abspath(MAP_HTML_FILE)
        try:
            m.save(map_filepath)
            self.map_status_label.config(text=f"Map generated at: {map_filepath}\nClick 'Open Map in Browser' to view.", bootstyle="success")
            self.open_map_button.config(state=NORMAL) # Enable button once map is generated
            self.logger.log_info(f"Map generated at: {map_filepath}")
        except Exception as e:
            self.map_status_label.config(text=f"ERROR: Could not save map file: {e}", bootstyle="danger")
            self.open_map_button.config(state=DISABLED) # Keep button disabled on error
            self.logger.log_error(f"Could not save map file: {e}", exc_info=True)


    def _check_geofence(self):
        """Checks if current position is inside any defined geofence."""
        if not self.geofences or 'lat' not in self.current_gps_data or 'lon' not in self.current_gps_data:
            self.logger.log_debug("Skipping geofence check: no geofences or no current GPS data.")
            return

        current_lat = self.current_gps_data['lat']
        current_lon = self.current_gps_data['lon']

        if math.isnan(current_lat) or math.isnan(current_lon):
            self.logger.log_debug("Skipping geofence check: invalid current GPS coordinates.")
            return # Cannot check geofence with invalid coordinates

        geofence_alert_triggered = False
        for gf in self.geofences:
            gf_lat = gf['latitude']
            gf_lon = gf['longitude']
            gf_radius = gf['radius']

            # Calculate distance using Haversine formula (re-using the utility function)
            distance = haversine_distance(current_lat, current_lon, gf_lat, gf_lon)

            if distance <= gf_radius:
                self.status_label.config(text=f"ALERT: Entered geofence '{gf['name']}'!", bootstyle="danger")
                self.logger.log_warning(f"Entered geofence: {gf['name']}")
                geofence_alert_triggered = True
                # messagebox.showinfo("Geofence Alert", f"You have entered the geofence: {gf['name']}")
                break # Alert for one geofence is enough

        if not geofence_alert_triggered:
            self.status_label.config(text="No geofence alerts.", bootstyle="info")
        self.logger.log_debug("Geofence check completed.")


    def _start_trip(self):
        """
        Starts a new trip, resetting metrics and enabling end button.
        New timestamped CSV and JSONL log files are created specifically for this trip.
        """
        self.logger.log_debug("Attempting to start trip.")
        if self.is_trip_active:
            messagebox.showwarning("Trip Already Active", "A trip is already in progress.")
            self.logger.log_warning("Attempted to start trip, but a trip is already active.")
            return

        if 'lat' not in self.current_gps_data or math.isnan(self.current_gps_data['lat']):
            messagebox.showwarning("No GPS Data", "Cannot start trip without valid GPS data.")
            self.logger.log_warning("Cannot start trip without valid GPS data.")
            return

        self.is_trip_active = True
        self.current_trip_start_time = datetime.now()
        self.current_trip_start_lat_lon = (self.current_gps_data['lat'], self.current_gps_data['lon'])
        self.current_trip_max_speed = 0.0 # Stored in m/s internally
        self.current_trip_distance = 0.0 # meters (base unit)
        self.last_lat_lon_for_distance = (self.current_gps_data['lat'], self.current_gps_data['lon'])

        # --- Create new trip log files with current date and time ---
        timestamp_str = self.current_trip_start_time.strftime("%Y%m%d_%H%M%S")
        trip_log_dir = self.settings_manager.get("trip_log_directory")
        os.makedirs(trip_log_dir, exist_ok=True) # Ensure directory exists
        self.logger.log_debug(f"Trip log directory ensured: {trip_log_dir}")

        trip_csv_filepath = os.path.join(trip_log_dir, f"trip_{timestamp_str}.csv")
        trip_jsonl_filepath = os.path.join(trip_log_dir, f"trip_{timestamp_str}.jsonl")

        # Convert to absolute paths before storing
        absolute_trip_csv_filepath = os.path.abspath(trip_csv_filepath)
        absolute_trip_jsonl_filepath = os.path.abspath(trip_jsonl_filepath)
        self.logger.log_debug(f"Trip log file paths: CSV={absolute_trip_csv_filepath}, JSONL={absolute_trip_jsonl_filepath}")

        try:
            # Open in 'w' mode to create new files and ensure no old data accumulation
            self.trip_csv_file_obj = open(absolute_trip_csv_filepath, 'w', newline='')
            self.trip_csv_writer_obj = csv.writer(self.trip_csv_file_obj)
            # Write CSV header for the new trip file
            header = [
                "Timestamp", "Latitude", "Longitude", "Altitude (MSL)",
                "Speed (m/s)", "Heading (deg)", "Num SV", "Fix Type",
                "PDOP", "HDOP", "VDOP"
            ]
            self.trip_csv_writer_obj.writerow(header)
            self.trip_csv_file_obj.flush()
            self.logger.log_info(f"New trip CSV log created: {absolute_trip_csv_filepath}")

            # Open in 'w' mode to create new files and ensure no old data accumulation
            self.trip_jsonl_file_obj = open(absolute_trip_jsonl_filepath, 'w')
            self.logger.log_info(f"New trip JSONL log created: {absolute_trip_jsonl_filepath}")

        except Exception as e:
            messagebox.showerror("Log File Error", f"Could not create trip log files: {e}")
            self.logger.log_error(f"Could not create trip log files: {e}", exc_info=True)
            # If logging fails, revert trip start
            self.is_trip_active = False
            self.current_trip_start_time = None
            self.current_trip_start_lat_lon = None
            if self.trip_csv_file_obj: self.trip_csv_file_obj.close()
            if self.trip_jsonl_file_obj: self.trip_jsonl_file_obj.close()
            self.trip_csv_file_obj = None
            self.trip_csv_writer_obj = None
            self.trip_jsonl_file_obj = None
            return

        self.start_trip_button.config(state=DISABLED)
        self.end_trip_button.config(state=NORMAL)
        self.status_label.config(text="Trip started!", bootstyle="success")
        self.logger.log_info("Trip started.")
        self.update_ui() # Force UI update to show initial trip metrics

    def _end_trip(self):
        """
        Ends the current trip, calculates summary, saves to history, and closes log files.
        The trip-specific log files are closed here.
        """
        self.logger.log_debug("Attempting to end trip.")
        if not self.is_trip_active:
            messagebox.showwarning("No Trip Active", "No trip is currently in progress.")
            self.logger.log_warning("Attempted to end trip, but no trip is active.")
            return

        self.is_trip_active = False
        end_time = datetime.now()
        
        # Ensure we have a valid start time for duration calculation
        if self.current_trip_start_time:
            duration = end_time - self.current_trip_start_time
            duration_str = str(duration).split('.')[0] # Remove microseconds
        else:
            duration_str = "N/A"
        self.logger.log_debug(f"Trip duration: {duration_str}")

        # Convert distance and max speed to preferred units for storage in trip history
        unit_preference = self.settings_manager.get("unit_preference")
        
        distance_val, distance_unit = self._convert_distance(self.current_trip_distance, unit_preference)
        max_speed_val, max_speed_unit = self._convert_speed(self.current_trip_max_speed, unit_preference, output_unit_only=True) # Get speed in m/s or ft/s

        trip_summary = {
            "start_time": self.current_trip_start_time.strftime("%Y-%m-%d %H:%M:%S") if self.current_trip_start_time else "N/A",
            "end_time": end_time.strftime("%Y-%m-%d %H:%M:%S"),
            "duration": duration_str,
            "distance": round(distance_val, 2),
            "distance_unit": distance_unit,
            "max_speed": round(max_speed_val, 2),
            "max_speed_unit": max_speed_unit,
            "csv_path": self.trip_csv_file_obj.name if self.trip_csv_file_obj else "", # Store the path
            "jsonl_path": self.trip_jsonl_file_obj.name if self.trip_jsonl_file_obj else "" # Store the path
        }
        self.trip_history.append(trip_summary)
        self.settings_manager.set("trip_history", self.trip_history)
        self.settings_manager.save_settings()
        self.logger.log_info(f"Trip summary saved: {trip_summary}")

        # --- Close trip log files ---
        if self.trip_csv_file_obj and not self.trip_csv_file_obj.closed:
            self.trip_csv_file_obj.close()
            self.logger.log_info("Trip CSV log file closed.")
        if self.trip_jsonl_file_obj and not self.trip_jsonl_file_obj.closed:
            self.trip_jsonl_file_obj.close()
            self.logger.log_info("Trip JSONL log file closed.")
        
        self.trip_csv_file_obj = None
        self.trip_csv_writer_obj = None
        self.trip_jsonl_file_obj = None

        self.start_trip_button.config(state=NORMAL)
        self.end_trip_button.config(state=DISABLED)
        self.status_label.config(text="Trip ended. Summary saved.", bootstyle="success")
        self.logger.log_info(f"Trip ended. Summary: {trip_summary}")
        self.update_ui() # Force UI update to clear current trip metrics and update history tab

    def _check_for_gps_data(self):
        """Checks the queue for new GPS data and updates the UI."""
        self.logger.log_debug("Checking for new GPS data in queue.")
        try:
            while True:
                data = self.data_queue.get_nowait()
                self._process_gps_data(data)
        except queue.Empty:
            pass

        # Check for NMEA data for display
        if self.settings_manager.get("display_nmea_console"):
            try:
                while True:
                    nmea_line = self.nmea_display_queue.get_nowait()
                    self.nmea_text.config(state="normal")
                    self.nmea_text.insert(END, nmea_line + "\n")
                    # Limit the number of lines
                    num_lines = int(self.nmea_text.index('end-1c').split('.')[0])
                    if num_lines > MAX_NMEA_LINES_DISPLAY:
                        self.nmea_text.delete(1.0, f"{num_lines - MAX_NMEA_LINES_DISPLAY + 1}.0")
                    self.nmea_text.see(END) # Auto-scroll to bottom
                    self.nmea_text.config(state="disabled")
            except queue.Empty:
                pass


        # Check for status messages from the logger
        try:
            while True:
                log_record = self.logger.queue.get_nowait()
                # Ensure log_record is a LogRecord object
                if isinstance(log_record, logging.LogRecord):
                    # Get the formatter from DataLogger's console_logger's first handler
                    # This assumes DataLogger's console_logger has at least one handler with a formatter
                    if self.logger.console_logger.handlers:
                        formatter = self.logger.console_logger.handlers[0].formatter
                        formatted_message = formatter.format(log_record)
                    else:
                        # Fallback if no handler or formatter found
                        formatted_message = log_record.getMessage() # Get raw message if no formatter
                        # Using print to stderr to avoid potential recursion if logger itself is failing
                        print("WARNING: DataLogger console_logger has no handlers for formatting.", file=sys.stderr)
                else:
                    # If it's already a string (e.g., if DataLogger puts formatted strings directly)
                    formatted_message = str(log_record)
                
                self.status_label.config(text=formatted_message, bootstyle="warning")
        except queue.Empty:
            pass

        self.update_id = self.after(DATA_FETCH_INTERVAL_MS, self._check_for_gps_data)
        self.logger.log_debug(f"Scheduled next GPS data check in {DATA_FETCH_INTERVAL_MS} ms.")

    def _process_gps_data(self, data):
        """Processes received GPS data and updates relevant UI elements."""
        self.logger.log_debug(f"Processing GPS data: {data.keys()}")
        # Handle system info updates (including port settings and comm status)
        if "sw_version" in data:
            self._update_system_info_ui(data) # Call new helper for system info
            self.logger.log_debug("System info updated.")
            return # This data is not current GPS position, so return early

        # Handle status messages
        if "status" in data:
            # Display status message in the UI.
            # GpsDataHandler already logs these errors/status messages,
            # so we don't need to re-log them here to avoid a feedback loop.
            self.status_label.config(text=data["status"], bootstyle="info")
            return # This is a status message, not GPS data

        # If it's actual GPS data
        self.current_gps_data = data
        
        # --- Update trip metrics if trip is active and log to trip files ---
        if self.is_trip_active:
            current_lat = data.get('lat')
            current_lon = data.get('lon')
            
            # Retrieve raw gSpeed (which is in mm/s from the ublox_gps library)
            # For offline playback, gSpeed is already converted to m/s by _parse_jsonl_log or _parse_csv_log
            # For live data, gSpeed is mm/s, so conversion is needed here for trip calculations.
            speed_mmps_raw = data.get('gSpeed', float('nan'))
            
            # Check if gSpeed is already in m/s (from offline playback) or still in mm/s (from live GPS)
            # A simple heuristic: if speed is very large, assume it's already m/s.
            # Otherwise, assume it's mm/s and convert.
            # A more robust solution would involve a flag in the data or knowing the source.
            if speed_mmps_raw > 1000: # Arbitrary threshold, assuming typical speeds won't exceed 1000 m/s
                current_speed_mps = speed_mmps_raw / 1000.0 if not math.isnan(speed_mmps_raw) else float('nan')
            else:
                current_speed_mps = speed_mmps_raw # Assume it's already m/s from offline data


            if current_lat is not None and current_lon is not None and \
               not math.isnan(current_lat) and not math.isnan(current_lon):
                
                # Update max speed
                if not math.isnan(current_speed_mps) and current_speed_mps > self.current_trip_max_speed:
                    self.current_trip_max_speed = current_speed_mps

                # Calculate distance if we have a previous point
                if self.last_lat_lon_for_distance:
                    prev_lat, prev_lon = self.last_lat_lon_for_distance
                    if not math.isnan(prev_lat) and not math.isnan(prev_lon):
                        segment_distance = haversine_distance(prev_lat, prev_lon, current_lat, current_lon)
                        self.current_trip_distance += segment_distance
                self.last_lat_lon_for_distance = (current_lat, current_lon)

                # Log to trip CSV file (opened in _start_trip)
                if self.trip_csv_writer_obj:
                    timestamp = datetime.now().isoformat()
                    row = [
                        timestamp,
                        format_coord(data.get('lat', float('nan'))),
                        format_coord(data.get('lon', float('nan'))),
                        format_value(data.get('hMSL', float('nan'))),
                        format_value(current_speed_mps, 2), # Log speed in m/s
                        format_value(data.get('headMot', float('nan'))),
                        data.get('numSV', 'N/A'),
                        data.get('fixType', 'N/A'),
                        format_value(data.get('pDOP', float('nan'))),
                        format_value(data.get('hDOP', float('nan'))),
                        format_value(data.get('vDOP', float('nan')))
                    ]
                    self.trip_csv_writer_obj.writerow(row)
                    self.trip_csv_file_obj.flush()
                    self.logger.log_debug("Logged data to trip CSV.")

                # Log to trip JSONL file (opened in _start_trip)
                if self.trip_jsonl_file_obj:
                    timestamp = datetime.now().isoformat()
                    # For JSONL, log the data as received (gSpeed in mm/s from live, or m/s from offline)
                    log_entry = {"timestamp": timestamp, "data": data} 
                    self.trip_jsonl_file_obj.write(json.dumps(log_entry) + '\n')
                    self.trip_jsonl_file_obj.flush()
                    self.logger.log_debug("Logged data to trip JSONL.")


        # Schedule a throttled UI update
        self._schedule_throttled_ui_update()
        
        self._check_geofence()

        # Add to track points for plotting
        lat = data.get('lat')
        lon = data.get('lon')
        if lat is not None and lon is not None and not math.isnan(lat) and not math.isnan(lon):
            self.track_points.append((lat, lon))
            if len(self.track_points) > self.max_track_points:
                self.track_points.pop(0) # Remove oldest point
            self.logger.log_debug(f"Track points updated, current count: {len(self.track_points)}")

            # Add to trend data history
            current_time_s = time.time() # Use raw time for x-axis for simplicity
            
            # Determine speed for trend plot (already in m/s if from offline, convert if from live)
            speed_for_trend = data.get('gSpeed', float('nan'))
            if self.offline_mode_active_var.get():
                # If in offline mode, gSpeed is already m/s from _parse_jsonl_log or _parse_csv_log
                speed_mps_for_trend = speed_for_trend
            else:
                # If in live mode, gSpeed is mm/s from ublox_gps, convert to m/s
                speed_mps_for_trend = speed_for_trend / 1000.0 if not math.isnan(speed_for_trend) else float('nan')


            self.trend_data_history.append({
                "time": current_time_s,
                "lat": lat,
                "lon": lon,
                "hMSL": data.get('hMSL', float('nan')),
                "gSpeed": speed_mps_for_trend, # Store speed in m/s for trend plot
                "numSV": data.get('numSV', float('nan')),
                "pDOP": data.get('pDOP', float('nan')),
                "hDOP": data.get('hDOP', float('nan')),
                "vDOP": data.get('vDOP', float('nan'))
            })
            if len(self.trend_data_history) > self.max_trend_data_points:
                self.trend_data_history.pop(0) # Remove oldest trend data point
            self.logger.log_debug(f"Trend data history size: {len(self.trend_data_history)}")


        # Log data if enabled (main app logs - these are timestamped and new on app start)
        if self.settings_manager.get("log_json"):
            self.logger.log_json(data)
            self.logger.log_debug("Logged data to main JSONL log.")
        if self.settings_manager.get("log_csv"):
            # Ensure gSpeed is converted to m/s before logging to CSV
            speed_mmps_raw_for_csv = data.get('gSpeed', float('nan'))
            data_for_csv = data.copy() # Create a copy to modify
            # Convert to m/s if from live GPS, otherwise assume it's already m/s from offline
            if self.offline_mode_active_var.get():
                data_for_csv['gSpeed'] = speed_mmps_raw_for_csv
            else:
                data_for_csv['gSpeed'] = speed_mmps_raw_for_csv / 1000.0 if not math.isnan(speed_mmps_raw_for_csv) else float('nan')
            self.logger.log_csv(data_for_csv)
            self.logger.log_debug("Logged data to main CSV log.")

        # Periodically clean old logs and check disk space (e.g., every 100 updates)
        if len(self.track_points) % 100 == 0:
            self.logger.clean_old_logs()
            self.logger.check_disk_space()
            self.logger.log_debug("Performed periodic log cleaning and disk space check.")

    def _schedule_throttled_ui_update(self):
        """Schedules a UI update if one is not already pending."""
        if not self.ui_update_scheduled:
            self.ui_update_scheduled = True
            self.after(self.ui_update_throttle_ms, self._perform_throttled_ui_update)
            self.logger.log_debug(f"Scheduled throttled UI update in {self.ui_update_throttle_ms} ms.")

    def _perform_throttled_ui_update(self):
        """Performs the actual UI update and resets the schedule flag."""
        self.logger.log_debug("Calling app.update_ui with new data (throttled).")
        self.update_ui()
        self.ui_update_scheduled = False
        self.logger.log_debug("Throttled UI update performed.")

    def _update_storage_info(self):
        """Updates the displayed disk storage information."""
        self.logger.log_debug("Updating storage information.")
        log_path = os.path.abspath(self.settings_manager.get("log_directory"))
        if not os.path.exists(log_path):
            self.total_disk_space_var.set("N/A")
            self.used_disk_space_var.set("N/A")
            self.free_disk_space_var.set("N/A")
            self.logger.log_warning(f"Log directory '{log_path}' does not exist. Cannot display storage info.")
            return

        try:
            total, used, free = shutil.disk_usage(log_path)
            # Convert bytes to GB for display
            total_gb = total / (1024**3)
            used_gb = used / (1024**3)
            free_gb = free / (1024**3)

            self.total_disk_space_var.set(f"{total_gb:.2f} GB")
            self.used_disk_space_var.set(f"{used_gb:.2f} GB")
            self.free_disk_space_var.set(f"{free_gb:.2f} GB")
            self.logger.log_debug(f"Storage info updated: Total={total_gb:.2f}GB, Used={used_gb:.2f}GB, Free={free_gb:.2f}GB")
        except Exception as e:
            self.logger.log_error(f"Could not get disk space info: {e}", exc_info=True)
            self.total_disk_space_var.set("Error")
            self.used_disk_space_var.set("Error")
            self.free_disk_space_var.set("Error")

    def _update_system_info_ui(self, sys_info):
        """Updates the system information UI elements."""
        self.logger.log_debug(f"Updating system info UI with: {sys_info.keys()}")
        self.info_vars["sw_version"].set(sys_info.get("sw_version", "N/A"))
        self.info_vars["hw_version"].set(sys_info.get("hw_version", "N/A"))
        self.info_vars["gnss_support"].set(sys_info.get("gnss_support", "N/A"))
        self.info_vars["rf_antenna_status"].set(sys_info.get("rf_status", "N/A"))

        # Update Port Settings display (read-only)
        if 'port_id' in sys_info:
            self.port_id_var.set(str(sys_info['port_id']))
            self.port_mode_var.set(str(sys_info['mode']))
            # Corrected: Use 'baudrate' key as stored in sys_info
            self.port_baudrate_var.set(str(sys_info['baudrate']))

            # Safely format in_proto and out_proto
            in_proto_val = sys_info['in_proto']
            if isinstance(in_proto_val, int):
                self.in_protocol_var.set(self.protocol_map.get(in_proto_val, f"Unknown (0x{in_proto_val:X})"))
            else:
                self.in_protocol_var.set(str(in_proto_val)) # Display as is (e.g., "N/A")

            out_proto_val = sys_info['out_proto']
            if isinstance(out_proto_val, int):
                self.out_protocol_var.set(self.protocol_map.get(out_proto_val, f"Unknown (0x{out_proto_val:X})"))
            else:
                self.out_protocol_var.set(str(out_proto_val)) # Display as is (e.g., "N/A")
        else:
            self.port_id_var.set("N/A")
            self.port_mode_var.set("N/A")
            self.port_baudrate_var.set("N/A")
            self.in_protocol_var.set("N/A")
            self.out_protocol_var.set("N/A")

        # Update Communication Status
        if 'txErrors' in sys_info:
            self.comm_status_vars["comm_errors"].set(str(sys_info['txErrors']))
            self.comm_status_vars["rx_buffer_usage"].set(f"{sys_info['rxBufUsage']}%")
            self.comm_status_vars["tx_buffer_usage"].set(f"{sys_info['txBufUsage']}%")
        else:
            self.comm_status_vars["comm_errors"].set("N/A")
            self.comm_status_vars["rx_buffer_usage"].set("N/A")
            self.comm_status_vars["tx_buffer_usage"].set("N/A")
        self.logger.log_debug("System info UI updated.")

    def _convert_speed(self, speed_mps, unit_preference, output_unit_only=False):
        """
        Converts speed from m/s to preferred units (km/h or mph).
        If output_unit_only is True, returns ft/s for imperial.
        """
        if math.isnan(speed_mps):
            return float('nan'), "N/A"

        if unit_preference == "metric":
            return speed_mps * 3.6, "km/h"
        elif unit_preference == "imperial":
            if output_unit_only: # For travel history, we want ft/s
                return speed_mps * 3.28084, "ft/s"
            else: # For dashboard, we want mph
                return speed_mps * 2.23694, "mph"
        return float('nan'), "N/A"

    def _convert_altitude(self, altitude_meters, unit_preference):
        """Converts altitude from meters to preferred units (meters or feet)."""
        if math.isnan(altitude_meters):
            return float('nan'), "N/A"

        if unit_preference == "metric":
            return altitude_meters, "m MSL"
        elif unit_preference == "imperial":
            return altitude_meters * 3.28084, "ft MSL" # 1 meter = 3.28084 feet
        return float('nan'), "N/A"

    def _convert_distance(self, distance_meters, unit_preference):
        """Converts distance from meters to preferred units (km or miles)."""
        if math.isnan(distance_meters):
            return float('nan'), "N/A"

        if unit_preference == "metric":
            return distance_meters / 1000.0, "km" # 1 km = 1000 meters
        elif unit_preference == "imperial":
            return distance_meters / 1609.34, "miles" # 1 mile = 1609.34 meters
        return float('nan'), "N/A"

    def update_ui(self):
        """Updates all UI elements with the latest GPS data."""
        self.logger.log_debug("Starting UI update cycle.")
        data = self.current_gps_data
        unit_preference = self.settings_manager.get("unit_preference")

        # Retrieve raw gSpeed (which is in mm/s from the ublox_gps library)
        # For offline playback, gSpeed is already converted to m/s by _parse_jsonl_log or _parse_csv_log
        # For live data, gSpeed is mm/s, so conversion is needed here for UI display.
        speed_raw_from_source = data.get('gSpeed', float('nan'))
        self.logger.log_debug(f"UI Update: Initial speed_raw_from_source: {speed_raw_from_source:.3f} (unit depends on source)")

        # Convert to m/s for internal consistency before applying threshold
        if self.offline_mode_active_var.get():
            # If in offline mode, gSpeed is already m/s from _parse_jsonl_log or _parse_csv_log
            speed_mps_converted = speed_raw_from_source
        else:
            # If in live mode, gSpeed is mm/s from ublox_gps, convert to m/s
            speed_mps_converted = speed_raw_from_source / 1000.0 if not math.isnan(speed_raw_from_source) else float('nan')

        self.logger.log_debug(f"UI Update: Converted speed_mps: {speed_mps_converted:.3f} m/s")

        # Apply speed noise threshold from settings
        speed_mps_filtered = speed_mps_converted
        current_speed_noise_threshold = self.settings_manager.get("speed_noise_threshold_mps") # Get from settings
        if not math.isnan(speed_mps_filtered) and speed_mps_filtered < current_speed_noise_threshold:
            speed_mps_filtered = 0.0 # Treat as stationary
            self.logger.log_debug(f"UI Update: Speed filtered to 0 m/s (below threshold {current_speed_noise_threshold} m/s).")
        else:
            self.logger.log_debug(f"UI Update: Speed not filtered. Current speed_mps: {speed_mps_filtered:.3f} m/s.")

        # Convert speed to preferred display units
        display_speed_val, display_speed_unit = self._convert_speed(speed_mps_filtered, unit_preference)
        self.logger.log_debug(f"UI Update: Speed for display: {display_speed_val:.2f} {display_speed_unit}")

        # Convert altitude to preferred display units
        display_altitude_val, display_altitude_unit = self._convert_altitude(data.get('hMSL', float('nan')), unit_preference)
        self.logger.log_debug(f"UI Update: Altitude for display: {display_altitude_val:.2f} {display_altitude_unit}")


        # Get descriptive fix type and its corresponding bootstyle
        fix_type_raw = data.get('fixType')
        fix_type_desc = self.fix_type_map.get(fix_type_raw, 'N/A')
        fix_type_style = self.fix_type_color_map.get(fix_type_raw, 'default') # 'default' or 'secondary' if not found
        self.logger.log_debug(f"UI Update: Fix Type Raw: {fix_type_raw}, Description: '{fix_type_desc}', Style: '{fix_type_style}'")


        # Update Driving Dashboard elements
        self.dashboard_speed_var.set(format_value(display_speed_val, 2))
        self.dashboard_speed_unit_var.set(display_speed_unit) # Set dynamic unit label
        self.dashboard_altitude_var.set(format_value(display_altitude_val, 2))
        self.dashboard_altitude_unit_var.set(display_altitude_unit) # Set dynamic unit label

        self.dashboard_heading_var.set(format_value(data.get('headMot', float('nan')), 2))
        self.dashboard_num_sv_var.set(data.get('numSV', 'N/A'))
        self.dashboard_fix_type_var.set(fix_type_desc)
        self.dashboard_fix_type_label.config(bootstyle=fix_type_style) # Dynamically set bootstyle
        self.dashboard_hdop_var.set(format_value(data.get('hDOP', float('nan')), 2))
        self.dashboard_vdop_var.set(format_value(data.get('vDOP', float('nan')), 2))
        self.dashboard_time_var.set(datetime.now().strftime("%H:%M:%S")) # Update current time

        # Update Current Position (also used by Driving Dashboard for Lat/Lon)
        self.pos_vars["latitude"].set(format_coord(data.get('lat', float('nan'))))
        self.pos_vars["longitude"].set(format_coord(data.get('lon', float('nan'))))
        self.pos_vars["altitude_(msl)"].set(format_value(display_altitude_val, 2))
        self.pos_vars["altitude_(msl)_unit"].set(display_altitude_unit.replace(" MSL", "")) # Remove MSL for this tab
        
        # Speed for GPS Data tab (m/s or ft/s)
        speed_for_gps_data_tab, speed_gps_data_unit = self._convert_speed(speed_mps_filtered, unit_preference, output_unit_only=True)
        self.pos_vars["speed"].set(format_value(speed_for_gps_data_tab, 2))
        self.pos_vars["speed_unit"].set(speed_gps_data_unit)

        self.pos_vars["heading_deg"].set(format_value(data.get('headMot', float('nan')), 2))
        self.pos_vars["satellites_in_use"].set(data.get('numSV', 'N/A'))
        self.pos_vars["fix_type"].set(fix_type_desc) # Use descriptive fix type here too

        # Update High-Precision Coordinates
        if 'hp_lat' in data and not math.isnan(data['hp_lat']):
            self.hp_lat_var.set(f"{data['hp_lat']:.8f}")
            self.hp_lon_var.set(f"{data['hp_lon']:.8f}")
            self.hp_height_var.set(f"{data['hp_height']:.3f} m") # High-precision height always in meters
        else:
            self.hp_lat_var.set("N/A")
            self.hp_lon_var.set("N/A")
            self.hp_height_var.set("N/A")

        if 'hAcc' in data and not math.isnan(data['hAcc']):
            self.h_acc_var.set(f"{data['hAcc']:.3f}")
            self.v_acc_var.set(f"{data['vAcc']:.3f}")
        else:
            self.h_acc_var.set("N/A")
            self.v_acc_var.set("N/A")

        # Update DOP Data
        self.dop_vars["pdop"].set(format_value(data.get('pDOP', float('nan')), 2))
        self.dop_vars["hdop"].set(format_value(data.get('hDOP', float('nan')), 2))
        self.dop_vars["vdop"].set(format_value(data.get('vDOP', float('nan')), 2))

        # Update Satellite Details
        for i in self.sat_tree.get_children():
            self.sat_tree.delete(i)

        satellites = data.get('satellites', [])
        for sat in satellites:
            # Only display satellites with CNO data (cno is not None and not NaN)
            cno = sat.get('cno')
            if cno is not None and not (isinstance(cno, float) and math.isnan(cno)):
                self.sat_tree.insert("", END, values=(
                    sat.get('svid', 'N/A'),
                    sat.get('gnssId', 'N/A'),
                    format_value(cno, 0), # CNO is typically integer or float, format as integer
                    format_value(sat.get('elev', float('nan')), 0),
                    format_value(sat.get('azim', float('nan')), 0),
                    "Yes" if sat.get('flags', {}).get('svUsed') == 1 else "No",
                    "Yes" if sat.get('flags', {}).get('diffCorr') == 1 else "No",
                    "Yes" if sat.get('flags', {}).get('sbasCorrUsed') == 1 else "No"
                ))

        # --- Update Trip Metrics Display ---
        if self.is_trip_active:
            if self.current_trip_start_time:
                duration = datetime.now() - self.current_trip_start_time
                self.trip_duration_var.set(f"Duration: {str(duration).split('.')[0]}")
            
            # Display current trip distance and max speed in the selected units
            display_current_distance, display_current_distance_unit = self._convert_distance(self.current_trip_distance, unit_preference)
            display_current_max_speed, display_current_max_speed_unit = self._convert_speed(self.current_trip_max_speed, unit_preference)
            
            self.trip_distance_var.set(f"Distance: {display_current_distance:.2f} {display_current_distance_unit}")
            self.trip_max_speed_var.set(f"Max Speed: {display_current_max_speed:.2f} {display_current_max_speed_unit}")
        else:
            self.trip_duration_var.set("Duration: N/A")
            self.trip_distance_var.set("Distance: N/A")
            self.trip_max_speed_var.set("Max Speed: N/A")


        # Get the currently selected tab text
        current_tab_text = self.notebook.tab(self.notebook.select(), "text")

        # Update plots and other dynamic elements based on active tab
        if current_tab_text == "Driving Dashboard":
            self.logger.log_debug(f"Updating compass with heading: {data.get('headMot', float('nan'))}")
            self._update_compass(data.get('headMot', float('nan'))) # Update compass
        elif current_tab_text == "Satellite Skyplot":
            self.logger.log_debug(f"Updating skyplot with {len(satellites)} satellites.")
            self._update_skyplot(satellites)
            self.logger.log_debug(f"Updating CNO barchart with {len(satellites)} satellites.")
            self._update_cno_barchart(satellites)
        elif current_tab_text == "Map":
            self.logger.log_debug(f"Generating Folium map with {len(self.track_points)} track points.")
            self._generate_folium_map()
        elif current_tab_text == "GPS Trend Data":
            self.logger.log_debug(f"Updating trend plots with {len(self.trend_data_history)} data points.")
            self._update_trend_plots()
        elif current_tab_text == "Travel History":
            self.logger.log_debug(f"Updating travel history tab with {len(self.trend_data_history)} data points.")
            self._update_travel_history_tab()
        elif current_tab_text == "Trip History":
            self.logger.log_debug(f"Updating trip history tab with {len(self.trip_history)} trips.")
            self._update_trip_history_tab()
        
        # Update Storage Info (always, or periodically)
        self._update_storage_info()
        self.logger.log_debug("UI update cycle completed.")

    def _update_compass(self, heading):
        """
        Updates the vehicle-style compass. The needle stays fixed at the top,
        and the cardinal directions rotate behind it.
        """
        self.logger.log_debug(f"Updating compass with heading: {heading}")
        colors = self._get_plot_colors()
        ax = self.ax_compass
        ax.clear() # Clear everything including needle and labels
        
        # --- Redraw static elements of the compass template ---
        ax.set_ylim(0, 1) # Small y-range for a flat compass
        ax.set_yticks([]) # Hide y-axis ticks
        ax.set_xticks([]) # Hide x-axis ticks
        ax.set_facecolor(colors["bg"])
        ax.grid(False) # No grid for this type of compass
        self.fig_compass.tight_layout()

        # Fixed Top Indicator (Red Triangle)
        ax.plot([0], [0.9], marker='^', markersize=12, color='red', zorder=10)

        # Fixed Bottom Indicator (Small Needle Below - Blue Triangle)
        ax.plot([0], [0.1], marker='v', markersize=8, color='blue', zorder=10)

        # Define the arc parameters
        arc_y_center = 0.5 # Base y-position for the center of the arc
        arc_depth = 0.1 # How much the arc dips at the ends
        arc_width_degrees = 90 # How many degrees from center to edge of visible arc

        # Define the visible x-axis limits (e.g., +/- arc_width_degrees around the center)
        ax.set_xlim(-arc_width_degrees, arc_width_degrees)

        # Generate points for the curved compass tape
        x_tape_degrees = np.linspace(-arc_width_degrees, arc_width_degrees, 200)
        # Simple quadratic for the arc
        y_tape = arc_y_center - arc_depth * (x_tape_degrees / arc_width_degrees)**2
        
        # Draw the tape as a thick line
        ax.plot(x_tape_degrees, y_tape, color='gray', linewidth=15, alpha=0.6, zorder=1, solid_capstyle='round')
        # --- End redraw static elements ---

        if math.isnan(heading):
            ax.text(0, 0.75, "N/A", color=colors["text"], fontsize=12, ha='center', va='center')
            self.compass_canvas.draw_idle()
            self.logger.log_debug("Compass updated (N/A heading).")
            return

        # Ensure heading is within 0-360
        heading = heading % 360

        # Cardinal directions and their degrees
        cardinal_points = {
            "N": 0, "NE": 45, "E": 90, "SE": 135, "S": 180, "SW": 225, "W": 270, "NW": 315
        }
        
        # Add minor tick lines (e.g., every 5 degrees) and cardinal labels
        for i in range(0, 360, 5): # 5-degree intervals for ticks
            # Calculate the relative position on the compass scale.
            relative_pos = i - heading
            
            # Normalize relative_pos to be within [-180, 180]
            if relative_pos > 180:
                relative_pos -= 360
            elif relative_pos < -180:
                relative_pos += 360

            # Only draw if within the visible x-axis range [-arc_width_degrees, arc_width_degrees]
            if -arc_width_degrees <= relative_pos <= arc_width_degrees:
                # Calculate y position on the arc for ticks and labels
                y_on_arc = arc_y_center - arc_depth * (relative_pos / arc_width_degrees)**2

                tick_length = 0.03
                label_offset = 0.07 # Distance below the arc for labels

                label_text = None
                is_major_tick = False
                
                # Check if this degree corresponds to a cardinal point for labels
                for label, degree in cardinal_points.items():
                    if i == degree:
                        label_text = label
                        is_major_tick = True
                        break
                
                # Add numerical labels for every 30 degrees (if not a cardinal point)
                if i % 30 == 0 and not label_text:
                    label_text = str(i)
                    is_major_tick = True

                # Draw tick line
                ax.plot([relative_pos, relative_pos], [y_on_arc - tick_length, y_on_arc],
                        color=colors["text"] if is_major_tick else colors["grid"],
                        linewidth=1.5 if is_major_tick else 0.8,
                        zorder=2)

                if label_text:
                    # Calculate rotation for labels to follow the curve
                    # The rotation angle is proportional to the relative position from the center
                    # A positive relative_pos means the label is to the right of center, rotate clockwise (negative angle)
                    # A negative relative_pos means the label is to the left of center, rotate counter-clockwise (positive angle)
                    rotation_factor = 0.3 # Adjust this to control how much labels rotate
                    rotation_angle = -relative_pos * rotation_factor

                    ax.text(relative_pos, y_on_arc - label_offset, label_text,
                            rotation=rotation_angle,
                            color=colors["text"], fontsize=9 if is_major_tick else 8,
                            ha='center', va='center', zorder=3)

        # Display current heading number at the top
        ax.text(0, 0.95, f"{int(heading)}°", color=colors["text"], fontsize=14, ha='center', va='bottom', weight='bold', zorder=11)

        self.fig_compass.tight_layout()
        self.compass_canvas.draw_idle()
        self.logger.log_debug("Compass updated.")


    def _update_cno_barchart(self, satellites):
        """Updates the CNO bar chart with new satellite data."""
        self.logger.log_debug(f"CNO barchart update: Received {len(satellites)} satellites for plotting.")
        colors = self._get_plot_colors()
        self.ax_cno.clear()
        self.ax_cno.set_xlabel("CNO (dBHz)", color=colors["text"])
        self.ax_cno.set_ylabel("SV ID", color=colors["text"]) # Re-apply Y-label
        self.ax_cno.set_title("Satellite CNO Levels", color=colors["text"])
        self.ax_cno.set_xlim(0, 50) # Typical CNO range, adjust if needed
        self.ax_cno.set_facecolor(colors["bg"]) # Ensure facecolor is set on clear
        self.ax_cno.tick_params(axis='x', colors=colors["text"])
        # --- MODIFICATION START ---
        # Reduce font size for y-axis (SV ID) labels to avoid clutter
        self.ax_cno.tick_params(axis='y', colors=colors["text"], labelsize=6) # Reduced labelsize
        # --- MODIFICATION END ---
        self.ax_cno.grid(True, axis='x', color=colors["grid"])

        cno_values = []
        sv_ids = []
        colors_bar = [] # Use a different variable name to avoid conflict with plot_colors

        # Define a mapping for GNSS IDs to single-letter prefixes
        gnss_prefix_map = {
            0: "G",   # GPS
            2: "E",   # Galileo
            3: "C",   # BeiDou
            5: "J",   # QZSS
            6: "R",   # GLONASS
            7: "S"    # SBAS
        }

        # Filter satellites with valid CNO and sort them by CNO for better visualization
        valid_sats = sorted([s for s in satellites if s.get('cno') is not None and not math.isnan(s['cno'])],
                            key=lambda x: x['cno'], reverse=True)

        for sat in valid_sats:
            cno_values.append(sat['cno'])
            # Format SV ID and GNSS ID for display using the new prefix
            gnss_prefix = gnss_prefix_map.get(sat.get('gnssId'), "?") # Use '?' for unknown GNSS ID
            sv_ids.append(f"{gnss_prefix}{sat['svid']}")
            colors_bar.append('green' if sat.get('flags', {}).get('svUsed') == 1 else 'orange') # Green if used, orange if not

        if cno_values:
            # Create horizontal bars
            self.ax_cno.barh(sv_ids, cno_values, color=colors_bar)
            self.ax_cno.set_yticks(np.arange(len(sv_ids)))
            self.ax_cno.set_yticklabels(sv_ids)
            self.ax_cno.invert_yaxis() # Highest CNO at the top

        self.fig_cno.tight_layout()
        self.cno_canvas.draw_idle()
        self.logger.log_debug("CNO barchart updated.")

    def _update_trend_plots(self):
        """Updates the GPS trend plots with new historical data."""
        self.logger.log_debug(f"Trend plots update: Received {len(self.trend_data_history)} data points.")
        colors = self._get_plot_colors() # Get colors dynamically
        
        # Check for minimum data points for line plots
        if not self.trend_data_history or len(self.trend_data_history) < 2: # Require at least 2 points for a line
            for ax in self.ax_trend_flat:
                ax.clear() # Clear previous data
                ax.set_facecolor(colors["bg"]) # Re-apply background
                ax.grid(True, color=colors["grid"]) # Re-apply grid
                ax.tick_params(axis='both', which='major', labelsize=7, colors=colors["text"]) # Re-apply tick colors
            self.fig_trend.tight_layout(pad=3.0)
            self.trend_canvas.draw_idle()
            self.logger.log_debug("Trend plots cleared (insufficient data).")
            return

        # Extract data for plotting
        times = np.array([d['time'] for d in self.trend_data_history])
        # Normalize times to start from 0 for relative time on x-axis
        start_time = times[0]
        relative_times = times - start_time

        latitudes = np.array([d['lat'] for d in self.trend_data_history])
        longitudes = np.array([d['lon'] for d in self.trend_data_history])
        altitudes = np.array([d['hMSL'] for d in self.trend_data_history])
        speeds = np.array([d['gSpeed'] for d in self.trend_data_history]) # Already in m/s
        num_svs = np.array([d['numSV'] for d in self.trend_data_history])
        pdops = np.array([d['pDOP'] for d in self.trend_data_history])
        hdops = np.array([d['hDOP'] for d in self.trend_data_history])
        vdops = np.array([d['vDOP'] for d in self.trend_data_history])

        # Define data sets to plot
        plot_data = [
            latitudes, longitudes, altitudes, speeds,
            num_svs, pdops, hdops, vdops
        ]
        
        # Define plot colors (can be customized)
        line_colors = ['blue', 'green', 'red', 'purple', 'cyan', 'magenta', 'orange', 'brown']

        # Update each subplot
        for i, ax in enumerate(self.ax_trend_flat):
            ax.clear() # Clear previous data
            ax.set_facecolor(colors["bg"]) # Set facecolor for each subplot
            ax.grid(True, color=colors["grid"]) # Ensure grid is drawn
            ax.tick_params(axis='both', which='major', labelsize=7, colors=colors["text"]) # Ensure tick colors are correct
            
            # Re-apply titles and labels
            plot_configs = [
                {"title": "Latitude Trend", "ylabel": "Latitude (deg)"},
                {"title": "Longitude Trend", "ylabel": "Longitude (deg)"},
                {"title": "Altitude (MSL) Trend", "ylabel": "Altitude (m)"},
                {"title": "Speed Trend", "ylabel": "Speed (m/s)"},
                {"title": "Satellites in Use Trend", "ylabel": "Number of SVs"},
                {"title": "PDOP Trend", "ylabel": "PDOP"},
                {"title": "HDOP Trend", "ylabel": "HDOP"},
                {"title": "VDOP Trend", "ylabel": "VDOP"},
            ]
            ax.set_title(plot_configs[i]["title"], fontsize=10, color=colors["text"])
            ax.set_ylabel(plot_configs[i]["ylabel"], fontsize=8, color=colors["text"])
            if i < len(self.ax_trend_flat) - 2: # Only set xlabel for bottom row plots
                ax.set_xlabel("Time (s)", fontsize=8, color=colors["text"])

            # Plot data, handling NaNs
            data_to_plot = plot_data[i]
            # Filter out NaN values for plotting
            valid_indices = ~np.isnan(data_to_plot)
            
            if np.any(valid_indices):
                ax.plot(relative_times[valid_indices], data_to_plot[valid_indices],
                        color=line_colors[i % len(line_colors)], linewidth=1.5)
                # Auto-scale y-axis based on valid data
                ax.autoscale_view(scalex=False, scaley=True)
            else:
                # If no valid data, display "N/A"
                ax.text(0.5, 0.5, "N/A", transform=ax.transAxes,
                        color=colors["text"], fontsize=12, ha='center', va='center')

            # Ensure x-axis limits are set based on relative_times
            if len(relative_times) > 0:
                ax.set_xlim(relative_times[0], relative_times[-1] + 1) # Add a small buffer
            else:
                ax.set_xlim(0, 10) # Default empty range

        self.fig_trend.tight_layout(pad=3.0)
        self.trend_canvas.draw_idle()
        self.logger.log_debug("Trend plots updated.")


    def _update_travel_history_tab(self):
        """Updates the Travel History tab with the current trend data history."""
        self.logger.log_debug(f"Travel history update: Populating treeview with {len(self.trend_data_history)} data points.")
        # Clear existing items in the Treeview
        for i in self.travel_history_tree.get_children():
            self.travel_history_tree.delete(i)

        unit_preference = self.settings_manager.get("unit_preference")

        if not self.trend_data_history:
            self.travel_history_tree.insert("", END, values=("", "No data yet.", "", "", ""))
            self.logger.log_debug("No trend data history to display.")
            return

        # Iterate through trend_data_history in reverse to show most recent at top
        for dp in reversed(self.trend_data_history):
            timestamp_dt = datetime.fromtimestamp(dp['time'])
            timestamp_str = timestamp_dt.strftime("%Y-%m-%d %H:%M:%S")

            # Convert speed from m/s to preferred unit for display
            display_speed, speed_unit = self._convert_speed(dp['gSpeed'], unit_preference)

            self.travel_history_tree.insert("", END, values=(
                timestamp_str,
                format_coord(dp['lat']),
                format_coord(dp['lon']),
                format_value(display_speed, 2),
                speed_unit
            ))
        self.logger.log_debug("Travel history treeview populated.")

    def _update_trip_history_tab(self):
        """Updates the Trip History tab with the latest trip summaries."""
        self.logger.log_debug("Updating trip history tab.")
        # This method simply reloads the data from the internal self.trip_history list
        # and repopulates the Treeview, ensuring it's always up-to-date.
        self._load_trip_history_to_tree()
        self.logger.log_debug("Trip history tab updated.")

    def _setup_menu(self):
        """Sets up the application menu bar."""
        self.logger.log_debug("Setting up application menu.")
        menubar = tk.Menu(self)
        self.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Exit", command=self.on_close)

        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self._show_about_dialog)
        self.logger.log_debug("Application menu setup complete.")

    def _show_about_dialog(self):
        """Displays the About dialog."""
        self.logger.log_info("Showing About dialog.")
        messagebox.showinfo(
            "About GPS Dashboard",
            "GPS Dashboard Application\n\n"
            "Version: 1.0\n"
            "Developed by: Your Name/Organization\n"
            "This application provides real-time GPS data visualization, logging, geofencing, and trip analysis.\n\n"
            "Libraries Used:\n"
            "- Tkinter (GUI)\n"
            "- ttkbootstrap (Theming)\n"
            "- Matplotlib (Plotting)\n"
            "- ublox_gps (U-Blox GPS communication)\n"
            "- pyserial (Serial communication)\n"
            "- Folium (Map generation)\n"
            "- tkhtmlview (HTML embedding)\n"
            "- numpy (Numerical operations)\n"
            "- shutil (Disk space checks)\n"
            "- json, csv, os, threading, time, queue, math, datetime, subprocess, webbrowser, logging, logging.handlers (Standard Python)"
        )

    def on_close(self):
        """Handles application shutdown, stopping threads and closing resources."""
        self.logger.log_info("Application closing initiated.")
        if self.update_id:
            self.after_cancel(self.update_id)
            self.logger.log_debug("Cancelled pending UI update.")

        self.stop_live_gps_event.set()
        if self.live_gps_thread and self.live_gps_thread.is_alive():
            self.live_gps_thread.join(timeout=2) # Give thread 2 seconds to stop
            if self.live_gps_thread.is_alive():
                self.logger.log_warning("Live GPS thread did not terminate gracefully.")
            else:
                self.logger.log_debug("Live GPS thread terminated.")
        
        self.stop_playback_event.set()
        if self.offline_playback_manager and self.offline_playback_manager.playback_thread and self.offline_playback_manager.playback_thread.is_alive():
            self.offline_playback_manager.playback_thread.join(timeout=2)
            if self.offline_playback_manager.playback_thread.is_alive():
                self.logger.log_warning("Offline playback thread did not terminate gracefully.")
            else:
                self.logger.log_debug("Offline playback thread terminated.")

        # Close main application loggers
        if self.logger and self.logger_initialized: # Only close if logger was successfully initialized
            self.logger.close()
            self.logger.log_info("Main DataLogger handlers closed.")
        elif self.logger: # If temporary logger was used but main wasn't initialized
             # Attempt to close temporary logger handlers if they exist
            for handler in list(self.logger.console_logger.handlers):
                self.logger.console_logger.removeHandler(handler)
                handler.close()
            print("Temporary DataLogger handlers closed during shutdown.", file=sys.stderr)


        # Close current trip log files if active
        if self.is_trip_active:
            if self.trip_csv_file_obj and not self.trip_csv_file_obj.closed:
                self.trip_csv_file_obj.close()
                self.logger.log_info("Trip CSV log file closed during shutdown.")
            if self.trip_jsonl_file_obj and not self.trip_jsonl_file_obj.closed:
                self.trip_jsonl_file_obj.close()
                self.logger.log_info("Trip JSONL log file closed during shutdown.")
            self.logger.log_info("Active trip log files closed.")

        self.settings_manager.save_settings() # Save settings one last time
        self.logger.log_info("Settings saved on shutdown.")

        self.destroy() # Destroy the Tkinter window
        self.logger.log_info("Tkinter window destroyed. Application exiting.")
        sys.exit(0) # Explicitly exit the application


if __name__ == "__main__":
    # Ensure a basic console logger is set up for very early debug messages
    # before the main DataLogger is fully initialized.
    # This helps catch issues even before SettingsManager is ready.
    # This is a temporary setup, the DataLogger will reconfigure logging later.
    try:
        # Check if a root logger handler already exists to avoid duplicates
        if not logging.root.handlers:
            logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
            logging.info("Basic console logging initialized for early startup.")
        else:
            logging.info("Root logger already has handlers, skipping basic console setup.")

        app = GpsDashboardApp()
        app.mainloop()
    except Exception as e:
        logging.critical(f"Unhandled exception during application startup: {e}", exc_info=True)
        # Fallback messagebox if Tkinter is not fully initialized
        try:
            messagebox.showerror("Application Startup Error", f"An unhandled error occurred during application startup: {e}\nCheck the console or log files for more details.")
        except tk.TclError:
            print(f"ERROR: Tkinter error during final error display. Unhandled exception: {e}", file=sys.stderr)
        sys.exit(1)

