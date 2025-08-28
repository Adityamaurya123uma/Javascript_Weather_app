#!/usr/bin/env python3
"""
master_hr_holiday_generator_fullscale.py
========================================
High-accuracy Hindu holiday generator — Option B (practical full-scale)

Save as: master_hr_holiday_generator_fullscale.py
Run:      python master_hr_holiday_generator_fullscale.py 2026 IN
"""

from __future__ import annotations
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import sys

RAD = math.pi / 180.0
DEG = 180.0 / math.pi
EARTH_RADIUS_KM = 6378.137


def norm_deg(x: float) -> float:
    x = x % 360.0
    if x < 0:
        x += 360.0
    return x


def wrap180(x: float) -> float:
    return (x + 180.0) % 360.0 - 180.0


# ----------------------
# Locations (extendable)
# ----------------------
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


# ----------------------
# Julian Day & TT/UT helpers
# ----------------------

def to_julian_day(dt: datetime) -> float:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
    y = dt.year
    m = dt.month
    D = dt.day + (dt.hour + (dt.minute + dt.second / 60.0) / 60.0) / 24.0
    if m <= 2:
        y -= 1
        m += 12
    A = y // 100
    B = 2 - A + (A // 4)
    JD = math.floor(365.25 * (y + 4716)) + math.floor(30.6001 * (m + 1)) + D + B - 1524.5
    return JD


def from_julian_day(jd: float) -> datetime:
    Z = int(jd + 0.5)
    F = (jd + 0.5) - Z
    if Z < 2299161:
        A = Z
    else:
        alpha = int((Z - 1867216.25) / 36524.25)
        A = Z + 1 + alpha - int(alpha / 4)
    B = A + 1524
    C = int((B - 122.1) / 365.25)
    D = int(365.25 * C)
    E = int((B - D) / 30.6001)
    day = B - D - int(30.6001 * E) + F
    month = E - 1 if E < 14 else E - 13
    year = C - 4716 if month > 2 else C - 4715
    day_int = int(day)
    frac = day - day_int
    hours = int(frac * 24.0)
    minutes = int((frac * 24.0 - hours) * 60.0)
    seconds = int(round((((frac * 24.0 - hours) * 60.0) - minutes) * 60.0))
    if seconds == 60:
        seconds = 59
    return datetime(year, month, day_int, hours, minutes, seconds, tzinfo=timezone.utc)


def T_centuries(jd: float) -> float:
    return (jd - 2451545.0) / 36525.0


# ----------------------
# ΔT estimate (seconds)
# ----------------------

def delta_t_seconds_approx(year: int, month: int = 1) -> float:
    y = year + (month - 0.5) / 12.0
    if 2005 <= y <= 2050:
        t = y - 2000
        dt = 62.92 + 0.32217 * t + 0.005589 * t * t
        return dt
    if 1900 <= y < 2005:
        t = y - 1900
        dt = -2.79 + 1.494119 * t - 0.0598939 * t * t + 0.0061966 * t * t * t - 0.000197 * t * t * t * t
        return dt
    if y >= 2050:
        t = y - 2000
        dt = 62.92 + 0.32217 * t + 0.005589 * t * t
        return dt
    return 68.0


def jd_tt_from_jd_ut(jd_ut: float) -> float:
    dt_s = delta_t_seconds_approx(from_julian_day(jd_ut).year, from_julian_day(jd_ut).month)
    return jd_ut + dt_s / 86400.0


def jd_ut_from_jd_tt(jd_tt: float) -> float:
    dt_s = delta_t_seconds_approx(from_julian_day(jd_tt).year, from_julian_day(jd_tt).month)
    return jd_tt - dt_s / 86400.0


# ----------------------
# Obliquity & nutation (approx)
# ----------------------

def mean_obliquity_deg(T: float) -> float:
    secs = 84381.406 - 46.836769 * T - 0.0001831 * T * T + 0.00200340 * T * T * T
    return secs / 3600.0


def nutation_approx(jd: float) -> tuple[float, float]:
    T = T_centuries(jd)
    Omega = math.radians(norm_deg(125.04452 - 1934.136261 * T + 0.0020708 * T * T))
    D = math.radians(norm_deg(297.85036 + 445267.111480 * T))
    delta_psi = (-17.20 * math.sin(Omega) - 1.32 * math.sin(2 * D)) / 3600.0
    delta_eps = (9.20 * math.cos(Omega) + 0.57 * math.cos(2 * D)) / 3600.0
    return delta_psi, delta_eps


# ----------------------
# Sun (TT) ecliptic longitude — Meeus improved
# ----------------------

def sun_ecliptic_longitude_deg(jd_tt: float) -> float:
    T = T_centuries(jd_tt)
    L0 = 280.4664567 + 36000.76982779 * T + 0.0003032028 * T * T
    M = 357.52911 + 35999.0502909 * T - 0.0001536 * T * T
    M_rad = math.radians(M)
    C = (1.914602 - 0.004817 * T - 0.000014 * T * T) * math.sin(M_rad)
    C += (0.019993 - 0.000101 * T) * math.sin(2 * M_rad) + 0.000289 * math.sin(3 * M_rad)
    true_long = L0 + C
    omega = 125.04 - 1934.136 * T
    lam = true_long - 0.00569 - 0.00478 * math.sin(math.radians(omega))
    return norm_deg(lam)


# ----------------------
# Moon (TT) extended periodic terms (reduced ELP-like)
# ----------------------

def moon_ecliptic_longitude_and_distance(jd_tt: float) -> tuple[float, float]:
    T = T_centuries(jd_tt)
    Lp = norm_deg(218.3164477 + 481267.88123421 * T - 0.0015786 * T * T + T ** 3 / 538841.0 - T ** 4 / 65194000.0)
    D = norm_deg(297.8501921 + 445267.1114034 * T - 0.0018819 * T * T)
    M = norm_deg(357.5291092 + 35999.0502909 * T - 0.0001536 * T * T)
    Mp = norm_deg(134.9633964 + 477198.8675055 * T + 0.0087414 * T * T)
    F = norm_deg(93.2720950 + 483202.0175233 * T - 0.0036539 * T * T)

    D_r = math.radians(D)
    M_r = math.radians(M)
    Mp_r = math.radians(Mp)
    F_r = math.radians(F)
    E = 1 - 0.002516 * T - 0.0000074 * T * T

    terms = [
        (6288774, 0, 0, 1, 0, 0, -20905355),
        (1274027, 2, 0, -1, 0, 0, -3699111),
        (658314, 2, 0, 0, 0, 0, -2955968),
        (213618, 0, 0, 2, 0, 0, -569925),
        (-185116, 0, 1, 0, 0, 1, 48888),
        (-114332, 0, 0, 0, 2, 0, -3149),
        (58793, 2, 0, -2, 0, 0, 246158),
        (57066, 2, -1, -1, 0, 1, -152138),
        (53322, 2, 0, 1, 0, 0, -170733),
        (45758, 2, -1, 0, 0, 1, -204586),
        (-40923, 0, 1, -1, 0, 1, -129620),
        (-34720, 1, 0, 0, 0, 0, 108743),
        (-30383, 0, 1, 1, 0, 1, 104755),
        (15327, 2, 0, 0, -2, 0, 10321),
        (-12528, 0, 0, 1, 2, 0, 0),
        (10980, 0, 0, 1, -2, 0, 79661),
        (10675, 4, 0, -1, 0, 0, -34782),
        (10034, 0, 0, 3, 0, 0, -23210),
        (8548, 4, 0, -2, 0, 0, 0),
        (-7888, 2, 1, -1, 0, 1, 0),
        (-6766, 2, 1, 0, 0, 1, 0),
        (-5163, 1, 0, -1, 0, 0, 0),
        (4987, 1, 1, 0, 0, 1, 0),
        (4036, 2, -1, 1, 0, 1, 0),
        (3994, 2, 0, 2, 0, 0, 0),
        (3861, 4, 0, 0, 0, 0, 0),
        (3665, 2, 0, -3, 0, 0, 0),
        (-2689, 0, 1, -2, 0, 1, 0),
    ]

    sigma_l = 0.0
    sigma_r = 0.0
    for coef, d_m, m_m, mp_m, f_m, e_flag, r_coef in terms:
        arg = d_m * D_r + m_m * M_r + mp_m * Mp_r + f_m * F_r
        efac = (E ** abs(m_m)) if e_flag else 1.0
        sigma_l += coef * efac * math.sin(arg)
        sigma_r += r_coef * efac * math.cos(arg)

    lam = Lp + sigma_l / 1e6
    dist = 385000.56 + sigma_r / 1000.0
    return norm_deg(lam), dist


# ----------------------
# Topocentric correction for Moon (parallax)
# ----------------------

def topocentric_moon_longitude(jd_tt: float, lat_deg: float, lon_deg: float, height_m: float = 0.0) -> float:
    lam_geo_deg, dist_km = moon_ecliptic_longitude_and_distance(jd_tt)
    parallax_rad = math.asin(EARTH_RADIUS_KM / dist_km)
    # approximate shift using small-angle approach (not full rigorous transform but effective)
    # Convert geocentric ecl lon to RA/Dec approximately then correct; simplified for speed.
    lam = math.radians(lam_geo_deg)
    eps = math.radians(mean_obliquity_deg(T_centuries(jd_tt)))
    x = math.cos(lam)
    y = math.cos(eps) * math.sin(lam)
    z = math.sin(eps) * math.sin(lam)
    ra = math.atan2(y, x)
    dec = math.atan2(z, math.sqrt(x * x + y * y))
    # compute local sidereal, hour angle
    jd_ut = jd_ut_from_jd_tt(jd_tt)
    T = (jd_ut - 2451545.0) / 36525.0
    GMST = norm_deg(280.46061837 + 360.98564736629 * (jd_ut - 2451545.0) + 0.000387933 * T * T - T * T * T / 38710000.0)
    LST_deg = norm_deg(GMST + lon_deg)
    LST = math.radians(LST_deg)
    HA = LST - ra
    lat = math.radians(lat_deg)
    # small corrections from parallax
    delta_ra = -math.asin(math.sin(parallax_rad) * math.sin(HA) / math.cos(dec))
    delta_dec = math.asin((math.sin(dec) - math.sin(parallax_rad) * math.sin(lat)) * math.cos(delta_ra) - math.cos(dec) * math.sin(delta_ra) * math.sin(lat))
    ra_top = ra + delta_ra
    dec_top = dec + delta_dec
    # back to ecliptic longitude
    sin_lam = math.sin(ra_top) * math.cos(eps) + math.tan(dec_top) * math.sin(eps)
    cos_lam = math.cos(ra_top)
    lam_top = math.atan2(sin_lam, cos_lam)
    return norm_deg(math.degrees(lam_top))


# ----------------------
# Sun RA/Dec & altitude helpers
# ----------------------

def sun_ra_dec_tt(jd_tt: float) -> tuple[float, float]:
    lam = math.radians(sun_ecliptic_longitude_deg(jd_tt))
    eps = math.radians(mean_obliquity_deg(T_centuries(jd_tt)))
    x = math.cos(lam)
    y = math.cos(eps) * math.sin(lam)
    z = math.sin(eps) * math.sin(lam)
    ra = math.atan2(y, x)
    dec = math.atan2(z, math.sqrt(x * x + y * y))
    return ra, dec


def sun_altitude_deg_at_ut(jd_ut: float, lat_deg: float, lon_deg: float) -> float:
    # compute TT near UT for RA/Dec
    jd_tt = jd_tt_from_jd_ut(jd_ut)
    ra, dec = sun_ra_dec_tt(jd_tt)
    T = (jd_ut - 2451545.0) / 36525.0
    GMST = norm_deg(280.46061837 + 360.98564736629 * (jd_ut - 2451545.0) + 0.000387933 * T * T - T * T * T / 38710000.0)
    LST_deg = norm_deg(GMST + lon_deg)
    LST = math.radians(LST_deg)
    H = LST - ra
    lat = math.radians(lat_deg)
    alt = math.degrees(math.asin(math.sin(dec) * math.sin(lat) + math.cos(dec) * math.cos(lat) * math.cos(H)))
    return alt


# ----------------------
# Sunrise/sunset robust solvers (bisection)
# ----------------------

def _find_sun_event_jd_utc(date_local: datetime, loc: Location, target_alt: float, is_rise: bool, step_minutes: int = 10) -> float:
    # local midnight as aware datetime
    tz = timezone(timedelta(hours=loc.tz))
    local_mid = datetime(date_local.year, date_local.month, date_local.day, 0, 0, 0, tzinfo=tz)
    utc_start = local_mid.astimezone(timezone.utc)
    jd_start = to_julian_day(utc_start)

    def f(jd):
        return sun_altitude_deg_at_ut(jd, loc.lat, loc.lon) - target_alt

    # Scan the local day to find a bracket where f changes sign in desired direction
    total_minutes = 24 * 60
    step_days = step_minutes / 1440.0
    samples = []
    jd = jd_start
    for _ in range(0, total_minutes // step_minutes + 1):
        samples.append((jd, f(jd)))
        jd += step_days

    bracket = None
    for (a_jd, a_f), (b_jd, b_f) in zip(samples, samples[1:]):
        if a_f == 0.0:
            return a_jd
        if b_f == 0.0:
            return b_jd
        crossed = (a_f <= 0.0 and b_f >= 0.0) if is_rise else (a_f >= 0.0 and b_f <= 0.0)
        if crossed:
            bracket = (a_jd, a_f, b_jd, b_f)
            break

    if bracket is None:
        # fallback: widen search +/- 1 day
        for day_offset in (-1, 1):
            jd0 = jd_start + day_offset
            a_f = f(jd0)
            b_f = f(jd0 + step_days)
            if is_rise and a_f <= 0.0 and b_f >= 0.0:
                bracket = (jd0, a_f, jd0 + step_days, b_f)
                break
            if (not is_rise) and a_f >= 0.0 and b_f <= 0.0:
                bracket = (jd0, a_f, jd0 + step_days, b_f)
                break
    if bracket is None:
        # As a last resort, return noon
        return jd_start + 0.5

    a, fa, b, fb = bracket
    # Bisection refine
    for _ in range(60):
        m = 0.5 * (a + b)
        fm = f(m)
        if abs(fm) < 1e-7 or (b - a) < 1e-8:
            return m
        # keep the subinterval that contains the root with sign change matching desired direction
        if is_rise:
            # we want crossing from negative to positive overall
            if fa <= 0.0 and fm <= 0.0:
                a, fa = m, fm
            else:
                b, fb = m, fm
        else:
            if fa >= 0.0 and fm >= 0.0:
                a, fa = m, fm
            else:
                b, fb = m, fm
    return 0.5 * (a + b)


def sunrise_jd_utc(date_local: datetime, loc: Location) -> float:
    return _find_sun_event_jd_utc(date_local, loc, target_alt=-0.833, is_rise=True)


def sunset_jd_utc(date_local: datetime, loc: Location) -> float:
    return _find_sun_event_jd_utc(date_local, loc, target_alt=-0.833, is_rise=False)


# ----------------------
# Lunar phase angle & tithi (TT, topocentric/geocentric)
# ----------------------

def lunar_phase_angle_tt_deg(jd_tt: float, use_topo: bool, loc: Location) -> float:
    if use_topo:
        lam_m = topocentric_moon_longitude(jd_tt, loc.lat, loc.lon, loc.height_m)
    else:
        lam_m, _ = moon_ecliptic_longitude_and_distance(jd_tt)
    lam_s = sun_ecliptic_longitude_deg(jd_tt)
    return norm_deg(lam_m - lam_s)


def tithi_at_local_sunrise(date_local: datetime, loc: Location) -> int:
    jd_sunrise_ut = sunrise_jd_utc(date_local, loc)
    jd_tt = jd_tt_from_jd_ut(jd_sunrise_ut)
    ang = lunar_phase_angle_tt_deg(jd_tt, False, loc)  # geocentric for stability
    return int(ang // 12.0) + 1


def tithi_at_local_sunset(date_local: datetime, loc: Location) -> int:
    jd_sunset_ut = sunset_jd_utc(date_local, loc)
    jd_tt = jd_tt_from_jd_ut(jd_sunset_ut)
    ang = lunar_phase_angle_tt_deg(jd_tt, False, loc)  # geocentric
    return int(ang // 12.0) + 1


# ----------------------
# Phase root-finders (TT)
# ----------------------

def find_phase_time_tt_near(jd_tt_guess: float, target_deg: float, loc: Location) -> float:
    x0 = jd_tt_guess - 1.0
    x1 = jd_tt_guess + 1.0
    def f(jd_tt):
        d = lunar_phase_angle_tt_deg(jd_tt, True, loc) - target_deg
        if d > 180.0:
            d -= 360.0
        if d < -180.0:
            d += 360.0
        return d
    y0 = f(x0)
    y1 = f(x1)
    for _ in range(60):
        if abs(y1 - y0) < 1e-12:
            break
        x2 = x1 - y1 * (x1 - x0) / (y1 - y0)
        y2 = f(x2)
        x0, y0, x1, y1 = x1, y1, x2, y2
        if abs(y1) < 1e-8:
            break
    return x1


# ----------------------
# Sidereal (Lahiri) conversion & ingress finder
# ----------------------

def lahiri_ayanamsa_deg(jd_tt: float) -> float:
    # Approximate Lahiri (Chitra Paksha) ayanamsa around J2000.0
    # Base value near J2000 (2000-01-01 12:00 TT) and linear drift ~1.39626 deg/century
    T = T_centuries(jd_tt)
    base_j2000 = 23.85308  # degrees (approximate Lahiri at J2000)
    drift_deg_per_century = 1.3962634  # precession in longitude per Julian century
    # small quadratic term improves over centuries; sign chosen to align with common tables
    quad = -0.000044 * (T * T)
    return norm_deg(base_j2000 + drift_deg_per_century * T + quad)


def to_sidereal_deg(lambda_tropical_deg: float, jd_tt: float) -> float:
    return norm_deg(lambda_tropical_deg - lahiri_ayanamsa_deg(jd_tt))


def find_solar_sidereal_ingress_tt_near(jd_tt_guess: float, target_sid_deg: float) -> float:
    x0 = jd_tt_guess - 2.0
    x1 = jd_tt_guess + 2.0
    def f(jd_tt):
        val = ((to_sidereal_deg(sun_ecliptic_longitude_deg(jd_tt), jd_tt) - target_sid_deg + 180.0) % 360.0) - 180.0
        return val
    y0 = f(x0)
    y1 = f(x1)
    for _ in range(80):
        if abs(y1 - y0) < 1e-12:
            break
        x2 = x1 - y1 * (x1 - x0) / (y1 - y0)
        y2 = f(x2)
        x0, y0, x1, y1 = x1, y1, x2, y2
        if abs(y1) < 1e-8:
            break
    return x1


# ----------------------
# Festivals assembly
# ----------------------

@dataclass
class Location:
    lat: float
    lon: float
    tz: float
    height_m: float = 0.0


def find_festivals_high_accuracy(year: int, loc: Location) -> dict:
    festivals = {}
    # Precompute lunations (TT)
    lun_list = []
    for month in range(1, 13):
        guess_ut = to_julian_day(datetime(year, month, 15, tzinfo=timezone.utc))
        guess_tt = jd_tt_from_jd_ut(guess_ut)
        nm_tt = find_phase_time_tt_near(guess_tt, 0.0, loc)
        fm_tt = find_phase_time_tt_near(guess_tt, 180.0, loc)
        lun_list.append(("NewMoon", nm_tt))
        lun_list.append(("FullMoon", fm_tt))
    # unique+sorted by TT
    lun_unique = sorted({(k, round(v, 6)) for k, v in lun_list}, key=lambda x: x[1])

    def tt_to_local_date(jd_tt):
        jd_ut = jd_ut_from_jd_tt(jd_tt)
        dt_utc = from_julian_day(jd_ut)
        return (dt_utc + timedelta(hours=loc.tz)).date(), jd_ut

    # Diwali: Kartika Amavasya (require tithi 30 at local sunset)
    diwali_candidates = []
    for k, jd_tt in lun_unique:
        if k == "NewMoon":
            d_local, jd_ut = tt_to_local_date(jd_tt)
            if d_local.year == year and d_local.month in (10, 11):
                diwali_candidates.append((d_local, jd_tt))
    if not diwali_candidates:
        guess_ut = to_julian_day(datetime(year, 11, 15, tzinfo=timezone.utc))
        nm_tt = find_phase_time_tt_near(jd_tt_from_jd_ut(guess_ut), 0.0, loc)
        diwali_candidates.append((tt_to_local_date(nm_tt)[0], nm_tt))
    # choose closest to Nov 1
    target_jd = to_julian_day(datetime(year, 11, 1, tzinfo=timezone.utc))
    diwali_candidates.sort(key=lambda x: abs(x[1] - target_jd))
    candidate_date = diwali_candidates[0][0]

    # Ensure Amavasya (tithi 30) prevails at local sunset, else adjust ±1–2 days
    diwali_date = candidate_date
    if tithi_at_local_sunset(candidate_date, loc) != 30:
        found = None
        for delta in (1, -1, 2, -2):
            try_dt = candidate_date + timedelta(days=delta)
            if tithi_at_local_sunset(try_dt, loc) == 30:
                found = try_dt
                break
        if found is not None:
            diwali_date = found
        else:
            # fallback to sunrise rule
            if tithi_at_local_sunrise(candidate_date, loc) == 30:
                diwali_date = candidate_date
            else:
                for delta in (1, -1, 2, -2):
                    try_dt = candidate_date + timedelta(days=delta)
                    if tithi_at_local_sunrise(try_dt, loc) == 30:
                        diwali_date = try_dt
                        break
    festivals["Diwali"] = diwali_date.isoformat()

    # Holi: Phalguna Purnima (full moon around March) — date of full moon (local date)
    holi_tt = None
    for k, jd_tt in lun_unique:
        if k == "FullMoon":
            d_local, _ = tt_to_local_date(jd_tt)
            if d_local.year == year and d_local.month in (2, 3, 4):
                if d_local.month == 3:
                    holi_tt = jd_tt
                    break
                if holi_tt is None:
                    holi_tt = jd_tt
    if holi_tt is None:
        holi_guess_tt = jd_tt_from_jd_ut(to_julian_day(datetime(year, 3, 15, tzinfo=timezone.utc)))
        holi_tt = find_phase_time_tt_near(holi_guess_tt, 180.0, loc)
    festivals["Holi"] = tt_to_local_date(holi_tt)[0].isoformat()

    # Maha Shivaratri: day before new moon in Feb/Mar
    nm_choice = None
    for k, jd_tt in lun_unique:
        if k == "NewMoon":
            d_local, _ = tt_to_local_date(jd_tt)
            if d_local.year == year and d_local.month in (2, 3):
                nm_choice = d_local
                break
    if nm_choice is None:
        nm_tt = find_phase_time_tt_near(jd_tt_from_jd_ut(to_julian_day(datetime(year, 2, 15, tzinfo=timezone.utc))), 0.0, loc)
        nm_choice = tt_to_local_date(nm_tt)[0]
    festivals["Maha Shivaratri"] = (nm_choice - timedelta(days=1)).isoformat()

    # Navratri (start): day after Ashwin Amavasya (Sep/Oct new moon)
    nav_start = None
    for k, jd_tt in lun_unique:
        if k == "NewMoon":
            d_local, _ = tt_to_local_date(jd_tt)
            if d_local.year == year and d_local.month in (9, 10):
                nav_start = (d_local + timedelta(days=1))
                break
    if nav_start is None:
        nm_tt = find_phase_time_tt_near(jd_tt_from_jd_ut(to_julian_day(datetime(year, 9, 15, tzinfo=timezone.utc))), 0.0, loc)
        nav_start = tt_to_local_date(nm_tt)[0] + timedelta(days=1)
    festivals["Navratri (Start)"] = nav_start.isoformat()

    # Guru Purnima: July full moon
    guru = None
    for k, jd_tt in lun_unique:
        if k == "FullMoon":
            d_local, _ = tt_to_local_date(jd_tt)
            if d_local.year == year and d_local.month == 7:
                guru = d_local
                break
    if guru is None:
        fm_tt = find_phase_time_tt_near(jd_tt_from_jd_ut(to_julian_day(datetime(year, 7, 15, tzinfo=timezone.utc))), 180.0, loc)
        guru = tt_to_local_date(fm_tt)[0]
    festivals["Guru Purnima"] = guru.isoformat()

    # Raksha Bandhan: Aug full moon
    raksha = None
    for k, jd_tt in lun_unique:
        if k == "FullMoon":
            d_local, _ = tt_to_local_date(jd_tt)
            if d_local.year == year and d_local.month == 8:
                raksha = d_local
                break
    if raksha is None:
        fm_tt = find_phase_time_tt_near(jd_tt_from_jd_ut(to_julian_day(datetime(year, 8, 15, tzinfo=timezone.utc))), 180.0, loc)
        raksha = tt_to_local_date(fm_tt)[0]
    festivals["Raksha Bandhan"] = raksha.isoformat()

    # Karwa Chauth: approximate 4 days before Diwali (still approximate)
    try:
        di = datetime.fromisoformat(festivals["Diwali"])
        festivals["Karwa Chauth"] = (di - timedelta(days=4)).date().isoformat()
    except Exception:
        festivals["Karwa Chauth"] = None

    # Makar Sankranti: sidereal Sun enters Capricorn (270° sidereal)
    jan_guess_tt = jd_tt_from_jd_ut(to_julian_day(datetime(year, 1, 14, tzinfo=timezone.utc)))
    ingress_tt = find_solar_sidereal_ingress_tt_near(jan_guess_tt, 270.0)
    festivals["Makar Sankranti"] = tt_to_local_date(ingress_tt)[0].isoformat()

    # Vishuva (March equinox, approximate)
    march_guess_tt = jd_tt_from_jd_ut(to_julian_day(datetime(year, 3, 20, tzinfo=timezone.utc)))
    best_j = None
    best_diff = 1e9
    for i in range(-3, 4):
        j = march_guess_tt + i
        diff = abs(((sun_ecliptic_longitude_deg(j) - 0.0 + 180.0) % 360.0) - 180.0)
        if diff < best_diff:
            best_diff = diff
            best_j = j
    festivals["Vishuva (March Equinox approx)"] = tt_to_local_date(best_j)[0].isoformat()

    return festivals


# ----------------------
# CLI
# ----------------------

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
    result = find_festivals_high_accuracy(year, loc)
    import json
    print(json.dumps(result, indent=2))