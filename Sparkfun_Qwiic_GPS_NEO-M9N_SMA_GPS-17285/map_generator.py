# map_generator.py

import os
import json
import csv
import math
import webbrowser
from datetime import datetime
from tkinter import messagebox

import folium # Import folium for map generation

from config import LOG_DIR
from utils import format_coord, format_value

class LogMapGenerator:
    def __init__(self, logger):
        self.logger = logger
        self.last_generated_map_path = None

    def load_log_file(self, filepath):
        file_extension = os.path.splitext(filepath)[1].lower()
        coordinates = []
        try:
            if file_extension == '.csv':
                coordinates = self._parse_csv_log(filepath)
            elif file_extension == '.jsonl':
                coordinates = self._parse_jsonl_log(filepath)
            else:
                raise ValueError("Unsupported file type. Please select a .csv or .jsonl file.")

            if not coordinates:
                raise ValueError("No valid GPS coordinates found in the selected log file.")
            
            return coordinates
        except ValueError as e:
            messagebox.showerror("Data Error", str(e))
            self.logger.log_warning(f"Error loading log file {filepath} for map generation: {e}")
            return None
        except Exception as e:
            messagebox.showerror("Error Loading File", f"An error occurred while loading the file: {e}")
            self.logger.log_error(f"Error loading log file {filepath} for map generation: {e}")
            return None

    def _parse_csv_log(self, filepath):
        coordinates = []
        try:
            with open(filepath, 'r', newline='') as f:
                reader = csv.DictReader(f)
                # Attempt to find latitude and longitude columns (case-insensitive)
                lat_key = next((key for key in reader.fieldnames if key.lower() == 'latitude'), None)
                lon_key = next((key for key in reader.fieldnames if key.lower() == 'longitude'), None)

                if not lat_key or not lon_key:
                    raise ValueError("CSV file must contain 'latitude' and 'longitude' columns.")

                for row in reader:
                    try:
                        lat = float(row[lat_key])
                        lon = float(row[lon_key])
                        if not math.isnan(lat) and not math.isnan(lon):
                            coordinates.append((lat, lon))
                    except (ValueError, TypeError):
                        self.logger.log_warning(f"Skipping invalid coordinate row in CSV for map: {row}")
                        continue
        except Exception as e:
            self.logger.log_error(f"Error parsing CSV log file {filepath} for map: {e}")
            raise
        return coordinates

    def _parse_jsonl_log(self, filepath):
        coordinates = []
        try:
            with open(filepath, 'r') as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                        # Assuming the JSON structure is {"timestamp": "...", "data": {"lat": ..., "lon": ...}}
                        if isinstance(entry, dict) and 'data' in entry and isinstance(entry['data'], dict):
                            lat = float(entry['data'].get('lat'))
                            lon = float(entry['data'].get('lon'))
                            if not math.isnan(lat) and not math.isnan(lon):
                                coordinates.append((lat, lon))
                    except (json.JSONDecodeError, ValueError, TypeError):
                        self.logger.log_warning(f"Skipping invalid JSON line in {filepath} for map: {line.strip()}")
                        continue
        except Exception as e:
            self.logger.log_error(f"Error parsing JSONL log file {filepath} for map: {e}")
            raise
        return coordinates

    def generate_map(self, coordinates, map_title="GPS Track Map"):
        if not coordinates:
            messagebox.showinfo("No Data", "No valid coordinates provided to generate map.")
            self.logger.log_info("No valid coordinates to generate map.")
            self.last_generated_map_path = None
            return None

        # Generate a unique filename with current date and time
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        map_filename = f"gps_log_map_{timestamp_str}.html"
        map_filepath = os.path.join(LOG_DIR, map_filename) # Save in main log directory

        # Start map at the first position
        map_center = coordinates[0]
        log_folium_map = folium.Map(location=map_center, zoom_start=15, tiles="OpenStreetMap", control_scale=True)

        # Add all points as a polyline
        if len(coordinates) > 1:
            folium.PolyLine(coordinates, color="blue", weight=2.5, opacity=1).add_to(log_folium_map)

        # Add start and end markers
        folium.Marker(coordinates[0], popup="Start", icon=folium.Icon(color='green', icon='play')).add_to(log_folium_map)
        folium.Marker(coordinates[-1], popup="End", icon=folium.Icon(color='red', icon='stop')).add_to(log_folium_map)

        # Add a title to the map
        title_html = f'''
             <h3 align="center" style="font-size:16px"><b>{map_title}</b></h3>
             '''
        log_folium_map.get_root().html.add_child(folium.Element(title_html))


        try:
            log_folium_map.save(map_filepath)
            self.logger.log_info(f"Log map generated at: {map_filepath}")
            self.last_generated_map_path = map_filepath
            # messagebox.showinfo("Map Generated", f"Map generated successfully at:\n{os.path.basename(map_filepath)}")
            return map_filepath
        except Exception as e:
            self.logger.log_error(f"Error saving log map: {e}")
            messagebox.showerror("Map Error", f"Could not generate map: {e}")
            self.last_generated_map_path = None
            return None

    def get_last_generated_map_path(self):
        return self.last_generated_map_path
