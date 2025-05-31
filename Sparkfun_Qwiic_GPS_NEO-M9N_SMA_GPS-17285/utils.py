# utils.py

import math

def format_coord(coord):
    """Formats a coordinate to 6 decimal places or 'N/A' if NaN."""
    if math.isnan(coord):
        return "N/A"
    return f"{coord:.6f}"

def format_value(value, precision=2):
    """Formats a float value to specified precision or 'N/A' if NaN."""
    if isinstance(value, (int, float)) and math.isnan(value):
        return "N/A"
    if isinstance(value, float):
        return f"{value:.{precision}f}"
    return str(value)

def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the distance between two points on Earth using the Haversine formula.
    Returns distance in meters.
    """
    R = 6371000 # Earth radius in meters

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance = R * c
    return distance
