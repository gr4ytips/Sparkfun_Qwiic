import json
import os

class SettingsManager:
    """
    Manages application settings, saving them to and loading them from a JSON file.
    """
    # Define a comprehensive map of available sensors and their metrics.
    # This map provides metadata for UI generation, plotting, and logging.
    # The keys for sensor and metric should match the keys used in the sensor_data dictionary
    # emitted by the SensorReaderThread.
    SENSOR_METRICS_MAP = {
        'bme280': {
            'temp_c': {'label': 'BME280 Temperature', 'unit': '°C', 'gauge_min': 0, 'gauge_max': 50},
            'temp_f': {'label': 'BME280 Temperature', 'unit': '°F', 'gauge_min': 32, 'gauge_max': 122},
            'humidity': {'label': 'BME280 Humidity', 'unit': '%RH', 'gauge_min': 0, 'gauge_max': 100},
            'pressure': {'label': 'BME280 Pressure', 'unit': 'hPa', 'gauge_min': 900, 'gauge_max': 1100},
            'altitude': {'label': 'BME280 Altitude', 'unit': 'm', 'gauge_min': -100, 'gauge_max': 1000},
            'dewpoint_c': {'label': 'BME280 Dew Point', 'unit': '°C', 'gauge_min': -10, 'gauge_max': 30},
            'dewpoint_f': {'label': 'BME280 Dew Point', 'unit': '°F', 'gauge_min': 14, 'gauge_max': 86},
        },
        'sgp40': {
            'voc_index': {'label': 'SGP40 VOC Index', 'unit': '', 'gauge_min': 0, 'gauge_max': 500},
        },
        'shtc3': {
            'temperature': {'label': 'SHTC3 Temperature', 'unit': '°C', 'gauge_min': 0, 'gauge_max': 50},
            'humidity': {'label': 'SHTC3 Humidity', 'unit': '%RH', 'gauge_min': 0, 'gauge_max': 100},
        },
        'proximity': {
            'proximity': {'label': 'Proximity Value', 'unit': '', 'gauge_min': 0, 'gauge_max': 255},
            'ambient_light': {'label': 'Ambient Light', 'unit': 'lux', 'gauge_min': 0, 'gauge_max': 1000},
            'white_light': {'label': 'White Light', 'unit': 'lux', 'gauge_min': 0, 'gauge_max': 1000},
        }
    }


    # Define a comprehensive set of appealing color themes.
    # Each theme includes colors for various UI elements and a recommended gauge style.
    THEMES = {
        "Default Light": {
            "native_style": "Fusion",
            "bg_color": "#F0F0F0", # Light gray background
            "text_color": "#333333", # Dark gray text
            "base_color": "#FFFFFF", # White for text edit backgrounds
            "alt_bg_color": "#E0E0E0", # Lighter gray for alternate backgrounds/group boxes
            "button_bg_color": "#007BFF", # Blue for buttons
            "button_text_color": "#FFFFFF", # White button text
            "highlight_color": "#0056B3", # Darker blue for highlight
            "highlighted_text_color": "#FFFFFF", # White for highlighted text
            "placeholder_text_color": "#AAAAAA", # Light gray placeholder
            "outline_color": "#B8B8B8", # Medium gray for borders/outlines
            "plot_bg_color": "#FFFFFF", # White plot background
            "plot_line_color_1": "#007BFF", # Blue for plot lines
            "plot_line_color_2": "#2ECC71", # Green for plot lines
            "plot_line_color_3": "#F1C40F", # Yellow for plot lines
            "plot_line_color_4": "#E74C3C", # Red for plot lines
            "plot_line_color_5": "#6F42C1", # Purple (New)
            "plot_line_color_6": "#20C997", # Teal (New)
            "plot_line_color_7": "#FD7E14", # Orange (New)
            "recommended_gauge_style": "Modern Blue Gauge" # Recommended gauge style
        },
        "Dark Mode": {
            "native_style": "Fusion",
            "bg_color": "#2B2B2B", # Dark charcoal background
            "text_color": "#E0E0E0", # Light gray text
            "base_color": "#3C3C3C", # Slightly lighter dark for text edit backgrounds
            "alt_bg_color": "#3A3A3A", # Slightly lighter dark gray for alternate backgrounds
            "button_bg_color": "#555555", # Medium gray for buttons
            "button_text_color": "#FFFFFF", # White button text
            "highlight_color": "#007ACC", # VS Code blue for highlight
            "highlighted_text_color": "#FFFFFF",
            "placeholder_text_color": "#808080", # Gray placeholder
            "outline_color": "#505050", # Dark gray for borders
            "plot_bg_color": "#3A3A3A", # Dark plot background
            "plot_line_color_1": "#4CAF50", # Green for plot lines
            "plot_line_color_2": "#2196F3", # Blue for plot lines
            "plot_line_color_3": "#FFC107", # Amber for plot lines
            "plot_line_color_4": "#F44336", # Red for plot lines
            "plot_line_color_5": "#BA55D3", # Medium Orchid (New)
            "plot_line_color_6": "#40E0D0", # Turquoise (New)
            "plot_line_color_7": "#FF8C00", # Dark Orange (New)
            "recommended_gauge_style": "Elegant Grey Gauge" # Recommended gauge style
        },
        "Blue Mode": { # Original Blue Mode from your 1theming_snippet.txt
            "native_style": "Fusion",
            "bg_color": "#1a2a40", # Dark blue-grey background
            "text_color": "#e0f2f7", # Very light blue-grey text for contrast
            "base_color": "#2b3e50", # Slightly lighter blue-grey for text edit backgrounds
            "alt_bg_color": "#3e5872", # Medium blue-grey for alternate backgrounds/group boxes
            "button_bg_color": "#4a86e8", # Medium blue for buttons
            "button_text_color": "#FFFFFF", # White button text
            "highlight_color": "#007ACC", # VS Code blue for highlight
            "highlighted_text_color": "#FFFFFF", # White for highlighted text
            "placeholder_text_color": "#9fb4c7", # Lighter blue-grey for placeholders
            "outline_color": "#6a829e", # Blue-grey for borders
            "plot_bg_color": "#1a2a40", # Dark blue-grey plot background (consistent with bg_color)
            "plot_line_color_1": "#4CAF50", # Green for plot lines
            "plot_line_color_2": "#2196F3", # Blue for plot lines
            "plot_line_color_3": "#FFC107", # Amber for plot lines
            "plot_line_color_4": "#F44336", # Red for plot lines
            "plot_line_color_5": "#BA55D3", # Medium Orchid (New)
            "plot_line_color_6": "#40E0D0", # Turquoise (New)
            "plot_line_color_7": "#FF8C00", # Dark Orange (New)
            "recommended_gauge_style": "Modern Blue Gauge" # Recommended gauge style
        },
        "High Contrast": {
            "native_style": "Fusion",
            "bg_color": "#000000", # Pure black background for maximum contrast
            "text_color": "#FFFFFF", # Pure white text
            "base_color": "#1A1A1A", # Slightly lighter black for input fields, etc.
            "alt_bg_color": "#2C2C2C", # Dark grey for alternate backgrounds/group boxes
            "button_bg_color": "#00FFFF", # Vibrant Cyan for buttons
            "button_text_color": "#000000", # Black button text (for contrast on bright button)
            "highlight_color": "#FF00FF", # Vibrant Magenta for highlights
            "highlighted_text_color": "#000000", # Black for text on highlight
            "placeholder_text_color": "#AAAAAA", # Light grey for placeholders
            "outline_color": "#666666", # Medium grey for borders
            "plot_bg_color": "#121212", # Very dark grey for plot backgrounds
            "plot_line_color_1": "#FF0000", # Bright Red
            "plot_line_color_2": "#00FF00", # Bright Green
            "plot_line_color_3": "#0000FF", # Bright Blue
            "plot_line_color_4": "#FFFF00", # Yellow
            "plot_line_color_5": "#FF8C00", # Dark Orange
            "plot_line_color_6": "#EE82EE", # Violet
            "plot_line_color_7": "#7CFC00", # Lawn Green
            "recommended_gauge_style": "High Contrast Gauge" # Recommended gauge style
        },
        "Ocean Blue": { # Original Ocean Blue from your 1theming_snippet.txt
            "native_style": "Fusion",
            "bg_color": "#ADD8E6", # Light Blue
            "text_color": "#1F456E", # Dark Blue text
            "base_color": "#E0FFFF", # Light Cyan
            "alt_bg_color": "#87CEEB", # Sky Blue
            "button_bg_color": "#4682B4", # Steel Blue
            "button_text_color": "#FFFFFF",
            "highlight_color": "#104E8B", # Darker Steel Blue
            "highlighted_text_color": "#FFFFFF",
            "placeholder_text_color": "#6A8FA8",
            "outline_color": "#5F9EA0", # Cadet Blue
            "plot_bg_color": "#E0FFFF", # Light Cyan plot background
            "plot_line_color_1": "#1E90FF", # Dodger Blue
            "plot_line_color_2": "#3CB371", # Medium Sea Green
            "plot_line_color_3": "#FFD700", # Gold
            "plot_line_color_4": "#CD5C5C", # Indian Red
            "plot_line_color_5": "#4169E1", # Royal Blue (New)
            "plot_line_color_6": "#00CED1", # Dark Turquoise (New)
            "plot_line_color_7": "#FF69B4", # Hot Pink (New)
            "recommended_gauge_style": "Modern Blue Gauge" # Recommended gauge style
        },
        "Forest Green": { # Original Forest Green from your 1theming_snippet.txt
            "native_style": "Fusion",
            "bg_color": "#D4EDDA", # Light mint green
            "text_color": "#285F3B", # Dark green text
            "base_color": "#F0FFF0", # Honeydew
            "alt_bg_color": "#A2D9B3", # Medium green
            "button_bg_color": "#4CAF50", # Green
            "button_text_color": "#FFFFFF",
            "highlight_color": "#388E3C", # Darker green
            "highlighted_text_color": "#FFFFFF",
            "placeholder_text_color": "#79B28D",
            "outline_color": "#6B8E23", # Olive Drab
            "plot_bg_color": "#F0FFF0", # Honeydew plot background
            "plot_line_color_1": "#28A745", # Green
            "plot_line_color_2": "#1E8449", # Darker Green
            "plot_line_color_3": "#FFC300", # Gold
            "plot_line_color_4": "#D35400", # Pumpkin
            "plot_line_color_5": "#8BC34A", # Light Green (New)
            "plot_line_color_6": "#7CB342", # Light Green Shade (New)
            "plot_line_color_7": "#FFEB3B", # Yellow (New)
            "recommended_gauge_style": "Forest Green Gauge" # Recommended gauge style
        },
        "Warm Sunset": {
            "native_style": "Fusion",
            "bg_color": "#FFF3E0", # Light Peach
            "text_color": "#5D4037", # Brown text
            "base_color": "#FFFAF0", # Floral White
            "alt_bg_color": "#FFE0B2", # Light Orange
            "button_bg_color": "#FF9800", # Orange
            "button_text_color": "#FFFFFF",
            "highlight_color": "#F57C00", # Darker Orange
            "highlighted_text_color": "#FFFFFF",
            "placeholder_text_color": "#D7B08C",
            "outline_color": "#C28B5E",
            "plot_bg_color": "#FFFAF0", # Floral White plot background
            "plot_line_color_1": "#FF6347", # Tomato
            "plot_line_color_2": "#FF8C00", # Dark Orange
            "plot_line_color_3": "#FFD700", # Gold
            "plot_line_color_4": "#CD5C5C", # Indian Red
            "plot_line_color_5": "#FF4500", # OrangeRed (New)
            "plot_line_color_6": "#F4A460", # Sandy Brown (New)
            "plot_line_color_7": "#DB7093", # Pale Violet Red (New)
            "recommended_gauge_style": "Warm Sunset Gauge" # Recommended gauge style
        },
        "Deep Purple": { # Original Deep Purple from your 1theming_snippet.txt
            "native_style": "Fusion",
            "bg_color": "#4A148C", # Deep Purple
            "text_color": "#E0BBE4", # Light Purple
            "base_color": "#6A1B9A", # Medium Purple
            "alt_bg_color": "#8E24AA", # Lighter Purple
            "button_bg_color": "#AB47BC", # Button Purple
            "button_text_color": "#FFFFFF",
            "highlight_color": "#8E24AA", # Darker Button Purple
            "highlighted_text_color": "#FFFFFF",
            "placeholder_text_color": "#C3B0E0",
            "outline_color": "#7B1FA2",
            "plot_bg_color": "#6A1B9A", # Medium Purple plot background
            "plot_line_color_1": "#BA68C8", # Purple 300
            "plot_line_color_2": "#E1BEE7", # Purple 100
            "plot_line_color_3": "#9C27B0", # Purple 500
            "plot_line_color_4": "#D81B60", # Deep Pink
            "plot_line_color_5": "#AD1457", # Pink (New)
            "plot_line_color_6": "#7B1FA2", # Purple (New)
            "plot_line_color_7": "#5E35B1", # Deep Purple (New)
            "recommended_gauge_style": "Vibrant Purple Gauge" # Recommended gauge style
        },
        "Soft Pink": {
            "native_style": "Fusion",
            "bg_color": "#FCE4EC", # Light Pink
            "text_color": "#880E4F", # Deep Pink
            "base_color": "#FFFFFF", # White
            "alt_bg_color": "#F8BBD0", # Medium Pink
            "button_bg_color": "#EC407A", # Button Pink
            "button_text_color": "#FFFFFF",
            "highlight_color": "#D81B60", # Darker Button Pink
            "highlighted_text_color": "#FFFFFF",
            "placeholder_text_color": "#F48FB1",
            "outline_color": "#E91E63",
            "plot_bg_color": "#FFFFFF", # White plot background
            "plot_line_color_1": "#EC407A", # Button Pink
            "plot_line_color_2": "#F06292", # Light Pink
            "plot_line_color_3": "#E91E63", # Medium Pink
            "plot_line_color_4": "#C2185B", # Dark Pink
            "plot_line_color_5": "#AD1457", # Darker Pink (New)
            "plot_line_color_6": "#880E4F", # Deepest Pink (New)
            "plot_line_color_7": "#FFCDD2", # Reddish Pink (New)
            "recommended_gauge_style": "Soft Pink Gauge" # Recommended gauge style (New custom gauge below)
        },
        "Vibrant Green": {
            "native_style": "Fusion",
            "bg_color": "#E8F5E9", # Very Light Green
            "text_color": "#1B5E20", # Dark Green
            "base_color": "#FFFFFF", # White
            "alt_bg_color": "#C8E6C9", # Light Green
            "button_bg_color": "#4CAF50", # Button Green
            "button_text_color": "#FFFFFF",
            "highlight_color": "#2E7D32", # Darker Button Green
            "highlighted_text_color": "#FFFFFF",
            "placeholder_text_color": "#A5D6A7",
            "outline_color": "#66BB6A",
            "plot_bg_color": "#FFFFFF", # White plot background
            "plot_line_color_1": "#4CAF50", # Green
            "plot_line_color_2": "#8BC34A", # Light Green
            "plot_line_color_3": "#CDDC39", # Lime Green
            "plot_line_color_4": "#FFEB3B", # Yellow
            "plot_line_color_5": "#7CB342", # Olive Green (New)
            "plot_line_color_6": "#33691E", # Dark Olive Green (New)
            "plot_line_color_7": "#A2D9B3", # Medium Green (New)
            "recommended_gauge_style": "Forest Green Gauge" # Recommended gauge style
        },
        "Cool Grey": {
            "native_style": "Fusion",
            "bg_color": "#ECEFF1", # Very Light Grey
            "text_color": "#37474F", # Dark Blue Grey
            "base_color": "#FFFFFF", # White
            "alt_bg_color": "#CFD8DC", # Light Blue Grey
            "button_bg_color": "#78909C", # Button Grey
            "button_text_color": "#FFFFFF",
            "highlight_color": "#546E7A", # Darker Button Grey
            "highlighted_text_color": "#FFFFFF",
            "placeholder_text_color": "#B0BEC5",
            "outline_color": "#90A4AE",
            "plot_bg_color": "#FFFFFF", # White plot background
            "plot_line_color_1": "#78909C", # Button Grey
            "plot_line_color_2": "#90A4AE", # Medium Grey
            "plot_line_color_3": "#B0BEC5", # Light Grey
            "plot_line_color_4": "#546E7A", # Darker Grey
            "plot_line_color_5": "#455A64", # Darkest Grey (New)
            "plot_line_color_6": "#263238", # Even Darker Grey (New)
            "plot_line_color_7": "#607D8B", # Blue Grey (New)
            "recommended_gauge_style": "Subtle Grey Gauge" # Recommended gauge style
        },
        "Earthy Tone": {
            "native_style": "Fusion",
            "bg_color": "#FBE9E7", # Light Salmon
            "text_color": "#4E342E", # Dark Brown
            "base_color": "#FFFFFF", # White
            "alt_bg_color": "#D7CCC8", # Light Brown
            "button_bg_color": "#8D6E63", # Button Brown
            "button_text_color": "#FFFFFF",
            "highlight_color": "#6D4C41", # Darker Button Brown
            "highlighted_text_color": "#FFFFFF",
            "placeholder_text_color": "#BCAAA4",
            "outline_color": "#A1887F",
            "plot_bg_color": "#FFFFFF", # White plot background
            "plot_line_color_1": "#8D6E63", # Brown
            "plot_line_color_2": "#A1887F", # Lighter Brown
            "plot_line_color_3": "#D7CCC8", # Lightest Brown
            "plot_line_color_4": "#4E342E", # Darkest Brown
            "plot_line_color_5": "#795548", # Medium Brown (New)
            "plot_line_color_6": "#5D4037", # Darker Brown (New)
            "plot_line_color_7": "#BF360C", # Deep Orange (New)
            "recommended_gauge_style": "Gold Rush Gauge" # Recommended gauge style
        },
        "Sunset Orange": {
            "native_style": "Fusion",
            "bg_color": "#FFF3E0", # Light Peach
            "text_color": "#6A1C00", # Dark Red-Orange
            "base_color": "#FFFAF0", # Floral White
            "alt_bg_color": "#FFD7B2", # Light Orange
            "button_bg_color": "#FF8C00", # Dark Orange
            "button_text_color": "#FFFFFF",
            "highlight_color": "#FF6347", # Tomato
            "highlighted_text_color": "#FFFFFF",
            "placeholder_text_color": "#E0B28C",
            "outline_color": "#D2691E", # Chocolate
            "plot_bg_color": "#FFFAF0", # Floral White plot background
            "plot_line_color_1": "#FF4500", # OrangeRed
            "plot_line_color_2": "#FFA07A", # Light Salmon
            "plot_line_color_3": "#FFD700", # Gold
            "plot_line_color_4": "#B22222", # Firebrick
            "plot_line_color_5": "#E9967A", # Dark Salmon
            "plot_line_color_6": "#CD853F", # Peru
            "plot_line_color_7": "#DAA520", # Goldenrod
            "recommended_gauge_style": "Warm Sunset Gauge" # Recommended gauge style
        },
        "Monochromatic Green": {
            "native_style": "Fusion",
            "bg_color": "#F0FFF0", # Honeydew
            "text_color": "#2E8B57", # Sea Green
            "base_color": "#FFFFFF", # White
            "alt_bg_color": "#DFF0D8", # Pale Green
            "button_bg_color": "#3CB371", # Medium Sea Green
            "button_text_color": "#FFFFFF",
            "highlight_color": "#20B2AA", # Light Sea Green
            "highlighted_text_color": "#FFFFFF",
            "placeholder_text_color": "#98FB98", # PaleGreen
            "outline_color": "#6B8E23", # Olive Drab
            "plot_bg_color": "#FFFFFF", # White plot background
            "plot_line_color_1": "#6B8E23", # Olive Drab
            "plot_line_color_2": "#8BC34A", # Light Green
            "plot_line_color_3": "#9ACD32", # YellowGreen
            "plot_line_color_4": "#ADFF2F", # GreenYellow
            "plot_line_color_5": "#32CD32", # LimeGreen
            "plot_line_color_6": "#228B22", # ForestGreen
            "plot_line_color_7": "#2E8B57", # SeaGreen
            "recommended_gauge_style": "Forest Green Gauge" # Recommended gauge style
        },
        "Cyberpunk Neon": {
            "native_style": "Fusion",
            "bg_color": "#0F0F0F", # Very dark almost black
            "text_color": "#00FFFF", # Neon Cyan
            "base_color": "#1F1F1F", # Darker grey for inputs
            "alt_bg_color": "#2A0A2A", # Dark purple-black for alternate
            "button_bg_color": "#FF00FF", # Neon Magenta
            "button_text_color": "#0F0F0F", # Black text on neon buttons
            "highlight_color": "#00FF00", # Neon Green
            "highlighted_text_color": "#0F0F0F", # Black text on neon highlight
            "placeholder_text_color": "#888888", # Grey placeholder
            "outline_color": "#444444", # Dark grey borders
            "plot_bg_color": "#0F0F0F", # Very dark plot background
            "plot_line_color_1": "#FF00FF", # Neon Magenta
            "plot_line_color_2": "#00FFFF", # Neon Cyan
            "plot_line_color_3": "#FFFF00", # Neon Yellow
            "plot_line_color_4": "#FF4500", # OrangeRed
            "plot_line_color_5": "#00FF00", # Neon Green
            "plot_line_color_6": "#FF1493", # Deep Pink
            "plot_line_color_7": "#8A2BE2", # Blue Violet
            "recommended_gauge_style": "High Contrast Gauge" # Recommended gauge style
        },
        "Light Gray": {
            "native_style": "Fusion",
            "bg_color": "#f0f0f0",
            "text_color": "#333333",
            "base_color": "#f8f8f8",
            "alt_bg_color": "#ffffff",
            "button_bg_color": "#007bff",
            "button_text_color": "#ffffff",
            "highlight_color": "#0056b3",
            "highlighted_text_color": "#ffffff",
            "placeholder_text_color": "#aaaaaa",
            "outline_color": "#bbb",
            "plot_bg_color": "#ffffff",
            "plot_line_color_1": "#007bff",
            "plot_line_color_2": "#28a745",
            "plot_line_color_3": "#ffc107",
            "plot_line_color_4": "#dc3545",
            "plot_line_color_5": "#6610f2",
            "plot_line_color_6": "#20c997",
            "plot_line_color_7": "#fd7e14",
            "recommended_gauge_style": "Elegant Grey Gauge" # Adjusted for better visual match
        },
        "Dark Grey Light Text": {
            "native_style": "Fusion",
            "bg_color": "#3c3f41", # Darker gray
            "text_color": "#fdfdfd", # White
            "base_color": "#4b4f52", # Lighter dark for text edit backgrounds
            "alt_bg_color": "#333333", # Pane background
            "button_bg_color": "#6a737d", # Grayish blue
            "button_text_color": "#fdfdfd", # White
            "highlight_color": "#586069", # Darker grayish blue
            "highlighted_text_color": "#fdfdfd",
            "placeholder_text_color": "#9e9e9e", # Medium gray
            "outline_color": "#505050", # Medium dark gray
            "plot_bg_color": "#333333", # Plot background
            "plot_line_color_1": "#79c0ff", # GitHub Blue
            "plot_line_color_2": "#fdfdfd", # White
            "plot_line_color_3": "#9e9e9e", # Medium gray
            "plot_line_color_4": "#f44336", # Red
            "plot_line_color_5": "#80deea", # Light Cyan
            "plot_line_color_6": "#ffab40", # Orange
            "plot_line_color_7": "#cddc39", # Lime
            "recommended_gauge_style": "Subtle Grey Gauge" # More appropriate for this theme
        },
        "Deep Ocean Blue": {
            "native_style": "Fusion",
            "bg_color": "#003366", # Dark Ocean Blue
            "text_color": "#E0FFFF", # Light Cyan
            "base_color": "#004080", # Lighter dark blue for inputs
            "alt_bg_color": "#002244", # Pane background
            "button_bg_color": "#4682B4", # Steel Blue
            "button_text_color": "#FFFFFF",
            "highlight_color": "#3A719D", # Darker Steel Blue (button hover)
            "highlighted_text_color": "#E0FFFF",
            "placeholder_text_color": "#6A8FA8",
            "outline_color": "#005099", # Medium blue
            "plot_bg_color": "#002244", # Plot background
            "plot_line_color_1": "#4682B4", # Steel Blue
            "plot_line_color_2": "#87CEEB", # Sky Blue
            "plot_line_color_3": "#E0FFFF", # Light Cyan
            "plot_line_color_4": "#FFD700", # Gold
            "plot_line_color_5": "#CD5C5C", # Indian Red
            "plot_line_color_6": "#4169E1", # Royal Blue
            "plot_line_color_7": "#00CED1", # Dark Turquoise
            "recommended_gauge_style": "Modern Blue Gauge"
        },
        "Deep Forest Green": {
            "native_style": "Fusion",
            "bg_color": "#228B22", # Forest Green
            "text_color": "#FFFFFF",
            "base_color": "#339933", # Lighter green for inputs
            "alt_bg_color": "#1B5E20", # Pane background
            "button_bg_color": "#66BB6A", # Light Green
            "button_text_color": "#FFFFFF",
            "highlight_color": "#4CAF50", # Medium Green (button hover)
            "highlighted_text_color": "#FFFFFF",
            "placeholder_text_color": "#A5D6A7",
            "outline_color": "#4CAF50", # Medium Green
            "plot_bg_color": "#1B5E20", # Plot background
            "plot_line_color_1": "#66BB6A", # Light Green
            "plot_line_color_2": "#A5D6A7", # Light Green Accent
            "plot_line_color_3": "#FFC300", # Gold
            "plot_line_color_4": "#D35400", # Pumpkin
            "plot_line_color_5": "#8BC34A", # Light Green
            "plot_line_color_6": "#7CB342", # Light Green Shade
            "plot_line_color_7": "#FFEB3B", # Yellow
            "recommended_gauge_style": "Forest Green Gauge"
        },
        "Royal Purple": {
            "native_style": "Fusion",
            "bg_color": "#4B0082", # Indigo
            "text_color": "#E0BBE4", # Light Purple
            "base_color": "#6A1B9A", # Medium Purple
            "alt_bg_color": "#8E24AA", # Lighter Purple
            "button_bg_color": "#AB47BC", # Button Purple
            "button_text_color": "#FFFFFF",
            "highlight_color": "#8E24AA", # Darker Button Purple
            "highlighted_text_color": "#FFFFFF",
            "placeholder_text_color": "#C3B0E0",
            "outline_color": "#7B1FA2",
            "plot_bg_color": "#6A1B9A", # Medium Purple plot background
            "plot_line_color_1": "#BA68C8", # Purple 300
            "plot_line_color_2": "#E1BEE7", # Purple 100
            "plot_line_color_3": "#9C27B0", # Purple 500
            "plot_line_color_4": "#D81B60", # Deep Pink
            "plot_line_color_5": "#AD1457", # Pink (New)
            "plot_line_color_6": "#7B1FA2", # Purple (New)
            "plot_line_color_7": "#5E35B1", # Deep Purple (New)
            "recommended_gauge_style": "Vibrant Purple Gauge"
        },
        "Warm Brown": {
            "native_style": "Fusion",
            "bg_color": "#704214", # Sepia Brown
            "text_color": "#F5DEB3", # Wheat
            "base_color": "#7C4F2A", # Lighter brown for inputs
            "alt_bg_color": "#5A2D0C", # Pane background
            "button_bg_color": "#A0522D", # Sienna
            "button_text_color": "#FFFFFF",
            "highlight_color": "#8B4513", # SaddleBrown (button hover)
            "highlighted_text_color": "#F5DEB3",
            "placeholder_text_color": "#DEB887",
            "outline_color": "#8B4513", # SaddleBrown
            "plot_bg_color": "#5A2D0C", # Plot background
            "plot_line_color_1": "#A0522D", # Sienna
            "plot_line_color_2": "#DEB887", # BurlyWood
            "plot_line_color_3": "#FFD700", # Gold
            "plot_line_color_4": "#CD5C5C", # Indian Red
            "plot_line_color_5": "#D2B48C", # Tan
            "plot_line_color_6": "#8B4513", # SaddleBrown
            "plot_line_color_7": "#BC8F8F", # RosyBrown
            "recommended_gauge_style": "Gold Rush Gauge"
        },


        # --- Gauge Specific Styles (distinct from UI themes) ---
        # These styles contain specific colors for gauge elements
        "Modern Blue Gauge": {
            "gauge_arc_background": "#ADD8E6", # Light Blue for the background arc
            "gauge_fill_low": "#4682B4", # Steel Blue for low range fill
            "gauge_fill_medium": "#1E90FF", # Dodger Blue for medium range fill
            "gauge_fill_high": "#4169E1", # Royal Blue for high range fill
            "gauge_needle": "#333333", # Dark Gray for the needle
            "gauge_outline": "#6A5ACD", # Slate Blue for the gauge outline and pivot
            "gauge_na": "#A9A9A9", # Dark Gray for N/A state
            "gauge_label_color": "#1F456E", # Dark Blue for gauge label (Contrasts well with light blue arc)
            "gauge_value_color": "#1F456E", # Dark Blue for gauge value (High contrast on light blue/white fills)
            "gauge_inner_circle": "#E0FFFF" # Light Cyan inner circle to match general theme background
        },
        "Warm Sunset Gauge": {
            "gauge_arc_background": "#FFE4B5", # Moccasin
            "gauge_fill_low": "#FFA07A", # Light Salmon
            "gauge_fill_medium": "#FF6347", # Tomato
            "gauge_fill_high": "#FF4500", # Orange Red
            "gauge_needle": "#8B0000", # Dark Red
            "gauge_outline": "#D2691E", # Chocolate
            "gauge_na": "#CD853F", # Peru
            "gauge_label_color": "#5D4037", # Brown for gauge label (Contrasts with warm background)
            "gauge_value_color": "#5D4037", # Brown for gauge value (Contrasts with orange/red fills)
            "gauge_inner_circle": "#FFFBF2" # Off-white inner circle
        },
        "Forest Green Gauge": {
            "gauge_arc_background": "#C8E6C9", # Light Green
            "gauge_fill_low": "#66BB6A", # Green 500
            "gauge_fill_medium": "#388E3C", # Green 700
            "gauge_fill_high": "#1B5E20", # Green 900
            "gauge_needle": "#424242", # Dark Gray
            "gauge_outline": "#2E7D32", # Dark Green
            "gauge_na": "#757575", # Grey
            "gauge_label_color": "#1B5E20", # Dark Green for gauge label (Good contrast on light green)
            "gauge_value_color": "#1B5E20", # Dark Green for gauge value (Good contrast on green fills)
            "gauge_inner_circle": "#F0FFF0" # Honeydew inner circle
        },
        "Elegant Grey Gauge": {
            "gauge_arc_background": "#E0E0E0", # Grey 300
            "gauge_fill_low": "#9E9E9E", # Grey 500
            "gauge_fill_medium": "#616161", # Grey 700
            "gauge_fill_high": "#212121", # Grey 900
            "gauge_needle": "#FF0000", # Red
            "gauge_outline": "#424242", # Dark Grey
            "gauge_na": "#BDBDBD", # Light Grey
            "gauge_label_color": "#212121", # Darkest Grey for gauge label (Good contrast on light grey)
            "gauge_value_color": "#212121", # Darkest Grey for gauge value (Good contrast on dark grey fills)
            "gauge_inner_circle": "#F5F5F5" # Very light grey inner circle
        },
        "Vibrant Purple Gauge": {
            "gauge_arc_background": "#E1BEE7", # Purple 100
            "gauge_fill_low": "#BA68C8", # Purple 300
            "gauge_fill_medium": "#9C27B0", # Purple 500
            "gauge_fill_high": "#6A1B9A", # Purple 800
            "gauge_needle": "#4A148C", # Deep Purple (for contrast)
            "gauge_outline": "#4A148C", # Dark Purple
            "gauge_na": "#CE93D8", # Purple 200
            "gauge_label_color": "#4A148C", # Deep Purple for gauge label (Contrasts with light purple)
            "gauge_value_color": "#4A148C", # Deep Purple for gauge value (Good contrast on purple fills)
            "gauge_inner_circle": "#F3E5F5" # Lighter purple inner circle
        },
        "High Contrast Gauge": {
            "gauge_arc_background": "#000000", # Black
            "gauge_fill_low": "#00FF00", # Bright Green
            "gauge_fill_medium": "#FFFF00", # Yellow
            "gauge_fill_high": "#FF0000", # Red
            "gauge_needle": "#FFFFFF", # White
            "gauge_outline": "#FFFFFF", # White outline
            "gauge_na": "#555555", # Dark Grey for N/A
            "gauge_label_color": "#FFFFFF", # White label (Max contrast on black)
            "gauge_value_color": "#00FFFF", # Cyan value (High visibility)
            "gauge_inner_circle": "#1A1A1A" # Very dark grey inner circle
        },
        "Subtle Grey Gauge": {
            "gauge_arc_background": "#F5F5F5", # WhiteSmoke
            "gauge_fill_low": "#A9A9A9", # DarkGray
            "gauge_fill_medium": "#808080", # Gray
            "gauge_fill_high": "#696969", # DimGray
            "gauge_needle": "#333333", # Dark Grey
            "gauge_outline": "#C0C0C0", # Silver
            "gauge_na": "#DCDCDC", # Gainsboro
            "gauge_label_color": "#2F4F4F", # Dark Slate Gray for gauge label (Good contrast on light grey)
            "gauge_value_color": "#2F4F4F", # Dark Slate Gray for gauge value (Good contrast on dark grey fills)
            "gauge_inner_circle": "#E0E0E0" # Light grey inner circle
        },
        "Gold Rush Gauge": {
            "gauge_arc_background": "#FDF5E6", # OldLace
            "gauge_fill_low": "#DAA520", # Goldenrod
            "gauge_fill_medium": "#FFD700", # Gold
            "gauge_fill_high": "#B8860B", # DarkGoldenrod
            "gauge_needle": "#8B4513", # SaddleBrown
            "gauge_outline": "#CD853F", # Peru
            "gauge_na": "#D2B48C", # Tan
            "gauge_label_color": "#8B4513", # SaddleBrown for gauge label (Good contrast on light gold)
            "gauge_value_color": "#8B4513", # SaddleBrown for gauge value (Good contrast on golden fills)
            "gauge_inner_circle": "#FFF8DC" # Cornsilk inner circle
        },
        "Soft Pink Gauge": {
            "gauge_arc_background": "#F8BBD0", # Medium Pink
            "gauge_fill_low": "#EC407A", # Button Pink
            "gauge_fill_medium": "#E91E63", # Medium Pink
            "gauge_fill_high": "#C2185B", # Dark Pink
            "gauge_needle": "#880E4F", # Deep Pink (for contrast)
            "gauge_outline": "#D81B60", # Darker Button Pink
            "gauge_na": "#FCE4EC", # Light Pink for N/A
            "gauge_label_color": "#880E4F", # Deep Pink for label (Good contrast on light pink)
            "gauge_value_color": "#880E4F", # Deep Pink for value (Good contrast on pink fills)
            "gauge_inner_circle": "#FFCDD2" # Reddish Pink inner circle
        },
        # --- NEW GAUGE STYLES (6 total) ---
        "Emerald Green Gauge": {
            "gauge_arc_background": "#B9F6CA", # Lightest Green
            "gauge_fill_low": "#69F0AE", # Lighter Green
            "gauge_fill_medium": "#00E676", # Medium Green
            "gauge_fill_high": "#00C853", # Dark Green
            "gauge_needle": "#1B5E20", # Deep Green (for contrast)
            "gauge_outline": "#1B5E20", # Deep Green
            "gauge_na": "#A5D6A7", # Pale Green
            "gauge_label_color": "#1B5E20", # Deep Green for label
            "gauge_value_color": "#1B5E20", # Deep Green for value
            "gauge_inner_circle": "#E8F5E9" # Very Light Green inner circle
        },
        "Ruby Red Gauge": {
            "gauge_arc_background": "#FFCDD2", # Lightest Red
            "gauge_fill_low": "#EF9A9A", # Lighter Red
            "gauge_fill_medium": "#E53935", # Medium Red
            "gauge_fill_high": "#C62828", # Dark Red
            "gauge_needle": "#B71C1C", # Deep Red (for contrast)
            "gauge_outline": "#B71C1C", # Deep Red
            "gauge_na": "#FFEBEE", # Pale Red
            "gauge_label_color": "#B71C1C", # Deep Red for label
            "gauge_value_color": "#B71C1C", # Deep Red for value
            "gauge_inner_circle": "#FCE4EC" # Light Pink inner circle
        },
        "Goldenrod Gauge": {
            "gauge_arc_background": "#FFFDE7", # Very Light Yellow
            "gauge_fill_low": "#FFECB3", # Light Yellow
            "gauge_fill_medium": "#FFCA28", # Medium Yellow
            "gauge_fill_high": "#FFA000", # Dark Orange-Yellow
            "gauge_needle": "#424242", # Dark Gray
            "gauge_outline": "#FF8F00", # Deep Orange-Yellow
            "gauge_na": "#FFF3E0", # Pale Yellow
            "gauge_label_color": "#FF8F00", # Deep Orange-Yellow for label
            "gauge_value_color": "#424242", # Dark Gray for value
            "gauge_inner_circle": "#FFF9C4" # Very Light Yellow inner circle
        },
        "Cool Cyan Gauge": {
            "gauge_arc_background": "#E0F7FA", # Lightest Cyan
            "gauge_fill_low": "#80DEEA", # Lighter Cyan
            "gauge_fill_medium": "#26C6DA", # Medium Cyan
            "gauge_fill_high": "#00ACC1", # Dark Cyan
            "gauge_needle": "#00838F", # Deep Cyan (for contrast)
            "gauge_outline": "#00838F", # Deep Cyan
            "gauge_na": "#B2EBF2", # Pale Cyan
            "gauge_label_color": "#00838F", # Deep Cyan for label
            "gauge_value_color": "#00838F", # Deep Cyan for value
            "gauge_inner_circle": "#E0FFFF" # Light Cyan inner circle
        },
        "Midnight Blue Gauge": {
            "gauge_arc_background": "#BBDEFB", # Light Blue
            "gauge_fill_low": "#64B5F6", # Medium Light Blue
            "gauge_fill_medium": "#2196F3", # Blue
            "gauge_fill_high": "#1976D2", # Dark Blue
            "gauge_needle": "#FFEB3B", # Yellow for contrast
            "gauge_outline": "#0D47A1", # Deep Blue
            "gauge_na": "#90CAF9", # Pale Blue
            "gauge_label_color": "#FFFFFF", # White for label
            "gauge_value_color": "#FFEB3B", # Yellow for value
            "gauge_inner_circle": "#E3F2FD" # Very light blue inner circle
        },
        "Sunny Yellow Gauge": {
            "gauge_arc_background": "#FFF9C4", # Very Light Yellow
            "gauge_fill_low": "#FFF176", # Light Yellow
            "gauge_fill_medium": "#FFEE58", # Medium Yellow
            "gauge_fill_high": "#FFD600", # Vibrant Yellow
            "gauge_needle": "#B71C1C", # Dark Red for contrast
            "gauge_outline": "#FBC02D", # Darker Yellow
            "gauge_na": "#FFFDE7", # Pale Yellow
            "gauge_label_color": "#B71C1C", # Dark Red for label
            "gauge_value_color": "#424242", # Dark Gray for value
            "gauge_inner_circle": "#FFFDE7" # Very Light Yellow inner circle
        }
    }


    def __init__(self, settings_file="settings.json"):
        # Define the path for the settings file.
        # It's placed in the current working directory for simplicity.
        self.settings_file = os.path.join(os.getcwd(), settings_file)
        self.settings = self._load_settings()

    def _load_settings(self):
        """Loads settings from the JSON file. Returns default settings if file not found or is invalid."""
        default_settings = {
            "log_path": os.path.join(os.getcwd(), "Sensor_Logs"),
            "archive_path": os.path.join(os.getcwd(), "Archive_Sensor_Logs"),
            "debug_log_path": os.path.join(os.getcwd(), "Debug_Logs", "debug.log"),
            "archive_enabled": True,
            "mock_data_enabled": False, # New setting for mock data toggle
            "play_alert_sound": True,
            "play_change_sound": True,
            "plot_time_range": "Last 10 minutes",
            "read_interval": 5, # Sensor read interval in seconds
            "plot_update_interval_ms": 1000, # Plot update interval in milliseconds
            "max_plot_data_points": 300, # Max data points to keep in memory for plots
            "log_sensor_settings": { # Which sensors to log data for (defaults enabled)
                'bme280': True,
                'sgp40': True,
                'shtc3': True,
                'proximity': True
            },
            "theme": "Default Light", # Default UI theme
            "gauge_style": "Modern Blue Gauge", # Default gauge style
            "debug_to_console_enabled": True, # New: control console output
            "debug_log_level": "DEBUG" # New: control console/file log level
        }
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    # Load existing settings
                    loaded_settings = json.load(f)
                    # Merge with default settings to ensure all keys are present
                    # Existing values in loaded_settings will override defaults
                    settings = {**default_settings, **loaded_settings}
                    # Handle specific nested dictionaries like log_sensor_settings
                    if "log_sensor_settings" in loaded_settings and "log_sensor_settings" in default_settings:
                        settings["log_sensor_settings"] = {**default_settings["log_sensor_settings"], **loaded_settings["log_sensor_settings"]}
                    
                    # Special handling to ensure THEMES from the class definition are always used
                    # and not overwritten by an old saved settings file that might lack new colors.
                    # We merge the loaded theme data with the class's default THEMES for each theme.
                    # This ensures plot_line_color_5, _6, _7 etc. are always present,
                    # and now also includes gauge_inner_circle.
                    for theme_name, theme_data in self.THEMES.items():
                        if theme_name in loaded_settings.get("THEMES", {}): # Check loaded_settings for theme data
                            # Merge specific theme details from loaded_settings into the class's THEMES
                            self.THEMES[theme_name].update(loaded_settings["THEMES"][theme_name])
                    
                    # If 'THEMES' was in loaded_settings, but we want to use the class's latest, remove it
                    settings.pop("THEMES", None)

                    print(f"Settings loaded from {self.settings_file}")
                    return settings
            else:
                print(f"Settings file not found at {self.settings_file}. Using default settings.")
        except json.JSONDecodeError as e:
            print(f"Error decoding settings JSON from {self.settings_file}: {e}. Using default settings.")
        except Exception as e:
            print(f"An unexpected error occurred loading settings: {e}. Using default settings.")
        return default_settings

    def save_settings(self):
        """Saves the current settings to the JSON file."""
        try:
            # When saving, ensure the latest THEMES from the class are saved.
            # Temporarily store the themes from self.settings if they exist to avoid
            # overwriting new themes defined in the class.
            current_settings_themes = self.settings.get("THEMES") 
            self.settings["THEMES"] = self.THEMES # Add the current THEMES from class for saving

            os.makedirs(os.path.dirname(self.settings_file), exist_ok=True)
            with open(self.settings_file, 'w') as f:
                json.dump(self.settings, f, indent=4)
            print(f"Settings saved to {self.settings_file}")
            
            # Restore original themes if they were different (this handles the case where
            # themes might have been loaded from a file and are now being overwritten
            # by the class defaults before saving)
            if current_settings_themes is not None:
                self.settings["THEMES"] = current_settings_themes
            else:
                # If THEMES was not originally in self.settings, remove it after saving
                # to keep self.settings clean of the large THEMES dictionary during runtime
                self.settings.pop("THEMES", None)

        except Exception as e:
            print(f"Error saving settings to {self.settings_file}: {e}")

    def get_setting(self, key, default=None):
        """Retrieves a setting by its key."""
        return self.settings.get(key, default)

    def set_setting(self, key, value):
        """Sets a setting's value."""
        self.settings[key] = value

    def get_all_settings(self):
        """Returns all current settings."""
        return self.settings.copy()

    def update_settings(self, new_settings_dict):
        """Updates multiple settings from a dictionary."""
        self.settings.update(new_settings_dict)
        self.save_settings()

    def get_available_themes(self):
        """Returns a list of available UI theme names (excluding gauge styles)."""
        # Filter out themes that are specifically for gauges (contain "Gauge" in their name)
        return [theme for theme in self.THEMES.keys() if "Gauge" not in theme]

    def get_available_gauge_styles(self):
        """Returns a list of available gauge style names."""
        # Return only themes that are specifically for gauges (contain "Gauge" in their name)
        return [style for style in self.THEMES.keys() if "Gauge" in style]

    def get_theme_data(self, theme_name):
        """Returns the dictionary of colors and styles for a given theme name."""
        return self.THEMES.get(theme_name)
