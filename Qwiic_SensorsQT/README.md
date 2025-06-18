Sparkfun Qwiic Sensor Dashboard
📊 This project provides a graphical user interface (GUI) application built with PyQt5 for monitoring various Sparkfun Qwiic connected to a Raspberry Pi. It offers real-time data visualization through gauges and plots, data logging, configurable settings, and sound alerts.

## 📝 Project Summary

The Sparkfun Qwiic Sensor Dashboard is designed to offer an intuitive way to interact with environmental and proximity sensors. It features a multi-tabbed interface for:

- 📋 **Dashboard**: Displays key sensor metrics using animated gauges for quick visual assessment.
- 🔍 **Sensor Details**: Provides individual plots and detailed readings for each connected sensor.
- 🗃️ **Logging**: Allows configuration of data logging paths, archiving, and debug logging levels.
- ⚙️ **Settings**: Manages application themes, sensor read intervals, plot update rates, and mock data toggling.

The application is built with a modular architecture, separating concerns like sensor interaction, data management, logging, and sound effects into distinct Python modules, enhancing maintainability and extensibility.

## ✨ Features

- 🔴 **Real-time Sensor Monitoring**: Live display of temperature, humidity, pressure, altitude, VOC index, proximity, and light values.
- 🧭 **Interactive Gauges**: Visually appealing custom gauges for key metrics with configurable color themes.
- 📈 **Dynamic Plotting**: Historical data visualization with adjustable time ranges and per-sensor plots using Matplotlib.
- 📝 **Data Logging**: Automatic logging of sensor data to CSV files with configurable paths and auto-archiving.
- 🐞 **Debug Logging**: Comprehensive debug logs to aid in troubleshooting and development.
- 🎨 **Theming System**: Customizable UI and gauge color themes for a personalized experience.
- 🧪 **Mock Data Mode**: Option to run the application with simulated sensor data for development or testing without physical hardware.
- 🔔 **Sound Alerts**: Optional sound effects for value changes and alerts.
- 📱 **Responsive UI**: Designed to adapt to different window sizes, including maximized mode on startup.

## 🧰 Hardware Requirements

To run this application with physical sensors, you will need the following hardware:

- 🧠 **Raspberry Pi 4 Model B**: The primary computing platform.
- 🧩 **SparkFun Qwiic pHAT v2.0 for Raspberry Pi**: This pHAT provides easy Qwiic connectivity for various sensors.
- 🌡️ **Qwiic Compatible Sensors**:
  - SparkFun Qwiic BME280
  - SparkFun Qwiic SGP40
  - SparkFun SHTC3
  - SparkFun Qwiic Proximity Sensor (VCNL4040/VCNL4200)
- 🔌 **Qwiic Cables**: To connect the sensors.
- 💾 **MicroSD Card**: 16GB or larger.
- 🔋 **Power Supply**: USB-C power supply.
- 🖥️ **Monitor, Keyboard, Mouse**: For setup.

## 💻 Software Requirements

- 🐧 **Operating System**: Raspberry Pi OS (Bullseye or newer)
- 🐍 **Python 3**
- 📦 **Libraries**:
  - PyQt5
  - matplotlib
  - numpy
  - qwiic and sensor-specific packages
  - Adafruit CircuitPython libraries
  - Standard Python libraries

## 🚀 Installation Steps

1. Prepare Raspberry Pi OS and enable I2C
2. Update your system:
   ```bash
   sudo apt update
   sudo apt upgrade
   ```
3. Install dependencies:
   ```bash
   sudo apt install python3-pyqt5 python3-pyqt5.qtmultimedia python3-matplotlib python3-pip
   pip3 install numpy adafruit-circuitpython-shtc3 adafruit-blinka
   pip3 install sparkfun-qwiic qwiic_bme280 qwiic_sgp40 qwiic_proximity
   ```
4. Clone the Repository:
   ```bash
   git clone https://github.com/gr4ytips/Sparkfun_Qwiic.git sensor_dashboard
   cd sensor_dashboard
   ```
5. (Optional) Add sound files: `alert.wav`, `up.wav`, `down.wav`

## ▶️ Usage

Run the app:

```bash
python3 main.py
```

## 🗂️ Project Structure

- `main.py`: Entry point
- `main_window.py`: GUI & interactions
- `settings_manager.py`: Settings and themes
- `custom_widgets.py`: GaugeWidget
- `sound_manager_qt.py`: Sound effects
- `data_manager.py`: Sensor data management
- `data_logger.py`: CSV logging
- `sensor_interface.py`: Sensor I/O and mocks
- `sensor_reader_thread.py`: Background reading

## ⚠️ Important Notes

- Ensure correct wiring and I2C is enabled
- Sound files optional, not mandatory
- Use Mock Data in Settings tab if needed
- Logging paths are configurable

## 📄 License

This project is licensed under the [Creative Commons Attribution 4.0 International License (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).

📘 **Attribution**: This project content was developed using Gemini, with feedback from gr4ytips.

## ⚖️ Liability, Warning, and Disclaimer

### 📌 Liability
This software is provided "as is", without warranty of any kind, express or implied, including but not limited to warranties of merchantability, fitness for a particular purpose, and non-infringement. In no event shall the authors or copyright holders be held liable for any claim, damages, or other liability, whether in an action of contract, tort, or otherwise, arising from, out of, or in connection with the software or the use or other dealings in the software.

### ⚠️ Warning
This application interacts with electronic hardware. Improper use—including incorrect wiring, exceeding voltage limits, or failing to follow safety procedures—may result in damage to the sensors, Raspberry Pi, connected components, or even personal injury. Always follow official hardware documentation and safety guidelines.

### 📢 Disclaimer
The developers of this software assume no responsibility for the integrity, accuracy, or usefulness of the sensor data in specific applications. It is your responsibility to verify the accuracy of sensor outputs and ensure safe usage in critical or commercial environments. The use of this software is entirely at your own risk.
