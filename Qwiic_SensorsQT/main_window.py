import sys
import os
import datetime
from PyQt5.QtWidgets import (
    QMainWindow, QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QTabWidget, QLabel, QComboBox, QPushButton, QLineEdit, QCheckBox,
    QGroupBox, QFileDialog, QScrollArea, QSizePolicy, QStatusBar, QMessageBox,
    QTextEdit, QStyleFactory, QSpacerItem # Import QSpacerItem for layout control
)
from PyQt5.QtGui import QFont, QPalette, QColor, QIcon, QIntValidator
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
import math # Import math for isnan, isinf
import collections # Import collections for deque

# Matplotlib for plotting
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.dates as mdates
import numpy as np # Import numpy for linspace in colormap

# Import custom modules
from settings_manager import SettingsManager
from custom_widgets import GaugeWidget
from sound_manager_qt import SoundManagerQt
from data_manager import DataManager
from data_logger import DataLogger
from sensor_reader_thread import SensorReaderThread

class MainWindow(QMainWindow):
    """
    Main application window for the Sparkfun Qwiic Sensors GUI.
    Manages UI layout, sensor data display, plotting, settings, and inter-thread communication.
    """
    # Define a signal for displaying messages on the status bar from any part of the GUI thread
    status_bar_message_signal = pyqtSignal(str, str) # message, color

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sparkfun Qwiic Sensor Dashboard")
        self.setGeometry(100, 100, 1200, 800) # Increased default window size
        self.showMaximized() # Start maximized for better viewing of multiple widgets

        # --- Managers and Threads ---
        self.settings_manager = SettingsManager()
        # Initialize current_theme_data early
        self.current_theme_data = self.settings_manager.get_theme_data(self.settings_manager.get_setting("theme"))
        if not self.current_theme_data:
            # This should ideally be caught during settings_manager init, but as a fallback
            # Changed from print() to self.debug_logger.error() to ensure it goes to log file
            # However, self.debug_logger is not yet initialized here.
            # We'll temporarily use a direct print, but log once debug_logger is available.
            sys.stderr.write("Initial theme not found, falling back to 'Default Light'. This message will not be in the log.\n")
            self.current_theme_data = self.settings_manager.get_theme_data("Default Light")


        self.data_manager = DataManager(max_data_points=self.settings_manager.get_setting("max_plot_data_points", 300))
        # Pass debug logger instance from DataLogger to other modules if needed
        self.data_logger = DataLogger(
            log_path=self.settings_manager.get_setting("log_path"),
            archive_path=self.settings_manager.get_setting("archive_path"),
            debug_log_path=self.settings_manager.get_setting("debug_log_path"),
            archive_enabled=self.settings_manager.get_setting("archive_enabled"),
            initial_log_settings=self.settings_manager.get_setting("log_sensor_settings"),
            debug_to_console_enabled=self.settings_manager.get_setting("debug_to_console_enabled"),
            debug_log_level=self.settings_manager.get_setting("debug_log_level")
        )
        # Ensure the debug_logger is accessible immediately after initialization
        self.debug_logger = self.data_logger.debug_logger
        self.debug_logger.info("MainWindow initialized: Setting up UI and loading settings.")

        # Now that debug_logger is available, log the theme fallback if it happened
        if not self.settings_manager.get_theme_data(self.settings_manager.get_setting("theme")):
            self.debug_logger.error("Initial theme was not found, fell back to 'Default Light'.")


        self.sound_manager = SoundManagerQt()
        # Connect sound manager's status signal to main window's status bar
        self.sound_manager.status_message_signal.connect(self._display_status_message)

        self.sensor_thread = SensorReaderThread(
            data_manager=self.data_manager,
            data_logger=self.data_logger,
            initial_read_interval=self.settings_manager.get_setting("read_interval"),
            use_mock_data=self.settings_manager.get_setting("mock_data_enabled")
        )
        self.sensor_thread.sensor_data_ready_signal.connect(self._update_ui_with_sensor_data)
        self.sensor_thread.status_message_signal.connect(self._display_status_message)

        # --- UI Elements ---
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)

        self.tabs = QTabWidget()
        self.main_layout.addWidget(self.tabs)

        # New instance variable to track the currently selected sensor for the dashboard plot
        self.current_dashboard_plot_sensor = "All Sensors"

        self._create_dashboard_tab()
        self._create_detail_tab()
        self._create_logging_tab()
        self._create_settings_tab()

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar_message_signal.connect(self._display_status_message)

        # --- Timers ---
        self.plot_update_timer = QTimer(self)
        self.plot_update_timer.setInterval(self.settings_manager.get_setting("plot_update_interval_ms", 1000)) # Default 1 second
        self.plot_update_timer.timeout.connect(self._update_plots)
        self.plot_update_timer.start()
        self.debug_logger.info(f"Plot update timer started with {self.plot_update_timer.interval()} ms interval.")


        # --- Initialize UI State ---
        self._load_initial_settings_to_ui()
        self._apply_current_theme() # Apply theme on startup
        self._update_gauge_colors() # Apply gauge style on startup
        self.sensor_thread.start() # Start the sensor reading thread
        self.debug_logger.info("Application UI setup complete. Sensor thread started.")


    def _create_dashboard_tab(self):
        """Creates the dashboard tab with summary gauges for key sensor metrics."""
        self.dashboard_tab = QWidget()
        self.tabs.addTab(self.dashboard_tab, "Dashboard")
        self.debug_logger.info("Creating Dashboard Tab.")

        # Use a horizontal layout for the main dashboard content
        self.dashboard_main_layout = QHBoxLayout(self.dashboard_tab)

        # Create a container for the sensor group boxes
        self.sensor_gauges_container = QWidget()
        self.sensor_gauges_layout = QGridLayout(self.sensor_gauges_container)
        self.sensor_gauges_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft) # Align items to top-left

        # Explicitly set column stretch factors for the QGridLayout
        # This prevents the columns from expanding unnecessarily and creating white space
        self.sensor_gauges_layout.setColumnStretch(0, 1) # First column gets stretch 1
        self.sensor_gauges_layout.setColumnStretch(1, 1) # Second column gets stretch 1
        self.sensor_gauges_layout.setColumnStretch(2, 1) # Third column also gets stretch 1 to ensure even distribution


        self.dashboard_gauges = {} # Dictionary to hold GaugeWidget instances

        # BME280 Gauges
        self.bme_group_box = self._create_sensor_group_box("BME280 (Temp/Hum/Pres)")
        bme_layout = QGridLayout(self.bme_group_box)

        self.dashboard_gauges['bme280_temp_c'] = GaugeWidget(self, "BME280 Temp (C)", 0, 50, "°C", debug_logger=self.debug_logger)
        bme_layout.addWidget(self.dashboard_gauges['bme280_temp_c'], 0, 0)
        self.dashboard_gauges['bme280_humidity'] = GaugeWidget(self, "BME280 Humidity", 0, 100, "%RH", debug_logger=self.debug_logger)
        bme_layout.addWidget(self.dashboard_gauges['bme280_humidity'], 0, 1)
        self.dashboard_gauges['bme280_pressure'] = GaugeWidget(self, "BME280 Pressure", 900, 1100, "hPa", debug_logger=self.debug_logger)
        bme_layout.addWidget(self.dashboard_gauges['bme280_pressure'], 1, 0)
        self.dashboard_gauges['bme280_altitude'] = GaugeWidget(self, "BME280 Altitude", -100, 1000, "m", debug_logger=self.debug_logger)
        bme_layout.addWidget(self.dashboard_gauges['bme280_altitude'], 1, 1)

        self.sensor_gauges_layout.addWidget(self.bme_group_box, 0, 0)
        self.debug_logger.debug("BME280 group box and gauges added.")

        # SGP40 Gauge
        self.sgp_group_box = self._create_sensor_group_box("SGP40 (VOC Index)")
        sgp_layout = QGridLayout(self.sgp_group_box)
        self.dashboard_gauges['sgp40_voc_index'] = GaugeWidget(self, "SGP40 VOC Index", 0, 500, "", debug_logger=self.debug_logger)
        sgp_layout.addWidget(self.dashboard_gauges['sgp40_voc_index'], 0, 0)
        self.sensor_gauges_layout.addWidget(self.sgp_group_box, 0, 1)
        self.debug_logger.debug("SGP40 group box and gauge added.")

        # SHTC3 Gauge
        self.shtc3_group_box = self._create_sensor_group_box("SHTC3 (Temp/Hum)")
        shtc3_layout = QGridLayout(self.shtc3_group_box)
        self.dashboard_gauges['shtc3_temperature'] = GaugeWidget(self, "SHTC3 Temp (C)", 0, 50, "°C", debug_logger=self.debug_logger)
        shtc3_layout.addWidget(self.dashboard_gauges['shtc3_temperature'], 0, 0)
        self.dashboard_gauges['shtc3_humidity'] = GaugeWidget(self, "SHTC3 Humidity", 0, 100, "%RH", debug_logger=self.debug_logger)
        shtc3_layout.addWidget(self.dashboard_gauges['shtc3_humidity'], 0, 1)
        self.sensor_gauges_layout.addWidget(self.shtc3_group_box, 1, 0)
        self.debug_logger.debug("SHTC3 group box and gauges added.")

        # Proximity Gauge
        self.proximity_group_box = self._create_sensor_group_box("Proximity Sensor")
        proximity_layout = QGridLayout(self.proximity_group_box)
        # Corrected: Changed the key to match the incoming data metric_key 'proximity'
        self.dashboard_gauges['proximity_proximity'] = GaugeWidget(self, "Proximity Value", 0, 255, "", debug_logger=self.debug_logger)
        proximity_layout.addWidget(self.dashboard_gauges['proximity_proximity'], 0, 0)
        self.sensor_gauges_layout.addWidget(self.proximity_group_box, 1, 1)
        self.debug_logger.debug("Proximity group box and gauge added.")

        # Add a QSpacerItem to push the group boxes to the top-left (vertical spacer)
        self.sensor_gauges_layout.addItem(QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding), 2, 0, 1, 2)
        # Add a QSpacerItem to push the group boxes to the left (horizontal spacer)
        self.sensor_gauges_layout.addItem(QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum), 0, 2, 3, 1) # Row 0, Col 2, spans 3 rows, 1 column


        # Add the sensor gauges container to a scroll area
        self.gauge_scroll_area = QScrollArea()
        self.gauge_scroll_area.setWidgetResizable(True)
        self.gauge_scroll_area.setWidget(self.sensor_gauges_container)
        self.gauge_scroll_area.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Expanding) # Allow vertical expansion and minimal horizontal expansion


        # Set stretch factors for the main dashboard layout
        # Give the gauge scroll area a smaller stretch factor (e.g., 1)
        # and the plot group box a larger one (e.g., 3)
        self.dashboard_main_layout.addWidget(self.gauge_scroll_area, 1) # Reduced stretch factor for gauges

        # --- Plot Graph Section (Combined or Individual) ---
        self.dashboard_plot_group_box = self._create_sensor_group_box("Sensor Data Plot")
        dashboard_plot_layout = QVBoxLayout(self.dashboard_plot_group_box)

        # Sensor selection for dashboard plot
        dashboard_plot_sensor_selection_layout = QHBoxLayout()
        dashboard_plot_sensor_selection_layout.addWidget(QLabel("Plot Sensor:"))
        self.dashboard_sensor_combo = QComboBox()
        # Populate with "All Sensors" and then available sensor keys from SENSOR_METRICS_MAP
        sensor_display_names = ["All Sensors"] + [
            self.settings_manager.SENSOR_METRICS_MAP[key].get('display_name', key.replace('_', ' ').title())
            for key in self.settings_manager.SENSOR_METRICS_MAP.keys()
        ]
        self.dashboard_sensor_combo.addItems(sensor_display_names)
        self.dashboard_sensor_combo.setCurrentText("All Sensors") # Default to combined plot
        self.dashboard_sensor_combo.currentTextChanged.connect(self._on_dashboard_sensor_selected)
        dashboard_plot_sensor_selection_layout.addWidget(self.dashboard_sensor_combo)
        dashboard_plot_sensor_selection_layout.addStretch(1)
        dashboard_plot_layout.addLayout(dashboard_plot_sensor_selection_layout)


        # Matplotlib Figure and Canvas for dashboard plot
        self.dashboard_fig, self.dashboard_ax = plt.subplots(figsize=(8, 6))
        self.dashboard_canvas = FigureCanvas(self.dashboard_fig)
        dashboard_plot_layout.addWidget(self.dashboard_canvas)

        # Apply initial theme to dashboard plot
        self._apply_plot_theme(self.dashboard_fig, self.dashboard_ax)

        # Combo box for selecting plot time range (reusing existing one but adding it to this new layout)
        plot_time_range_layout = QHBoxLayout()
        plot_time_range_layout.addWidget(QLabel("Plot Data Range:"))
        self.plot_time_range_combo = QComboBox() # Existing combo box
        self.plot_time_range_combo.addItems(["Last 10 minutes", "Last 30 minutes", "Last hour", "Last 6 hours", "Last 24 hours", "All data"])
        self.plot_time_range_combo.setCurrentText(self.settings_manager.get_setting("plot_time_range", "Last 10 minutes"))
        self.plot_time_range_combo.currentTextChanged.connect(self._on_plot_time_range_changed)
        plot_time_range_layout.addWidget(self.plot_time_range_combo)
        plot_time_range_layout.addStretch(1) # Push combo box to left
        dashboard_plot_layout.addLayout(plot_time_range_layout)

        # Add the dashboard plot group box to the main dashboard layout, give it more space
        self.dashboard_main_layout.addWidget(self.dashboard_plot_group_box, 3) # Main plot gets larger stretch factor

        # List to hold references to plot lines for dynamic updates
        self.dashboard_plot_lines = {} # Renamed from combined_plot_lines
        self.dashboard_plot_data_series = {} # Renamed from combined_plot_data_series

        self.debug_logger.info("Dashboard Tab created.")

    def _create_detail_tab(self):
        """Creates the detail tab with individual sensor plots and detailed information."""
        self.detail_tab = QWidget()
        self.tabs.addTab(self.detail_tab, "Sensor Details")
        self.debug_logger.info("Creating Sensor Details Tab.")

        self.detail_main_layout = QVBoxLayout(self.detail_tab)

        # Dropdown to select sensor for detailed view
        sensor_selection_layout = QHBoxLayout()
        sensor_selection_layout.addWidget(QLabel("Select Sensor:"))
        self.detail_sensor_combo = QComboBox()
        self.detail_sensor_combo.addItems(["BME280", "SGP40", "SHTC3", "Proximity"]) # Hardcoded for now
        self.detail_sensor_combo.currentTextChanged.connect(self._on_detail_sensor_selected)
        sensor_selection_layout.addWidget(self.detail_sensor_combo)
        sensor_selection_layout.addStretch(1)
        self.detail_main_layout.addLayout(sensor_selection_layout)

        # Container for sensor-specific details (gauges and plots)
        # This will be dynamically populated with a QHBoxLayout in _on_detail_sensor_selected
        self.sensor_detail_container = QWidget()
        # Initialize with a basic layout that will be cleared.
        # This is a placeholder; its content will be replaced dynamically.
        self.current_detail_content_layout = QHBoxLayout(self.sensor_detail_container)
        self.detail_main_layout.addWidget(self.sensor_detail_container)

        self.detail_gauges = {} # To hold gauges for the currently selected detail sensor
        # self.detail_plots will store {'sensor_key_metric_key': {'figure': fig, 'ax': ax, 'canvas': canvas}} for individual plots
        # or {'sensor_key': {'figure': fig, 'axes': axes_array, 'canvas': canvas, 'lines': {metric_key: line}}} for combined plots
        self.detail_plots = {}
        self.detail_plot_lines = {} # {metric_key: Line2D object} for detail plots
        self.detail_plot_data_series = {} # {metric_key: deque} for detail plots

        self.debug_logger.info("Sensor Details Tab created.")
        # Initialize view for default sensor
        self._on_detail_sensor_selected(self.detail_sensor_combo.currentText())

    def _create_logging_tab(self):
        """Creates the logging tab for configuring data logging and archiving."""
        self.logging_tab = QWidget()
        self.tabs.addTab(self.logging_tab, "Logging")
        self.debug_logger.info("Creating Logging Tab.")

        logging_layout = QVBoxLayout(self.logging_tab)

        # Log Path Configuration
        log_path_group = QGroupBox("Live Log Files Location")
        log_path_layout = QHBoxLayout(log_path_group)
        self.log_path_label = QLabel(self.settings_manager.get_setting("log_path"))
        self.log_path_label.setWordWrap(True)
        self.log_path_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        log_path_layout.addWidget(self.log_path_label)
        self.log_path_button = QPushButton("Browse...")
        self.log_path_button.clicked.connect(self._browse_log_path)
        log_path_layout.addWidget(self.log_path_button)
        logging_layout.addWidget(log_path_group)

        # Archive Path Configuration
        archive_path_group = QGroupBox("Archive Logs Location")
        archive_path_layout = QHBoxLayout(archive_path_group)
        self.archive_path_label = QLabel(self.settings_manager.get_setting("archive_path"))
        self.archive_path_label.setWordWrap(True)
        self.archive_path_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        archive_path_layout.addWidget(self.archive_path_label)
        self.archive_path_button = QPushButton("Browse...")
        self.archive_path_button.clicked.connect(self._browse_archive_path)
        archive_path_layout.addWidget(self.archive_path_button)
        logging_layout.addWidget(archive_path_group)

        # Debug Log Path Configuration
        debug_log_path_group = QGroupBox("Debug Log File Location")
        debug_log_path_layout = QHBoxLayout(debug_log_path_group)
        self.debug_log_path_label = QLabel(self.settings_manager.get_setting("debug_log_path"))
        self.debug_log_path_label.setWordWrap(True)
        self.debug_log_path_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        debug_log_path_layout.addWidget(self.debug_log_path_label)
        self.debug_log_path_button = QPushButton("Browse...")
        self.debug_log_path_button.clicked.connect(self._browse_debug_log_path)
        debug_log_path_layout.addWidget(self.debug_log_path_button)
        logging_layout.addWidget(debug_log_path_group)

        # Logging Options
        logging_options_group = QGroupBox("Logging Options")
        logging_options_layout = QVBoxLayout(logging_options_group)

        self.archive_checkbox = QCheckBox("Enable Automatic Archiving (every 24 hours)")
        self.archive_checkbox.setChecked(self.settings_manager.get_setting("archive_enabled"))
        logging_options_layout.addWidget(self.archive_checkbox)

        self.console_debug_checkbox = QCheckBox("Enable Debug Output to Console")
        self.console_debug_checkbox.setChecked(self.settings_manager.get_setting("debug_to_console_enabled"))
        logging_options_layout.addWidget(self.console_debug_checkbox)

        # Debug Log Level selection
        debug_level_layout = QHBoxLayout()
        debug_level_layout.addWidget(QLabel("Debug Log Level:"))
        self.debug_level_combo = QComboBox()
        self.debug_level_combo.addItems(["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"])
        self.debug_level_combo.setCurrentText(self.settings_manager.get_setting("debug_log_level"))
        debug_level_layout.addWidget(self.debug_level_combo)
        debug_level_layout.addStretch(1)
        logging_options_layout.addLayout(debug_level_layout)

        logging_layout.addWidget(logging_options_group)

        # Sensor Logging Enable/Disable
        sensor_log_group = QGroupBox("Enable Logging Per Sensor")
        self.sensor_log_layout = QVBoxLayout(sensor_log_group)
        self.sensor_log_checkboxes = {} # To hold checkboxes for each sensor/metric

        # Dynamically create checkboxes for each sensor based on SENSOR_METRICS_MAP
        for sensor_key, metrics in self.settings_manager.SENSOR_METRICS_MAP.items():
            initial_state = self.settings_manager.get_setting("log_sensor_settings", {}).get(sensor_key, True)
            checkbox = QCheckBox(f"Log {sensor_key.replace('_', ' ').title()} Data")
            checkbox.setChecked(initial_state)
            self.sensor_log_checkboxes[sensor_key] = checkbox
            self.sensor_log_layout.addWidget(checkbox)

        sensor_log_group.setLayout(self.sensor_log_layout)
        logging_layout.addWidget(sensor_log_group)

        # Apply Logging Settings Button
        apply_logging_button = QPushButton("Apply Logging Settings")
        apply_logging_button.clicked.connect(self._apply_logging_settings)
        logging_layout.addWidget(apply_logging_button)

        logging_layout.addStretch(1) # Pushes content to top
        self.debug_logger.info("Logging Tab created.")

    def _create_settings_tab(self):
        """Creates the settings tab for general application configurations."""
        self.settings_tab = QWidget()
        self.tabs.addTab(self.settings_tab, "Settings")
        self.debug_logger.info("Creating Settings Tab.")

        settings_layout = QVBoxLayout(self.settings_tab)

        # Theme Selection
        theme_group = QGroupBox("Application Theme")
        theme_layout = QHBoxLayout(theme_group)
        theme_layout.addWidget(QLabel("Select UI Theme:"))
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(self.settings_manager.get_available_themes())
        self.theme_combo.setCurrentText(self.settings_manager.get_setting("theme"))
        self.theme_combo.currentTextChanged.connect(self._on_theme_changed)
        theme_layout.addWidget(self.theme_combo)
        theme_layout.addStretch(1)
        settings_layout.addWidget(theme_group)

        # Gauge Style Selection
        gauge_style_group = QGroupBox("Gauge Color Style")
        gauge_style_layout = QHBoxLayout(gauge_style_group)
        gauge_style_layout.addWidget(QLabel("Select Gauge Color Style:"))
        self.gauge_style_combo = QComboBox()
        self.gauge_style_combo.addItems(self.settings_manager.get_available_gauge_styles())
        self.gauge_style_combo.setCurrentText(self.settings_manager.get_setting("gauge_style"))
        self.gauge_style_combo.currentTextChanged.connect(self._on_gauge_style_changed)
        gauge_style_layout.addWidget(self.gauge_style_combo)
        gauge_style_layout.addStretch(1)
        settings_layout.addWidget(gauge_style_group)


        # Sensor Read Interval
        read_interval_group = QGroupBox("Sensor Read Interval")
        read_interval_layout = QHBoxLayout(read_interval_group)
        read_interval_layout.addWidget(QLabel("Read Interval (seconds):"))
        self.read_interval_input = QLineEdit(str(self.settings_manager.get_setting("read_interval")))
        self.read_interval_input.setValidator(QIntValidator(1, 3600)) # 1 second to 1 hour
        read_interval_layout.addWidget(self.read_interval_input)
        self.apply_interval_button = QPushButton("Apply Interval")
        self.apply_interval_button.clicked.connect(self._apply_read_interval)
        read_interval_layout.addWidget(self.apply_interval_button)
        read_interval_layout.addStretch(1)
        settings_layout.addWidget(read_interval_group)

        # Plot Update Interval
        plot_update_interval_group = QGroupBox("Plot Update Interval")
        plot_update_interval_layout = QHBoxLayout(plot_update_interval_group)
        plot_update_interval_layout.addWidget(QLabel("Plot Update Interval (ms):"))
        self.plot_update_interval_input = QLineEdit(str(self.settings_manager.get_setting("plot_update_interval_ms")))
        self.plot_update_interval_input.setValidator(QIntValidator(100, 10000)) # 100ms to 10 seconds
        plot_update_interval_layout.addWidget(self.plot_update_interval_input)
        self.apply_plot_interval_button = QPushButton("Apply Plot Interval")
        self.apply_plot_interval_button.clicked.connect(self._apply_plot_update_interval)
        plot_update_interval_layout.addWidget(self.apply_plot_interval_button)
        plot_update_interval_layout.addStretch(1)
        settings_layout.addWidget(plot_update_interval_group)

        # Max Plot Data Points
        max_plot_points_group = QGroupBox("Maximum Plot Data Points")
        max_plot_points_layout = QHBoxLayout(max_plot_points_group)
        max_plot_points_layout.addWidget(QLabel("Max Data Points:"))
        self.max_plot_points_input = QLineEdit(str(self.settings_manager.get_setting("max_plot_data_points")))
        self.max_plot_points_input.setValidator(QIntValidator(50, 5000)) # 50 to 5000 data points
        max_plot_points_layout.addWidget(self.max_plot_points_input)
        self.apply_max_points_button = QPushButton("Apply Max Points")
        self.apply_max_points_button.clicked.connect(self._apply_max_plot_data_points)
        max_plot_points_layout.addWidget(self.apply_max_points_button)
        max_plot_points_layout.addStretch(1)
        settings_layout.addWidget(max_plot_points_group)

        # Mock Data Toggle
        mock_data_group = QGroupBox("Data Source")
        mock_data_layout = QHBoxLayout(mock_data_group)
        self.mock_data_checkbox = QCheckBox("Use Mock Sensor Data")
        self.mock_data_checkbox.setChecked(self.settings_manager.get_setting("mock_data_enabled"))
        self.mock_data_checkbox.stateChanged.connect(self._on_mock_data_toggled)
        mock_data_layout.addWidget(self.mock_data_checkbox)
        mock_data_layout.addStretch(1)
        settings_layout.addWidget(mock_data_group)

        # Sound Options
        sound_options_group = QGroupBox("Sound Effects")
        sound_options_layout = QVBoxLayout(sound_options_group)
        self.alert_sound_checkbox = QCheckBox("Play Alert Sound")
        self.alert_sound_checkbox.setChecked(self.settings_manager.get_setting("play_alert_sound"))
        sound_options_layout.addWidget(self.alert_sound_checkbox)
        self.change_sound_checkbox = QCheckBox("Play Value Change Sound (Up/Down)")
        self.change_sound_checkbox.setChecked(self.settings_manager.get_setting("play_change_sound"))
        sound_options_layout.addWidget(self.change_sound_checkbox)
        settings_layout.addWidget(sound_options_group)

        # Manual Archive Button
        manual_archive_button = QPushButton("Archive Logs Now")
        manual_archive_button.clicked.connect(self._manual_archive_trigger)
        settings_layout.addWidget(manual_archive_button)

        settings_layout.addStretch(1)
        self.debug_logger.info("Settings Tab created.")

    def _create_sensor_group_box(self, title):
        """Helper to create a themed QGroupBox."""
        group_box = QGroupBox(title)
        # Apply QSS for group box title color and border
        group_box.setStyleSheet(self._get_qss_for_groupbox())
        return group_box

    def _display_status_message(self, message, message_type='info'):
        """
        Displays a message in the status bar with color based on message_type.
        message_type: 'info', 'warning', 'danger', 'success'
        """
        color_map = {
            'info': self.current_theme_data['plot_line_color_1'], # Typically blue
            'warning': self.current_theme_data['plot_line_color_3'], # Typically yellow/orange
            'danger': self.current_theme_data['plot_line_color_4'], # Typically red
            'success': self.current_theme_data['plot_line_color_2'] # Typically green
        }
        color_hex = color_map.get(message_type, self.current_theme_data['text_color'])

        # Log the status bar message to the debug logger
        self.debug_logger.debug(f"Status Bar Message: {message} (Color: {message_type}, Hex: {color_hex})")

        self.status_bar.setStyleSheet(f"QStatusBar {{ color: {color_hex}; }}")
        self.status_bar.showMessage(message, 5000) # Message disappears after 5 seconds

    def _load_initial_settings_to_ui(self):
        """Loads settings from SettingsManager and updates UI elements accordingly."""
        self.debug_logger.info("Loading initial settings to UI.")
        self.log_path_label.setText(self.settings_manager.get_setting("log_path"))
        self.archive_path_label.setText(self.settings_manager.get_setting("archive_path"))
        self.debug_log_path_label.setText(self.settings_manager.get_setting("debug_log_path"))
        self.archive_checkbox.setChecked(self.settings_manager.get_setting("archive_enabled"))
        self.console_debug_checkbox.setChecked(self.settings_manager.get_setting("debug_to_console_enabled"))
        self.debug_level_combo.setCurrentText(self.settings_manager.get_setting("debug_log_level"))

        # Update sensor logging checkboxes
        log_sensor_settings = self.settings_manager.get_setting("log_sensor_settings", {})
        for sensor_key, checkbox in self.sensor_log_checkboxes.items():
            checkbox.setChecked(log_sensor_settings.get(sensor_key, True)) # Default to True if not specified

        self.theme_combo.setCurrentText(self.settings_manager.get_setting("theme"))
        self.gauge_style_combo.setCurrentText(self.settings_manager.get_setting("gauge_style"))
        self.read_interval_input.setText(str(self.settings_manager.get_setting("read_interval")))
        self.plot_update_interval_input.setText(str(self.settings_manager.get_setting("plot_update_interval_ms")))
        self.max_plot_points_input.setText(str(self.settings_manager.get_setting("max_plot_data_points")))
        self.mock_data_checkbox.setChecked(self.settings_manager.get_setting("mock_data_enabled"))
        self.alert_sound_checkbox.setChecked(self.settings_manager.get_setting("play_alert_sound"))
        self.change_sound_checkbox.setChecked(self.settings_manager.get_setting("play_change_sound"))
        
        # Load initial state for dashboard sensor combo
        initial_dashboard_plot_sensor = self.settings_manager.get_setting("dashboard_plot_sensor", "All Sensors")
        if initial_dashboard_plot_sensor == "All Sensors":
            self.dashboard_sensor_combo.setCurrentText("All Sensors")
        else:
            # Ensure the display name is used if it exists in SENSOR_METRICS_MAP
            # Iterate through SENSOR_METRICS_MAP to find the display name
            display_name = "" # Initialize display_name
            for key, metrics_map_val in self.settings_manager.SENSOR_METRICS_MAP.items(): # Renamed metrics to metrics_map_val to avoid confusion
                if key == initial_dashboard_plot_sensor:
                    display_name = metrics_map_val.get('display_name', key.replace('_', ' ').title())
                    self.dashboard_sensor_combo.setCurrentText(display_name)
                    break # Exit loop once found
            if not display_name: # If not found or not set, default to "All Sensors"
                self.dashboard_sensor_combo.setCurrentText("All Sensors")

        self.plot_time_range_combo.setCurrentText(self.settings_manager.get_setting("plot_time_range", "Last 10 minutes"))

        self.debug_logger.info("Initial settings applied to UI elements.")


    def _on_plot_time_range_changed(self, text):
        """Handles changes in the plot time range selection."""
        self.debug_logger.info(f"Plot time range changed to: {text}")
        self.settings_manager.set_setting("plot_time_range", text)
        self.settings_manager.save_settings() # Save setting immediately
        self.debug_logger.debug("Forcing plot update due to time range change.")
        self._update_plots() # Force a plot update with the new range
        self._display_status_message(f"Plot time range set to '{text}'.", 'info')

    def _on_dashboard_sensor_selected(self, sensor_display_name):
        """Handles changes in the dashboard plot sensor selection."""
        self.debug_logger.info(f"Dashboard plot sensor selection changed to: {sensor_display_name}")
        
        # Convert display name back to normalized key if it's a specific sensor
        if sensor_display_name == "All Sensors":
            self.current_dashboard_plot_sensor = "All Sensors"
        else:
            # Find the sensor key from the display name
            found_key = None
            for key, metrics_map_val in self.settings_manager.SENSOR_METRICS_MAP.items(): # Renamed metrics to metrics_map_val
                if metrics_map_val.get('display_name', key.replace('_', ' ').title()) == sensor_display_name:
                    found_key = key
                    break
            self.current_dashboard_plot_sensor = found_key if found_key else "All Sensors" # Fallback

        self.settings_manager.set_setting("dashboard_plot_sensor", self.current_dashboard_plot_sensor)
        self.settings_manager.save_settings()
        self.debug_logger.debug(f"Dashboard plot: Current selected sensor (internal key): {self.current_dashboard_plot_sensor}")
        self._update_plots() # Force a plot update with the new sensor selection
        self._display_status_message(f"Dashboard plot showing data for '{sensor_display_name}'.", 'info')


    def _browse_log_path(self):
        """Opens a dialog to select the log file directory."""
        directory = QFileDialog.getExistingDirectory(self, "Select Log Directory", self.log_path_label.text())
        if directory:
            self.log_path_label.setText(directory)
            self._display_status_message(f"New log path selected: {directory}", 'info')
            self.debug_logger.info(f"New log path selected: {directory}")

    def _browse_archive_path(self):
        """Opens a dialog to select the archive directory."""
        directory = QFileDialog.getExistingDirectory(self, "Select Archive Directory", self.archive_path_label.text())
        if directory:
            self.archive_path_label.setText(directory)
            self._display_status_message(f"New archive path selected: {directory}", 'info')
            self.debug_logger.info(f"New archive path selected: {directory}")

    def _browse_debug_log_path(self):
        """Opens a dialog to select the debug log file path."""
        # For a file, QFileDialog.getSaveFileName is more appropriate
        file_path, _ = QFileDialog.getSaveFileName(self, "Select Debug Log File", self.debug_log_path_label.text(), "Log Files (*.log);;All Files (*)")
        if file_path:
            self.debug_log_path_label.setText(file_path)
            self._display_status_message(f"New debug log file selected: {file_path}", 'info')
            self.debug_logger.info(f"New debug log file selected: {file_path}")


    def _apply_logging_settings(self):
        """Applies the configured logging settings and sends them to the DataLogger thread."""
        self.debug_logger.info("Applying new logging settings.")

        new_log_path = self.log_path_label.text()
        new_archive_path = self.archive_path_label.text()
        new_debug_log_path = self.debug_log_path_label.text() # Get new debug log path
        new_archive_enabled = self.archive_checkbox.isChecked()
        new_console_debug_enabled = self.console_debug_checkbox.isChecked() # Get new console debug setting
        new_debug_log_level = self.debug_level_combo.currentText() # Get new debug log level

        # Gather new sensor logging settings
        new_sensor_log_settings = {
            sensor_key: checkbox.isChecked()
            for sensor_key, checkbox in self.sensor_log_checkboxes.items()
        }

        # Update settings manager
        self.settings_manager.update_settings({
            "log_path": new_log_path,
            "archive_path": new_archive_path,
            "debug_log_path": new_debug_log_path, # Save new debug log path
            "archive_enabled": new_archive_enabled,
            "log_sensor_settings": new_sensor_log_settings,
            "debug_to_console_enabled": new_console_debug_enabled,
            "debug_log_level": new_debug_log_level
        })
        self.debug_logger.info("SettingsManager updated with new logging settings.")

        # Send update message to sensor thread to reconfigure DataLogger
        self.sensor_thread.control_queue.put({
            'type': 'update_log_settings',
            'log_path_str': new_log_path,
            'archive_path_str': new_archive_path,
            'debug_log_path_str': new_debug_log_path,
            'archive_enabled_bool': new_archive_enabled,
            'new_sensor_log_settings': new_sensor_log_settings,
            'new_debug_log_level': new_debug_log_level
        })
        self.debug_logger.info("Update log settings command sent to sensor thread.")
        self._display_status_message("Logging settings applied. DataLogger will reconfigure.", 'info')

    def _manual_archive_trigger(self):
        """Triggers a manual log archive via the sensor thread."""
        self.debug_logger.info("Manual archive triggered.")
        self.sensor_thread.control_queue.put({'type': 'archive_now'})
        self._display_status_message("Manual log archive requested. Check logs tab for status.", 'info')


    def _on_theme_changed(self, theme_name):
        """
        Handles changes in the UI theme selection and suggests a corresponding gauge style.
        """
        self.debug_logger.info(f"UI Theme changed to: {theme_name}")

        # Get the new UI theme data
        new_ui_theme_data = self.settings_manager.get_theme_data(theme_name)
        if not new_ui_theme_data:
            self.debug_logger.error(f"Theme '{theme_name}' not found. Using default 'Default Light' theme.")
            new_ui_theme_data = self.settings_manager.get_theme_data("Default Light") # Fallback
            self.theme_combo.setCurrentText("Default Light") # Update combo box if fallback
            theme_name = "Default Light" # Update theme_name to reflect actual applied theme

        # Save the selected UI theme
        self.settings_manager.set_setting("theme", theme_name)
        self.settings_manager.save_settings()

        # Update the current_theme_data instance variable
        self.current_theme_data = new_ui_theme_data

        # Apply the general UI theme
        self._apply_current_theme()

        # --- Automatic Gauge Style Suggestion ---
        recommended_gauge_style = new_ui_theme_data.get("recommended_gauge_style")
        if recommended_gauge_style and self.gauge_style_combo.currentText() != recommended_gauge_style:
            # If there's a recommendation and it's not already selected, apply it.
            # This will trigger _on_gauge_style_changed automatically because of signal connection.
            self.debug_logger.info(f"UI theme '{theme_name}' recommends gauge style '{recommended_gauge_style}'. Applying it.")
            self.gauge_style_combo.setCurrentText(recommended_gauge_style)
            # The _on_gauge_style_changed method (connected to currentTextChanged) will handle
            # saving the new gauge style and updating gauge colors.
        elif not recommended_gauge_style:
            self.debug_logger.warning(f"UI theme '{theme_name}' does not have a 'recommended_gauge_style'. Gauge style will not auto-sync.")
        else:
            self.debug_logger.debug(f"Gauge style already matches recommended style '{recommended_gauge_style}' or no recommendation found.")


        self._display_status_message(f"UI theme changed to '{theme_name}'.", 'info')

    def _on_gauge_style_changed(self, style_name):
        """Handles changes in the gauge color style selection."""
        self.debug_logger.info(f"Gauge Style changed to: {style_name}")
        self.settings_manager.set_setting("gauge_style", style_name)
        self.settings_manager.save_settings()
        self._update_gauge_colors()
        self._display_status_message(f"Gauge style changed to '{style_name}'.", 'info')


    def _apply_read_interval(self):
        """Applies the new sensor read interval."""
        try:
            new_interval = int(self.read_interval_input.text())
            if new_interval <= 0:
                raise ValueError("Interval must be positive.")
            self.settings_manager.set_setting("read_interval", new_interval)
            self.settings_manager.save_settings()
            self.sensor_thread.control_queue.put({'type': 'update_read_interval', 'interval': new_interval})
            self._display_status_message(f"Sensor read interval set to {new_interval} seconds.", 'success')
            self.debug_logger.info(f"Sensor read interval updated to {new_interval} seconds.")
        except ValueError as e:
            self._display_status_message(f"Invalid read interval: {e}", 'danger')
            self.debug_logger.error(f"Invalid read interval input: {e}")

    def _apply_plot_update_interval(self):
        """Applies the new plot update interval."""
        try:
            new_interval_ms = int(self.plot_update_interval_input.text())
            if new_interval_ms <= 0:
                raise ValueError("Interval must be positive.")
            self.settings_manager.set_setting("plot_update_interval_ms", new_interval_ms)
            self.settings_manager.save_settings()
            self.plot_update_timer.setInterval(new_interval_ms)
            self._display_status_message(f"Plot update interval set to {new_interval_ms} ms.", 'success')
            self.debug_logger.info(f"Plot update interval updated to {new_interval_ms} ms.")
        except ValueError as e:
            self._display_status_message(f"Invalid plot update interval: {e}", 'danger')
            self.debug_logger.error(f"Invalid plot update interval input: {e}")

    def _apply_max_plot_data_points(self):
        """Applies the new maximum number of plot data points."""
        try:
            new_max_points = int(self.max_plot_points_input.text())
            if new_max_points <= 0:
                raise ValueError("Max data points must be positive.")
            self.settings_manager.set_setting("max_plot_data_points", new_max_points)
            self.settings_manager.save_settings()
            # The deque needs to be re-initialized for the maxlen to take effect
            self.data_manager.sensor_data_history = collections.deque(self.data_manager.sensor_data_history, maxlen=new_max_points)
            self.data_manager.timestamps = collections.deque(self.data_manager.timestamps, maxlen=new_max_points)
            self._display_status_message(f"Max plot data points set to {new_max_points}.", 'success')
            self.debug_logger.info(f"Max plot data points updated to {new_max_points}.")
        except ValueError as e:
            self._display_status_message(f"Invalid max plot data points: {e}", 'danger')
            self.debug_logger.error(f"Invalid max plot data points input: {e}")

    def _on_mock_data_toggled(self, state):
        """Handles toggling of mock data usage."""
        enable_mock = bool(state == Qt.Checked)
        self.settings_manager.set_setting("mock_data_enabled", enable_mock)
        self.settings_manager.save_settings()
        self.sensor_thread.control_queue.put({'type': 'toggle_mock_data', 'enable': enable_mock})
        self._display_status_message(f"Mock data mode {'enabled' if enable_mock else 'disabled'}.", 'info')
        self.debug_logger.info(f"Mock data mode toggled to {enable_mock}.")


    def _update_ui_with_sensor_data(self, sensor_data):
        """
        Receives sensor data from the SensorReaderThread and updates the UI.
        This method runs in the main GUI thread.
        """
        self.debug_logger.debug(f"UI update: Received sensor_data. Keys: {list(sensor_data.keys())}")

        play_change_sound_enabled = self.settings_manager.get_setting("play_change_sound", True) # Use settings for sound toggle

        # Update Dashboard Gauges
        self.debug_logger.debug("UI update: Updating Dashboard Gauges.")
        for sensor_key, metrics in sensor_data.items():
            normalized_sensor_key = sensor_key.replace('-', '_') # Normalize key for dictionary access
            # self.debug_logger.debug(f"UI update: Processing dashboard gauges for sensor: {sensor_key} (normalized: {normalized_sensor_key})") # Too verbose for regular debug

            for metric_key, value in metrics.items():
                gauge_key = f"{normalized_sensor_key}_{metric_key}"
                if gauge_key in self.dashboard_gauges:
                    gauge = self.dashboard_gauges[gauge_key]
                    # self.debug_logger.debug(f"UI update: Gauge '{gauge_key}'. Old value: {gauge.current_value}, New value: {value}") # Too verbose

                    # Check for non-finite values before updating gauge
                    if value is not None and not math.isnan(value) and not math.isinf(value):
                        # Play sound if value changes significantly (e.g., more than 1% of range)
                        if self.settings_manager.get_setting("play_change_sound") and \
                           not math.isnan(gauge.current_value): # Check gauge.current_value for NaN too
                            range_val = gauge.max_val - gauge.min_val
                            if range_val > 0: # Avoid division by zero
                                change_percent = abs(value - gauge.current_value) / range_val
                                if change_percent > 0.01: # 1% change threshold
                                    direction = 'up' if value > gauge.current_value else 'down'
                                    self.sound_manager.play_change_sound(direction, play_change_sound_enabled)
                                    self.debug_logger.debug(f"UI update: Played '{direction}' sound for {gauge_key} due to {change_percent*100:.2f}% change.") # Added more detail
                        gauge.update_value(value)
                    else:
                        gauge.update_value(float('nan')) # Explicitly set NaN if invalid

                # else: # Commented out as this warning is expected for metrics not on dashboard gauges
                #     self.debug_logger.warning(f"Dashboard Gauge '{gauge_key}' not found in self.dashboard_gauges. This should not happen.")

        # Update Detail Tab Gauges and Plots (only for the currently selected sensor)
        current_detail_sensor_key = self.detail_sensor_combo.currentText().split(' ')[0].lower() # e.g., 'bme280' from 'BME280'
        if current_detail_sensor_key == "proximity": # Handle "Proximity Sensor" case
            current_detail_sensor_key = "proximity"
        self.debug_logger.debug(f"UI update: Checking detail tab gauges for selected sensor: {current_detail_sensor_key}.")

        # FIX: Ensure we get the metrics specifically for the current_detail_sensor_key
        # The previous code was iterating over the `metrics` variable from the dashboard loop,
        # which would be the last sensor processed there, causing incorrect updates.
        if current_detail_sensor_key in sensor_data:
            detail_metrics_for_selected_sensor = sensor_data[current_detail_sensor_key]
            self.debug_logger.debug(f"UI update: Received sensor_data for {current_detail_sensor_key}: {detail_metrics_for_selected_sensor}") 
            for metric_key, value in detail_metrics_for_selected_sensor.items(): # Corrected iteration
                gauge_key = f"{current_detail_sensor_key}_{metric_key}"
                if gauge_key in self.detail_gauges:
                    # Check for non-finite values before updating gauge
                    if value is not None and not math.isnan(value) and not math.isinf(value):
                        self.detail_gauges[gauge_key].update_value(value)
                    else:
                        self.detail_gauges[gauge_key].update_value(float('nan')) # Explicitly set NaN if invalid
                else:
                     self.debug_logger.warning(f"Detail Tab Gauge '{gauge_key}' not found in self.detail_gauges. This might be expected if the metric is not gauged.")


        self.debug_logger.debug("UI update: Triggering _update_plots for all plots.")
        self._update_plots() # Update all plots (dashboard and detail)

    def _apply_plot_theme(self, fig, ax):
        """Applies the current theme colors to a given Matplotlib figure and axes."""
        theme = self.current_theme_data
        self.debug_logger.debug(f"Applying plot theme to figure {fig.number} and axis {ax}. Theme: {theme.get('theme_name', 'N/A')}")

        # Set figure background color
        fig.patch.set_facecolor(theme['bg_color']) # Changed to theme['bg_color'] for consistency with other theme elements
        self.debug_logger.debug(f"Plot theme: Figure background set to {theme['bg_color']}.")

        # Set axes face color (plot area background)
        ax.set_facecolor(theme['plot_bg_color'])
        self.debug_logger.debug(f"Plot theme: Axis facecolor set to {theme['plot_bg_color']}.")

        # Set tick label colors
        ax.tick_params(axis='x', colors=theme['text_color'])
        ax.tick_params(axis='y', colors=theme['text_color'])
        self.debug_logger.debug(f"Plot theme: Tick colors set to {theme['text_color']}.")

        # Set label colors
        ax.xaxis.label.set_color(theme['text_color'])
        ax.yaxis.label.set_color(theme['text_color'])
        self.debug_logger.debug(f"Plot theme: Label colors set to {theme['text_color']}.")

        # Set title color
        ax.title.set_color(theme['text_color'])
        self.debug_logger.debug(f"Plot theme: Title color set to {theme['text_color']}.")

        # Set spine (border) colors
        ax.spines['bottom'].set_color(theme['outline_color'])
        ax.spines['top'].set_color(theme['outline_color'])
        ax.spines['left'].set_color(theme['outline_color'])
        ax.spines['right'].set_color(theme['outline_color'])
        self.debug_logger.debug(f"Plot theme: Spine colors set to {theme['outline_color']}.")

        # Set grid color
        ax.grid(True, linestyle=':', alpha=0.7, color=theme['outline_color'])
        self.debug_logger.debug(f"Plot theme: Grid color set to {theme['outline_color']}.")

        # If a legend exists, update its colors
        if ax.legend_:
            ax.legend_.get_frame().set_facecolor(theme['alt_bg_color'])
            ax.legend_.get_frame().set_edgecolor(theme['outline_color'])
            # Update legend text color
            for text in ax.legend_.get_texts():
                text.set_color(theme['text_color'])
            self.debug_logger.debug("Plot theme: Legend colors updated.")


    def _update_plots(self):
        """Fetches filtered data and updates all active plots (Dashboard and Detail tabs)."""
        time_range = self.settings_manager.get_setting("plot_time_range", "Last 10 minutes")
        self.debug_logger.debug(f"Plot update: Fetching data for time range '{time_range}'.")
        timestamps, all_sensor_data_history = self.data_manager.get_filtered_data(time_range)
        self.debug_logger.debug(f"Plot update: Fetched {len(timestamps)} timestamps and {len(all_sensor_data_history)} data points.")

        # --- Update Dashboard Plot (Combined or Individual) ---
        self.debug_logger.debug("Plot update: Updating Dashboard Plot.")
        self.dashboard_ax.clear() # Clear existing plot lines
        self._apply_plot_theme(self.dashboard_fig, self.dashboard_ax) # Re-apply theme after clearing
        self.dashboard_plot_lines = {} # Clear and reinitialize plot lines for new plot type
        self.debug_logger.debug("Dashboard plot: Axes cleared and plot lines reinitialized.")


        if not timestamps:
            self.dashboard_ax.text(0.5, 0.5, "No Data Available",
                                   horizontalalignment='center', verticalalignment='center',
                                   transform=self.dashboard_ax.transAxes, fontsize=16, color='gray')
            self.dashboard_canvas.draw_idle()
            self.debug_logger.info("Dashboard plot: No timestamps found, displaying 'No Data Available'.")
            # Still proceed to update detail plots in case they have data or need to show "No Data"
            self._update_detail_plots_data(timestamps, all_sensor_data_history)
            return

        # Convert timestamps to matplotlib recognizable date format
        dates = mdates.date2num(timestamps) # Corrected line: directly pass datetime objects
        self.debug_logger.debug(f"Dashboard plot: Converted {len(timestamps)} datetime objects to Matplotlib dates.")


        # Prepare data for dashboard plot based on selected sensor
        plot_metrics_info = []
        plot_colors = [
            self.current_theme_data['plot_line_color_1'],
            self.current_theme_data['plot_line_color_2'],
            self.current_theme_data['plot_line_color_3'],
            self.current_theme_data['plot_line_color_4'],
            self.current_theme_data.get('plot_line_color_5', '#000000'), # Fallback to black if not found
            self.current_theme_data.get('plot_line_color_6', '#000000'),
            self.current_theme_data.get('plot_line_color_7', '#000000')
        ]
        color_idx = 0

        handles = []
        labels = []
        plot_title = ""

        if self.current_dashboard_plot_sensor == "All Sensors":
            plot_title = "Combined Sensor Data Over Time"
            # Define which metrics are considered "main" for the combined dashboard plot
            dashboard_all_sensors_metrics = {
                'bme280': ['temp_c', 'temp_f', 'humidity', 'pressure', 'altitude', 'dewpoint_c', 'dewpoint_f'], # Include all BME280 metrics
                'sgp40': ['voc_index'],
                'shtc3': ['temperature', 'humidity'],
                'proximity': ['proximity', 'ambient_light', 'white_light'] # Include all Proximity metrics
            }

            self.debug_logger.debug(f"Dashboard plot: Plotting ALL Sensors. Selected metrics: {dashboard_all_sensors_metrics}")

            for sensor_key, metrics_to_include in dashboard_all_sensors_metrics.items(): # Iterate over our curated list
                is_logging_enabled = self.settings_manager.get_setting("log_sensor_settings", {}).get(sensor_key, False)
                if not is_logging_enabled:
                    self.debug_logger.debug(f"Dashboard plot: Logging DISABLED for sensor '{sensor_key}', skipping in All Sensors view.")
                    continue

                has_any_data = any(sensor_key in data for data in all_sensor_data_history)
                if not has_any_data:
                    self.debug_logger.debug(f"Dashboard plot: Sensor '{sensor_key}' has NO data in history, skipping in All Sensors view.")
                    continue

                # Get the full metric details from SettingsManager.SENSOR_METRICS_MAP
                full_sensor_metrics_map = self.settings_manager.SENSOR_METRICS_MAP.get(sensor_key, {})
                for metric_key in metrics_to_include: # Iterate through the curated metrics
                    details = full_sensor_metrics_map.get(metric_key)
                    if details:
                        plot_metrics_info.append((sensor_key, metric_key, details['label'], details['unit']))
                        self.debug_logger.debug(f"Dashboard plot: Adding metric '{metric_key}' from sensor '{sensor_key}' to plot list (All Sensors curated).")
                    else:
                        self.debug_logger.warning(f"Dashboard plot: Metric details not found for {sensor_key}.{metric_key}. Skipping (All Sensors curated).")
        else: # Individual sensor selected
            normalized_sensor_key = self.current_dashboard_plot_sensor
            plot_title = f"{normalized_sensor_key.replace('_', ' ').title()} Sensor Data Over Time"
            
            # When an individual sensor is selected, plot ALL its metrics defined in SENSOR_METRICS_MAP.
            metrics_for_selected_sensor = self.settings_manager.SENSOR_METRICS_MAP.get(normalized_sensor_key, {})
            self.debug_logger.debug(f"Dashboard plot: Plotting individual sensor: {normalized_sensor_key}. All its metrics from SENSOR_METRICS_MAP: {list(metrics_for_selected_sensor.keys())}")

            for metric_key, details in metrics_for_selected_sensor.items():
                plot_metrics_info.append((normalized_sensor_key, metric_key, details['label'], details['unit']))
                self.debug_logger.debug(f"Dashboard plot: Adding metric '{metric_key}' from sensor '{normalized_sensor_key}' to plot list (Individual Sensor from SENSOR_METRICS_MAP).")

        self.debug_logger.debug(f"Dashboard plot: Final list of metrics to plot: {[info[1] for info in plot_metrics_info]}.")

        # Plot each selected metric on the dashboard plot
        for sensor_key, metric_key, label, unit in plot_metrics_info:
            full_metric_key = f"{sensor_key}_{metric_key}"
            self.debug_logger.debug(f"Dashboard plot: Attempting to plot {full_metric_key}.")

            metric_values = [
                data.get(sensor_key, {}).get(metric_key, float('nan'))
                for data in all_sensor_data_history
            ]
            self.debug_logger.debug(f"Dashboard plot: Raw values for {full_metric_key}: {metric_values[:5]}... (first 5)")

            # Filter out NaN and Inf values for plotting
            valid_data_indices = [i for i, val in enumerate(metric_values) if val is not None and not math.isnan(val) and not math.isinf(val)]
            filtered_dates = [dates[i] for i in valid_data_indices]
            filtered_values = [metric_values[i] for i in valid_data_indices]
            self.debug_logger.debug(f"Dashboard plot: Filtered {len(filtered_values)} valid data points for {full_metric_key}. Data: {filtered_values[:5]}...") # Added filtered data to log
            if filtered_values:
                self.debug_logger.debug(f"Dashboard plot: Min/Max values for {full_metric_key}: {min(filtered_values):.2f}/{max(filtered_values):.2f}")


            if filtered_dates and filtered_values:
                # Always create a new line after clearing the axes
                line, = self.dashboard_ax.plot(filtered_dates, filtered_values,
                                             color=plot_colors[color_idx % len(plot_colors)],
                                             label=f"{label} ({unit})", marker='o', markersize=2, linestyle='-')
                self.dashboard_plot_lines[full_metric_key] = line # Store the new line object
                self.debug_logger.debug(f"Dashboard plot: Created and stored NEW line for {full_metric_key}.")

                handles.append(self.dashboard_plot_lines[full_metric_key])
                labels.append(f"{label} ({unit})")
                color_idx += 1
                self.debug_logger.debug(f"Dashboard plot: Plotted line for {full_metric_key} with color {plot_colors[(color_idx-1) % len(plot_colors)]}. Data points: {len(filtered_values)}")
            else:
                # If no data, ensure the line is not drawn (it was cleared by ax.clear())
                self.debug_logger.info(f"Dashboard plot: No valid data (after NaN/inf filter) to plot for {full_metric_key}. Line will not be visible.")


        if handles:
            self.dashboard_ax.legend(handles=handles, labels=labels, loc='upper left', frameon=True,
                                    facecolor=self.current_theme_data['alt_bg_color'],
                                    edgecolor=self.current_theme_data['outline_color'],
                                    labelcolor=self.current_theme_data['text_color'])
            self.debug_logger.debug("Dashboard plot: Legend added/updated.")
        else:
            # If no data across all metrics, display "No Data Available"
            self.dashboard_ax.text(0.5, 0.5, "No Data Available (Dashboard)",
                                   horizontalalignment='center', verticalalignment='center',
                                   transform=self.dashboard_ax.transAxes, fontsize=16, color='gray')
            if self.dashboard_ax.legend_: # Remove legend if no data to avoid empty box
                self.dashboard_ax.legend_ = None
            self.debug_logger.info("Dashboard plot: No lines plotted, displaying 'No Data Available'.")

        self.dashboard_ax.set_title(plot_title)
        self.dashboard_ax.set_xlabel("Time")
        self.dashboard_ax.set_ylabel("Value") # Y-axis label is generic as it can be mixed units
        self.dashboard_ax.grid(True, linestyle=':', alpha=0.7, color=self.current_theme_data['outline_color'])
        self.dashboard_ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        self.dashboard_fig.autofmt_xdate() # Auto-format dates for better readability
        self.debug_logger.debug("Dashboard plot: X-axis formatted and auto-rotated.")

        # Dynamic Y-axis scaling for dashboard plot
        all_plot_values = []
        for sensor_key, metric_key, _, _ in plot_metrics_info: # Iterate through metrics that were considered for plotting
            metric_values_flat = [
                data.get(sensor_key, {}).get(metric_key, float('nan'))
                for data in all_sensor_data_history
            ]
            valid_metric_values = [val for val in metric_values_flat if val is not None and not math.isnan(val) and not math.isinf(val)]
            all_plot_values.extend(valid_metric_values)

        if all_plot_values:
            min_val = min(all_plot_values)
            max_val = max(all_plot_values)
            y_buffer = (max_val - min_val) * 0.1 # 10% buffer
            if y_buffer == 0: # Handle case where all values are the same
                y_buffer = abs(min_val) * 0.1 if min_val != 0 else 1 # Add a fixed buffer if range is zero
            self.dashboard_ax.set_ylim(min_val - y_buffer, max_val + y_buffer)
            self.debug_logger.debug(f"Dashboard plot Y-axis: Adjusted to [{min_val - y_buffer:.2f}, {max_val + y_buffer:.2f}].")
        else:
            # Fallback for y-axis if no data at all
            self.dashboard_ax.set_ylim(0, 1)
            self.debug_logger.debug("Dashboard plot Y-axis: Set to default [0, 1] as no valid data.")

        self.dashboard_ax.relim()
        self.dashboard_ax.autoscale_view(True,True,True)


        self.dashboard_canvas.draw_idle()
        self.debug_logger.debug("Dashboard plot updated and redrawn.")

        # --- Update Detail Plots ---
        self.debug_logger.debug("Plot update: Triggering _update_detail_plots_data.")
        self._update_detail_plots_data(timestamps, all_sensor_data_history)


    def _on_detail_sensor_selected(self, sensor_display_name):
        """
        Dynamically populates the detail tab with gauges and plots for the selected sensor.
        Clears previous content and adds new widgets.
        This now always creates a two-column layout: gauges on left, plots on right.
        """
        self.debug_logger.info(f"Detail sensor selected: {sensor_display_name}")

        # Clear existing widgets from the current_detail_content_layout
        # We need to correctly dispose of widgets when changing layouts.
        self.debug_logger.debug("Detail tab: Clearing existing widgets and layouts.")
        self._clear_layout(self.current_detail_content_layout)
        self.debug_logger.debug("Detail tab: Existing widgets and layouts cleared.")

        self.detail_gauges.clear()
        # Close matplotlib figures to free memory before clearing
        self.debug_logger.debug("Detail tab: Closing existing matplotlib figures.")
        for plot_key, plot_info in list(self.detail_plots.items()): # Use list() to avoid RuntimeError: dictionary changed size during iteration
            if 'figure' in plot_info and plot_info['figure']:
                plt.close(plot_info['figure'])
                self.debug_logger.debug(f"Detail tab: Closed figure for {plot_key}.")

        self.detail_plots.clear()
        self.detail_plot_lines.clear()
        self.detail_plot_data_series.clear() # Clear data series for the old sensor
        self.debug_logger.debug("Detail tab: Cleared detail gauges, plots, lines, and data series references.")


        # Extract normalized sensor key (e.g., 'bme280' from 'BME280')
        normalized_sensor_key = sensor_display_name.split(' ')[0].lower()
        if normalized_sensor_key == "proximity": # Handle "Proximity Sensor" case
            normalized_sensor_key = "proximity"
        self.debug_logger.debug(f"Detail tab: Normalized sensor key: {normalized_sensor_key}")

        metrics_for_selected_sensor = self.settings_manager.SENSOR_METRICS_MAP.get(normalized_sensor_key, {})
        if not metrics_for_selected_sensor:
            self.debug_logger.warning(f"Detail tab: No metric map found for sensor: {normalized_sensor_key}. Displaying 'No detailed metrics' message.")
            # Display a message or empty state if no metrics are defined
            no_data_label = QLabel(f"No detailed metrics defined for {sensor_display_name}.")
            no_data_label.setAlignment(Qt.AlignCenter)
            self.current_detail_content_layout.addWidget(no_data_label) # Add to the main horizontal layout
            return

        # --- Left Panel: Gauges ---
        self.debug_logger.debug(f"Detail tab: Creating gauges for {sensor_display_name}.")
        gauges_container = QWidget()
        gauges_layout = QGridLayout(gauges_container)
        gauges_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        row, col = 0, 0
        for metric_key, details in metrics_for_selected_sensor.items():
            gauge_label = details['label']
            gauge_unit = details['unit']
            gauge_min = details['gauge_min']
            gauge_max = details['gauge_max']

            gauge_widget = GaugeWidget(self, f"{gauge_label} ({gauge_unit})", gauge_min, gauge_max, gauge_unit, debug_logger=self.debug_logger)
            self.detail_gauges[f"{normalized_sensor_key}_{metric_key}"] = gauge_widget
            gauges_layout.addWidget(gauge_widget, row, col)
            self.debug_logger.debug(f"Detail tab: Added gauge for {gauge_label} ({gauge_unit}) at ({row},{col}).")

            col += 1
            if col > 1: # Limit to 2 gauges per row in the left panel for better spacing
                col = 0
                row += 1

        self._update_gauge_colors()
        gauges_group_box = self._create_sensor_group_box(f"{sensor_display_name} Gauges")
        gauges_group_box.setLayout(gauges_layout)

        gauges_scroll_area = QScrollArea()
        gauges_scroll_area.setWidgetResizable(True)
        gauges_scroll_area.setWidget(gauges_group_box)
        gauges_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff) # No horizontal scroll
        gauges_scroll_area.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding) # Take available vertical space

        self.current_detail_content_layout.addWidget(gauges_scroll_area, 1) # Add with stretch factor
        self.debug_logger.debug(f"Detail tab: Gauges container added for {sensor_display_name}.")


        # --- Right Panel: Plots ---
        self.debug_logger.debug(f"Detail tab: Creating plots for {sensor_display_name}.")
        plots_container = QWidget()
        plots_layout = QVBoxLayout(plots_container)
        plots_layout.setAlignment(Qt.AlignTop)

        # plot_colors is now defined directly in _update_detail_plots_data
        # to ensure it's always in scope and reflects current theme.

        # For BME280 and SHTC3, create a combined plot with subplots (or individual if only 1 metric for some reason)
        num_metrics = len(metrics_for_selected_sensor)
        self.debug_logger.debug(f"Detail tab plots: Number of metrics for {normalized_sensor_key}: {num_metrics}.")

        # Dynamic grid calculation for subplots to accommodate all metrics
        rows = math.ceil(math.sqrt(num_metrics)) # Aim for a roughly square grid
        cols = math.ceil(num_metrics / rows)
        self.debug_logger.debug(f"Detail tab plots: Calculated grid: {rows}x{cols}.")

        # Adjust for specific sensor combinations if needed for better aesthetics
        if normalized_sensor_key == 'bme280':
            # 3x3 gives 9 subplots, enough for 7 BME280 metrics with some room
            rows, cols = 3, 3 
            self.debug_logger.debug(f"Detail tab plots: Override grid for BME280 to 3x3.")
        elif normalized_sensor_key == 'shtc3':
            rows, cols = 1, 2 # 2 subplots for 2 SHTC3 metrics
            self.debug_logger.debug(f"Detail tab plots: Override grid for SHTC3 to 1x2.")
        elif normalized_sensor_key == 'proximity':
            # Proximity has 3 metrics. A 1x3 layout or 2x2 for better aspect ratio
            rows, cols = 2, 2 # Max 4 subplots, good for 3 metrics
            self.debug_logger.debug(f"Detail tab plots: Override grid for proximity to 2x2.")
        elif normalized_sensor_key == 'sgp40':
            rows, cols = 1, 1 # Single plot for single metric sensors
            self.debug_logger.debug(f"Detail tab plots: Override grid for sgp40 to 1x1.")


        if num_metrics > 0: # Only create plot if there are metrics to show
            fig, axes = plt.subplots(rows, cols, figsize=(10, 3 * rows))
            self.debug_logger.debug(f"Detail tab plots: Created figure and axes for {normalized_sensor_key}.")

            # Ensure axes is always iterable and flat, even for single subplot cases
            if not isinstance(axes, np.ndarray):
                axes = np.array([axes]) # Make it an array if it's a single Axes object
            axes = axes.flatten() # Flatten to iterate easily
            self.debug_logger.debug(f"Detail tab plots: Flattened axes array. Total subplots: {len(axes)}.")


            # Apply theme to the main figure and all subplots
            fig.patch.set_facecolor(self.current_theme_data['bg_color']) # Set figure background
            self.debug_logger.debug(f"Detail tab plots: Figure background set to {self.current_theme_data['bg_color']}.")
            for i, ax in enumerate(axes):
                self._apply_plot_theme(fig, ax) # Apply theme to each subplot's elements
                self.debug_logger.debug(f"Detail tab plots: Applied theme to subplot {i}.")


            # Map metrics to subplots and store line references
            combined_plot_lines_for_sensor = {}
            for i, (metric_key, details) in enumerate(metrics_for_selected_sensor.items()):
                if i < len(axes): # Ensure we don't go out of bounds if num_metrics is less than rows*cols
                    ax = axes[i]
                    ax.set_title(f"{details['label']} ({details['unit']})")
                    ax.set_xlabel("Time")
                    ax.set_ylabel(details['unit'])
                    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))

                    # The 'plot_colors' definition is now inside _update_detail_plots_data
                    # Ensure line object is created with markers and linestyle, and stored
                    # Line color will be applied during _update_detail_plots_data as well
                    line, = ax.plot([], [], marker='o', markersize=2, linestyle='-')
                    combined_plot_lines_for_sensor[metric_key] = line
                    # Each metric will have its own deque for plot data on the detail tab for this combined plot
                    self.detail_plot_data_series[f"{normalized_sensor_key}_{metric_key}"] = collections.deque(maxlen=self.settings_manager.get_setting("max_plot_data_points", 300))
                    self.debug_logger.debug(f"Detail tab plots: Initialized line for {normalized_sensor_key}_{metric_key} on subplot {i}.")
                else:
                    self.debug_logger.warning(f"Detail tab plots: Not enough axes ({len(axes)}) for all metrics in {normalized_sensor_key}. Skipping metric {metric_key}.")

            # Hide any unused subplots
            for j in range(num_metrics, len(axes)): # Start from num_metrics, not i+1
                self.debug_logger.debug(f"Detail tab plots: Hiding unused subplot {j}.")
                # Access the subplot and turn it off
                axes[j].set_visible(False)
                # To completely remove it from the layout, which is better
                # fig.delaxes(axes[j]) # This can cause issues with tight_layout later, better to set invisible
                self.debug_logger.debug(f"Detail tab plots: Subplot {j} set to invisible.")


            fig.tight_layout() # Adjust subplot parameters for a tight layout
            self.debug_logger.debug("Detail tab plots: Applied tight layout to figure.")

            canvas = FigureCanvas(fig)
            self.detail_plots[normalized_sensor_key] = {
                'figure': fig,
                'axes': axes,
                'canvas': canvas,
                'lines': combined_plot_lines_for_sensor
            }
            plots_layout.addWidget(canvas)
            self.debug_logger.debug(f"Detail tab plots: Canvas added to layout for {normalized_sensor_key}.")

        plots_group_box = self._create_sensor_group_box(f"{sensor_display_name} Plots")
        plots_group_box.setLayout(plots_layout)

        plots_scroll_area = QScrollArea()
        plots_scroll_area.setWidgetResizable(True)
        plots_scroll_area.setWidget(plots_group_box)
        plots_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff) # No horizontal scroll
        plots_scroll_area.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        self.current_detail_content_layout.addWidget(plots_scroll_area, 2) # Add with stretch factor

        self.debug_logger.info(f"Detail tab UI updated for {sensor_display_name}.")
        # Force an immediate plot update for the new sensor
        self.debug_logger.debug(f"Detail tab: Forcing immediate plot update for {sensor_display_name}.")
        self._update_detail_plots_data(self.data_manager.timestamps, self.data_manager.sensor_data_history)

    def _clear_layout(self, layout):
        """Recursively clears all widgets and layouts within a layout."""
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                if item.widget():
                    self.debug_logger.debug(f"Clearing layout: Deleting widget {item.widget().objectName()}.")
                    item.widget().deleteLater()
                else:
                    self.debug_logger.debug(f"Clearing layout: Clearing sub-layout {item.layout()}.")
                    self._clear_layout(item.layout())
        self.debug_logger.debug(f"Layout {layout} cleared.")


    def _update_detail_plots_data(self, timestamps, all_sensor_data_history):
        """Updates the data in the plots on the detail tab."""
        self.debug_logger.debug(f"Detail plot data update: Starting. Total timestamps: {len(timestamps)}")

        current_detail_sensor_key = self.detail_sensor_combo.currentText().split(' ')[0].lower()
        if current_detail_sensor_key == "proximity": # Handle "Proximity Sensor" case
            current_detail_sensor_key = "proximity"
        self.debug_logger.debug(f"Detail plot data update: Currently selected sensor: {current_detail_sensor_key}")

        metrics_for_current_detail = self.settings_manager.SENSOR_METRICS_MAP.get(current_detail_sensor_key, {})
        self.debug_logger.debug(f"Detail plot data update: Metrics for selected sensor: {list(metrics_for_current_detail.keys())}")

        # Define plot_colors here to ensure it's always in scope
        plot_colors = [
            self.current_theme_data['plot_line_color_1'],
            self.current_theme_data['plot_line_color_2'],
            self.current_theme_data['plot_line_color_3'],
            self.current_theme_data['plot_line_color_4'],
            self.current_theme_data.get('plot_line_color_5', '#000000'), # Fallback to black if not found
            self.current_theme_data.get('plot_line_color_6', '#000000'),
            self.current_theme_data.get('plot_line_color_7', '#000000')
        ]
        self.debug_logger.debug(f"Detail plot data update: Using {len(plot_colors)} plot colors.")


        # Find the correct plot info for the current sensor
        plot_info_dict = self.detail_plots.get(current_detail_sensor_key)

        if not plot_info_dict: # No plot info for this sensor (e.g., if it has no metrics)
            self.debug_logger.info(f"Detail plot data update: No plot_info_dict found for {current_detail_sensor_key}. Skipping plot update.")
            return

        canvas = plot_info_dict['canvas']
        self.debug_logger.debug(f"Detail plot data update: Updating combined plots for {current_detail_sensor_key}. Number of lines: {len(plot_info_dict.get('lines', {}))}")

        # Convert timestamps to matplotlib recognizable date format
        if timestamps:
            dates = mdates.date2num(timestamps) # Corrected: Directly pass datetime objects
        else:
            dates = []

        # Re-apply figure background (axes handled individually below)
        detail_fig = plot_info_dict['figure']
        # Robust theme application: Check if 'bg_color' exists in current_theme_data
        if self.current_theme_data and 'bg_color' in self.current_theme_data:
            detail_fig.set_facecolor(self.current_theme_data['bg_color'])
            self.debug_logger.debug(f"Detail plot data update: Figure background set to {detail_fig.get_facecolor()}.")
        else:
            self.debug_logger.warning("Detail plot data update: 'bg_color' not found in theme data. Using default figure background.")
            detail_fig.set_facecolor('#ADD8E6') # Fallback to a light blue


        # Check if there's any relevant data to plot
        has_any_sensor_data_in_history = any(
            current_detail_sensor_key in data and data.get(current_detail_sensor_key) is not None and isinstance(data.get(current_detail_sensor_key), dict) and len(data.get(current_detail_sensor_key)) > 0
            for data in all_sensor_data_history
        )
        
        has_relevant_data = (
            len(dates) > 0 and 
            has_any_sensor_data_in_history and
            len(metrics_for_current_detail) > 0 # Ensure there are metrics defined for this sensor
        )

        if not has_relevant_data:
            self.debug_logger.info(f"Detail plot data update: No timestamps or relevant data for {current_detail_sensor_key}. Clearing and showing 'No Data Available'.")
            
            if 'axes' in plot_info_dict:
                for i, ax in enumerate(plot_info_dict['axes']):
                    # Ensure axis is visible before clearing/drawing 'No Data Available'
                    ax.set_visible(True) # In case it was hidden previously for unused subplot
                    ax.clear()
                    self._apply_plot_theme(detail_fig, ax) # Re-apply theme to cleared axis

                    # Get metric key for this subplot if it exists in the configured metrics
                    metric_keys_list = list(metrics_for_current_detail.keys())
                    metric_key_for_subplot = metric_keys_list[i] if i < len(metric_keys_list) else None

                    # Restore title and labels
                    if metric_key_for_subplot:
                        details = metrics_for_current_detail.get(metric_key_for_subplot, {})
                        ax.set_title(f"{details.get('label', metric_key_for_subplot)} ({details.get('unit', '')})")
                        ax.set_ylabel(details.get('unit', 'Value'))
                    else:
                        ax.set_title("")
                        ax.set_ylabel("") # Clear label for unused axes
                    ax.set_xlabel("Time")
                    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))

                    # Display "No Data Available" text
                    ax.text(0.5, 0.5, "No Data Available",
                            horizontalalignment='center', verticalalignment='center',
                            transform=ax.transAxes, fontsize=12, color='gray')
                    
                    self.debug_logger.debug(f"Detail plot data update: Cleared and set 'No Data Available' for subplot {i} on {current_detail_sensor_key}.")
            
            detail_fig.tight_layout()
            canvas.draw_idle()
            self.debug_logger.debug(f"Detail plot data update: Canvas redrawn for {current_detail_sensor_key} with 'No Data Available'.")
            return

        metrics_to_plot = list(metrics_for_current_detail.keys())

        # Keep track of which axes have been used for plotting data
        used_axes_indices = set()

        for i, metric_key in enumerate(metrics_to_plot):
            full_metric_key = f"{current_detail_sensor_key}_{metric_key}"
            
            # Ensure the subplot axis exists for the current metric.
            if i >= len(plot_info_dict['axes']):
                self.debug_logger.error(f"Detail plot data update: Not enough axes for metric {metric_key}. Axes available: {len(plot_info_dict['axes'])} Required index: {i}")
                continue # Skip this metric if no corresponding axis

            ax = plot_info_dict['axes'][i]
            used_axes_indices.add(i) # Mark this axis as used

            self.debug_logger.debug(f"Detail plot data update: Processing line for {metric_key}.")

            ax.clear() # Clear subplot for redraw
            self._apply_plot_theme(detail_fig, ax) # Re-apply theme to cleared subplot
            self.debug_logger.debug(f"Detail plot data update: Subplot for {metric_key} cleared and theme re-applied.")

            details = metrics_for_current_detail.get(metric_key, {})
            ax.set_title(f"{details.get('label', metric_key)} ({details.get('unit', '')})")
            ax.set_xlabel("Time")
            ax.set_ylabel(details.get('unit', 'Value'))
            ax.grid(True)
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
            self.debug_logger.debug(f"Detail plot data update: Subplot titles/labels reset for {metric_key}.")

            values_from_history = [
                data.get(current_detail_sensor_key, {}).get(metric_key, float('nan'))
                for data in all_sensor_data_history
            ]
            self.debug_logger.debug(f"Detail plot data update: Raw values for {current_detail_sensor_key}.{metric_key}: {values_from_history[:5]}... (first 5)")

            valid_data_indices = [idx for idx, val in enumerate(values_from_history) if val is not None and not math.isnan(val) and not math.isinf(val)]
            filtered_dates = [dates[idx] for idx in valid_data_indices]
            filtered_values = [values_from_history[idx] for idx in valid_data_indices]
            
            if filtered_dates and filtered_values:
                # Always create a new line object for consistency after clearing the axis
                line, = ax.plot(filtered_dates, filtered_values, color=plot_colors[i % len(plot_colors)], marker='o', markersize=2, linestyle='-')
                plot_info_dict['lines'][metric_key] = line # Store the new line object
                self.debug_logger.debug(f"Detail plot data update: Re-created plot line for {metric_key}.")

                # Dynamic X-axis limits
                if len(filtered_dates) > 1:
                    ax.set_xlim(min(filtered_dates), max(filtered_dates) + (max(filtered_dates) - min(filtered_dates)) * 0.05)
                elif len(filtered_dates) == 1:
                    single_point_date = filtered_dates[0]
                    ax.set_xlim(single_point_date - (1/1440), single_point_date + (1/1440)) # +/- 1 minute for single point
                else:
                    ax.set_xlim(0,1)

                # Dynamic Y-axis limits for individual subplot
                min_val = min(filtered_values)
                max_val = max(filtered_values)
                y_buffer = (max_val - min_val) * 0.1
                if y_buffer == 0:
                    y_buffer = abs(min_val) * 0.1 if min_val != 0 else 1
                ax.set_ylim(min_val - y_buffer, max_val + y_buffer)
                self.debug_logger.debug(f"Detail plot data update: Min/Max values for {current_detail_sensor_key}.{metric_key}: {min_val:.2f}/{max_val:.2f}. Y-axis adjusted to [{min_val - y_buffer:.2f}, {max_val + y_buffer:.2f}].")
                
                ax.relim()
                ax.autoscale_view(True,True,True)
                self.debug_logger.debug(f"Detail plot data update: Filtered {len(filtered_dates)} valid data points for {current_detail_sensor_key}.{metric_key}. Axes auto-scaled.")
            else:
                # If no valid data, display "No Data Available" message in the subplot
                ax.text(0.5, 0.5, "No Data Available",
                        horizontalalignment='center',
                        verticalalignment='center',
                        transform=ax.transAxes,
                        color=self.current_theme_data.get('plot_tick_color', 'gray'),
                        fontsize=12)
                # Ensure the line object is cleared or a dummy one is used
                # Since we clear() and then re-plot(), any existing line is effectively gone.
                # If no data, no line is created.
                self.debug_logger.info(f"Detail plot data update: No valid data for {current_detail_sensor_key}.{metric_key}. Displaying 'No Data Available'.")

        # Hide any subplots that were not used for plotting data in this update cycle
        all_axes_indices = set(range(len(plot_info_dict['axes'])))
        unused_axes_indices = all_axes_indices - used_axes_indices
        for j in unused_axes_indices:
            self.debug_logger.debug(f"Detail plot data update: Hiding unused subplot {j}.")
            plot_info_dict['axes'][j].set_visible(False) # Set unused subplots invisible

        detail_fig.autofmt_xdate()
        self.debug_logger.debug("Detail plot data update: Fig.autofmt_xdate() called for detail plots.")
        canvas.draw()
        canvas.flush_events()
        self.debug_logger.debug(f"Detail plot data update: Canvas redrawn for detail plots of {current_detail_sensor_key}.")
        self.debug_logger.debug(f"Detail plot data update: Completed for {current_detail_sensor_key}.")


    def _apply_current_theme(self):
        """Applies the currently selected theme to the entire application."""
        theme_name = self.settings_manager.get_setting("theme")
        self.current_theme_data = self.settings_manager.get_theme_data(theme_name)
        if not self.current_theme_data:
            self.debug_logger.error(f"Theme '{theme_name}' not found. Using default.")
            self.current_theme_data = self.settings_manager.get_theme_data("Default Light") # Fallback
            self.theme_combo.setCurrentText("Default Light") # Update combo box if fallback

        self.debug_logger.info(f"Applying theme: {theme_name}.")

        # Apply native style (e.g., Fusion)
        # Robust theme application: Check if 'native_style' exists
        native_style = self.current_theme_data.get("native_style", "Fusion")
        QApplication.setStyle(QStyleFactory.create(native_style))
        self.debug_logger.debug(f"Theme application: Set native style to {native_style}.")

        # Apply palette colors
        palette = self.palette()
        # Robust theme application: Check for each color key
        palette.setColor(QPalette.Window, QColor(self.current_theme_data.get("bg_color", "#F0F0F0")))
        palette.setColor(QPalette.WindowText, QColor(self.current_theme_data.get("text_color", "#333333")))
        palette.setColor(QPalette.Base, QColor(self.current_theme_data.get("base_color", "#FFFFFF")))
        palette.setColor(QPalette.AlternateBase, QColor(self.current_theme_data.get("alt_bg_color", "#E0E0E0")))
        palette.setColor(QPalette.Text, QColor(self.current_theme_data.get("text_color", "#333333")))
        palette.setColor(QPalette.Button, QColor(self.current_theme_data.get("button_bg_color", "#007BFF")))
        palette.setColor(QPalette.ButtonText, QColor(self.current_theme_data.get("button_text_color", "#FFFFFF")))
        palette.setColor(QPalette.Highlight, QColor(self.current_theme_data.get("highlight_color", "#0056b3")))
        palette.setColor(QPalette.HighlightedText, QColor(self.current_theme_data.get("highlighted_text_color", "#FFFFFF")))
        palette.setColor(QPalette.PlaceholderText, QColor(self.current_theme_data.get("placeholder_text_color", "#A0A0A0")))
        self.setPalette(palette)
        self.debug_logger.debug("Theme application: Applied palette colors.")

        # Apply QSS for specific widgets that don't fully respect palette or need custom styling
        self.setStyleSheet(self._get_qss_for_app())
        self.debug_logger.debug("Theme application: Applied main QSS stylesheet.")


        # Update specific widgets that might need individual style recalculation or repainting
        # Update GroupBox titles
        self.debug_logger.debug("Theme application: Updating GroupBox QSS.")
        for group_box in self.findChildren(QGroupBox):
            group_box.setStyleSheet(self._get_qss_for_groupbox())

        # Update plot backgrounds and text colors
        self.debug_logger.debug("Theme application: Triggering _update_plots to redraw with new theme.")
        self._update_plots() # This will re-draw plots with new colors

        self.debug_logger.info(f"Theme '{theme_name}' applied.")

    def _update_gauge_colors(self):
        """Applies the selected gauge color style to all active gauge widgets."""
        gauge_style_name = self.settings_manager.get_setting("gauge_style")
        gauge_style_data = self.settings_manager.get_theme_data(gauge_style_name)

        if not gauge_style_data:
            self.debug_logger.error(f"Gauge style data for '{gauge_style_name}' not found. Cannot apply gauge style.")
            self._display_status_message(f"Error: Gauge style '{gauge_style_name}' not found.", 'danger')
            return

        self.debug_logger.debug(f"Applying gauge style data: {gauge_style_data}")

        # Update dashboard gauges
        for metric_key, gauge_widget in self.dashboard_gauges.items():
            self.debug_logger.debug(f"Applying colors to dashboard gauge: {metric_key}")
            gauge_widget.set_colors(
                arc_background=gauge_style_data.get("gauge_arc_background", "#E0E0E0"),
                label_color=gauge_style_data.get("gauge_label_color", "#333333"),
                value_color=gauge_style_data.get("gauge_value_color", "#333333"),
                outline_color=gauge_style_data.get("gauge_outline", "#B8B8B8"),
                fill_low=gauge_style_data.get("gauge_fill_low", "#2ECC71"),
                fill_medium=gauge_style_data.get("gauge_fill_medium", "#F1C40F"),
                fill_high=gauge_style_data.get("gauge_fill_high", "#E74C3C"),
                na_color=gauge_style_data.get("gauge_na", "#95A5A6"),
                needle_color=gauge_style_data.get("gauge_needle", "#000000"), # Added needle_color
                gauge_inner_circle=gauge_style_data.get("gauge_inner_circle", "#FFFFFF") # Pass inner circle color
            )
            gauge_widget.update() # Ensure repaint after setting colors

        # Update detail gauges (if any are active)
        for metric_key, gauge_widget in self.detail_gauges.items():
            self.debug_logger.debug(f"Applying colors to detail gauge: {metric_key}")
            gauge_widget.set_colors(
                arc_background=gauge_style_data.get("gauge_arc_background", "#E0E0E0"),
                label_color=gauge_style_data.get("gauge_label_color", "#333333"),
                value_color=gauge_style_data.get("gauge_value_color", "#333333"),
                outline_color=gauge_style_data.get("gauge_outline", "#B8B8B8"),
                fill_low=gauge_style_data.get("gauge_fill_low", "#2ECC71"),
                fill_medium=gauge_style_data.get("gauge_fill_medium", "#F1C40F"),
                fill_high=gauge_style_data.get("gauge_fill_high", "#E74C3C"),
                na_color=gauge_style_data.get("gauge_na", "#95A5A6"),
                needle_color=gauge_style_data.get("gauge_needle", "#000000"), # Added needle_color
                gauge_inner_circle=gauge_style_data.get("gauge_inner_circle", "#FFFFFF") # Pass inner circle color
            )
            gauge_widget.update() # Ensure repaint after setting colors

        self.debug_logger.info("Gauge colors updated based on selected style.")
        self.update() # Force repaint of MainWindow to ensure all elements are consistent

    def _get_qss_for_app(self):
        """Returns the main QSS stylesheet for the application, based on the current theme."""
        if not hasattr(self, 'current_theme_data'):
            return ""
        theme = self.current_theme_data
        return f"""
            QMainWindow {{
                background-color: {theme.get("bg_color", "#F0F0F0")};
                color: {theme.get("text_color", "#333333")};
            }}
            QTabWidget::pane {{
                border: 1px solid {theme.get("outline_color", "#A0A0A0")};
                background-color: {theme.get("alt_bg_color", "#E0E0E0")};
            }}
            QTabWidget::tab-bar {{
                left: 5px;
            }}
            QTabBar::tab {{
                background: {theme.get("alt_bg_color", "#E0E0E0")};
                color: {theme.get("text_color", "#333333")};
                border: 1px solid {theme.get("outline_color", "#A0A0A0")};
                border-bottom-left-radius: 4px;
                border-bottom-right-radius: 44px;
                padding: 8px 15px;
            }}
            QTabBar::tab:selected {{
                background: {theme.get("highlight_color", "#0056b3")};
                color: {theme.get("highlighted_text_color", "#FFFFFF")};
                border-color: {theme.get("highlight_color", "#0056b3")};
            }}
            QTabBar::tab:hover {{
                background: {theme.get("highlight_color", "#0056b3")}; /* Same as selected for consistency */
                color: {theme.get("highlighted_text_color", "#FFFFFF")};
            }}
            QLineEdit {{
                background-color: {theme.get("base_color", "#FFFFFF")};
                color: {theme.get("text_color", "#333333")};
                border: 1px solid {theme.get("outline_color", "#A0A0A0")};
                border-radius: 4px;
                padding: 5px;
            }}
            QLineEdit:read-only {{
                background-color: {theme.get("alt_bg_color", "#E0E0E0")};
                color: {theme.get("placeholder_text_color", "#A0A0A0")};
            }}
            QComboBox {{
                background-color: {theme.get("base_color", "#FFFFFF")};
                color: {theme.get("text_color", "#333333")};
                border: 1px solid {theme.get("outline_color", "#A0A0A0")};
                border-radius: 4px;
                padding: 3px;
            }}
            QComboBox::drop-down {{
                border: 0px; /* No border for the arrow */
            }}
            QComboBox::down-arrow {{
                image: url(data:image/png;base64,iVBORw0KGgoAAAABAAAAAQCAMAAADm4gqRAAAAAXNSR0IArs4c6QAAACtQTFRFAAAA/Pz8/v7+/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39Nn7DngAAAAp0Uk5TAAECAwQFBgcICQoLIQ4XNAAAACxJREFUCNdjYGBiYGZiZGDgY2ZiYGRmYGJgYGRgZmRiYGZmYGJgYmRgYmBgZAEQZgAB2t1hNAAAAABJRU5ErkJggg==); /* Down arrow */
                width: 10px;
                height: 10px;
                margin-right: 5px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {theme.get("base_color", "#FFFFFF")};
                color: {theme.get("text_color", "#333333")};
                selection-background-color: {theme.get("highlight_color", "#0056b3")};
                selection-color: {theme.get("highlighted_text_color", "#FFFFFF")};
            }}
            QCheckBox {{
                color: {theme.get("text_color", "#333333")};
            }}
            QCheckBox::indicator {{
                width: 15px;
                height: 15px;
                border: 1px solid {theme.get("outline_color", "#A0A0A0")};
                border-radius: 3px;
                background-color: {theme.get("base_color", "#FFFFFF")};
            }}
            QCheckBox::indicator:checked {{
                background-color: {theme.get("button_bg_color", "#007BFF")};
                image: url(data:image/png;base64,iVBORw0KGgoAAAABAAAAAQCAMAAADtlSYSAAAABlBMVEUAAAAAAAAAAAAAAAC/vsC/vsC/vsC/vsC/vsC/vsC/vsC/vsC/vsC/vsAAACwHlX4AAAACHRSTlMA+O/fX1/DydF0kGE1AAAACXBIWXMAAABIAAAASABGyWsUAAAAI0lEQVQYV2NgYGBkYmRgZGFlYmRgYGJkYGRgYAZiYGJmYAAAZAAFG9g3m1UAAAAASUVORK5CYII=); /* Tiny checkmark */
            }}
            QCheckBox::indicator:disabled {{
                background-color: {theme.get("alt_bg_color", "#E0E0E0")};
                border: 1px solid {theme.get("alt_bg_color", "#E0E0E0")};\
            }}
            QTextEdit {{
                background-color: {theme.get("base_color", "#FFFFFF")};
                color: {theme.get("text_color", "#333333")};
                border: 1px solid {theme.get("outline_color", "#A0A0A0")};
                border-radius: 4px;
                padding: 5px;
            }}
            QScrollArea {{
                border: 1px solid {theme.get("outline_color", "#A0A0A0")};
                border-radius: 4px;
            }}
            QStatusBar {{
                background-color: {theme.get("alt_bg_color", "#E0E0E0")};
                color: {theme.get("text_color", "#333333")};
            }}
            QScrollBar:vertical {{
                border: 1px solid {theme.get("outline_color", "#A0A0A0")};
                background: {theme.get("alt_bg_color", "#E0E0E0")};
                width: 10px;
                margin: 21px 0 21px 0;
            }}
            QScrollBar::handle:vertical {{
                background: {theme.get("button_bg_color", "#007BFF")};
                min-height: 20px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                background: {theme.get("alt_bg_color", "#E0E0E0")};
                height: 20px;
                subcontrol-origin: margin;
            }}
            QScrollBar::up-arrow:vertical, QScrollBar::down-arrow:vertical {{
                background: {theme.get("text_color", "#333333")};
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: none;
            }}
        """

    def _get_qss_for_button(self):
        """Returns QSS for QPushButton widgets."""
        if not hasattr(self, 'current_theme_data'):
            return ""
        theme = self.current_theme_data
        return f"""
            QPushButton {{
                background-color: {theme.get("button_bg_color", "#007BFF")};
                color: {theme.get("button_text_color", "#FFFFFF")};
                border: none;
                border-radius: 8px;
                padding: 8px 15px;
                font-size: 12px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {theme.get("highlight_color", "#0056b3")};
            }}
            QPushButton:pressed {{
                background-color: {theme.get("highlight_color", "#0056b3")};
                border-style: inset;
            }}
            QPushButton:disabled {{
                background-color: {theme.get("alt_bg_color", "#E0E0E0")};
                color: {theme.get("placeholder_text_color", "#A0A0A0")};
            }}
        """

    def _get_qss_for_groupbox(self):
        """Returns QSS for QGroupBox widgets."""
        if not hasattr(self, 'current_theme_data'):
            return ""
        theme = self.current_theme_data
        return f"""
            QGroupBox {{
                background-color: {theme.get("alt_bg_color", "#E0E0E0")};
                border: 1px solid {theme.get("outline_color", "#A0A0A0")};
                border-radius: 8px;
                margin-top: 10px; /* Space for title */
                padding-top: 15px; /* Adjust padding for title */
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top center; /* Position at the top center */
                padding: 0 5px;
                background-color: {theme.get("alt_bg_color", "#E0E0E0")}; /* Match groupbox background */
                color: {theme.get("text_color", "#333333")};
                font-weight: bold;
                font-size: 14px;
            }}
        """

    def closeEvent(self, event):
        """Handles the application close event, ensuring threads are stopped and settings saved."""
        self.debug_logger.info("Application close event triggered.")
        reply = QMessageBox.question(self, 'Message',
                                     "Are you sure you want to quit?", QMessageBox.Yes |
                                     QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            self.debug_logger.info("User confirmed application shutdown.")
            # Stop plot update timer
            if self.plot_update_timer.isActive():
                self.plot_update_timer.stop()
                self.debug_logger.debug("Plot update timer stopped.")

            # Request sensor thread to stop
            if self.sensor_thread.isRunning():
                self.debug_logger.debug("Sensor thread stop signal sent.")
                self.sensor_thread.stop()
                self.debug_logger.debug("Waiting for sensor thread to join.")
                self.sensor_thread.wait(5000) # Wait up to 5 seconds for the thread to finish
                if self.sensor_thread.isRunning():
                    self.debug_logger.warning("Sensor thread did not terminate gracefully.")
                else:
                    self.status_bar_message_signal.emit("Sensor thread terminated successfully.", 'info')
                    self.data_logger.debug_logger.info("Sensor thread terminated successfully.")

            # Request final archive on shutdown (this will also close log files)
            try:
                self.data_logger.debug_logger.info("Attempting final log archive on shutdown.")
                self.data_logger.archive_logs()
                self.status_bar_message_signal.emit("Final log archive completed.", 'info')
                self.data_logger.debug_logger.info("Final log archive completed during shutdown.")
            except Exception as e:
                self.status_bar_message_signal.emit(f"Error during final log archive: {e}", 'danger')
                self.data_logger.debug_logger.error(f"Error during final log archive on shutdown: {e}")

            self.data_logger.close_all_log_files() # Ensure all CSV files are closed - redundant with archive_logs but good for safety
            self.data_logger.debug_logger.debug("All CSV log files closed (explicit call).\n")
            self.settings_manager.save_settings() # Final save of settings
            self.data_logger.debug_logger.info("Final settings saved.")

            event.accept()
            self.data_logger.debug_logger.info("Application exit accepted.")
        else:
            event.ignore()
            self.data_logger.debug_logger.info("Application exit ignored by user.")
