from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QSizePolicy, QApplication
from PyQt5.QtGui import QFont, QPainter, QBrush, QColor, QPen, QPalette
from PyQt5.QtCore import Qt, QRectF, QPointF
import math # Import math for isnan, isinf

# --- Custom Gauge Widget (PyQt5) ---
class GaugeWidget(QWidget):
    def __init__(self, master, label_text, min_val, max_val, unit, gauge_size=150, debug_logger=None, **kwargs):
        super().__init__(master, **kwargs)
        self.label_text = label_text
        self.min_val = float(min_val)
        self.max_val = float(max_val)
        self.unit = unit
        self.gauge_size = gauge_size
        self.current_value = float('nan') # Initialize with NaN to indicate no data yet
        self.debug_logger = debug_logger # Store debug logger instance

        if self.debug_logger:
            self.debug_logger.debug(f"GaugeWidget initialized for '{label_text}' with size {gauge_size}.")


        # Set fixed size for the gauge widget
        # Adjusted height to better accommodate the gauge and labels
        # Reduced height because the value label will now be inside the gauge
        self.setFixedSize(self.gauge_size + 20, self.gauge_size + 50) 

        # Main layout for the widget
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(5, 5, 5, 5) # Reduced margins

        # Top label for the sensor metric name
        self.label = QLabel(self.label_text)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setFont(QFont("Arial", 10, QFont.Bold))
        # Label color will be updated by set_colors
        self.main_layout.addWidget(self.label, alignment=Qt.AlignTop)

        # Value label - now positioned directly on the gauge in paintEvent
        self.value_label = QLabel("N/A")
        self.value_label.setAlignment(Qt.AlignCenter)
        self.value_label.setFont(QFont("Arial", 14, QFont.Bold)) # Larger font for value
        # Value label color will be updated by set_colors
        # Add the value_label to the layout, but let paintEvent handle its geometry
        # Adding it to the layout prevents it from being garbage collected prematurely
        self.main_layout.addWidget(self.value_label) 
        self.value_label.hide() # Initially hide it, paintEvent will show/position

        # Initialize colors with defaults (these will be overwritten by set_colors)
        self._arc_background_color = QColor("#E0E0E0") # Light gray for the un-filled part of the arc
        self._label_color = QColor("#333333")     # Color for the gauge title/label
        self._value_color = QColor("#333333")     # Color for the numerical value
        self._outline_color = QColor("#B8B8B8")       # Medium gray for borders and needle pivot
        self._fill_low_color = QColor("#2ECC71")           # Green for low range values
        self._fill_medium_color = QColor("#F1C40F")        # Yellow for medium range values
        self._fill_high_color = QColor("#E74C3C")          # Red for high range values
        self._na_color = QColor("#95A5A6")            # Grey for N/A state
        self._needle_color = QColor("#000000") # Black default (was already _needle_color in previous version)
        self._gauge_inner_circle_color = QColor("#FFFFFF") # Default inner circle color


        # Setup palette for text labels (can be overridden by stylesheet)
        palette = self.palette()
        palette.setColor(QPalette.WindowText, self._label_color)
        self.setPalette(palette)

    def set_colors(self, arc_background, label_color, value_color, outline_color,
                   fill_low, fill_medium, fill_high, na_color, needle_color, gauge_inner_circle):
        """
        Sets the colors for various parts of the gauge.
        This method is called by MainWindow when the theme changes.
        """
        self._arc_background_color = QColor(arc_background)
        self._label_color = QColor(label_color)
        self._value_color = QColor(value_color)
        self._outline_color = QColor(outline_color)
        self._fill_low_color = QColor(fill_low)
        self._fill_medium_color = QColor(fill_medium)
        self._fill_high_color = QColor(fill_high)
        self._na_color = QColor(na_color)
        self._needle_color = QColor(needle_color)
        self._gauge_inner_circle_color = QColor(gauge_inner_circle) # Store the inner circle color

        if self.debug_logger:
            self.debug_logger.debug(f"Gauge '{self.label_text}': set_colors called. Inner circle color set to: {gauge_inner_circle}")

        # Update label colors immediately
        palette = self.palette()
        palette.setColor(QPalette.WindowText, self._label_color)
        self.setPalette(palette)
        self.label.setStyleSheet(f"QLabel {{ color: {label_color}; }}")
        self.value_label.setStyleSheet(f"QLabel {{ color: {value_color}; }}")

        self.update() # Trigger a repaint

    def update_value(self, value):
        """Updates the current value displayed on the gauge."""
        old_value = self.current_value
        self.current_value = float(value)

        # Update the text of the value label, handling NaN
        if math.isnan(self.current_value):
            self.value_label.setText("N/A")
        elif self.unit == '%RH': # Format humidity with one decimal place
            self.value_label.setText(f"{self.current_value:.1f}{self.unit}")
        elif self.unit == 'hPa' or self.unit == 'lux' or self.unit == 'm': # Format with two decimal places for pressure, altitude, light
             self.value_label.setText(f"{self.current_value:.2f}{self.unit}")
        elif self.unit == '°C' or self.unit == '°F': # Format with one decimal place for temperatures
            self.value_label.setText(f"{self.current_value:.1f}{self.unit}")
        else: # Default formatting for others (e.g., VOC index)
            self.value_label.setText(f"{self.current_value:.0f}{self.unit}") # Integer for VOC index


        if self.debug_logger:
            # self.debug_logger.debug(f"Gauge '{self.label_text}': Value updated to {self.current_value}. Old: {old_value}") # Too verbose
            pass

        self.update() # Trigger repaint to draw new needle position

    def paintEvent(self, event):
        """Custom painting for the gauge widget."""
        if self.debug_logger:
            self.debug_logger.debug(f"Gauge '{self.label_text}': paintEvent triggered. Current value: {self.current_value}")

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        width = self.width()
        height = self.height()

        # Position the title_label above the gauge first
        title_label_height = self.label.fontMetrics().height() # Use self.label not self.title_label
        title_label_x_pos = 0
        title_label_y_pos = 5 # Small padding from the top of the widget
        self.label.setGeometry( # Use self.label not self.title_label
            title_label_x_pos, title_label_y_pos,
            width, title_label_height
        )

        # Calculate remaining height after placing title
        remaining_height = height - title_label_height - 10 # 10 for bottom padding below gauge

        # Calculate outer_radius based on remaining height and width
        outer_radius = min((width - 20) // 2, remaining_height // 2 - 10) # 20 for side padding, 10 for some buffer
        outer_radius = max(50, outer_radius) # Ensure minimum size for visibility

        inner_radius = outer_radius * 0.7 # Thickness of the arc

        center_x = width // 2
        # Center Y for the arc: below title, vertically centered in remaining space for gauge
        center_y = int(title_label_y_pos + title_label_height + outer_radius) 


        # Define the bounding rectangle for the outer arc
        # Qt's drawArc uses a bounding rectangle and angles in 1/16th of a degree
        arc_rect = QRectF(center_x - outer_radius, center_y - outer_radius, 
                          outer_radius * 2, outer_radius * 2)

        # Draw the background arc (the un-filled part)
        painter.setBrush(QBrush(self._arc_background_color)) # Use _arc_background_color
        painter.setPen(QPen(self._outline_color, 2))
        painter.drawPie(arc_rect, 45 * 16, 270 * 16) # Start at 45 deg, sweep 270 deg


        if not (math.isnan(self.current_value) or math.isinf(self.current_value)):
            # Calculate the fill percentage
            range_val = self.max_val - self.min_val
            if range_val == 0: # Avoid division by zero
                normalized_value = 0 # Define normalized_value here
            else:
                normalized_value = (self.current_value - self.min_val) / range_val
            normalized_value = max(0.0, min(1.0, normalized_value)) # Clamp between 0 and 1

            # Determine color based on value range (for fill)
            fill_color = self._fill_low_color # Use _fill_low_color
            if range_val > 0: # Avoid division by zero (already checked above, but good for clarity)
                # Define thresholds for color change (e.g., 33% and 66% of the range)
                low_threshold = self.min_val + range_val * 0.33
                high_threshold = self.min_val + range_val * 0.66

                if self.current_value >= high_threshold:
                    fill_color = self._fill_high_color # Use _fill_high_color
                elif self.current_value >= low_threshold:
                    fill_color = self._fill_medium_color # Use _fill_medium_color
                else:
                    fill_color = self._fill_low_color # Use _fill_low_color
            
            # Calculate sweep_angle_deg here, after normalized_value is defined
            sweep_angle_deg = normalized_value * 270 

            painter.setPen(QPen(fill_color, 8)) # Match background arc thickness
            painter.drawArc(QRectF(center_x - outer_radius, center_y - outer_radius,
                                   outer_radius * 2, outer_radius * 2),
                            int(45 * 16), int(sweep_angle_deg * 16))


            # Draw inner circle to create arc effect
            if self.debug_logger:
                self.debug_logger.debug(f"Gauge '{self.label_text}': Drawing inner circle with color: {self._gauge_inner_circle_color.name()}")
            painter.setBrush(QBrush(self._gauge_inner_circle_color)) 
            painter.setPen(Qt.NoPen) # No outline for this fill, as you wanted it only filled
            painter.drawEllipse(QRectF(center_x - inner_radius, center_y - inner_radius,
                                       inner_radius * 2, inner_radius * 2))

            # Draw the needle
            painter.save() # Save painter state
            painter.translate(center_x, center_y) # Move origin to center of gauge

            # Calculate needle angle
            # The angles for arc drawing (45 to 315) mean 0% is at 45 deg, 100% is at 315 deg
            # Total sweep is 270 degrees.
            # Convert normalized_value (0 to 1) to an angle from 45 to 315.
            needle_angle_deg = 45 + (normalized_value * 270)
            
            # Rotate such that 0 degrees points right, and 180 points left.
            # PyQt's coordinate system has positive Y downwards. Rotation is clockwise.
            # To get needle to point correctly, we adjust the rotation origin.
            # We want 0% to be at 45 degrees, 100% at 315 degrees (clockwise from 0 on x-axis)
            painter.rotate(needle_angle_deg - 90) # Adjust for standard 0-deg at right horizontal and Qt's rotation

            needle_length = inner_radius + ((outer_radius - inner_radius) / 2) # Needle reaches center of arc thickness
            
            # Use the themed needle color
            painter.setPen(QPen(self._needle_color, 3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.drawLine(0, 0, int(needle_length), 0) # Draw horizontal needle starting from translated origin
            
            # Draw center pivot point
            painter.setBrush(QBrush(self._needle_color)) # Use theme's needle color for pivot
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPointF(0,0), 5, 5) # Draw a small circle at the pivot
            
            painter.restore() # Restore painter state (undoes translate and rotate)
            if self.debug_logger:
                self.debug_logger.debug(f"Gauge '{self.label_text}': Needle drawn at {needle_angle_deg} degrees for value {self.current_value}.")

            # Position the value_label in the center of the inner circle
            value_label_width = self.value_label.fontMetrics().width(self.value_label.text())
            value_label_height = self.value_label.fontMetrics().height()

            text_x = int(center_x - value_label_width / 2)
            # Position vertically in the center of the inner circle
            text_y = int(center_y - value_label_height / 2) 

            self.value_label.setGeometry(text_x, text_y, value_label_width, value_label_height)
            self.value_label.show() # Ensure it's visible

        else:
            # When value is N/A, hide the needle and show N/A text directly
            # Draw the full background arc (the un-filled part) using N/A colors
            painter.setBrush(QBrush(self._na_color))
            painter.setPen(QPen(self._outline_color, 4)) # Thicker outline for N/A state
            painter.drawArc(QRectF(center_x - outer_radius, center_y - outer_radius,
                                   outer_radius * 2, outer_radius * 2),
                            45 * 16, 270 * 16) # Draw the full semi-circle (matching main arc)

            # Draw inner circle to create arc effect (even in N/A state)
            if self.debug_logger:
                self.debug_logger.debug(f"Gauge '{self.label_text}': Drawing N/A inner circle with color: {self._gauge_inner_circle_color.name()}")
            painter.setBrush(QBrush(self._gauge_inner_circle_color)) 
            painter.setPen(Qt.NoPen) # No outline for this fill, as you wanted it only filled
            painter.drawEllipse(QRectF(center_x - inner_radius, center_y - inner_radius,
                                       inner_radius * 2, inner_radius * 2))
            
            # Hide the value_label QLabel as "N/A" is drawn directly by the painter
            self.value_label.hide()

            # Draw "N/A" directly in the center of the inner circle
            text_rect = QRectF(center_x - inner_radius, center_y - inner_radius,
                               inner_radius * 2, inner_radius * 2) 
            painter.setPen(QPen(self._value_color)) # Use value_color for N/A text
            painter.setFont(self.value_label.font()) # Use the same font as value_label
            painter.drawText(text_rect, Qt.AlignCenter, "N/A")
            if self.debug_logger:
                self.debug_logger.debug(f"Gauge '{self.label_text}': Displaying N/A for value {self.current_value}.")

