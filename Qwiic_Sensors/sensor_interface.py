import random # For mocking sensor data
import sys

# Import actual qwiic and adafruit sensor libraries
# Wrap board import in try-except for non-SBC platforms like Windows/macOS
try:
    import board # For Adafruit I2C
    # Initialize I2C for Adafruit sensors
    I2C_BUS = board.I2C()
    SENSORS_AVAILABLE = True
except (ImportError, NotImplementedError) as e: # Catch both ImportError and NotImplementedError
    print(f"Hardware I2C/Board support not fully available or detected: {e}. Running in mock mode.")
    # Mock imports if libraries are not installed or board is not supported
    qwiic_bme280 = None
    qwiic_sgp40 = None
    adafruit_shtc3 = None
    qwiic_proximity = None
    I2C_BUS = None
    SENSORS_AVAILABLE = False
except Exception as e: # Catch any other unexpected errors during board/I2C setup
    print(f"An unexpected error occurred during board/I2C setup: {e}. Running in mock mode.")
    qwiic_bme280 = None
    qwiic_sgp40 = None
    adafruit_shtc3 = None
    qwiic_proximity = None
    I2C_BUS = None
    SENSORS_AVAILABLE = False

# Only attempt to import qwiic sensors if SENSORS_AVAILABLE is still True
if SENSORS_AVAILABLE:
    try:
        import qwiic_bme280
        import qwiic_sgp40
        import adafruit_shtc3
        import qwiic_proximity
    except ImportError:
        print("Qwiic sensor libraries not found, even if board was detected. Running in mock mode.")
        qwiic_bme280 = None
        qwiic_sgp40 = None
        adafruit_shtc3 = None
        qwiic_proximity = None
        SENSORS_AVAILABLE = False
else: # If SENSORS_AVAILABLE is already False due to board error, ensure qwiic imports are also None
    qwiic_bme280 = None
    qwiic_sgp40 = None
    adafruit_shtc3 = None
    qwiic_proximity = None


class SensorInterface:
    def __init__(self, status_queue):
        self.status_queue = status_queue
        self.bme = None
        self.sgp = None
        self.prox = None
        self.sht = None

        self._initialize_sensors()

    def _initialize_sensors(self):
        """Initializes all connected sensors."""
        if qwiic_bme280 and SENSORS_AVAILABLE:
            self.bme = qwiic_bme280.QwiicBme280()
            if not self.bme.connected:
                self.status_queue.put({'type': 'status_message', 'message': "BME280 not connected!", 'color': 'red'})
                self.bme = None
            else:
                self.bme.begin()
                self.status_queue.put({'type': 'status_message', 'message': "BME280 connected.", 'color': 'green'})
        elif not SENSORS_AVAILABLE:
            self.status_queue.put({'type': 'status_message', 'message': "BME280 library not found (mocking).", 'color': 'red'})
        else:
            self.status_queue.put({'type': 'status_message', 'message': "BME280 sensor object not created.", 'color': 'orange'})


        if qwiic_sgp40 and SENSORS_AVAILABLE:
            self.sgp = qwiic_sgp40.QwiicSGP40()
            if self.sgp.begin() != 0:
                self.status_queue.put({'type': 'status_message', 'message': "SGP40 not connected!", 'color': 'red'})
                self.sgp = None
            else:
                self.status_queue.put({'type': 'status_message', 'message': "SGP40 connected.", 'color': 'green'})
        elif not SENSORS_AVAILABLE:
            self.status_queue.put({'type': 'status_message', 'message': "SGP40 library not found (mocking).", 'color': 'red'})
        else:
            self.status_queue.put({'type': 'status_message', 'message': "SGP40 sensor object not created.", 'color': 'orange'})


        if qwiic_proximity and SENSORS_AVAILABLE:
            self.prox = qwiic_proximity.QwiicProximity()
            if not self.prox.connected:
                self.status_queue.put({'type': 'status_message', 'message': "Proximity sensor not connected!", 'color': 'red'})
                self.prox = None
            else:
                self.prox.begin()
                self.prox.power_on_proximity()
                self.prox.power_on_ambient()
                self.prox.enable_white_channel()
                self.status_queue.put({'type': 'status_message', 'message': "Proximity sensor connected.", 'color': 'green'})
        elif not SENSORS_AVAILABLE:
            self.status_queue.put({'type': 'status_message', 'message': "Proximity library not found (mocking).", 'color': 'red'})
        else:
            self.status_queue.put({'type': 'status_message', 'message': "Proximity sensor object not created.", 'color': 'orange'})


        if adafruit_shtc3 and I2C_BUS and SENSORS_AVAILABLE:
            try:
                self.sht = adafruit_shtc3.SHTC3(I2C_BUS)
                self.status_queue.put({'type': 'status_message', 'message': "SHTC3 connected.", 'color': 'green'})
            except ValueError:
                self.status_queue.put({'type': 'status_message', 'message': "SHTC3 not found on I2C bus!", 'color': 'red'})
                self.sht = None
            except Exception as e:
                self.status_queue.put({'type': 'status_message', 'message': f"SHTC3 init error: {e}", 'color': 'red'})
                self.sht = None
        elif not SENSORS_AVAILABLE:
            self.status_queue.put({'type': 'status_message', 'message': "SHTC3 library or I2C bus not found (mocking).", 'color': 'red'})
        else:
            self.status_queue.put({'type': 'status_message', 'message': "SHTC3 sensor object not created.", 'color': 'orange'})

    def read_all_sensors(self):
        """Reads data from all initialized sensors or generates mock data."""
        sensor_data = {}

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
                self.status_queue.put({'type': 'status_message', 'message': f"BME280 read error: {e}", 'color': 'orange'})
                sensor_data['bme280'] = {k: float('nan') for k in ['temp_c', 'humidity', 'pressure', 'altitude', 'temp_f', 'dewpoint_c', 'dewpoint_f']}
        else:
            # Mock data for BME280 if not available or not connected
            sensor_data['bme280'] = {
                'temp_c': random.uniform(20, 30),
                'humidity': random.uniform(40, 60),
                'pressure': random.uniform(900, 1100),
                'altitude': random.uniform(500, 1500),
                'temp_f': random.uniform(68, 86),
                'dewpoint_c': random.uniform(10, 20),
                'dewpoint_f': random.uniform(50, 68)
            } if not SENSORS_AVAILABLE else {k: float('nan') for k in ['temp_c', 'humidity', 'pressure', 'altitude', 'temp_f', 'dewpoint_c', 'dewpoint_f']}

        # SGP40
        if self.sgp:
            try:
                sensor_data['sgp40'] = {'voc_index': self.sgp.get_VOC_index()}
            except Exception as e:
                self.status_queue.put({'type': 'status_message', 'message': f"SGP40 read error: {e}", 'color': 'orange'})
                sensor_data['sgp40'] = {'voc_index': float('nan')}
        else:
            # Mock data for SGP40 if not available or not connected
            sensor_data['sgp40'] = {'voc_index': random.uniform(0, 500)} if not SENSORS_AVAILABLE else {'voc_index': float('nan')}

        # SHTC3
        if self.sht:
            try:
                sensor_data['shtc3'] = {
                    'temperature': self.sht.temperature,
                    'humidity': self.sht.relative_humidity
                }
            except Exception as e:
                self.status_queue.put({'type': 'status_message', 'message': f"SHTC3 read error: {e}", 'color': 'orange'})
                sensor_data['shtc3'] = {'temperature': float('nan'), 'humidity': float('nan')}
        else:
            # Mock data for SHTC3 if not available or not connected
            sensor_data['shtc3'] = {
                'temperature': random.uniform(20, 30),
                'humidity': random.uniform(40, 60)
            } if not SENSORS_AVAILABLE else {'temperature': float('nan'), 'humidity': float('nan')}

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
                self.status_queue.put({'type': 'status_message', 'message': f"Proximity read error: {e}", 'color': 'orange'})
                sensor_data['proximity'] = {'proximity': float('nan'), 'ambient_light': float('nan'), 'white_light': float('nan')}
        else:
            # Mock data for Proximity if not available or not connected
            sensor_data['proximity'] = {
                'proximity': random.randint(0, 255),
                'ambient_light': random.randint(0, 1023),
                'white_light': random.randint(0, 1023)
            } if not SENSORS_AVAILABLE else {'proximity': float('nan'), 'ambient_light': float('nan'), 'white_light': float('nan')}

        return sensor_data

