import collections
import datetime

class DataManager:
    def __init__(self, max_data_points=300):
        self.sensor_data_history = collections.deque(maxlen=max_data_points)
        self.timestamps = collections.deque(maxlen=max_data_points)

    def add_data(self, timestamp, data):
        """Adds new sensor data and its timestamp to the history."""
        self.timestamps.append(timestamp)
        self.sensor_data_history.append(data)

    def get_filtered_data(self, time_range_str):
        """
        Returns filtered sensor data and timestamps based on the specified time range.
        """
        if not self.timestamps:
            return [], []

        current_time = datetime.datetime.now()
        time_limit = None

        if time_range_str == "Last 10 minutes":
            time_limit = current_time - datetime.timedelta(minutes=10)
        elif time_range_str == "Last 30 minutes":
            time_limit = current_time - datetime.timedelta(minutes=30)
        elif time_range_str == "Last hour":
            time_limit = current_time - datetime.timedelta(hours=1)
        elif time_range_str == "Last 6 hours":
            time_limit = current_time - datetime.timedelta(hours=6)
        elif time_range_str == "Last 24 hours":
            time_limit = current_time - datetime.timedelta(hours=24)
        # If "All data" or no match, time_limit remains None, returning all data

        filtered_timestamps = []
        filtered_sensor_data = []

        for i, timestamp in enumerate(self.timestamps):
            if time_limit is None or timestamp >= time_limit:
                filtered_timestamps.append(timestamp)
                filtered_sensor_data.append(self.sensor_data_history[i])
        
        return filtered_timestamps, filtered_sensor_data

    def get_latest_values(self):
        """Returns the most recent sensor data."""
        if self.sensor_data_history:
            return self.sensor_data_history[-1]
        return {}
