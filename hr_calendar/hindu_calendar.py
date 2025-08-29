"""Hindu calendar class-centric API and festival computations.

This class owns the Hindu festival rules and orchestrates astronomical
computations via helper modules. The design keeps accuracy equivalent to the
previous functions while providing a clean OOP surface.
"""

from datetime import datetime, timedelta, timezone, date
from typing import List, Tuple, Dict
from .locations import Location
from .phase import tithi_at_local_sunrise, tithi_at_local_sunset, find_phase_time_tt_near, lunar_phase_angle_tt_deg
from .time_utils import to_julian_day, jd_tt_from_jd_ut, jd_ut_from_jd_tt, from_julian_day
from .sidereal import find_solar_sidereal_ingress_tt_near
from .astro import sun_ecliptic_longitude_deg
from .utils import wrap180
from .rise_set import sunrise_jd_utc, sunset_jd_utc


class HinduCalendar:
    """High-level class for Hindu calendar computations at a given location.

    Provides convenient methods for:
    - festivals_for_year: simple mapping (name → ISO date), all logic here
    - tithi_at_sunrise/tithi_at_sunset
    - phase_time_near: solve for lunar phase near a UTC datetime
    """

    def __init__(self, location: Location):
        self.location = location

    def festivals_for_year(self, year: int) -> dict:
        """Compute Hindu festivals for a year at this location.

        Returns a mapping of festival name → ISO local date string.
        """
        lun_unique = self._precompute_lunations(year)
        diwali = self._compute_diwali(year, lun_unique).isoformat()
        # Holi (color play) is the day after Holika Dahan (Purnima at Pradosh)
        holika = self._compute_holika_dahan(year, lun_unique)
        holi = (holika + timedelta(days=1)).isoformat()
        shiv = self._compute_maha_shivaratri(year, lun_unique).isoformat()
        nav = self._compute_navratri_start(year, lun_unique).isoformat()
        guru = self._compute_guru_purnima(year, lun_unique).isoformat()
        raksha = self._compute_raksha_bandhan(year, lun_unique).isoformat()
        makar = self._compute_makar_sankranti(year).isoformat()
        vishuva = self._compute_vishuva(year).isoformat()
        try:
            di_dt = datetime.fromisoformat(diwali)
            karwa = (di_dt - timedelta(days=4)).date().isoformat()
        except Exception:
            karwa = None
        return {
            "Diwali": diwali,
            "Holi": holi,
            "Maha Shivaratri": shiv,
            "Navratri (Start)": nav,
            "Guru Purnima": guru,
            "Raksha Bandhan": raksha,
            "Karwa Chauth": karwa,
            "Makar Sankranti": makar,
            "Vishuva (March Equinox approx)": vishuva,
        }

    def tithi_at_sunrise(self, date_local: datetime) -> int:
        return tithi_at_local_sunrise(date_local, self.location)

    def tithi_at_sunset(self, date_local: datetime) -> int:
        return tithi_at_local_sunset(date_local, self.location)

    def phase_time_near(self, dt_utc: datetime, target_deg: float) -> float:
        jd_ut = to_julian_day(dt_utc)
        jd_tt = jd_tt_from_jd_ut(jd_ut)
        return find_phase_time_tt_near(jd_tt, target_deg, self.location)

    # ----------
    # Internals
    # ----------

    def _jd_ut_from_local(self, dt_local: datetime) -> float:
        """Convert a timezone-aware or naive local datetime to UT-based JD."""
        if dt_local.tzinfo is None:
            tz = timezone(timedelta(hours=self.location.tz))
            dt_local = dt_local.replace(tzinfo=tz)
        dt_utc = dt_local.astimezone(timezone.utc)
        return to_julian_day(dt_utc)

    def _tithi_at_local_clock(self, base_date: date, hour: int, minute: int) -> int:
        """Tithi number at given local clock time on base_date."""
        tz = timezone(timedelta(hours=self.location.tz))
        dt_local = datetime(base_date.year, base_date.month, base_date.day, hour, minute, 0, tzinfo=tz)
        jd_ut = self._jd_ut_from_local(dt_local)
        jd_tt = jd_tt_from_jd_ut(jd_ut)
        ang = lunar_phase_angle_tt_deg(jd_tt, False, self.location)
        return int(ang // 12.0) + 1

    def _sunrise_sunset_ut(self, base_date: date) -> Tuple[float, float]:
        """Return (sunrise_ut_jd, sunset_ut_jd) for base_date at location."""
        jd_rise = sunrise_jd_utc(datetime(base_date.year, base_date.month, base_date.day), self.location)
        jd_set = sunset_jd_utc(datetime(base_date.year, base_date.month, base_date.day), self.location)
        return jd_rise, jd_set

    def _pradosh_center_tithi(self, base_date: date) -> int:
        """Tithi at the center of Pradosh (≈72 min after sunset)."""
        _, jd_set = self._sunrise_sunset_ut(base_date)
        pradosh_center = jd_set + (72.0 / 1440.0)
        jd_tt = jd_tt_from_jd_ut(pradosh_center)
        ang = lunar_phase_angle_tt_deg(jd_tt, False, self.location)
        return int(ang // 12.0) + 1

    def _nishita_tithi(self, base_date: date) -> int:
        """Tithi at Nishita (midpoint of the night between sunset and next sunrise)."""
        _, jd_set = self._sunrise_sunset_ut(base_date)
        jd_rise_next, _ = self._sunrise_sunset_ut(base_date + timedelta(days=1))
        mid = 0.5 * (jd_set + jd_rise_next)
        jd_tt = jd_tt_from_jd_ut(mid)
        ang = lunar_phase_angle_tt_deg(jd_tt, False, self.location)
        return int(ang // 12.0) + 1

    def _aparahna_tithi(self, base_date: date) -> int:
        """Tithi at center of Aparahna (middle of last third of daytime)."""
        jd_rise, jd_set = self._sunrise_sunset_ut(base_date)
        day_len = jd_set - jd_rise
        center_last_third = jd_rise + (5.0 / 6.0) * day_len
        jd_tt = jd_tt_from_jd_ut(center_last_third)
        ang = lunar_phase_angle_tt_deg(jd_tt, False, self.location)
        return int(ang // 12.0) + 1

    def _precompute_lunations(self, year: int) -> List[Tuple[str, float]]:
        """Scan and bracket new/full moons, refine with phase root-finder.

        Returns list of (kind, rounded_jd_tt) sorted by TT.
        """
        start_utc = datetime(year, 1, 1, tzinfo=timezone.utc) - timedelta(days=1)
        end_utc = datetime(year, 12, 31, tzinfo=timezone.utc) + timedelta(days=2)
        jd_tt_start = jd_tt_from_jd_ut(to_julian_day(start_utc))
        jd_tt_end = jd_tt_from_jd_ut(to_julian_day(end_utc))

        step_days = 0.25
        lun_list: List[Tuple[str, float]] = []

        j = jd_tt_start
        prev_new = wrap180(lunar_phase_angle_tt_deg(j, False, self.location) - 0.0)
        prev_full = wrap180(lunar_phase_angle_tt_deg(j, False, self.location) - 180.0)

        while j < jd_tt_end:
            jn = j + step_days
            cur_new = wrap180(lunar_phase_angle_tt_deg(jn, False, self.location) - 0.0)
            cur_full = wrap180(lunar_phase_angle_tt_deg(jn, False, self.location) - 180.0)

            if prev_new == 0.0 or cur_new == 0.0 or (prev_new < 0.0 and cur_new > 0.0) or (prev_new > 0.0 and cur_new < 0.0):
                guess = 0.5 * (j + jn)
                nm_tt = find_phase_time_tt_near(guess, 0.0, self.location)
                lun_list.append(("NewMoon", nm_tt))

            if prev_full == 0.0 or cur_full == 0.0 or (prev_full < 0.0 and cur_full > 0.0) or (prev_full > 0.0 and cur_full < 0.0):
                guess = 0.5 * (j + jn)
                fm_tt = find_phase_time_tt_near(guess, 180.0, self.location)
                lun_list.append(("FullMoon", fm_tt))

            j = jn
            prev_new = cur_new
            prev_full = cur_full

        lun_unique = sorted({(k, round(v, 6)) for k, v in lun_list}, key=lambda x: x[1])
        return lun_unique

    def _tt_to_local_date(self, jd_tt: float) -> Tuple[date, float]:
        """Convert TT JD to (local civil date, UT JD) at this calendar's location."""
        jd_ut = jd_ut_from_jd_tt(jd_tt)
        dt_utc = from_julian_day(jd_ut)
        return (dt_utc + timedelta(hours=self.location.tz)).date(), jd_ut

    def _compute_diwali(self, year: int, lun_unique: List[Tuple[str, float]]) -> date:
        """Diwali (Kartik Amavasya): require Amavasya at local sunset.

        Seed candidates by selecting the Oct/Nov new moon nearest Nov 1. If
        sunset tithi is not Amavasya, probe ±1–2 days and fall back to sunrise.
        """
        diwali_candidates: List[Tuple[date, float]] = []
        for kind, jd_tt in lun_unique:
            if kind == "NewMoon":
                d_local, _ = self._tt_to_local_date(jd_tt)
                if d_local.year == year and d_local.month in (10, 11):
                    diwali_candidates.append((d_local, jd_tt))
        if not diwali_candidates:
            guess_ut = to_julian_day(datetime(year, 11, 15, tzinfo=timezone.utc))
            nm_tt = find_phase_time_tt_near(jd_tt_from_jd_ut(guess_ut), 0.0, self.location)
            diwali_candidates.append((self._tt_to_local_date(nm_tt)[0], nm_tt))
        target_jd = to_julian_day(datetime(year, 11, 1, tzinfo=timezone.utc))
        diwali_candidates.sort(key=lambda x: abs(x[1] - target_jd))
        seed_date = diwali_candidates[0][0]

        chosen = seed_date
        def ok(d: date) -> bool:
            # Prefer Pradosh-center tithi per common observance
            return self._pradosh_center_tithi(d) == 30

        if not ok(seed_date):
            found = None
            for delta in (1, -1, 2, -2):
                try_dt = seed_date + timedelta(days=delta)
                if ok(try_dt):
                    found = try_dt
                    break
            if found is not None:
                chosen = found
            else:
                if self.tithi_at_sunrise(seed_date) == 30:
                    chosen = seed_date
                else:
                    for delta in (1, -1, 2, -2):
                        try_dt = seed_date + timedelta(days=delta)
                        if self.tithi_at_sunrise(try_dt) == 30:
                            chosen = try_dt
                            break
        return chosen

    def _compute_holika_dahan(self, year: int, lun_unique: List[Tuple[str, float]]) -> date:
        """Holika Dahan: require Purnima at Pradosh (evening) around March."""
        fm_tt = None
        fm_local = None
        for kind, jd_tt in lun_unique:
            if kind == "FullMoon":
                d_local, _ = self._tt_to_local_date(jd_tt)
                if d_local.year == year and d_local.month in (2, 3, 4):
                    fm_tt = jd_tt
                    fm_local = d_local
                    if d_local.month == 3:
                        break
        if fm_tt is None:
            holi_guess_tt = jd_tt_from_jd_ut(to_julian_day(datetime(year, 3, 15, tzinfo=timezone.utc)))
            fm_tt = find_phase_time_tt_near(holi_guess_tt, 180.0, self.location)
            fm_local = self._tt_to_local_date(fm_tt)[0]
        for delta in (0, -1, 1):
            d = fm_local + timedelta(days=delta)
            if self._pradosh_center_tithi(d) == 15:
                return d
        return fm_local

    def _compute_maha_shivaratri(self, year: int, lun_unique: List[Tuple[str, float]]) -> date:
        """Maha Shivaratri: Krishna Chaturdashi (tithi 29) at Nishita in Feb/Mar."""
        candidates: List[date] = []
        for kind, jd_tt in lun_unique:
            if kind == "NewMoon":
                d_local, _ = self._tt_to_local_date(jd_tt)
                if d_local.year == year and d_local.month in (2, 3):
                    candidates.extend([d_local - timedelta(days=1), d_local - timedelta(days=2), d_local])
        if not candidates:
            nm_tt = find_phase_time_tt_near(jd_tt_from_jd_ut(to_julian_day(datetime(year, 2, 15, tzinfo=timezone.utc))), 0.0, self.location)
            d_local = self._tt_to_local_date(nm_tt)[0]
            candidates = [d_local - timedelta(days=1), d_local - timedelta(days=2), d_local]
        for d in sorted(set(candidates)):
            if self._nishita_tithi(d) == 29:
                return d
        return sorted(set(candidates))[0]

    def _compute_navratri_start(self, year: int, lun_unique: List[Tuple[str, float]]) -> date:
        """Navratri start: day after Ashwin Amavasya (Sep/Oct new moon)."""
        nav_start = None
        for kind, jd_tt in lun_unique:
            if kind == "NewMoon":
                d_local, _ = self._tt_to_local_date(jd_tt)
                if d_local.year == year and d_local.month in (9, 10):
                    nav_start = d_local + timedelta(days=1)
                    break
        if nav_start is None:
            nm_tt = find_phase_time_tt_near(jd_tt_from_jd_ut(to_julian_day(datetime(year, 9, 15, tzinfo=timezone.utc))), 0.0, self.location)
            nav_start = self._tt_to_local_date(nm_tt)[0] + timedelta(days=1)
        return nav_start

    def _compute_guru_purnima(self, year: int, lun_unique: List[Tuple[str, float]]) -> date:
        """Guru Purnima: July full moon."""
        guru = None
        for kind, jd_tt in lun_unique:
            if kind == "FullMoon":
                d_local, _ = self._tt_to_local_date(jd_tt)
                if d_local.year == year and d_local.month == 7:
                    guru = d_local
                    break
        if guru is None:
            fm_tt = find_phase_time_tt_near(jd_tt_from_jd_ut(to_julian_day(datetime(year, 7, 15, tzinfo=timezone.utc))), 180.0, self.location)
            guru = self._tt_to_local_date(fm_tt)[0]
        return guru

    def _compute_raksha_bandhan(self, year: int, lun_unique: List[Tuple[str, float]]) -> date:
        """Raksha Bandhan: August full moon."""
        raksha = None
        for kind, jd_tt in lun_unique:
            if kind == "FullMoon":
                d_local, _ = self._tt_to_local_date(jd_tt)
                if d_local.year == year and d_local.month == 8:
                    raksha = d_local
                    break
        if raksha is None:
            fm_tt = find_phase_time_tt_near(jd_tt_from_jd_ut(to_julian_day(datetime(year, 8, 15, tzinfo=timezone.utc))), 180.0, self.location)
            raksha = self._tt_to_local_date(fm_tt)[0]
        return raksha

    def _compute_makar_sankranti(self, year: int) -> date:
        """Makar Sankranti: sidereal Sun enters Capricorn (270° Lahiri)."""
        jan_guess_tt = jd_tt_from_jd_ut(to_julian_day(datetime(year, 1, 14, tzinfo=timezone.utc)))
        ingress_tt = find_solar_sidereal_ingress_tt_near(jan_guess_tt, 270.0)
        local_date, _ = self._tt_to_local_date(ingress_tt)
        return local_date

    def _compute_vishuva(self, year: int) -> date:
        """Vishuva (March equinox, approximate) by minimizing |λ☉| over ±3 days."""
        march_guess_tt = jd_tt_from_jd_ut(to_julian_day(datetime(year, 3, 20, tzinfo=timezone.utc)))
        best_j = None
        best_diff = 1e9
        for i in range(-3, 4):
            j = march_guess_tt + i
            diff = abs(((sun_ecliptic_longitude_deg(j) - 0.0 + 180.0) % 360.0) - 180.0)
            if diff < best_diff:
                best_diff = diff
                best_j = j
        local_date, _ = self._tt_to_local_date(best_j)
        return local_date

    # ------------------------------
    # Additional holiday convenience
    # ------------------------------

    def _compute_maha_shivaratri_holiday(self, year: int) -> date:
        """Wrapper for Maha Shivaratri using internal lunar logic."""
        lunations = self._precompute_lunations(year)
        return self._compute_maha_shivaratri(year, lunations)

    def _compute_holi_holiday(self, year: int) -> date:
        """Wrapper for Holi (Phalguna Purnima)."""
        lunations = self._precompute_lunations(year)
        return self._compute_holi(year, lunations)

    def _compute_mahavir_jayanti_holiday(self, year: int) -> date:
        """Mahavir Jayanti (Chaitra Shukla Trayodashi, simplified).

        Approximation: take the April full moon (Chaitra Purnima) and search
        nearby days for sunrise tithi == 13 (Trayodashi).
        """
        lun = self._precompute_lunations(year)
        # Pick April full moon or nearest to Apr 15
        fm_tt = None
        best = (1e9, None)
        target_jd = to_julian_day(datetime(year, 4, 15, tzinfo=timezone.utc))
        for kind, jd_tt in lun:
            if kind != "FullMoon":
                continue
            d_local, _ = self._tt_to_local_date(jd_tt)
            if d_local.year == year and d_local.month == 4:
                fm_tt = jd_tt
                break
            # track nearest to Apr 15 if April not found
            diff = abs(jd_tt - target_jd)
            if diff < best[0]:
                best = (diff, jd_tt)
        if fm_tt is None:
            fm_tt = best[1]
        fm_local, _ = self._tt_to_local_date(fm_tt)
        # Search a small window around two days before full moon
        for delta in (-3, -2, -1, 0, 1):
            candidate = fm_local + timedelta(days=delta - 2)
            if self.tithi_at_sunrise(candidate) == 13:
                return candidate
        return fm_local + timedelta(days=-2)

    def _compute_good_friday_holiday(self, year: int) -> date:
        """Good Friday: two days before Easter Sunday (Gregorian computus)."""
        easter = self._easter_sunday_gregorian(year)
        return easter - timedelta(days=2)

    def _compute_buddha_purnima_holiday(self, year: int) -> date:
        """Buddha Purnima (Vaishakha Purnima): prefer Purnima at sunrise in May."""
        lun = self._precompute_lunations(year)
        candidates: List[date] = []
        for kind, jd_tt in lun:
            if kind == "FullMoon":
                d_local, _ = self._tt_to_local_date(jd_tt)
                if d_local.year == year and d_local.month in (4, 5):
                    candidates.append(d_local)
        for d in candidates:
            if d.month == 5 and self.tithi_at_sunrise(d) == 15:
                return d
        for d in candidates:
            if d.month == 5:
                return d
        for d in candidates:
            if self.tithi_at_sunrise(d) == 15:
                return d
        return candidates[0] if candidates else date(year, 5, 1)

    def _compute_janmashtami_holiday(self, year: int) -> date:
        """Janmashtami (Bhadrapada Krishna Ashtami, simplified).

        Approximation: take the August full moon and search the next two weeks
        for a day where sunset tithi == 23 (Krishna Ashtami).
        """
        lun = self._precompute_lunations(year)
        fm_local = None
        # Prefer August full moon; otherwise take September
        for month_target in (8, 9):
            for kind, jd_tt in lun:
                if kind != "FullMoon":
                    continue
                d_local, _ = self._tt_to_local_date(jd_tt)
                if d_local.year == year and d_local.month == month_target:
                    fm_local = d_local
                    break
            if fm_local is not None:
                break
        if fm_local is None:
            # Fallback: nearest to Aug 15
            best = (1e9, None)
            target_jd = to_julian_day(datetime(year, 8, 15, tzinfo=timezone.utc))
            for kind, jd_tt in lun:
                if kind != "FullMoon":
                    continue
                diff = abs(jd_tt - target_jd)
                if diff < best[0]:
                    best = (diff, self._tt_to_local_date(jd_tt)[0])
            fm_local = best[1]
        # Scan next fortnight for Krishna Ashtami (tithi 23)
        for d in range(1, 15):
            day = fm_local + timedelta(days=d)
            if self.tithi_at_sunset(day) == 23:
                return day
        # Fallback approximate 8 days after full moon
        return fm_local + timedelta(days=8)

    def _compute_dussehra_holiday(self, year: int) -> date:
        """Dussehra (Vijayadashami): ensure Dashami at Aparahna in Ashwin."""
        lun = self._precompute_lunations(year)
        start = self._compute_navratri_start(year, lun)
        seed = start + timedelta(days=9)
        if self._aparahna_tithi(seed) == 10:
            return seed
        for delta in (-1, 1, -2, 2):
            d = seed + timedelta(days=delta)
            if self._aparahna_tithi(d) == 10:
                return d
        return seed

    def _compute_diwali_deepavali_holiday(self, year: int) -> date:
        """Diwali/Deepavali convenience wrapper."""
        lun = self._precompute_lunations(year)
        return self._compute_diwali(year, lun)

    def _compute_guru_nanak_jayanti_holiday(self, year: int) -> date:
        """Guru Nanak Jayanti (Kartik Purnima): prefer Purnima at sunrise in Nov."""
        lun = self._precompute_lunations(year)
        candidates: List[date] = []
        for kind, jd_tt in lun:
            if kind != "FullMoon":
                continue
            d_local, _ = self._tt_to_local_date(jd_tt)
            if d_local.year == year and d_local.month in (10, 11):
                candidates.append(d_local)
        for d in candidates:
            if d.month == 11 and self.tithi_at_sunrise(d) == 15:
                return d
        for d in candidates:
            if d.month == 11:
                return d
        for d in candidates:
            if self.tithi_at_sunrise(d) == 15:
                return d
        return candidates[0] if candidates else date(year, 11, 1)

    def _easter_sunday_gregorian(self, year: int) -> date:
        """Compute Easter Sunday (Gregorian) using Anonymous Gregorian algorithm."""
        a = year % 19
        b = year // 100
        c = year % 100
        d = b // 4
        e = b % 4
        f = (b + 8) // 25
        g = (b - f + 1) // 3
        h = (19 * a + b - d - g + 15) % 30
        i = c // 4
        k = c % 4
        L = (32 + 2 * e + 2 * i - h - k) % 7
        m = (a + 11 * h + 22 * L) // 451
        month = (h + L - 7 * m + 114) // 31
        day = ((h + L - 7 * m + 114) % 31) + 1
        return date(year, month, day)