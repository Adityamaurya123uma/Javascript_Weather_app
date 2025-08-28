from dataclasses import dataclass


@dataclass
class Location:
    lat: float
    lon: float
    tz: float
    height_m: float = 0.0


# Format: code : (lat_deg, lon_deg, tz_offset_hours, height_m)
LOCATIONS = {
    "IN": (28.6139, 77.2090, 5.5, 216.0),    # New Delhi
    "NP": (27.7172, 85.3240, 5.75, 1400.0),  # Kathmandu
    "MU": (-20.1609, 57.5012, 4.0, 40.0),    # Port Louis
    "FJ": (-18.1248, 178.4501, 12.0, 33.0),  # Suva
    "UK": (51.5074, -0.1278, 0.0, 11.0),     # London
    "US": (40.7128, -74.0060, -5.0, 10.0),   # New York
    "SG": (1.3521, 103.8198, 8.0, 15.0),     # Singapore
    "CA": (43.6532, -79.3832, -5.0, 76.0),   # Toronto
}