🛰️ GPS Dashboard Application
A versatile desktop application for real-time GPS data visualization, logging, geofencing, and trip analysis. Built with Python and Tkinter, featuring a modern UI with ttkbootstrap and powerful plotting capabilities with Matplotlib and Folium.

✨ Features
📊 Real-time GPS Data Display: View live latitude, longitude, altitude, speed, heading, satellite information, and fix type.

🧭 Driving Dashboard: A dedicated, visually engaging dashboard for key driving metrics like current speed, altitude, and a dynamic compass.

📡 Satellite Skyplot & CNO Levels: Visualize satellite positions relative to your location and monitor signal strength (CNO).

🗺️ Interactive Map View: See your current track plotted on an interactive map (generated using Folium) that can be opened in a web browser.

📍 Geofencing: Define custom geofences and receive alerts when entering or exiting them.

📝 Data Logging: Log raw NMEA, processed JSON, and CSV data to local files for later analysis.

📈 GPS Trend Plots: Observe historical trends for various GPS parameters like position, speed, and DOP values.

🛣️ Trip Logging & Analysis: Start and end trips to record duration, distance, max speed, and analyze driving habits (hard braking, sharp cornering).

💾 Offline Playback: Load and replay previously recorded GPS log files for analysis or demonstration purposes.

⚙️ Customizable Settings: Adjust logging preferences, theme, unit preferences (metric/imperial), and more.

🗄️ Disk Space Monitoring: Keep an eye on your log directory's disk usage to prevent storage issues.

💻 Software & Hardware Requirements
Software Prerequisites
Python 3.8+: Download and install from python.org.

pip: Python's package installer (usually comes with Python).

Hardware Requirements
U-Blox GPS Module: This application is specifically designed to interface with U-Blox GPS modules (e.g., Sparkfun Qwiic GPS NEO-M9N).

USB-to-Serial Adapter: If your GPS module connects via serial (UART), you'll need a USB-to-Serial adapter to connect it to your computer.

Compatible Operating System: Tested on Linux, Windows, and macOS.

🚀 Installation
Clone the repository:

git clone https://github.com/your-username/gps-dashboard.git
cd gps-dashboard

Create a virtual environment (recommended):

python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

Install dependencies:

pip install -r requirements.txt

(If requirements.txt is not provided, you would manually install them like this:)

pip install ttkbootstrap matplotlib pyserial folium tkhtmlview numpy micropython-ublox

Note: The micropython-ublox library is crucial for communicating with U-Blox GPS modules. If you encounter issues, ensure it's correctly installed for your environment.

▶️ Usage
Activate your virtual environment (if you created one):

# On Windows:
.\venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

Run the application:

python gps_dashboard_app.py

Connect your GPS Module:

Ensure your U-Blox GPS module is connected to your computer via a serial port (e.g., /dev/ttyACM0 on Linux, COMx on Windows).

The application will attempt to auto-connect based on the port and baudrate specified in settings.json (or the default values).

You can adjust these settings in the "Settings" tab if needed.

Navigate through tabs:

Driving Dashboard: See primary driving metrics.

GPS Data: Detailed raw and processed GPS information.

Satellite Skyplot: Visual representation of satellites.

Map: View your live track on a generated map.

Geofencing: Add, edit, or delete geofences.

NMEA Console: View raw NMEA sentences (if enabled in settings).

GPS Trend Data: Historical plots of various GPS parameters.

Travel History: A table of real-time data points.

Trip History: Summaries of completed trips.

Trip Analysis: Analyze selected trips from history.

Log File Map: Generate maps from any saved log file.

Settings: Configure application preferences.

Offline Playback:

Go to the "Settings" tab.

Check "Enable Offline Mode".

Click "Browse" to select a .csv or .jsonl log file.

Use the "Play", "Pause", and "Stop" buttons to control playback. Adjust speed with the slider.

When offline mode is disabled, the application will attempt to reconnect to the live GPS module.

⚙️ Configuration
The application uses a settings.json file (created automatically on first run) to store user preferences. You can modify these settings directly within the "Settings" tab of the application.

Key configurable settings include:

port: Serial port of your GPS module (e.g., /dev/ttyACM0, COM3).

baudrate: Baud rate for serial communication (e.g., 115200, 38400).

theme: Application UI theme (e.g., darkly, flatly, cosmo).

log_nmea, log_json, log_csv: Boolean flags to enable/disable different log file types.

display_nmea_console: Enable/disable displaying raw NMEA data in the console tab.

log_directory, trip_log_directory: Paths for saving log files.

log_max_bytes_mb, log_backup_count, max_log_age_days: Log file rotation settings.

speed_noise_threshold_mps: Threshold below which speed is considered zero for analysis.

unit_preference: Choose between "metric" (km/h, m, km) and "imperial" (mph, ft, miles) units for display.

offline_mode_active: Boolean to enable/disable offline playback mode.

offline_log_filepath: Path to the last loaded offline log file.

📸 Main Screens (Placeholders)
(Replace these with actual screenshots of your application)

Main Dashboard
Map View
Settings Tab
Trip Analysis
⚠️ Disclaimers, Liability, and Warnings
Disclaimer
This software is provided "as is", without warranty of any kind, express or implied, including but not limited to the warranties of merchantability, fitness for a particular purpose and noninfringement. In no event shall the authors or copyright holders be liable for any claim, damages or other liability, whether in an action of contract, tort or otherwise, arising from, out of or in connection with the software or the use or other dealings in the software.

Limitation of Liability
The developer(s) of this application shall not be liable for any direct, indirect, incidental, special, consequential, or exemplary damages, including but not limited to, damages for loss of profits, goodwill, use, data, or other intangible losses (even if the developer(s) have been advised of the possibility of such damages), resulting from: (i) the use or the inability to use the application; (ii) the cost of procurement of substitute goods and services resulting from any goods, data, information, or services purchased or obtained or messages received or transactions entered into through or from the application; (iii) unauthorized access to or alteration of your transmissions or data; (iv) statements or conduct of any third party on the application; or (v) any other matter relating to the application.

Important Warning
This application is for informational and experimental purposes only and should NOT be used for critical navigation, safety-of-life applications, or any situation where accurate and reliable positioning is essential. GPS data can be inaccurate, delayed, or unavailable due to various factors (e.g., signal interference, satellite availability, environmental conditions, hardware limitations). Always use certified and reliable navigation equipment for critical tasks.

🤝 Contributing
Contributions are welcome! If you have suggestions for improvements, bug fixes, or new features, please feel free to:

Fork the repository.

Create a new branch (git checkout -b feature/YourFeature).

Make your changes.

Commit your changes (git commit -m 'Add new feature').

Push to the branch (git push origin feature/YourFeature).

Open a Pull Request.

📜 License
This project is licensed under the MIT License - see the LICENSE file for details.

🙏 Credits
Developed using Gemini, with significant input and contributions from gr4ytips.