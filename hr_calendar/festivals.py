from .locations import Location
from .hindu_calendar import HinduCalendar


def find_festivals_high_accuracy(year: int, loc: Location) -> dict:
    """Compatibility wrapper: return a simple mapping using HinduCalendar.

    This function exists to preserve the earlier public API. It delegates all
    computation to the class-based implementation.
    """
    cal = HinduCalendar(loc)
    return cal.festivals_for_year(year)