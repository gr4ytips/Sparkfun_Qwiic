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
        self.layout = QVBoxLayout(self)
        self.layout.setAlignment(Qt.AlignCenter)
        
        # Label for the gauge's title (e.g., "BME280 Temperature")
        self.title_label = QLabel(self.label_text, self)
        self.title_label.setAlignment(Qt.AlignCenter)
        font = QFont("Arial", 10, QFont.Bold)
        self.title_label.setFont(font)
        # Initial stylesheet, will be updated by set_colors
        self.title_label.setStyleSheet("color: black;") 
        self.layout.addWidget(self.title_label)

        # Label for displaying the current value
        self.value_label = QLabel("N/A", self)
        self.value_label.setAlignment(Qt.AlignCenter)
        value_font = QFont("Arial", 14, QFont.Bold)
        self.value_label.setFont(value_font)
        # Initial stylesheet, will be updated by set_colors
        self.value_label.setStyleSheet("color: black;")
        # Remove from layout, as its position is now manually managed in paintEvent
        # self.layout.addWidget(self.value_label) 

        # Color properties, initialized with defaults, will be updated by set_colors method
        # Renamed for consistency with CustomWidget's theme property naming
        self._arc_background_color = QColor("#E0E0E0") # Light gray for the un-filled part of the arc
        self._label_color = QColor("#333333")     # Color for the gauge title/label
        self._value_color = QColor("#333333")     # Color for the numerical value
        self._outline_color = QColor("#B8B8B8")       # Medium gray for borders and needle pivot
        self._fill_low_color = QColor("#2ECC71")           # Green for low range values
        self._fill_medium_color = QColor("#F1C40F")        # Yellow for medium range values
        self._fill_high_color = QColor("#E74C3C")          # Red for high range values
        self._na_color = QColor("#95A5A6")            # Grey for N/A state
        self._needle_color = QColor("#000000") # Black default
        self._gauge_inner_circle_color = QColor("#FFFFFF") # Default inner circle color


    def set_colors(self, arc_background, label_color, value_color, outline_color,
                   fill_low, fill_medium, fill_high, na_color, needle_color, gauge_inner_circle):
        """
        Sets the color scheme for the gauge. This method is called from MainWindow
        when the theme or gauge style changes.
        """
        self._arc_background_color = QColor(arc_background)
        self._label_color = QColor(label_color) 
        self._value_color = QColor(value_color) 
        self._outline_color = QColor(outline_color)
        self._fill_low_color = QColor(fill_low)
        self._fill_medium_color = QColor(fill_medium)
        self._fill_high_color = QColor(fill_high)
        self._na_color = QColor(na_color)
        self._needle_color = QColor(needle_color) # New: Assign needle color
        self._gauge_inner_circle_color = QColor(gauge_inner_circle) # New: Assign inner circle color

        if self.debug_logger:
            self.debug_logger.debug(f"Gauge '{self.label_text}': set_colors called. Inner circle color set to: {self._gauge_inner_circle_color.name()}, Needle color: {self._needle_color.name()}")
        
        # Also update the QLabel stylesheets directly
        self.title_label.setStyleSheet(f"color: {self._label_color.name()};") # Use new label color
        self.value_label.setStyleSheet(f"color: {self._value_color.name()};") # Use new value color
        
        self.update() # Request a repaint to apply new colors


    def update_value(self, value):
        """Updates the current value displayed by the gauge."""
        old_value = self.current_value
        self.current_value = float(value) # Ensure value is float

        # Update the value label text immediately
        if math.isnan(self.current_value) or math.isinf(self.current_value):
            self.value_label.setText("N/A")
        elif self.unit == '%RH': # Format humidity with one decimal place
            self.value_label.setText(f"{self.current_value:.1f}{self.unit}")
        elif self.unit == 'hPa' or self.unit == 'lux' or self.unit == 'm': # Format with two decimal places for pressure, altitude, light
             self.value_label.setText(f"{self.current_value:.2f}{self.unit}")
        elif self.unit == '°C' or self.unit == '°F': # Format with one decimal place for temperatures
            self.value_label.setText(f"{self.current_value:.1f}{self.unit}")
        else: # Default formatting for others (e.g., VOC index)
            self.value_label.setText(f"{self.current_value:.0f}{self.unit}") # Integer for VOC index
        
        # Only request repaint if the value has significantly changed to avoid excessive repaints
        # Or if the old value was NaN/infinity and now it's a number, or vice versa
        if math.isnan(old_value) != math.isnan(self.current_value) or \
           math.isinf(old_value) != math.isinf(self.current_value) or \
           (not (math.isnan(self.current_value) or math.isinf(self.current_value)) and \
           abs(self.current_value - old_value) > 0.01): # Threshold for repaint
            self.update()


    def paintEvent(self, event):
        """
        Custom paint event for drawing the gauge.
        This draws a semi-circular arc and a needle indicating the current value.
        """
        if self.debug_logger:
            self.debug_logger.debug(f"Gauge '{self.label_text}': paintEvent triggered. Current value: {self.current_value}")

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        width = self.width()
        height = self.height()

        # Position the title_label above the gauge first
        title_label_height = self.title_label.fontMetrics().height()
        title_label_x_pos = 0
        title_label_y_pos = 5 # Small padding from the top of the widget
        self.title_label.setGeometry(
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
        painter.setBrush(QBrush(self._arc_background_color))
        painter.setPen(QPen(self._outline_color, 2))
        painter.drawPie(arc_rect, 0 * 16, 180 * 16) # Full semi-circle from 0 to 180 degrees


        if not (math.isnan(self.current_value) or math.isinf(self.current_value)):
            # Calculate the fill percentage
            range_val = self.max_val - self.min_val
            if range_val == 0: # Avoid division by zero
                normalized_value = 0
            else:
                normalized_value = (self.current_value - self.min_val) / range_val
            normalized_value = max(0.0, min(1.0, normalized_value)) # Clamp between 0 and 1

            # Determine color based on value range (for fill)
            fill_color = self._fill_low_color
            if normalized_value > 0.75: # Example thresholds, adjust as needed
                fill_color = self._fill_high_color
            elif normalized_value > 0.4:
                fill_color = self._fill_medium_color

            # Draw the filled arc
            # Qt angles are counter-clockwise for positive values, 0 is at 3 o'clock.
            # Our gauge goes from 0 (right) to 180 (left). So 0 is our 0, 180 is our 180.
            # The start angle for the fill should be 180 degrees (left side), sweeping
            # negatively (clockwise) by the span angle.
            span_angle = 180 * normalized_value 
            painter.setBrush(QBrush(fill_color))
            painter.setPen(QPen(self._outline_color, 8)) # Use outline color for the arc's outer edge and match thickness
            painter.drawArc(arc_rect, int(180 * 16), int(-span_angle * 16))


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

            # Calculate needle angle: 0 degrees is right, 180 degrees is left.
            # A value at min_val should be at 0 degrees, max_val at 180 degrees.
            needle_angle_deg = 180 * normalized_value
            
            # Rotate such that 0 degrees is horizontal to the right, and 180 is horizontal to the left
            # PyQt's coordinate system has positive Y downwards. Rotation is clockwise.
            # So, to make 0% point right (0 deg) and 100% point left (180 deg),
            # we start with a needle pointing right (0 degrees relative to rotated axis)
            # and rotate it clockwise by 'needle_angle_deg'.
            painter.rotate(needle_angle_deg) 

            needle_length = outer_radius - 15 # Shorter than outer radius
            painter.setPen(QPen(self._needle_color, 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)) # Use themed needle color
            painter.drawLine(0, 0, int(needle_length), 0) # Draw horizontal needle starting from translated origin
            
            # Draw center pivot point
            painter.setBrush(QBrush(self._outline_color)) # Use theme's outline color for pivot
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
            # If value is NaN, draw the "N/A" state
            # Draw the full background arc using the N/A color for fill and a thicker outline
            painter.setBrush(QBrush(self._na_color))
            painter.setPen(QPen(self._outline_color, 4))
            painter.drawPie(arc_rect, 0 * 16, 180 * 16) # Draw the full semi-circle

            # Explicitly draw the inner circle for the N/A state
            if self.debug_logger:
                self.debug_logger.debug(f"Gauge '{self.label_text}': Drawing N/A inner circle with color: {self._gauge_inner_circle_color.name()}")
            painter.setBrush(QBrush(self._gauge_inner_circle_color))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QRectF(center_x - inner_radius, center_y - inner_radius,
                                       inner_radius * 2, inner_radius * 2))

            # Hide the value_label QLabel as "N/A" is drawn directly by the painter
            self.value_label.hide()

            # Draw "N/A" directly in the center of the inner circle
            painter.setPen(QPen(self._value_color)) # N/A text now uses gauge_value_color
            font = QFont("Arial", 16, QFont.Bold) # Use consistent font for N/A
            painter.setFont(font)
            text_rect = QRectF(center_x - inner_radius, center_y - inner_radius,
                               inner_radius * 2, inner_radius * 2) 
            painter.drawText(text_rect, Qt.AlignCenter, "N/A")
            if self.debug_logger:
                self.debug_logger.debug(f"Gauge '{self.label_text}': Displaying N/A for value {self.current_value}.")

