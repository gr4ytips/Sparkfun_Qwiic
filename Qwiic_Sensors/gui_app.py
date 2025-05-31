import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import ttkbootstrap as tb
from ttkbootstrap.constants import *
import threading
import time
import queue
import datetime
import sys
import subprocess
import os

# Import modularized components
from sensor_reader import SensorReader
from data_manager import DataManager
from data_logger import DataLogger
from gui_widgets import GaugeWidget
from sound_manager import SoundManager

import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

class SensorGUI(tb.Window):
    def __init__(self):
        super().__init__(themename="superhero")
        self.title("Multi-Sensor Data Logger")
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

        # Ensure last_sensor_values is initialized very early
        self.last_sensor_values = {} # Moved to be one of the first instance attributes

        # --- Loading Screen Setup ---
        self.loading_screen_window = None
        self.loading_screen_active = True
        self._show_loading_screen()

        # --- Queues for inter-thread communication ---
        self.data_queue = queue.Queue() # SensorReader -> GUI (sensor data)
        self.status_queue = queue.Queue() # SensorReader/other modules -> GUI (status messages)

        # --- Initialize modular components ---
        self.data_manager = DataManager()
        self.data_logger = DataLogger(
            log_path=os.path.join(os.getcwd(), "sensor_logs"),
            archive_path=os.path.join(os.getcwd(), "sensor_archives"),
            archive_enabled=True,
            initial_log_settings={
                'bme280': True, 'sgp40': True, 'shtc3': True, 'proximity': True
            },
            status_queue=self.status_queue
        )
        self.sound_manager = SoundManager(self.status_queue)

        # --- Configuration Variables (Tkinter String/Boolean Vars) ---
        self.log_path = tk.StringVar(value=self.data_logger._log_path_internal)
        self.archive_path = tk.StringVar(value=self.data_logger._archive_path_internal)
        self.archive_enabled = tk.BooleanVar(value=self.data_logger._archive_enabled_internal)
        self.play_alert_sound = tk.BooleanVar(value=True)
        self.play_change_sound = tk.BooleanVar(value=True)

        self.plot_time_range = tk.StringVar(value="Last 10 minutes")
        self.plot_update_interval = tk.StringVar(value="5") # Initial read interval

        self.log_settings = {
            'bme280': tk.BooleanVar(value=True),
            'sgp40': tk.BooleanVar(value=True),
            'shtc3': tk.BooleanVar(value=True),
            'proximity': tk.BooleanVar(value=True)
        }
        # Update initial log settings in data_logger based on Tkinter vars
        initial_log_settings_values = {sensor: var.get() for sensor, var in self.log_settings.items()}
        self.data_logger.update_config(
            self.log_path.get(), self.archive_path.get(), self.archive_enabled.get(), initial_log_settings_values
        )

        # --- Threading and Communication ---
        self.stop_event = threading.Event()
        self.after_id = None # To store after() call ID for cancellation

        # Initialize and start the SensorReader thread
        self.sensor_thread = SensorReader(
            self.data_queue, self.status_queue, self.data_manager, self.data_logger,
            self.stop_event, int(self.plot_update_interval.get())
        )
        self.sensor_thread.start()
        print("GUI: Sensor thread started.")

        # --- Build UI ---
        self._create_widgets()

        # --- Start periodic data checking ---
        # Changed to use lambda for robust self reference
        self.after_id = self.after(100, lambda: self._check_for_data())
        self._update_status_bar("Application started. Waiting for sensor data...", color='info')

    def _show_loading_screen(self):
        """Creates and displays a loading screen."""
        self.loading_screen_window = tk.Toplevel(self)
        self.loading_screen_window.title("Loading...")
        self.loading_screen_window.transient(self)
        self.loading_screen_window.grab_set()
        self.loading_screen_window.resizable(False, False)
        self.loading_screen_window.config(bg=self.style.colors.dark)

        self.loading_screen_window.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() // 2) - (self.loading_screen_window.winfo_width() // 2)
        y = self.winfo_y() + (self.winfo_height() // 2) - (self.loading_screen_window.winfo_height() // 2)
        self.loading_screen_window.geometry(f"+{x}+{y}")

        loading_frame = ttk.Frame(self.loading_screen_window, padding=20)
        loading_frame.pack(padx=20, pady=20)

        ttk.Label(loading_frame, text="Initializing Sensors and Loading Data...",
                  font=("Arial", 12, "bold"), foreground=self.style.colors.light).pack(pady=10)

        progress_bar = ttk.Progressbar(loading_frame, mode='indeterminate', length=200)
        progress_bar.pack(pady=10)
        progress_bar.start(10)

        self.update_idletasks()
        self.loading_screen_window.update()

    def _hide_loading_screen(self):
        """Hides and destroys the loading screen."""
        if self.loading_screen_window and self.loading_screen_active:
            self.loading_screen_window.grab_release()
            self.loading_screen_window.destroy()
            self.loading_screen_window = None
            self.loading_screen_active = False

    def _create_widgets(self):
        """Creates all GUI widgets and lays them out."""
        self.main_notebook = ttk.Notebook(self)
        self.main_notebook.pack(fill=BOTH, expand=YES, padx=5, pady=5)

        # --- Sensor Data & Plots Tab (First Tab) ---
        data_tab_frame = ttk.Frame(self.main_notebook)
        self.main_notebook.add(data_tab_frame, text="Sensor Data & Plots")

        data_canvas = tk.Canvas(data_tab_frame, highlightthickness=0, bg=self.style.colors.dark)
        data_scrollbar_y = ttk.Scrollbar(data_tab_frame, orient="vertical", command=data_canvas.yview)
        data_scrollbar_x = ttk.Scrollbar(data_tab_frame, orient="horizontal", command=data_canvas.xview)

        data_scrollbar_y.pack(side=RIGHT, fill=Y)
        data_scrollbar_x.pack(side=BOTTOM, fill=X)
        data_canvas.pack(side=LEFT, fill=BOTH, expand=YES)

        data_canvas.configure(yscrollcommand=data_scrollbar_y.set, xscrollcommand=data_scrollbar_x.set)

        data_content_frame = ttk.Frame(data_canvas, padding=5, relief=tk.RIDGE)
        data_canvas.create_window((0, 0), window=data_content_frame, anchor="nw")
        data_content_frame.bind('<Configure>', lambda e: data_canvas.configure(scrollregion=data_canvas.bbox("all")))

        # --- Controls & Settings Tab (Second Tab) ---
        controls_tab_frame = ttk.Frame(self.main_notebook)
        self.main_notebook.add(controls_tab_frame, text="Controls & Settings")

        controls_canvas = tk.Canvas(controls_tab_frame, highlightthickness=0, bg=self.style.colors.dark)
        controls_scrollbar_y = ttk.Scrollbar(controls_tab_frame, orient="vertical", command=controls_canvas.yview)
        controls_scrollbar_x = ttk.Scrollbar(controls_tab_frame, orient="horizontal", command=controls_canvas.xview)
        
        controls_scrollbar_y.pack(side=RIGHT, fill=Y)
        controls_scrollbar_x.pack(side=BOTTOM, fill=X)
        controls_canvas.pack(side=LEFT, fill=BOTH, expand=YES)

        controls_canvas.configure(yscrollcommand=controls_scrollbar_y.set, xscrollcommand=controls_scrollbar_x.set)
        
        controls_content_frame = ttk.Frame(controls_canvas, padding=5, relief=tk.RIDGE)
        controls_canvas.create_window((0, 0), window=controls_content_frame, anchor="nw")
        controls_content_frame.bind('<Configure>', lambda e: controls_canvas.configure(scrollregion=controls_canvas.bbox("all")))

        # Common mouse wheel binding for both canvases
        def _on_mouse_wheel(event):
            current_tab_id = self.main_notebook.select()
            current_tab_widget = self.main_notebook.nametowidget(current_tab_id)

            if current_tab_widget == controls_tab_frame:
                canvas_to_scroll = controls_canvas
            elif current_tab_widget == data_tab_frame:
                canvas_to_scroll = data_canvas
            else:
                return

            if sys.platform == "darwin":
                canvas_to_scroll.yview_scroll(-1 * int(event.delta), "units")
            elif sys.platform == "win32":
                canvas_to_scroll.yview_scroll(-1 * int(event.delta / 120), "units")
            else:
                if event.num == 4:
                    canvas_to_scroll.yview_scroll(-1, "units")
                elif event.num == 5:
                    canvas_to_scroll.yview_scroll(1, "units")

        self.bind_all("<MouseWheel>", _on_mouse_wheel)
        self.bind_all("<Button-4>", _on_mouse_wheel)
        self.bind_all("<Button-5>", _on_mouse_wheel)

        self.style.configure("TCheckbutton", font="Arial 9")
        self.style.configure("TButton", font="Arial 9")
        self.text_color = self.style.colors.light

        # --- Widgets for Controls & Settings Tab (packed into controls_content_frame) ---
        status_label = ttk.Label(controls_content_frame, text="Sensor Status:", font="Arial 10 bold")
        status_label.pack(pady=(0, 2), anchor=W)
        
        self.status_text = tk.Text(controls_content_frame, height=5, wrap=tk.WORD, state=tk.DISABLED,
                                   background=self.style.colors.dark, foreground=self.style.colors.info,
                                   font="Arial 8")
        self.status_text.pack(fill=X, pady=(0, 5))

        sound_frame = ttk.LabelFrame(controls_content_frame, text="Sound Settings", padding=5)
        sound_frame.pack(fill=X, pady=5)
        
        self.alert_sound_checkbox = ttk.Checkbutton(
            sound_frame,
            text="Play Alert Sound",
            variable=self.play_alert_sound,
            bootstyle="round-toggle"
        )
        self.alert_sound_checkbox.pack(pady=1, anchor=W)
        
        self.change_sound_checkbox = ttk.Checkbutton(
            sound_frame,
            text="Play Change Sounds",
            variable=self.play_change_sound,
            bootstyle="round-toggle"
        )
        self.change_sound_checkbox.pack(pady=1, anchor=W)

        if not self.sound_manager.sound_system_available:
            self.alert_sound_checkbox.config(state=tk.DISABLED)
            self.change_sound_checkbox.config(state=tk.DISABLED)
            ttk.Label(sound_frame, text="Sound system not available. Sound disabled.", bootstyle="warning", font="Arial 8").pack(pady=1, anchor=W)

        log_frame = ttk.LabelFrame(controls_content_frame, text="Logging Settings", padding=5)
        log_frame.pack(fill=X, pady=5)

        ttk.Label(log_frame, text="Log Directory:", font="Arial 9").pack(pady=(0, 2), anchor=W)
        self.log_path_entry = ttk.Entry(log_frame, textvariable=self.log_path, font="Arial 8")
        self.log_path_entry.pack(fill=X, expand=YES)
        ttk.Button(log_frame, text="Browse Log Path", command=self._browse_log_path).pack(fill=X, pady=2)

        ttk.Label(log_frame, text="Archive Directory:", font="Arial 9").pack(pady=(5, 2), anchor=W)
        self.archive_path_entry = ttk.Entry(log_frame, textvariable=self.archive_path, font="Arial 8")
        self.archive_path_entry.pack(fill=X, expand=YES)
        ttk.Button(log_frame, text="Browse Archive Path", command=self._browse_archive_path).pack(fill=X, pady=2)
        
        ttk.Checkbutton(log_frame, text="Enable Auto-Archiving", variable=self.archive_enabled).pack(pady=2, anchor=W)
        ttk.Button(log_frame, text="Apply Log Settings", command=self._apply_log_settings).pack(fill=X, pady=5)
        ttk.Button(log_frame, text="Archive Now", command=self._trigger_archive_now, bootstyle="info").pack(fill=X, pady=2)

        sensor_log_toggle_frame = ttk.LabelFrame(controls_content_frame, text="Sensor Logging", padding=5)
        sensor_log_toggle_frame.pack(fill=X, pady=5)
        
        for sensor_name, var in self.log_settings.items():
            ttk.Checkbutton(sensor_log_toggle_frame, text=f"Log {sensor_name.upper()}", variable=var).pack(pady=1, anchor=W)

        plot_settings_frame = ttk.LabelFrame(controls_content_frame, text="Plot Settings", padding=5)
        plot_settings_frame.pack(fill=X, pady=5)

        ttk.Label(plot_settings_frame, text="Time Range:", font="Arial 9").pack(pady=(0, 2), anchor=W)
        self.time_range_combobox = ttk.Combobox(
            plot_settings_frame,
            textvariable=self.plot_time_range,
            values=["Last 10 minutes", "Last 30 minutes", "Last hour", "Last 6 hours", "Last 24 hours", "All data"],
            state="readonly",
            font="Arial 8"
        )
        self.time_range_combobox.pack(fill=X, expand=YES, pady=2)
        self.time_range_combobox.set("Last 10 minutes")

        ttk.Label(plot_settings_frame, text="Read Interval (seconds):", font="Arial 9").pack(pady=(5, 2), anchor=W)
        self.read_interval_entry = ttk.Entry(plot_settings_frame, textvariable=self.plot_update_interval, font="Arial 8")
        self.read_interval_entry.pack(fill=X, expand=YES, pady=2)

        ttk.Button(plot_settings_frame, text="Apply Plot Settings", command=self._apply_plot_settings).pack(fill=X, pady=5)

        folder_buttons_frame = ttk.Frame(controls_content_frame)
        folder_buttons_frame.pack(fill=X, pady=5)
        ttk.Button(folder_buttons_frame, text="Open Log", command=self._open_log_folder, bootstyle="secondary").pack(side=LEFT, expand=YES, fill=X, padx=1)
        ttk.Button(folder_buttons_frame, text="Open Archive", command=self._open_archive_folder, bootstyle="secondary").pack(side=RIGHT, expand=YES, fill=X, padx=1)

        # --- Widgets for Sensor Data & Plots Tab (packed into data_content_frame) ---
        readings_frame = ttk.LabelFrame(data_content_frame, text="Current Sensor Readings", padding=5)
        readings_frame.pack(fill=X, pady=5)

        self.reading_labels = {}
        self.gauge_widgets = {}
        column_limit = 2

        sensors_to_display = {
            'bme280': [
                ("Temp C:", "temp_c", "°C", True, 0, 50),
                ("Temp F:", "temp_f", "°F", False),
                ("Humidity:", "humidity", "%", True, 0, 100),
                ("Pressure:", "pressure", "hPa", False),
                ("Altitude:", "altitude", "ft", False),
                ("Dew C:", "dewpoint_c", "°C", False),
                ("Dew F:", "dewpoint_f", "°F", False),
            ],
            'sgp40': [
                ("VOC Index:", "voc_index", "", True, 0, 500),
            ],
            'shtc3': [
                ("Temp SHT:", "temperature", "°C", True, 0, 50),
                ("Hum SHT:", "humidity", "%", True, 0, 100),
            ],
            'proximity': [
                ("Proximity:", "proximity", "", True, 0, 255),
                ("Ambient:", "ambient_light", "", False),
                ("White:", "white_light", "", False),
            ]
        }

        sensor_readings_grid_frame = ttk.Frame(readings_frame)
        sensor_readings_grid_frame.pack(fill=BOTH, expand=YES)

        current_row_in_grid = 0
        current_col_in_grid = 0

        for sensor, metrics in sensors_to_display.items():
            sensor_block_frame = ttk.LabelFrame(sensor_readings_grid_frame, text=sensor.upper(), padding=2)
            sensor_block_frame.grid(row=current_row_in_grid, column=current_col_in_grid,
                                    sticky="nsew", padx=2, pady=2)

            sensor_readings_grid_frame.grid_columnconfigure(current_col_in_grid, weight=1)

            block_row_idx = 0
            for metric in metrics:
                label_text, key, unit, is_gauge = metric[0], metric[1], metric[2], metric[3]
                
                if is_gauge:
                    min_val, max_val = metric[4], metric[5]
                    gauge = GaugeWidget(
                        sensor_block_frame,
                        label_text=label_text.replace(":", ""),
                        min_val=min_val,
                        max_val=max_val,
                        unit=unit,
                        size=80,
                        style_colors=self.style.colors,
                        bg=self.style.colors.dark
                    )
                    gauge.grid(row=block_row_idx, column=0, columnspan=2, pady=2)
                    self.gauge_widgets[f"{sensor}_{key}"] = gauge
                else:
                    ttk.Label(sensor_block_frame, text=label_text, font="Arial 8").grid(row=block_row_idx, column=0, sticky=W, padx=2, pady=0)
                    value_label = ttk.Label(sensor_block_frame, text="N/A", font="Arial 8 bold")
                    value_label.grid(row=block_row_idx, column=1, sticky=W)
                    self.reading_labels[f"{sensor}_{key}"] = (value_label, unit)

                block_row_idx += 1

            current_col_in_grid += 1
            if current_col_in_grid >= column_limit:
                current_col_in_grid = 0
                current_row_in_grid += 1

        for r in range(current_row_in_grid + 1):
            sensor_readings_grid_frame.grid_rowconfigure(r, weight=1)

        self.plot_notebook = ttk.Notebook(data_content_frame)
        self.plot_notebook.pack(fill=BOTH, expand=YES, pady=5)

        self.plot_elements = {}

        self._add_plot_tab("Combined")
        self._add_plot_tab("BME280")
        self._add_plot_tab("SGP40")
        self._add_plot_tab("SHTC3")
        self._add_plot_tab("Proximity")

        self.status_bar = ttk.Label(self, text="Ready", bootstyle="info", anchor=W, padding=3, font="Arial 8")
        self.status_bar.pack(side=BOTTOM, fill=X)


    def _add_plot_tab(self, tab_name):
        """Adds a new tab to the plot notebook and initializes its plot."""
        frame = ttk.Frame(self.plot_notebook)
        self.plot_notebook.add(frame, text=tab_name)
        
        fig, ax1 = plt.subplots(figsize=(6, 3))
        
        fig.patch.set_facecolor(self.style.colors.dark)
        ax1.set_facecolor(self.style.colors.dark)

        ax1.tick_params(axis='x', colors=self.text_color, labelsize=7)
        ax1.tick_params(axis='y', colors=self.text_color, labelsize=7)
        ax1.set_xlabel("Time", color=self.text_color, fontsize=8)
        ax1.set_title(f"{tab_name} Data", color=self.text_color, fontsize=9)
        ax1.grid(True, linestyle='--', alpha=0.6, color=self.style.colors.secondary)

        canvas = FigureCanvasTkAgg(fig, master=frame)
        canvas_widget = canvas.get_tk_widget()
        canvas_widget.pack(fill=BOTH, expand=YES)
        canvas.draw()

        self.plot_elements[tab_name] = {
            'figure': fig,
            'ax1': ax1,
            'ax2': None,
            'canvas': canvas,
            'lines': {}
        }

        if tab_name == "Combined":
            self.plot_elements[tab_name]['ax2'] = ax1.twinx()
            ax2 = self.plot_elements[tab_name]['ax2']
            ax2.tick_params(axis='y', colors=self.text_color, labelsize=7)
            self.plot_elements[tab_name]['ax1'].set_ylabel("Temp (°C) / VOC", color=self.text_color, fontsize=8)
            ax2.set_ylabel("Humidity (%) / Proximity", color=self.text_color, fontsize=8)

            self.plot_elements[tab_name]['lines']['bme_temp'], = ax1.plot([], [], label='BME280 Temp', color=self.style.colors.primary)
            self.plot_elements[tab_name]['lines']['sht_temp'], = ax1.plot([], [], label='SHTC3 Temp', color=self.style.colors.success)
            self.plot_elements[tab_name]['lines']['voc'], = ax1.plot([], [], label='SGP40 VOC', color=self.style.colors.warning)
            self.plot_elements[tab_name]['lines']['bme_hum'], = ax2.plot([], [], label='BME280 Hum', color=self.style.colors.info, linestyle='--')
            self.plot_elements[tab_name]['lines']['sht_hum'], = ax2.plot([], [], label='SHTC3 Hum', color=self.style.colors.danger, linestyle='--')
            self.plot_elements[tab_name]['lines']['prox'], = ax2.plot([], [], label='Proximity', color=self.style.colors.secondary, linestyle=':')
            
            lines = [v for k, v in self.plot_elements[tab_name]['lines'].items()]
            labels = [l.get_label() for l in lines]
            ax1.legend(lines, labels, loc='upper left', frameon=False, labelcolor=self.text_color, fontsize=7)

        elif tab_name == "BME280":
            self.plot_elements[tab_name]['ax2'] = ax1.twinx()
            ax2 = self.plot_elements[tab_name]['ax2']
            ax2.tick_params(axis='y', colors=self.text_color, labelsize=7)
            ax1.set_ylabel("Temp (°C/F) / Pressure (hPa)", color=self.text_color, fontsize=8)
            ax2.set_ylabel("Hum (%) / Alt (ft) / Dewpoint", color=self.text_color, fontsize=8)
            
            self.plot_elements[tab_name]['lines']['temp_c'], = ax1.plot([], [], label='Temp (°C)', color=self.style.colors.primary)
            self.plot_elements[tab_name]['lines']['temp_f'], = ax1.plot([], [], label='Temp (°F)', color=self.style.colors.success)
            self.plot_elements[tab_name]['lines']['pressure'], = ax1.plot([], [], label='Pressure (hPa)', color=self.style.colors.warning)
            self.plot_elements[tab_name]['lines']['humidity'], = ax2.plot([], [], label='Humidity (%)', color=self.style.colors.info, linestyle='--')
            self.plot_elements[tab_name]['lines']['altitude'], = ax2.plot([], [], label='Altitude (ft)', color=self.style.colors.danger, linestyle='--')
            self.plot_elements[tab_name]['lines']['dewpoint_c'], = ax2.plot([], [], label='Dewpoint (°C)', color=self.style.colors.secondary, linestyle=':')
            self.plot_elements[tab_name]['lines']['dewpoint_f'], = ax2.plot([], [], label='Dewpoint (°F)', color=self.style.colors.dark, linestyle=':')
            
            lines = [v for k, v in self.plot_elements[tab_name]['lines'].items()]
            labels = [l.get_label() for l in lines]
            ax1.legend(lines, labels, loc='upper left', frameon=False, labelcolor=self.text_color, fontsize=7)

        elif tab_name == "SGP40":
            ax1.set_ylabel("VOC Index", color=self.text_color, fontsize=8)
            self.plot_elements[tab_name]['lines']['voc_index'], = ax1.plot([], [], label='VOC Index', color=self.style.colors.warning)
            ax1.legend(loc='upper left', frameon=False, labelcolor=self.text_color, fontsize=7)

        elif tab_name == "SHTC3":
            self.plot_elements[tab_name]['ax2'] = ax1.twinx()
            ax2 = self.plot_elements[tab_name]['ax2']
            ax2.tick_params(axis='y', colors=self.text_color, labelsize=7)
            ax1.set_ylabel("Temperature (°C)", color=self.text_color, fontsize=8)
            ax2.set_ylabel("Humidity (%)", color=self.text_color, fontsize=8)

            self.plot_elements[tab_name]['lines']['temperature'], = ax1.plot([], [], label='Temp (°C)', color=self.style.colors.success)
            self.plot_elements[tab_name]['lines']['humidity'], = ax2.plot([], [], label='Humidity (%)', color=self.style.colors.danger, linestyle='--')
            
            lines = [v for k, v in self.plot_elements[tab_name]['lines'].items()]
            labels = [l.get_label() for l in lines]
            ax1.legend(lines, labels, loc='upper left', frameon=False, labelcolor=self.text_color, fontsize=7)

        elif tab_name == "Proximity":
            self.plot_elements[tab_name]['ax2'] = ax1.twinx()
            ax2 = self.plot_elements[tab_name]['ax2']
            ax2.tick_params(axis='y', colors=self.text_color, labelsize=7)
            ax1.set_ylabel("Proximity", color=self.text_color, fontsize=8)
            ax2.set_ylabel("Light Value", color=self.text_color, fontsize=8)
            
            self.plot_elements[tab_name]['lines']['proximity'], = ax1.plot([], [], label='Proximity', color=self.style.colors.secondary)
            self.plot_elements[tab_name]['lines']['ambient_light'], = ax2.plot([], [], label='Ambient Light', color=self.style.colors.info, linestyle='--')
            self.plot_elements[tab_name]['lines']['white_light'], = ax2.plot([], [], label='White Light', color=self.style.colors.primary, linestyle=':')
            
            lines = [v for k, v in self.plot_elements[tab_name]['lines'].items()]
            labels = [l.get_label() for l in lines]
            ax1.legend(lines, labels, loc='upper left', frameon=False, labelcolor=self.text_color, fontsize=7)


    def _update_plot(self):
        """Updates all plots based on the current data and time range selection."""
        filtered_timestamps, filtered_sensor_data = self.data_manager.get_filtered_data(self.plot_time_range.get())

        if not filtered_timestamps:
            for tab_name, elements in self.plot_elements.items():
                for line in elements['lines'].values():
                    line.set_data([], [])
                elements['ax1'].set_ylim(0, 100)
                if elements['ax2']: elements['ax2'].set_ylim(0, 100)
                elements['canvas'].draw_idle()
            return

        x_min, x_max = filtered_timestamps[0], filtered_timestamps[-1]

        for tab_name, elements in self.plot_elements.items():
            ax1 = elements['ax1']
            ax2 = elements['ax2']
            lines = elements['lines']
            canvas = elements['canvas']

            ax1.set_xlim(x_min, x_max)
            if ax2: ax2.set_xlim(x_min, x_max)

            y1_data_for_scaling = []
            y2_data_for_scaling = []

            # Populate lines with data based on tab_name
            if tab_name == "Combined":
                lines['bme_temp'].set_data(filtered_timestamps, [d.get('bme280', {}).get('temp_c', float('nan')) for d in filtered_sensor_data])
                lines['sht_temp'].set_data(filtered_timestamps, [d.get('shtc3', {}).get('temperature', float('nan')) for d in filtered_sensor_data])
                lines['voc'].set_data(filtered_timestamps, [d.get('sgp40', {}).get('voc_index', float('nan')) for d in filtered_sensor_data])
                lines['bme_hum'].set_data(filtered_timestamps, [d.get('bme280', {}).get('humidity', float('nan')) for d in filtered_sensor_data])
                lines['sht_hum'].set_data(filtered_timestamps, [d.get('shtc3', {}).get('humidity', float('nan')) for d in filtered_sensor_data])
                lines['prox'].set_data(filtered_timestamps, [d.get('proximity', {}).get('proximity', float('nan')) for d in filtered_sensor_data])

                y1_data_for_scaling.extend([d.get('bme280', {}).get('temp_c', float('nan')) for d in filtered_sensor_data])
                y1_data_for_scaling.extend([d.get('shtc3', {}).get('temperature', float('nan')) for d in filtered_sensor_data])
                y1_data_for_scaling.extend([d.get('sgp40', {}).get('voc_index', float('nan')) for d in filtered_sensor_data])
                y2_data_for_scaling.extend([d.get('bme280', {}).get('humidity', float('nan')) for d in filtered_sensor_data])
                y2_data_for_scaling.extend([d.get('shtc3', {}).get('humidity', float('nan')) for d in filtered_sensor_data])
                y2_data_for_scaling.extend([d.get('proximity', {}).get('proximity', float('nan')) for d in filtered_sensor_data])

            elif tab_name == "BME280":
                lines['temp_c'].set_data(filtered_timestamps, [d.get('bme280', {}).get('temp_c', float('nan')) for d in filtered_sensor_data])
                lines['temp_f'].set_data(filtered_timestamps, [d.get('bme280', {}).get('temp_f', float('nan')) for d in filtered_sensor_data])
                lines['pressure'].set_data(filtered_timestamps, [d.get('bme280', {}).get('pressure', float('nan')) for d in filtered_sensor_data])
                lines['humidity'].set_data(filtered_timestamps, [d.get('bme280', {}).get('humidity', float('nan')) for d in filtered_sensor_data])
                lines['altitude'].set_data(filtered_timestamps, [d.get('bme280', {}).get('altitude', float('nan')) for d in filtered_sensor_data])
                lines['dewpoint_c'].set_data(filtered_timestamps, [d.get('bme280', {}).get('dewpoint_c', float('nan')) for d in filtered_sensor_data])
                lines['dewpoint_f'].set_data(filtered_timestamps, [d.get('bme280', {}).get('dewpoint_f', float('nan')) for d in filtered_sensor_data])

                y1_data_for_scaling.extend([d.get('bme280', {}).get('temp_c', float('nan')) for d in filtered_sensor_data])
                y1_data_for_scaling.extend([d.get('bme280', {}).get('temp_f', float('nan')) for d in filtered_sensor_data])
                y1_data_for_scaling.extend([d.get('bme280', {}).get('pressure', float('nan')) for d in filtered_sensor_data])
                y2_data_for_scaling.extend([d.get('bme280', {}).get('humidity', float('nan')) for d in filtered_sensor_data])
                y2_data_for_scaling.extend([d.get('bme280', {}).get('altitude', float('nan')) for d in filtered_sensor_data])
                y2_data_for_scaling.extend([d.get('bme280', {}).get('dewpoint_c', float('nan')) for d in filtered_sensor_data])
                y2_data_for_scaling.extend([d.get('bme280', {}).get('dewpoint_f', float('nan')) for d in filtered_sensor_data])

            elif tab_name == "SGP40":
                lines['voc_index'].set_data(filtered_timestamps, [d.get('sgp40', {}).get('voc_index', float('nan')) for d in filtered_sensor_data])
                y1_data_for_scaling.extend([d.get('sgp40', {}).get('voc_index', float('nan')) for d in filtered_sensor_data])

            elif tab_name == "SHTC3":
                lines['temperature'].set_data(filtered_timestamps, [d.get('shtc3', {}).get('temperature', float('nan')) for d in filtered_sensor_data])
                lines['humidity'].set_data(filtered_timestamps, [d.get('shtc3', {}).get('humidity', float('nan')) for d in filtered_sensor_data])
                y1_data_for_scaling.extend([d.get('shtc3', {}).get('temperature', float('nan')) for d in filtered_sensor_data])
                y2_data_for_scaling.extend([d.get('shtc3', {}).get('humidity', float('nan')) for d in filtered_sensor_data])

            elif tab_name == "Proximity":
                lines['proximity'].set_data(filtered_timestamps, [d.get('proximity', {}).get('proximity', float('nan')) for d in filtered_sensor_data])
                lines['ambient_light'].set_data(filtered_timestamps, [d.get('proximity', {}).get('ambient_light', float('nan')) for d in filtered_sensor_data])
                lines['white_light'].set_data(filtered_timestamps, [d.get('proximity', {}).get('white_light', float('nan')) for d in filtered_sensor_data])
                y1_data_for_scaling.extend([d.get('proximity', {}).get('proximity', float('nan')) for d in filtered_sensor_data])
                y2_data_for_scaling.extend([d.get('proximity', {}).get('ambient_light', float('nan')) for d in filtered_sensor_data])
                y2_data_for_scaling.extend([d.get('proximity', {}).get('white_light', float('nan')) for d in filtered_sensor_data])

            y1_data_for_scaling = [val for val in y1_data_for_scaling if not (isinstance(val, float) and (val == float('nan') or val == float('inf') or val == float('-inf')))]
            y2_data_for_scaling = [val for val in y2_data_for_scaling if not (isinstance(val, float) and (val == float('nan') or val == float('inf') or val == float('-inf')))]

            if y1_data_for_scaling:
                min_y1, max_y1 = min(y1_data_for_scaling), max(y1_data_for_scaling)
                if min_y1 == max_y1:
                    ax1.set_ylim(min_y1 * 0.9, min_y1 * 1.1 + 1)
                else:
                    ax1.set_ylim(min_y1 - (max_y1 - min_y1) * 0.1, max_y1 + (max_y1 - min_y1) * 0.1)
            else:
                ax1.set_ylim(0, 100)

            if ax2 and y2_data_for_scaling:
                min_y2, max_y2 = min(y2_data_for_scaling), max(y2_data_for_scaling)
                if min_y2 == max_y2:
                    ax2.set_ylim(min_y2 * 0.9, min_y2 * 1.1 + 1)
                else:
                    ax2.set_ylim(min_y2 - (max_y2 - min_y2) * 0.1, max_y2 + (max_y2 - min_y2) * 0.1)
            elif ax2:
                ax2.set_ylim(0, 100)

            canvas.draw_idle()

    def _check_for_data(self):
        """
        Periodically checks the data queue for new sensor readings and status messages
        and updates the GUI.
        """
        while True:
            try:
                message = self.data_queue.get_nowait()
                if message['type'] == 'sensor_data':
                    data = message['data']
                    
                    # Update current readings display and gauges
                    latest_values = self.data_manager.get_latest_values()
                    if latest_values: # Ensure there's data to process
                        for sensor_name, sensor_values in latest_values.items():
                            for key, value in sensor_values.items():
                                label_key = f"{sensor_name}_{key}"
                                if label_key in self.gauge_widgets:
                                    self.gauge_widgets[label_key].update_value(value)
                                elif label_key in self.reading_labels:
                                    label_widget, unit = self.reading_labels[label_key]
                                    current_value = value
                                    previous_value = self.last_sensor_values.get(label_key) # Use instance variable for last values
                                    
                                    if isinstance(current_value, (int, float)) and not (current_value == float('nan') or current_value == float('inf') or current_value == float('-inf')):
                                        label_widget.config(text=f"{current_value:.2f} {unit}")
                                        if previous_value is not None and isinstance(previous_value, (int, float)) and not (previous_value == float('nan') or previous_value == float('inf') or previous_value == float('-inf')):
                                            if current_value > previous_value:
                                                self.sound_manager.play_change_sound('up', self.play_change_sound.get()) # Corrected
                                            elif current_value < previous_value:
                                                self.sound_manager.play_change_sound('down', self.play_change_sound.get()) # Corrected
                                        self.last_sensor_values[label_key] = current_value
                                    else:
                                        label_widget.config(text=f"N/A {unit}")

                    self._update_plot()
                    self.sound_manager.play_alert_sound(self.play_alert_sound.get())

                    if self.loading_screen_active:
                        self._hide_loading_screen()

                # Process status messages
                elif message['type'] == 'status_message':
                    self._update_status_bar(message['message'], color=message['color'])

            except queue.Empty:
                break # No more messages in queue, exit loop

        # Changed to use lambda for robust self reference
        self.after_id = self.after(100, lambda: self._check_for_data())

    def _update_status_bar(self, message, color='info'):
        """Updates the status bar message and color, and logs to the text widget."""
        self.status_bar.config(text=message, bootstyle=color)
        self.status_text.config(state=tk.NORMAL)
        self.status_text.insert(tk.END, f"{datetime.datetime.now().strftime('%H:%M:%S')} - {message}\n")
        self.status_text.see(tk.END)
        self.status_text.config(state=tk.DISABLED)

    def _browse_log_path(self):
        folder_selected = filedialog.askdirectory(initialdir=self.log_path.get())
        if folder_selected:
            self.log_path.set(folder_selected)

    def _browse_archive_path(self):
        folder_selected = filedialog.askdirectory(initialdir=self.archive_path.get())
        if folder_selected:
            self.archive_path.set(folder_selected)

    def _apply_log_settings(self):
        """Sends updated logging configuration to the sensor thread (which passes to DataLogger)."""
        new_log_path_str = self.log_path.get()
        new_archive_path_str = self.archive_path.get()
        archive_enabled_bool = self.archive_enabled.get()

        current_sensor_log_settings = {sensor: var.get() for sensor, var in self.log_settings.items()}

        if self.sensor_thread and self.sensor_thread.is_alive():
            try:
                self.sensor_thread.control_queue.put({
                    'type': 'update_log_settings',
                    'log_path_str': new_log_path_str,
                    'archive_path_str': new_archive_path_str,
                    'archive_enabled_bool': archive_enabled_bool,
                    'new_sensor_log_settings': current_sensor_log_settings
                })
                self._update_status_bar("Log settings sent to sensor thread.", color='info')
            except Exception as e:
                self._update_status_bar(f"Error sending log settings: {e}", color='red')
        else:
            self._update_status_bar("Sensor thread not running. Cannot apply settings.", color='orange')

    def _apply_plot_settings(self):
        """
        Applies the selected plot time range and updates the sensor read interval.
        Sends a control message to the SensorReader thread for the interval change.
        """
        new_interval_str = self.plot_update_interval.get()
        try:
            new_interval = int(new_interval_str)
            if new_interval <= 0:
                raise ValueError("Read interval must be a positive integer.")

            if self.sensor_thread and self.sensor_thread.is_alive():
                self.sensor_thread.control_queue.put({
                    'type': 'update_read_interval',
                    'interval': new_interval
                })
                self._update_status_bar(f"Plot settings applied. Sensor read interval set to {new_interval}s.", color='info')
            else:
                self._update_status_bar("Sensor thread not running. Cannot apply interval.", color='orange')
            
            self._update_plot()

        except ValueError:
            self._update_status_bar("Invalid interval. Please enter a positive integer.", color='danger')
            messagebox.showerror("Invalid Input", "Please enter a valid positive integer for the Read Interval.")
        except Exception as e:
            self._update_status_bar(f"Error applying plot settings: {e}", color='red')
            messagebox.showerror("Error", f"An error occurred while applying plot settings: {e}")

    def _trigger_archive_now(self):
        """Forces an immediate log archive by sending a command to the sensor thread."""
        if self.sensor_thread and self.sensor_thread.is_alive():
            try:
                self.sensor_thread.control_queue.put({'type': 'archive_now'})
                self._update_status_bar("Manual log archive initiated.", color='blue')
            except Exception as e:
                self._update_status_bar(f"Error initiating manual archive: {e}", color='red')
        else:
            self._update_status_bar("Sensor thread not running. Cannot archive logs.", color='orange')

    def _open_folder(self, path):
        """Opens a given folder in the native file explorer."""
        try:
            path = os.path.abspath(path)
            if not os.path.exists(path):
                os.makedirs(path, exist_ok=True)
            
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
            self._update_status_bar(f"Opened folder: {path}", color='info')
        except Exception as e:
            self._update_status_bar(f"Failed to open folder {path}: {e}", color='red')
            messagebox.showerror("Error", f"Could not open folder:\n{e}")

    def _open_log_folder(self):
        self._open_folder(self.log_path.get())

    def _open_archive_folder(self):
        self._open_folder(self.archive_path.get())

    def _on_closing(self):
        """Handles graceful shutdown when the window is closed."""
        if messagebox.askokcancel("Quit", "Do you want to quit?"):
            self._update_status_bar("Shutting down sensor thread and archiving logs...", color='blue')
            print("GUI: Initiating shutdown sequence.")

            self.stop_event.set()
            print("GUI: stop_event set.")

            if self.sensor_thread and self.sensor_thread.is_alive():
                try:
                    # Send a final archive command to ensure logs are archived on shutdown
                    self.sensor_thread.control_queue.put({'type': 'archive_now'})
                    print("GUI: Sent 'archive_now' command to sensor thread.")
                except Exception as e:
                    print(f"GUI: Error sending final archive command on shutdown: {e}")
                    self._update_status_bar(f"Error during shutdown archiving request: {e}", color='red')

                print("GUI: Waiting for sensor thread to join (max 60 seconds).")
                self.sensor_thread.join(timeout=60)

                if self.sensor_thread.is_alive():
                    print("GUI: Warning: Sensor thread might still be running.")
                    self._update_status_bar("Warning: Sensor thread might still be running.", color='orange')
                else:
                    print("GUI: Sensor thread successfully joined.")
            else:
                print("GUI: Sensor thread was not running or already stopped.")
                self._update_status_bar("Sensor thread already stopped.", color='gray')
            
            if self.after_id:
                self.after_cancel(self.after_id)
                self.after_id = None
                print("GUI: Cancelled _check_for_data.")
            
            # Quit pygame mixer if it was initialized
            self.sound_manager.quit_mixer()

            print("GUI: Destroying Tkinter window.")
            self.destroy()
            print("GUI: Tkinter window destroyed. Exiting application.")
            sys.exit(0)
