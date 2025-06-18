from PyQt5.QtCore import QThread, pyqtSignal, QObject, QTimer
import time
import datetime
import queue # Still using queue for control messages from GUI to thread

from sensor_interface import SensorInterface
from data_logger import DataLogger
from data_manager import DataManager

class SensorReaderThread(QThread):
    """
    A QThread subclass responsible for continuously reading sensor data,
    managing historical data, logging, and sending updates to the GUI.
    It processes control messages from the GUI and triggers automatic archiving.
    """
    # Signals to communicate with the main GUI thread
    sensor_data_ready_signal = pyqtSignal(dict) # Emits the latest sensor readings
    status_message_signal = pyqtSignal(str, str) # message, color ('info', 'warning', 'danger')

    def __init__(self, data_manager: DataManager, data_logger: DataLogger, initial_read_interval=5, use_mock_data=False, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.data_logger = data_logger
        # SensorInterface now emits its own status messages, which are connected in MainWindow
        self.sensor_interface = SensorInterface(parent=self, use_mock_data=use_mock_data) # Pass self as parent for QObject cleanup
        
        # Connect SensorInterface's status signal to this thread's status signal
        # This allows SensorInterface to send messages directly to the GUI via this thread
        self.sensor_interface.status_message_signal.connect(self.status_message_signal.emit)

        self.read_interval = initial_read_interval # Seconds between full sensor reads
        self.polling_interval_ms = 100 # Milliseconds for responsiveness within sleep
        self.control_queue = queue.Queue() # Queue for control messages from GUI (e.g., update interval, archive now)
        self._is_running = True # Control flag for the run loop

    def run(self):
        """Main loop for reading sensors and processing data."""
        self.status_message_signal.emit("Sensor thread started.", 'info')
        next_read_time = time.time()

        while self._is_running:
            # Process control messages from the GUI
            try:
                while True:
                    control_message = self.control_queue.get(timeout=self.polling_interval_ms / 1000.0)
                    self._process_control_message(control_message)
            except queue.Empty:
                pass # No control message, continue

            current_time = time.time()
            if current_time >= next_read_time:
                # Read sensors
                sensor_readings = self.sensor_interface.read_all_sensors()
                timestamp = datetime.datetime.now()

                # Add data to DataManager history
                self.data_manager.add_data(timestamp, sensor_readings)

                # Log data using DataLogger
                self.data_logger.log_sensor_data(sensor_readings)

                # Send data to GUI for real-time display/plotting
                self.sensor_data_ready_signal.emit(sensor_readings)

                # Check for automatic archiving (DataLogger manages its own interval)
                self.data_logger.check_and_archive_auto()

                # Calculate next read time based on the actual time of the last read
                next_read_time = current_time + self.read_interval
            
            # Sleep for a short duration to remain responsive to stop events and control messages
            time_to_wait = next_read_time - time.time()
            if time_to_wait > 0:
                # Sleep in chunks to allow control messages to be processed
                sleep_chunk = self.polling_interval_ms / 1000.0
                while time_to_wait > 0 and self._is_running:
                    sleep_duration = min(time_to_wait, sleep_chunk)
                    time.sleep(sleep_duration)
                    time_to_wait -= sleep_duration
            
        self.status_message_signal.emit("Sensor thread stopped.", 'info')
        self.quit() # Properly end the QThread

    def stop(self):
        """Signals the thread to stop its execution."""
        self._is_running = False
        # Put a dummy message in the queue to unblock it if it's waiting
        # This ensures the thread can exit the queue.get() call quickly
        self.control_queue.put({'type': 'shutdown'})
        self.status_message_signal.emit("Sensor thread stop signal received.", 'info')

    def _process_control_message(self, control_message):
        """Processes control messages received from the GUI."""
        msg_type = control_message.get('type')

        if msg_type == 'update_log_settings':
            # Update data logger configuration
            new_log_path = control_message.get('log_path_str')
            new_archive_path = control_message.get('archive_path_str')
            new_debug_log_path = control_message.get('debug_log_path_str')
            new_archive_enabled = control_message.get('archive_enabled_bool')
            new_sensor_log_settings = control_message.get('new_sensor_log_settings')
            new_debug_to_console_enabled = control_message.get('new_debug_to_console_enabled') # Get new arg
            new_debug_log_level = control_message.get('new_debug_log_level') # Get new arg

            self.data_logger.update_config(
                new_log_path, 
                new_archive_path, 
                new_debug_log_path,
                new_archive_enabled,
                new_sensor_log_settings,
                new_debug_to_console_enabled, # Pass new arg
                new_debug_log_level # Pass new arg
            )
            self.status_message_signal.emit("Logging configuration updated by sensor thread.", 'info')

        elif msg_type == 'archive_now':
            # Trigger manual archive
            self.data_logger.archive_logs()
            self.status_message_signal.emit("Manual log archive initiated by sensor thread.", 'info')
        
        elif msg_type == 'update_read_interval':
            # Update the sensor reading interval
            try:
                new_interval = int(control_message['interval'])
                if new_interval <= 0:
                    raise ValueError("Read interval must be a positive integer.")
                self.read_interval = new_interval
                self.status_message_signal.emit(f"Sensor read interval updated to {new_interval} seconds (thread).", 'info')
            except ValueError as e:
                self.status_message_signal.emit(f"Invalid read interval received by thread: {e}", 'danger')
        
        elif msg_type == 'toggle_mock_data':
            # Toggle mock data setting in sensor interface
            enable_mock = control_message['enable']
            self.sensor_interface.set_use_mock_data(enable_mock)
            self.status_message_signal.emit(f"Sensor interface mock data mode set to {enable_mock}.", 'info')
        
        elif msg_type == 'shutdown':
            # Handle shutdown request
            self._is_running = False
            self.status_message_signal.emit("Shutdown command received in sensor thread.", 'info')
        
        else:
            self.status_message_signal.emit(f"Unknown control message type received: {msg_type}", 'warning')

