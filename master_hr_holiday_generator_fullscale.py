#!/usr/bin/env python3
"""
master_hr_holiday_generator_fullscale.py
========================================
High-accuracy Hindu holiday generator — CLI wrapper

Run: python master_hr_holiday_generator_fullscale.py 2026 IN
"""

from __future__ import annotations
import sys
from datetime import datetime
from hr_calendar.locations import LOCATIONS, Location
from hr_calendar.hindu_calendar import HinduCalendar
import json


def print_usage_and_exit():
    print("Usage: python master_hr_holiday_generator_fullscale.py YEAR [LOCATION_CODE]")
    print("Available location codes:", ", ".join(sorted(LOCATIONS.keys())))
    sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print_usage_and_exit()
    try:
        year = int(sys.argv[1])
    except Exception:
        print("Invalid year")
        print_usage_and_exit()
    code = sys.argv[2] if len(sys.argv) > 2 else "IN"
    if code not in LOCATIONS:
        print(f"Unknown code '{code}'. Available: {', '.join(sorted(LOCATIONS.keys()))}")
        sys.exit(1)
    lat, lon, tz, height = LOCATIONS[code]
    loc = Location(lat=lat, lon=lon, tz=tz, height_m=height)
    cal = HinduCalendar(loc)
    result = cal.festivals_for_year(year)
    print(json.dumps(result, indent=2))