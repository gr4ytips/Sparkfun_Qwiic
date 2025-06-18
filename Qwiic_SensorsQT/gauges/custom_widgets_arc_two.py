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
        self.setFixedSize(self.gauge_size + 20, self.gauge_size + 50) 

        self.layout = QVBoxLayout(self)
        self.layout.setAlignment(Qt.AlignCenter)
        self.setContentsMargins(0, 0, 0, 0) # Remove extra margins

        self.title_label = QLabel(label_text, self)
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setFont(QFont("Arial", 10))
        # Colors will be set by _update_gauge_colors in MainWindow
        self.layout.addWidget(self.title_label, alignment=Qt.AlignCenter)

        self.value_label = QLabel("N/A", self)
        self.value_label.setAlignment(Qt.AlignCenter)
        self.value_label.setFont(QFont("Arial", 14, QFont.Bold))
        # Colors will be set by _update_gauge_colors in MainWindow
        self.layout.addWidget(self.value_label, alignment=Qt.AlignCenter)
        # The actual gauge drawing happens in paintEvent, which is triggered by update()


        # Initialize colors with defaults (these will be overwritten by set_colors)
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

        # Disable auto-filling background so parent background can show through
        self.setAutoFillBackground(False)
        self.setAttribute(Qt.WA_StyledBackground, True) # Allow stylesheet to control background

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
        self._gauge_inner_circle_color = QColor(gauge_inner_circle) 

        if self.debug_logger:
            self.debug_logger.debug(f"Gauge '{self.label_text}': set_colors called. Inner circle color set to: {self._gauge_inner_circle_color.name()}, Needle color: {self._needle_color.name()}")
        
        # Update the QLabel stylesheets directly
        self.title_label.setStyleSheet(f"color: {self._label_color.name()};")
        self.value_label.setStyleSheet(f"color: {self._value_color.name()};")
        
        self.update() # Request a repaint to apply new colors


    def update_value(self, value):
        """Updates the gauge's displayed value and triggers a repaint."""
        # Ensure value is a float, especially important for NaN/Inf checks
        try:
            old_value = self.current_value # Store old value for change detection
            self.current_value = float(value)
        except (ValueError, TypeError):
            old_value = self.current_value # Store old value for change detection
            self.current_value = float('nan') # Handle cases where value might not be directly convertible to float

        if isinstance(self.current_value, (int, float)) and not (math.isnan(self.current_value) or math.isinf(self.current_value)):
            # Determine appropriate precision for display based on unit
            if self.unit == '%RH':
                display_text = f"{self.current_value:.1f}{self.unit}"
            elif self.unit in ['hPa', 'lux', 'm']:
                display_text = f"{self.current_value:.2f}{self.unit}"
            elif self.unit in ['°C', '°F']:
                display_text = f"{self.current_value:.1f}{self.unit}"
            else: # Default for VOC index, etc.
                display_text = f"{int(self.current_value)}{self.unit}"
            
            self.value_label.setText(display_text)
        else:
            self.value_label.setText("N/A")
        
        # Only request repaint if the value has significantly changed to avoid excessive repaints
        # Or if the old value was NaN/infinity and now it's a number, or vice versa
        if math.isnan(old_value) != math.isnan(self.current_value) or \
           math.isinf(old_value) != math.isinf(self.current_value) or \
           (not (math.isnan(self.current_value) or math.isinf(self.current_value)) and \
           abs(self.current_value - old_value) > 0.01): # Threshold for repaint
            self.update() # Trigger repaint of the gauge to update the needle/arc

    def paintEvent(self, event):
        """Custom painting for the semi-circular gauge."""
        if self.debug_logger:
            self.debug_logger.debug(f"Gauge '{self.label_text}': paintEvent triggered. Current value: {self.current_value}")

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect()
        center_x = rect.center().x()
        center_y = rect.height() * 0.7 # Adjust center Y for semi-circle
        radius = min(rect.width(), rect.height() * 2) * 0.4 # Make radius relative to widget size

        # Ensure radius is not too small
        if radius < 10:
            return

        # Define the bounding rectangle for the arc
        arc_rect = QRectF(center_x - radius, center_y - radius, radius * 2, radius * 2)

        # Draw the background arc
        painter.setBrush(QBrush(self._arc_background_color)) # Use theme-aware background color
        painter.setPen(QPen(self._outline_color, 2)) # Use theme-aware outline color
        painter.drawPie(arc_rect, 0 * 16, 180 * 16) # Full semi-circle for background

        # Draw value segments (e.g., green, yellow, red)
        # Assuming min_val and max_val define the full range (180 degrees)
        # You can divide this into segments. Example: Green (0-33%), Yellow (33-66%), Red (66-100%)
        total_range = self.max_val - self.min_val
        
        # Only draw segments if total_range is valid to avoid division by zero or nonsensical values
        if total_range > 0:
            # Low segment (e.g., first 33% of the range)
            painter.setBrush(QBrush(self._fill_low_color)) # Use theme-aware low fill color
            painter.setPen(Qt.NoPen)
            # This segment goes from 180 (left) to 180 - (0.33 * 180) degrees (sweeping clockwise)
            painter.drawPie(arc_rect, int(180 * 16), int(-0.33 * 180 * 16))

            # Medium segment (e.g., 33%-66% of the range)
            painter.setBrush(QBrush(self._fill_medium_color)) # Use theme-aware medium fill color
            # This segment starts where the low segment ends, and sweeps for another 33%
            painter.drawPie(arc_rect, int((180 - (0.33 * 180)) * 16), int(-0.33 * 180 * 16))

            # High segment (e.g., 66%-100% of the range)
            painter.setBrush(QBrush(self._fill_high_color)) # Use theme-aware high fill color
            # This segment starts where the medium segment ends, and sweeps for the remaining 34%
            painter.drawPie(arc_rect, int((180 - (0.66 * 180)) * 16), int(-0.34 * 180 * 16))
            

        # Draw the needle if value is not NaN/Inf
        if not (math.isnan(self.current_value) or math.isinf(self.current_value)):
            # Clamp value to min/max range
            clamped_value = max(self.min_val, min(self.max_val, self.current_value))
            
            # Calculate percentage of value within the range
            percentage = (clamped_value - self.min_val) / (self.max_val - self.min_val) if (self.max_val - self.min_val) != 0 else 0

            # 0% (min_val) corresponds to 180 degrees (left)
            # 100% (max_val) corresponds to 0 degrees (right)
            needle_angle_deg = 180 - (percentage * 180) # Angle from 0 (right) to 180 (left)
            
            needle_length = radius * 0.7 # Needle is a bit shorter than the radius
            
            # Save painter state to restore after translation and rotation
            painter.save() 
            painter.translate(center_x, center_y) # Translate origin to the center of the arc
            
            # Rotate by the calculated angle. 0 degrees is to the right (positive x-axis).
            # The line is drawn from (0,0) outwards along the positive x-axis initially.
            # So, rotate by `needle_angle_deg` directly.
            painter.rotate(needle_angle_deg) 
            
            painter.setPen(QPen(self._needle_color, 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)) # Use theme-aware needle color
            painter.drawLine(0, 0, int(needle_length), 0) # Draw horizontal needle starting from translated origin
            
            # Draw center pivot point
            painter.setBrush(QBrush(self._needle_color)) # Use theme's needle color for pivot (often same as needle)
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPointF(0,0), 5, 5) # Draw a small circle at the pivot
            
            painter.restore() # Restore painter state (undoes translate and rotate)
            if self.debug_logger:
                self.debug_logger.debug(f"Gauge '{self.label_text}': Needle drawn at {needle_angle_deg} degrees for value {self.current_value}.")

        else:
            # If value is NaN, draw the "N/A" state
            # Draw the full background arc using the N/A color for fill and a thicker outline
            painter.setBrush(QBrush(self._na_color)) # Use theme-aware N/A color
            painter.setPen(QPen(self._outline_color, 4)) # Use theme-aware outline color
            painter.drawPie(arc_rect, 0 * 16, 180 * 16) # Draw the full semi-circle

            # Draw the inner circle for N/A state using theme color
            if self.debug_logger:
                self.debug_logger.debug(f"Gauge '{self.label_text}': Drawing N/A inner circle with color: {self._gauge_inner_circle_color.name()}")
            painter.setBrush(QBrush(self._gauge_inner_circle_color))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QRectF(center_x - radius * 0.7, center_y - radius * 0.7,
                                       radius * 1.4, radius * 1.4))

            # Optionally, draw "N/A" text
            painter.setPen(QPen(self._value_color, 2)) # N/A text now uses theme-aware value color
            font = QFont("Arial", 16, QFont.Bold)
            painter.setFont(font)
            # Position the "N/A" text within the gauge's bounds
            text_rect = QRectF(center_x - radius * 0.7, center_y - radius * 0.7, radius * 1.4, radius * 1.4) # Approximate center area
            painter.drawText(text_rect, Qt.AlignCenter, "N/A")
            if self.debug_logger:
                self.debug_logger.debug(f"Gauge '{self.label_text}': N/A state drawn.")

        # Manually position the value_label in the center of the arc area
        # This label is a QLabel, overlaid on the painting.
        value_label_height = self.value_label.fontMetrics().height()
        # Adjust value_label_width to prevent text truncation
        value_label_width = self.width() - 20 # Give some padding

        # Position the value_label within the arc's empty space, slightly above center_y
        value_label_y_pos = int(center_y - value_label_height / 2) - int(radius * 0.2) # Adjusted based on radius
        value_label_x_pos = int((self.width() - value_label_width) / 2) # Center horizontally
        
        self.value_label.setGeometry(
            value_label_x_pos, value_label_y_pos, 
            value_label_width, value_label_height
        )
        self.value_label.show() # Ensure it's visible, as it might have been hidden for N/A state in CustomWidget


