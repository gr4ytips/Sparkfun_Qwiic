import tkinter as tk
from tkinter import ttk # ttk is used for styling, even if not directly in GaugeWidget's core drawing

# --- Custom Gauge Widget ---
class GaugeWidget(tk.Canvas):
    def __init__(self, master, label_text, min_val, max_val, unit, size=100, style_colors=None, font_family="Arial", **kwargs):
        super().__init__(master, width=size, height=size, highlightthickness=0, **kwargs)
        self.label_text = label_text
        self.min_val = min_val
        self.max_val = max_val
        self.unit = unit
        self.size = size
        # Provide a default style_colors object if none is passed, for standalone testing or flexibility
        self.style_colors = style_colors if style_colors else type('Colors', (object,), {'primary': 'blue', 'danger': 'red', 'success': 'green', 'dark': 'gray', 'light': 'white', 'secondary': 'lightgray', 'info': 'cyan', 'warning': 'yellow'})()
        self.font_family = font_family

        self.center_x = size / 2
        self.center_y = size * 0.7 
        self.radius = size * 0.4

        self.value_text_id = None
        self.gauge_arc_id = None

        self._draw_gauge()

    def _draw_gauge(self):
        """Draws the static elements of the gauge (background arc, min/max labels, main label)."""
        # Background arc
        self.create_arc(
            self.center_x - self.radius, self.center_y - self.radius,
            self.center_x + self.radius, self.center_y + self.radius,
            start=0, extent=180, style=tk.ARC, outline=self.style_colors.secondary, width=2
        )

        # Min value label
        self.create_text(
            self.center_x - self.radius - 5, self.center_y,
            text=str(self.min_val), anchor=tk.E, fill=self.style_colors.light,
            font=(self.font_family, 7)
        )
        # Max value label
        self.create_text(
            self.center_x + self.radius + 5, self.center_y,
            text=str(self.max_val), anchor=tk.W, fill=self.style_colors.light,
            font=(self.font_family, 7)
        )

        # Main gauge label (e.g., "Temp C:")
        self.create_text(
            self.center_x, self.center_y - self.radius * 0.8,
            text=self.label_text, anchor=tk.S, fill=self.style_colors.light,
            font=(self.font_family, 8, "bold")
        )

        # Placeholder for the dynamic value text
        self.value_text_id = self.create_text(
            self.center_x, self.center_y + self.radius * 0.3,
            text="N/A", anchor=tk.N, fill=self.style_colors.info,
            font=(self.font_family, 10, "bold")
        )

    def update_value(self, value):
        """
        Updates the gauge's dynamic elements (filled arc and value text) based on the new value.
        Handles NaN/Inf values gracefully.
        """
        if not isinstance(value, (int, float)) or value == float('nan') or value == float('inf') or value == float('-inf'):
            display_text = "N/A"
            fill_color = self.style_colors.secondary # Gray for N/A
            extent = 0 # No fill
        else:
            # Clamp value within min/max range
            clamped_value = max(self.min_val, min(self.max_val, value))
            
            range_span = self.max_val - self.min_val
            if range_span == 0: 
                percentage = 0
            else:
                percentage = (clamped_value - self.min_val) / range_span
            
            extent = percentage * 180 # Map 0-1 percentage to 0-180 degrees

            # Determine fill color based on percentage
            if percentage < 0.33:
                fill_color = self.style_colors.success # Green for low
            elif percentage < 0.66:
                fill_color = self.style_colors.warning # Yellow for medium
            else:
                fill_color = self.style_colors.danger # Red for high
            
            display_text = f"{value:.1f}{self.unit}" # Format value for display


        # Delete previous filled arc to redraw
        if self.gauge_arc_id:
            self.delete(self.gauge_arc_id)

        # Create new filled arc
        self.gauge_arc_id = self.create_arc(
            self.center_x - self.radius, self.center_y - self.radius,
            self.center_x + self.radius, self.center_y + self.radius,
            start=0, extent=extent, style=tk.ARC, outline="", width=10, 
            tags="gauge_fill", fill=fill_color 
        )
        # Ensure the fill arc is drawn above the background arc
        self.tag_raise("gauge_fill")

        # Update the value text
        self.itemconfig(self.value_text_id, text=display_text, fill=fill_color)
