from datetime import datetime, timedelta, timezone
from .locations import Location
from .time_utils import to_julian_day, jd_tt_from_jd_ut, jd_ut_from_jd_tt, from_julian_day
from .phase import tithi_at_local_sunrise, tithi_at_local_sunset, find_phase_time_tt_near
from .sidereal import find_solar_sidereal_ingress_tt_near
from .astro import sun_ecliptic_longitude_deg


def find_festivals_high_accuracy(year: int, loc: Location) -> dict:
    festivals = {}
    lun_list = []
    for month in range(1, 13):
        guess_ut = to_julian_day(datetime(year, month, 15, tzinfo=timezone.utc))
        guess_tt = jd_tt_from_jd_ut(guess_ut)
        nm_tt = find_phase_time_tt_near(guess_tt, 0.0, loc)
        fm_tt = find_phase_time_tt_near(guess_tt, 180.0, loc)
        lun_list.append(("NewMoon", nm_tt))
        lun_list.append(("FullMoon", fm_tt))
    lun_unique = sorted({(k, round(v, 6)) for k, v in lun_list}, key=lambda x: x[1])

    def tt_to_local_date(jd_tt):
        jd_ut = jd_ut_from_jd_tt(jd_tt)
        dt_utc = from_julian_day(jd_ut)
        return (dt_utc + timedelta(hours=loc.tz)).date(), jd_ut

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
    target_jd = to_julian_day(datetime(year, 11, 1, tzinfo=timezone.utc))
    diwali_candidates.sort(key=lambda x: abs(x[1] - target_jd))
    candidate_date = diwali_candidates[0][0]

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
            if tithi_at_local_sunrise(candidate_date, loc) == 30:
                diwali_date = candidate_date
            else:
                for delta in (1, -1, 2, -2):
                    try_dt = candidate_date + timedelta(days=delta)
                    if tithi_at_local_sunrise(try_dt, loc) == 30:
                        diwali_date = try_dt
                        break
    festivals["Diwali"] = diwali_date.isoformat()

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

    try:
        di = datetime.fromisoformat(festivals["Diwali"])
        festivals["Karwa Chauth"] = (di - timedelta(days=4)).date().isoformat()
    except Exception:
        festivals["Karwa Chauth"] = None

    jan_guess_tt = jd_tt_from_jd_ut(to_julian_day(datetime(year, 1, 14, tzinfo=timezone.utc)))
    ingress_tt = find_solar_sidereal_ingress_tt_near(jan_guess_tt, 270.0)
    festivals["Makar Sankranti"] = tt_to_local_date(ingress_tt)[0].isoformat()

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