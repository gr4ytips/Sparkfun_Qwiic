# 🛰️ GPS Dashboard Application

A versatile Python desktop app for **real-time GPS data visualization**, **logging**, **geofencing**, and **trip analysis**. Built with `tkinter`, `ttkbootstrap`, and powered by `Matplotlib`, `Folium`, and `sparkfun-ublox-gps`.

---

## ✨ Features

- 📊 **Live GPS Data**: Latitude, longitude, altitude, speed, heading, fix type, satellites
- 🧭 **Driving Dashboard**: Speed, altitude, compass, and dynamic indicators
- 📡 **Satellite Skyplot**: Visual CNO and satellite positioning
- 🗺️ **Interactive Map View**: Real-time track plotted with `folium`
- 📍 **Geofencing**: Custom alerts for entering/exiting zones
- 📝 **Data Logging**: Save NMEA, JSON, and CSV formats
- 📈 **Trend Plots**: Analyze speed, DOP, and location history
- 🛣️ **Trip Logging**: Track trip duration, distance, max speed, and driving events
- 💾 **Offline Playback**: Replay `.csv` or `.jsonl` logs
- ⚙️ **Customizable Settings**: Themes, units, logging, ports
- 🗄️ **Disk Monitoring**: Warns if logs consume too much space

---

## 💻 Requirements

### Software
- Python ≥ 3.8
- pip
- Libraries:  
  `ttkbootstrap`, `matplotlib`, `pyserial`, `folium`, `tkhtmlview`, `numpy`, `sparkfun-ublox-gps`

### Hardware
- U-Blox GPS module (e.g. Sparkfun Qwiic GPS NEO-M9N)
- USB-to-Serial adapter (if not using USB directly)
- Linux / Windows / macOS

---

## 🚀 Installation

```bash
git clone https://github.com/gr4ytips/Sparkfun_Qwiic.git
cd Sparkfun_Qwiic_GPS_NEO-M9N_SMA_GPS-17285
python -m venv venv
source venv/bin/activate      # On Windows use: .\venv\Scripts\activate
pip install -r requirements.txt
```

If no `requirements.txt`:

```bash
pip install ttkbootstrap matplotlib pyserial folium tkhtmlview numpy sparkfun-ublox-gps
```

---

## ▶️ Usage

```bash
python gps_dashboard_app.py
```

- App auto-connects to your GPS (configured via `settings.json`)
- Customize in-app via **Settings** tab

### Navigation Tabs:

- **Driving Dashboard** – Speed, compass, altitude
- **GPS Data** – Raw and processed NMEA fields
- **Skyplot** – Satellite view & signal strength
- **Map** – Live or historical map view
- **Geofencing** – Create/edit zone alerts
- **Console** – Raw NMEA output
- **Trends** – Graphs of historical GPS values
- **Trip History** – Past drives with metrics
- **Trip Analysis** – Event analytics like braking/cornering
- **Offline Playback** – Load log file and simulate session

---

## ⚙️ Configuration

Settings are stored in `settings.json`. Editable via app or manually:

```json
{
  "port": "/dev/ttyACM0",
  "baudrate": 115200,
  "theme": "flatly",
  "unit_preference": "metric",
  "log_csv": true,
  "log_json": true,
  "log_nmea": false
}
```

---

## 📸 Screenshots *(Replace placeholders)*

- ![Dashboard](https://github.com/gr4ytips/Sparkfun_Qwiic/blob/main/Sparkfun_Qwiic_GPS_NEO-M9N_SMA_GPS-17285/images/GPS%20Dashboard.png)
- ![Map View](https://via.placeholder.com/600x300?text=Live+Map)
- ![Settings](https://via.placeholder.com/600x300?text=Settings+Tab)
- ![Trip Analysis](https://via.placeholder.com/600x300?text=Trip+Analytics)

---

## ⚠️ Disclaimer

This app is **experimental** and should **not be used for critical navigation**. GPS data is subject to signal loss, hardware variation, and interference.

> Use certified tools for safety-of-life applications.

---

## 🤝 Contributing

1. Fork and clone  
2. Create a branch: `git checkout -b feature/my-feature`  
3. Make and commit your changes  
4. Push and open a PR

---

## 📜 License

This project is licensed under the [MIT License](LICENSE).

---

## 🙏 Credits

Developed using **Gemini**, with contributions and feedback from [gr4ytips](https://github.com/gr4ytips)
