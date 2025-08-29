from datetime import datetime
from .locations import Location
from .festivals import find_festivals_high_accuracy
from .phase import tithi_at_local_sunrise, tithi_at_local_sunset, find_phase_time_tt_near
from .time_utils import to_julian_day, jd_tt_from_jd_ut
from .astro import sun_ecliptic_longitude_deg


class HinduCalendar:
    def __init__(self, location: Location):
        self.location = location

    def festivals_for_year(self, year: int) -> dict:
        return find_festivals_high_accuracy(year, self.location)

    def tithi_at_sunrise(self, date_local: datetime) -> int:
        return tithi_at_local_sunrise(date_local, self.location)

    def tithi_at_sunset(self, date_local: datetime) -> int:
        return tithi_at_local_sunset(date_local, self.location)

    def phase_time_near(self, dt_utc: datetime, target_deg: float) -> float:
        jd_ut = to_julian_day(dt_utc)
        jd_tt = jd_tt_from_jd_ut(jd_ut)
        return find_phase_time_tt_near(jd_tt, target_deg, self.location)