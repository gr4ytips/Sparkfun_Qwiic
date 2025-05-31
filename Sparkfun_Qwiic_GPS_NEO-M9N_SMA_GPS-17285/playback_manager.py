# playback_manager.py

import os
import threading
import time
import queue
import json
import csv
import math
from datetime import datetime, timedelta
from tkinter import messagebox, DISABLED, NORMAL # For UI interaction

from config import DATA_FETCH_INTERVAL_MS
from utils import format_coord, format_value

class OfflinePlaybackManager:
    """Manages loading and playing back GPS data from log files."""
    def __init__(self, data_queue, stop_event, logger, playback_speed_var, playback_status_var, playback_progress_var, play_button, pause_button, stop_button):
        self.data_queue = data_queue
        self.stop_event = stop_event # Event to stop the playback thread
        self.logger = logger
        self.playback_speed_var = playback_speed_var
        self.playback_status_var = playback_status_var
        self.playback_progress_var = playback_progress_var

        # References to buttons for state management
        self.play_button = play_button
        self.pause_button = pause_button
        self.stop_button = stop_button

        self.loaded_data = []
        self.current_index = 0
        self.is_playing = False
        self.total_data_points = 0
        self.playback_thread = None
        self.playback_file_path = None # To store the path of the currently loaded file

        self.playback_status_var.set("Stopped")
        self.playback_progress_var.set("0%")
        self.logger.log_debug("OfflinePlaybackManager initialized.")

    def _parse_csv_log(self, filepath):
        """Parses a CSV log file and returns a list of dictionaries."""
        data = []
        try:
            with open(filepath, 'r', newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    dp = {}
                    try:
                        # Convert relevant fields to float, handle 'N/A' or missing values
                        dp['lat'] = float(row.get('Latitude', float('nan')))
                        dp['lon'] = float(row.get('Longitude', float('nan')))
                        dp['hMSL'] = float(row.get('Altitude (MSL)', float('nan')))
                        # Speed from CSV is expected to be in m/s
                        dp['gSpeed'] = float(row.get('Speed (m/s)', float('nan')))
                        dp['headMot'] = float(row.get('Heading (deg)', float('nan')))
                        dp['numSV'] = int(float(row.get('Num SV', float('nan')))) if row.get('Num SV', 'N/A') != 'N/A' else float('nan')
                        dp['fixType'] = int(float(row.get('Fix Type', float('nan')))) if row.get('Fix Type', 'N/A') != 'N/A' else float('nan')
                        dp['pDOP'] = float(row.get('PDOP', float('nan')))
                        dp['hDOP'] = float(row.get('HDOP', float('nan')))
                        dp['vDOP'] = float(row.get('VDOP', float('nan')))
                        
                        # High-precision fields (if available, otherwise NaN)
                        dp['hp_lat'] = float(row.get('HP Latitude', float('nan')))
                        dp['hp_lon'] = float(row.get('HP Longitude', float('nan')))
                        dp['hp_height'] = float(row.get('HP Height (m)', float('nan')))
                        dp['hAcc'] = float(row.get('Horizontal Accuracy (m)', float('nan')))
                        dp['vAcc'] = float(row.get('Vertical Accuracy (m)', float('nan')))

                        # Satellites info is not typically in simple CSV rows, so leave empty for now
                        dp['satellites'] = [] 

                        data.append(dp)
                    except ValueError as ve:
                        self.logger.log_warning(f"Skipping row in CSV due to data conversion error: {ve} - Row: {row}")
                        continue
                    except KeyError as ke:
                        self.logger.log_warning(f"Missing expected column in CSV: {ke} - Row: {row}")
                        continue
            self.logger.log_info(f"Loaded {len(data)} data points from CSV: {filepath}")
        except Exception as e:
            self.logger.log_error(f"Error reading CSV file {filepath}: {e}", exc_info=True)
            messagebox.showerror("File Error", f"Could not read CSV file: {e}")
        return data

    def _parse_jsonl_log(self, filepath):
        """Parses a JSONL log file and returns a list of dictionaries."""
        data = []
        try:
            with open(filepath, 'r') as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                        if isinstance(entry, dict) and 'data' in entry and isinstance(entry['data'], dict):
                            dp = entry['data'].copy()
                            # Ensure gSpeed is converted from mm/s to m/s if it's from live data
                            # Assuming if gSpeed is a very large number, it's in mm/s
                            if 'gSpeed' in dp and not math.isnan(dp['gSpeed']) and dp['gSpeed'] > 1000:
                                dp['gSpeed'] /= 1000.0 # Convert mm/s to m/s
                            data.append(dp)
                    except json.JSONDecodeError as jde:
                        self.logger.log_warning(f"Skipping invalid JSON line: {jde} - Line: {line.strip()}")
                        continue
                    except Exception as e:
                        self.logger.log_warning(f"Skipping line due to unexpected error: {e} - Line: {line.strip()}")
                        continue
            self.logger.log_info(f"Loaded {len(data)} data points from JSONL: {filepath}")
        except Exception as e:
            self.logger.log_error(f"Error reading JSONL file {filepath}: {e}", exc_info=True)
            messagebox.showerror("File Error", f"Could not read JSONL file: {e}")
        return data

    def load_file(self, filepath):
        """Loads data from a specified CSV or JSONL file."""
        self.logger.log_info(f"Loading playback file: {filepath}")
        self.stop_playback() # Ensure any current playback is stopped
        self.loaded_data = []
        self.current_index = 0
        self.total_data_points = 0
        self.playback_file_path = filepath # Store the path for future reference

        file_extension = os.path.splitext(filepath)[1].lower()
        try:
            if file_extension == '.csv':
                self.loaded_data = self._parse_csv_log(filepath)
            elif file_extension == '.jsonl':
                self.loaded_data = self._parse_jsonl_log(filepath)
            else:
                messagebox.showerror("Unsupported File Type", "Please select a .csv or .jsonl file for playback.")
                self.playback_status_var.set("Unsupported file type")
                self.logger.log_warning(f"Unsupported file type selected for playback: {filepath}")
                self.play_button.config(state=DISABLED) # Disable play button on error
                self.pause_button.config(state=DISABLED)
                self.stop_button.config(state=DISABLED)
                return

            self.total_data_points = len(self.loaded_data)
            if self.total_data_points > 0:
                self.playback_status_var.set("Ready")
                self.playback_progress_var.set(f"0 / {self.total_data_points} (0.0%)")
                self.play_button.config(state=NORMAL) # Enable play button if data loaded
                self.pause_button.config(state=DISABLED)
                self.stop_button.config(state=DISABLED)
                self.logger.log_info(f"Successfully loaded {self.total_data_points} data points from {filepath}.")
            else:
                self.playback_status_var.set("No data")
                self.playback_progress_var.set("0%")
                self.play_button.config(state=DISABLED) # Disable play button if no data
                self.pause_button.config(state=DISABLED)
                self.stop_button.config(state=DISABLED)
                messagebox.showwarning("No Data", "No valid GPS data points found in the selected file.")
                self.logger.log_warning(f"No valid data points found in {filepath}.")

        except Exception as e:
            messagebox.showerror("Error Loading File", f"An error occurred while loading the file: {e}")
            self.playback_status_var.set("Error loading file")
            self.play_button.config(state=DISABLED) # Disable play button on error
            self.pause_button.config(state=DISABLED)
            self.stop_button.config(state=DISABLED)
            self.logger.log_error(f"Error loading playback file {filepath}: {e}", exc_info=True)


    def start_playback(self):
        """Starts or resumes offline data playback."""
        if not self.loaded_data:
            messagebox.showwarning("No Data Loaded", "Please load a log file first.")
            self.logger.log_warning("Attempted to start playback without loaded data.")
            return

        if self.is_playing:
            self.logger.log_debug("Playback already running.")
            return

        self.logger.log_info("Starting offline playback.")
        self.is_playing = True
        self.stop_event.clear() # Clear stop signal to allow thread to run

        # --- Button State Management: Play pressed ---
        self.play_button.config(state=DISABLED)
        self.pause_button.config(state=NORMAL)
        self.stop_button.config(state=NORMAL)
        # --- End Button State Management ---

        if not self.playback_thread or not self.playback_thread.is_alive():
            self.playback_thread = threading.Thread(target=self._run_playback, daemon=True)
            self.playback_thread.start()
            self.logger.log_debug("Playback thread started.")
        self.playback_status_var.set("Playing")

    def pause_playback(self):
        """Pauses offline data playback."""
        if not self.is_playing:
            self.logger.log_debug("Playback already paused or stopped.")
            return

        self.logger.log_info("Pausing offline playback.")
        self.is_playing = False

        # --- Button State Management: Pause pressed ---
        self.play_button.config(state=NORMAL) # Enable play to resume
        self.pause_button.config(state=DISABLED)
        self.stop_button.config(state=NORMAL)
        # --- End Button State Management ---

        self.playback_status_var.set("Paused")

    def stop_playback(self):
        """Stops the playback thread and resets state."""
        self.logger.log_debug("Stopping offline playback.")
        self.is_playing = False
        self.stop_event.set() # Signal the thread to stop
        
        # Only attempt to join the thread if it's not the current thread
        if self.playback_thread and self.playback_thread.is_alive() and threading.current_thread() != self.playback_thread:
            self.playback_thread.join(timeout=0.5) # Give it a moment to terminate
        
        self.current_index = 0
        self.playback_status_var.set("Stopped")
        self.playback_progress_var.set("0%")
        self.data_queue.put({"status": "Offline playback stopped."}) # Send a status message
        self.logger.log_info("Offline playback stopped.")

        # --- Button State Management: Stop pressed ---
        # When playback stops (either manually or by reaching end),
        # the play button should be enabled if there's data to play,
        # and pause/stop buttons should be disabled.
        self.play_button.config(state=NORMAL if self.total_data_points > 0 else DISABLED)
        self.pause_button.config(state=DISABLED)
        self.stop_button.config(state=DISABLED)
        self.logger.log_debug(f"Playback stop: total_data_points={self.total_data_points}, Play button state set to {self.play_button['state']}.")
        # --- End Button State Management ---


    def _run_playback(self):
        """The main loop for offline data playback."""
        while not self.stop_event.is_set():
            if not self.is_playing:
                time.sleep(0.1) # Wait if paused
                continue

            if self.current_index >= self.total_data_points:
                self.logger.log_info("End of offline playback data. Stopping.")
                self.stop_playback() # Stop instead of looping
                break # Exit the thread loop

            data_point = self.loaded_data[self.current_index]
            self.data_queue.put(data_point) # Push data to the main queue

            self.current_index += 1
            progress_percent = (self.current_index / self.total_data_points) * 100 if self.total_data_points > 0 else 0
            self.playback_progress_var.set(f"{self.current_index} / {self.total_data_points} ({progress_percent:.1f}%)")

            # Calculate sleep duration based on playback speed
            # DATA_FETCH_INTERVAL_MS is in milliseconds, convert to seconds
            sleep_duration = (DATA_FETCH_INTERVAL_MS / 1000.0) / self.playback_speed_var.get()
            time.sleep(sleep_duration)

