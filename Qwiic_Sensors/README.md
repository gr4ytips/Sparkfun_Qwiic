# 🚀 Qwiic Sensor Dashboard

> Developed by **Gemini** with feedback from **Gra4ytips**  
> 📜 _No warranty is expressed or implied._  
> 🧾 Licensed under [Creative Commons Attribution-ShareAlike 4.0 International](http://creativecommons.org/licenses/by-sa/4.0/)

---

## 📖 Overview

The **Qwiic Sensor Dashboard** is a Python-based GUI application to monitor, log, and visualize data from various **SparkFun Qwiic** sensors.  
✨ Built with `tkinter`, `ttkbootstrap`, and `matplotlib`, it offers a modern, responsive UI optimized for Raspberry Pi screens.

---

## ✨ Features

- 📡 **Real-time Sensor Readings**: BME280, SGP40, SHTC3, Proximity
- 🎛️ **Custom Gauges**: Eye-catching metric visualization
- 📝 **Data Logging**: Toggle per-sensor, set log folders
- 📦 **Automatic Log Archiving**: Compress and store old logs
- 📊 **Interactive Plots**: View historical data in multiple timeframes
- 🕒 **Configurable Read Interval**
- 🔊 **Sound Alerts**: Optional audio cues with `pygame`
- 🖥️ **Responsive UI**: Scrollable, works well on small screens
- 🧭 **Tabbed Interface**: Clear separation of settings and data views

---

## 🧰 Hardware Requirements

- 🍓 Raspberry Pi.
- 🧩 SparkFun Qwiic sensors: BME280, SGP40, Proximity & SHTC3
- 🔌 Qwiic HAT or adapter
- 🖼️ Raspberry Pi Monitor (≥ 800x480)

---

## 💻 Software Requirements

```bash
Python >= 3.7
pip
tkinter
ttkbootstrap
matplotlib
pygame (optional)
qwiic, qwiic_bme280, qwiic_sgp40, qwiic_proximity
adafruit-circuitpython-shtc3
Adafruit-Blinka
```

---

## ⚙️ Installation

1. **Clone the repo**
```bash
git clone https://github.com/gr4ytips/Sparkfun_Qwiic.git
cd Sparkfun_Qwiic/Qwiic_Sensors
```

2. **Install dependencies**
```bash
pip install ttkbootstrap matplotlib pygame sparkfun-qwiic sparkfun-qwiic-bme280 \
sparkfun-qwiic-sgp40 sparkfun-qwiic-proximity adafruit-circuitpython-shtc3 adafruit-blinka
```
> ⚠️ `pygame` is optional  
> 🧪 Runs in mock mode if no physical sensors detected

3. **Enable I2C on Pi**
```bash
sudo raspi-config  # Interface Options → I2C → Enable
```

4. **(Optional) Add Sound Files**
Place `alert.wav`, `up.wav`, and `down.wav` in the project folder.

---

## ▶️ Usage

```bash
python main.py
```

🕐 App initializes sensors and loads the dashboard.

---

## 🧭 User Interface Breakdown

### 🛠️ Controls & Settings Tab
- 🔄 **Sensor Status:** Realtime log output
- 🔊 **Sound Settings:** Toggle alert/change sounds
- 🗃️ **Logging:** Set paths, enable/disable archiving
- 🧮 **Sensor Toggles:** Choose what to log
- 🪄 **Plot Settings:** Select plot range and read interval
- 📂 **Open Folders:** Quick access to logs and archives

### 📈 Sensor Data & Plots Tab
- 🧪 **Live Readings:** Colorful gauges for sensor values
- 📓 **Notebook Tabs:** Separate plots per sensor:
  - 📊 **Combined:** Overview of key metrics
  - 🌡️ **BME280:** Temp, humidity, pressure, altitude
  - 💨 **SGP40:** VOC index
  - 🧴 **SHTC3:** Temp and humidity
  - 👁️ **Proximity:** Distance, light, and white light

🧭 Both tabs support vertical and horizontal scrollbars.

---

## 🖼️ UI Preview

> ![UI Screenshot Placeholder](https://via.placeholder.com/600x300?text=Qwiic+Dashboard+UI+Screenshot)

---

## 📅 Planned Enhancements

- 📁 Export formats: TXT, CSV, JSON
- 🚨 Custom sensor alert thresholds
- ⬇️ Data export button
- 🔍 Enhanced plot interactivity (zoom, pan)

---

## 🧾 License

[![License: CC BY-SA 4.0](https://img.shields.io/badge/License-CC%20BY--SA%204.0-lightgrey.svg)](http://creativecommons.org/licenses/by-sa/4.0/)

---

Made with ❤️ and sensors.
