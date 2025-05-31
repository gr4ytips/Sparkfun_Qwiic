import threading
import time
import queue
import datetime

from sensor_interface import SensorInterface
from data_logger import DataLogger
from data_manager import DataManager

class SensorReader(threading.Thread):
    def __init__(self, data_queue, status_queue, data_manager, data_logger, stop_event, initial_read_interval=5):
        super().__init__()
        self.data_queue = data_queue # For sending raw sensor data to GUI for display/plotting
        self.status_queue = status_queue # For sending status messages to GUI
        self.data_manager = data_manager # Instance of DataManager
        self.data_logger = data_logger # Instance of DataLogger
        self.sensor_interface = SensorInterface(status_queue) # Instance of SensorInterface
        self.stop_event = stop_event
        self.read_interval = initial_read_interval # Seconds between full sensor reads
        self.polling_interval_ms = 100 # Milliseconds for responsiveness within sleep
        self.control_queue = queue.Queue() # Queue for control messages from GUI (e.g., update interval, archive now)

    def run(self):
        """Main loop for reading sensors and processing data."""
        print("SensorReader thread: Starting run loop.")
        next_read_time = time.time()

        while not self.stop_event.is_set():
            # Process control messages from the GUI
            try:
                while True:
                    control_message = self.control_queue.get_nowait()
                    if control_message['type'] == 'update_log_settings':
                        # Pass updated log settings to the DataLogger
                        self.data_logger.update_config(
                            control_message['log_path_str'],
                            control_message['archive_path_str'],
                            control_message['archive_enabled_bool'],
                            control_message['new_sensor_log_settings']
                        )
                    elif control_message['type'] == 'archive_now':
                        # Trigger immediate archive
                        self.data_logger.archive_logs()
                    elif control_message['type'] == 'update_read_interval':
                        # Update the sensor reading interval
                        try:
                            new_interval = int(control_message['interval'])
                            if new_interval <= 0:
                                raise ValueError("Read interval must be a positive integer.")
                            self.read_interval = new_interval
                            self.status_queue.put({'type': 'status_message', 'message': f"Sensor read interval updated to {new_interval} seconds (thread).", 'color': 'green'})
                        except ValueError as e:
                            self.status_queue.put({'type': 'status_message', 'message': f"Invalid read interval received by thread: {e}", 'color': 'red'})
                    if self.stop_event.is_set():
                        break # Exit control message loop if stop event is set
            except queue.Empty:
                pass # No control messages, continue

            if self.stop_event.is_set():
                print("SensorReader thread: Stop event set after control message check. Breaking main loop.")
                break

            current_time = time.time()
            if current_time >= next_read_time:
                # Check and trigger automatic log archiving if due
                self.data_logger.check_and_archive_auto()
                
                if self.stop_event.is_set():
                    print("SensorReader thread: Stop event set after automatic archive check. Breaking main loop.")
                    break

                # Read data from sensors
                sensor_readings = self.sensor_interface.read_all_sensors()
                timestamp = datetime.datetime.now()

                # Add data to DataManager history
                self.data_manager.add_data(timestamp, sensor_readings)

                # Log data using DataLogger
                self.data_logger.log_sensor_data(sensor_readings)

                # Send data to GUI for real-time display/plotting
                self.data_queue.put({'type': 'sensor_data', 'data': sensor_readings})

                next_read_time = current_time + self.read_interval
                # print(f"SensorReader thread: Next read scheduled for {next_read_time - time.time():.2f} seconds.")

            # Sleep for a short duration to remain responsive to stop events and control messages
            time_to_wait = next_read_time - time.time()
            if time_to_wait > 0:
                sleep_chunk = self.polling_interval_ms / 1000.0
                while time_to_wait > 0 and not self.stop_event.is_set():
                    sleep_duration = min(time_to_wait, sleep_chunk)
                    time.sleep(sleep_duration)
                    time_to_wait -= sleep_duration
            
        print("SensorReader thread: Main loop exited. Initiating cleanup.")
        self.status_queue.put({'type': 'status_message', 'message': "Sensor thread stopped.", 'color': 'gray'})
        print("SensorReader thread: Cleanup complete. Thread exiting.")

