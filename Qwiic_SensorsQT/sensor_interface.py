import random # For mocking sensor data
import sys
from PyQt5.QtCore import QObject, pyqtSignal # For status messages

# Global flags to track if sensor libraries are importable
_QWIIC_BME280_AVAILABLE = False
_QWIIC_SGP40_AVAILABLE = False
_ADAFRUIT_SHTC3_AVAILABLE = False
_QWIIC_PROXIMITY_AVAILABLE = False
_BOARD_AVAILABLE = False
_I2C_BUS = None # Global I2C bus instance

# Attempt to import board and initialize I2C first
try:
    import board # For Adafruit I2C
    # Initialize I2C for Adafruit sensors
    _I2C_BUS = board.I2C()
    _BOARD_AVAILABLE = True
    print("Hardware I2C/Board support detected.")
except (ImportError, NotImplementedError) as e:
    print(f"Hardware I2C/Board support not fully available or detected: {e}.")
except Exception as e:
    print(f"An unexpected error occurred during board/I2C setup: {e}.")

# Only attempt to import qwiic and adafruit sensors if board is available
if _BOARD_AVAILABLE:
    try:
        import qwiic_bme280
        _QWIIC_BME280_AVAILABLE = True
    except ImportError:
        print("qwiic_bme280 library not found.")
    
    try:
        import qwiic_sgp40
        _QWIIC_SGP40_AVAILABLE = True
    except ImportError:
        print("qwiic_sgp40 library not found.")

    try:
        import adafruit_shtc3
        _ADAFRUIT_SHTC3_AVAILABLE = True
    except ImportError:
        print("adafruit_shtc3 library not found.")
    
    try:
        import qwiic_proximity
        _QWIIC_PROXIMITY_AVAILABLE = True
    except ImportError:
        print("qwiic_proximity library not found.")

class SensorInterface(QObject):
    """
    Handles reading data from various SparkFun Qwiic and Adafruit sensors.
    Can operate in a mock data mode for development/testing without hardware.
    Emits status messages.
    """
    status_message_signal = pyqtSignal(str, str) # message, color ('info', 'warning', 'danger')

    def __init__(self, parent=None, use_mock_data=False):
        super().__init__(parent)
        self._use_mock_data = use_mock_data # Flag to force mock data
        self.bme = None
        self.sgp = None
        self.prox = None
        self.sht = None

        self._initialize_sensors()

    def set_use_mock_data(self, enable_mock):
        """
        Sets whether the interface should use mock data or attempt to read from hardware.
        If changing from mock to real, attempts to re-initialize sensors.
        """
        if self._use_mock_data != enable_mock:
            self._use_mock_data = enable_mock
            self.status_message_signal.emit(f"Mock data mode {'enabled' if enable_mock else 'disabled'}.", 'info')
            self._initialize_sensors() # Re-initialize if mode changes

    def _initialize_sensors(self):
        """Initializes all connected sensors or reports mock mode status."""
        self.bme = None
        self.sgp = None
        self.prox = None
        self.sht = None

        if self._use_mock_data:
            self.status_message_signal.emit("Operating in mock data mode. Hardware sensors are not initialized.", 'info')
            return

        # Initialize BME280
        if _QWIIC_BME280_AVAILABLE:
            try:
                self.bme = qwiic_bme280.QwiicBme280()
                if not self.bme.connected:
                    self.status_message_signal.emit("BME280 not connected!", 'danger')
                    self.bme = None
                else:
                    self.bme.begin()
                    self.status_message_signal.emit("BME280 connected.", 'success')
            except Exception as e:
                self.status_message_signal.emit(f"BME280 initialization error: {e}", 'danger')
                self.bme = None
        else:
            self.status_message_signal.emit("BME280 library not available.", 'warning')

        # Initialize SGP40
        if _QWIIC_SGP40_AVAILABLE:
            try:
                self.sgp = qwiic_sgp40.QwiicSGP40()
                if self.sgp.begin() != 0: # begin() returns 0 on success
                    self.status_message_signal.emit("SGP40 not connected or failed to begin!", 'danger')
                    self.sgp = None
                else:
                    self.status_message_signal.emit("SGP40 connected.", 'success')
            except Exception as e:
                self.status_message_signal.emit(f"SGP40 initialization error: {e}", 'danger')
                self.sgp = None
        else:
            self.status_message_signal.emit("SGP40 library not available.", 'warning')

        # Initialize Proximity Sensor
        if _QWIIC_PROXIMITY_AVAILABLE:
            try:
                self.prox = qwiic_proximity.QwiicProximity()
                if not self.prox.connected:
                    self.status_message_signal.emit("Proximity sensor not connected!", 'danger')
                    self.prox = None
                else:
                    self.prox.begin()
                    self.prox.power_on_proximity()
                    self.prox.power_on_ambient()
                    self.prox.enable_white_channel()
                    self.status_message_signal.emit("Proximity sensor connected.", 'success')
            except Exception as e:
                self.status_message_signal.emit(f"Proximity sensor initialization error: {e}", 'danger')
                self.prox = None
        else:
            self.status_message_signal.emit("Proximity library not available.", 'warning')

        # Initialize SHTC3
        if _ADAFRUIT_SHTC3_AVAILABLE and _BOARD_AVAILABLE and _I2C_BUS:
            try:
                self.sht = adafruit_shtc3.SHTC3(_I2C_BUS)
                self.status_message_signal.emit("SHTC3 connected.", 'success')
            except ValueError:
                self.status_message_signal.emit("SHTC3 not found on I2C bus!", 'danger')
                self.sht = None
            except Exception as e:
                self.status_message_signal.emit(f"SHTC3 initialization error: {e}", 'danger')
                self.sht = None
        else:
            self.status_message_signal.emit("SHTC3 library or I2C bus not available.", 'warning')

    def read_all_sensors(self):
        """Reads data from all initialized sensors or generates mock data based on mode."""
        sensor_data = {}

        # If mock data is explicitly enabled, generate mock data for all sensors
        if self._use_mock_data:
            sensor_data['bme280'] = {
                'temp_c': random.uniform(20, 30),
                'humidity': random.uniform(40, 60),
                'pressure': random.uniform(900, 1100),
                'altitude': random.uniform(500, 1500),
                'temp_f': random.uniform(68, 86),
                'dewpoint_c': random.uniform(10, 20),
                'dewpoint_f': random.uniform(50, 68)
            }
            sensor_data['sgp40'] = {'voc_index': random.uniform(0, 500)}
            sensor_data['shtc3'] = {'temperature': random.uniform(20, 30), 'humidity': random.uniform(40, 60)}
            sensor_data['proximity'] = {
                'proximity': random.randint(0, 255),
                'ambient_light': random.randint(0, 1023),
                'white_light': random.randint(0, 1023)
            }
            return sensor_data

        # If not in mock mode, attempt to read from real sensors, falling back to NaN if error
        # BME280
        if self.bme:
            try:
                sensor_data['bme280'] = {
                    'temp_c': self.bme.get_temperature_celsius(),
                    'humidity': self.bme.read_humidity(),
                    'pressure': self.bme.read_pressure(),
                    'altitude': self.bme.get_altitude_feet(),
                    'temp_f': self.bme.get_temperature_fahrenheit(),
                    'dewpoint_c': self.bme.get_dewpoint_celsius(),
                    'dewpoint_f': self.bme.get_dewpoint_fahrenheit()
                }
            except Exception as e:
                self.status_message_signal.emit(f"BME280 read error: {e}", 'warning')
                sensor_data['bme280'] = {k: float('nan') for k in ['temp_c', 'humidity', 'pressure', 'altitude', 'temp_f', 'dewpoint_c', 'dewpoint_f']}
        else:
            sensor_data['bme280'] = {k: float('nan') for k in ['temp_c', 'humidity', 'pressure', 'altitude', 'temp_f', 'dewpoint_c', 'dewpoint_f']}

        # SGP40
        if self.sgp:
            try:
                sensor_data['sgp40'] = {'voc_index': self.sgp.get_VOC_index()}
            except Exception as e:
                self.status_message_signal.emit(f"SGP40 read error: {e}", 'warning')
                sensor_data['sgp40'] = {'voc_index': float('nan')}
        else:
            sensor_data['sgp40'] = {'voc_index': float('nan')}

        # SHTC3
        if self.sht:
            try:
                sensor_data['shtc3'] = {
                    'temperature': self.sht.temperature,
                    'humidity': self.sht.relative_humidity
                }
            except Exception as e:
                self.status_message_signal.emit(f"SHTC3 read error: {e}", 'warning')
                sensor_data['shtc3'] = {'temperature': float('nan'), 'humidity': float('nan')}
        else:
            sensor_data['shtc3'] = {'temperature': float('nan'), 'humidity': float('nan')}

        # Proximity
        if self.prox:
            try:
                prox_value = self.prox.get_proximity()
                light_value = self.prox.get_ambient()
                white_value = self.prox.get_white()
                sensor_data['proximity'] = {
                    'proximity': prox_value,
                    'ambient_light': light_value,
                    'white_light': white_value
                }
            except Exception as e:
                self.status_message_signal.emit(f"Proximity read error: {e}", 'warning')
                sensor_data['proximity'] = {'proximity': float('nan'), 'ambient_light': float('nan'), 'white_light': float('nan')}
        else:
            sensor_data['proximity'] = {'proximity': float('nan'), 'ambient_light': float('nan'), 'white_light': float('nan')}

        return sensor_data

