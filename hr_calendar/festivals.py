from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone, date
from typing import Dict, List, Tuple, Callable, Any

from .locations import Location
from .time_utils import to_julian_day, jd_tt_from_jd_ut, jd_ut_from_jd_tt, from_julian_day
from .phase import tithi_at_local_sunrise, tithi_at_local_sunset, find_phase_time_tt_near, lunar_phase_angle_tt_deg
from .sidereal import find_solar_sidereal_ingress_tt_near
from .astro import sun_ecliptic_longitude_deg
from .utils import wrap180


@dataclass
class FestivalDetail:
    """Container for a single festival's computed outcome and supporting context.

    Fields:
    - name: Festival name
    - local_date: Observance local date (location's civil date)
    - iso: ISO-8601 string for local_date
    - rationale: Human-readable summary of the rule used and why this date was chosen
    - metadata: Opaque dict with supporting values (JDs, tithi checks, candidates)

    The metadata is intentionally a dict to allow additions without breaking callers.
    """
    name: str
    local_date: date
    iso: str
    rationale: str
    metadata: Dict[str, Any]


def _precompute_lunations(year: int, loc: Location) -> List[Tuple[str, float]]:
    """Find all new and full moons by scanning and bracketing, then refining.

    - Scans TT over the year with small steps to detect sign changes of
      wrap180(phase - target), for targets 0° (new) and 180° (full).
    - Each detected crossing is refined with the existing root finder.
    - Results are rounded and deduplicated, preserving previous behavior while
      improving robustness near month boundaries.
    """
    # Scan slightly beyond the year to catch boundary lunations
    start_utc = datetime(year, 1, 1, tzinfo=timezone.utc) - timedelta(days=1)
    end_utc = datetime(year, 12, 31, tzinfo=timezone.utc) + timedelta(days=2)
    jd_tt_start = jd_tt_from_jd_ut(to_julian_day(start_utc))
    jd_tt_end = jd_tt_from_jd_ut(to_julian_day(end_utc))

    step_days = 0.25  # 6-hour step for reliable bracketing
    lun_list: List[Tuple[str, float]] = []

    j = jd_tt_start
    prev_new = wrap180(lunar_phase_angle_tt_deg(j, False, loc) - 0.0)
    prev_full = wrap180(lunar_phase_angle_tt_deg(j, False, loc) - 180.0)

    while j < jd_tt_end:
        jn = j + step_days
        cur_new = wrap180(lunar_phase_angle_tt_deg(jn, False, loc) - 0.0)
        cur_full = wrap180(lunar_phase_angle_tt_deg(jn, False, loc) - 180.0)

        # Detect crossings for new moon
        if prev_new == 0.0 or cur_new == 0.0 or (prev_new < 0.0 and cur_new > 0.0) or (prev_new > 0.0 and cur_new < 0.0):
            guess = 0.5 * (j + jn)
            nm_tt = find_phase_time_tt_near(guess, 0.0, loc)
            lun_list.append(("NewMoon", nm_tt))

        # Detect crossings for full moon
        if prev_full == 0.0 or cur_full == 0.0 or (prev_full < 0.0 and cur_full > 0.0) or (prev_full > 0.0 and cur_full < 0.0):
            guess = 0.5 * (j + jn)
            fm_tt = find_phase_time_tt_near(guess, 180.0, loc)
            lun_list.append(("FullMoon", fm_tt))

        j = jn
        prev_new = cur_new
        prev_full = cur_full

    lun_unique = sorted({(k, round(v, 6)) for k, v in lun_list}, key=lambda x: x[1])
    return lun_unique


def _tt_to_local_date(jd_tt: float, loc: Location) -> Tuple[date, float]:
    """Convert TT to local civil date for the given location, returning (local_date, jd_ut)."""
    jd_ut = jd_ut_from_jd_tt(jd_tt)
    dt_utc = from_julian_day(jd_ut)
    return (dt_utc + timedelta(hours=loc.tz)).date(), jd_ut


def compute_diwali_detail(year: int, loc: Location, lun_unique: List[Tuple[str, float]]) -> FestivalDetail:
    """Compute Diwali (Kartik Amavasya) using sunset tithi.

    Rule implemented:
    - Select the new moon that falls in local Oct/Nov. If multiple, use the one closest to Nov 1 as a seed.
    - Choose the date on which Amavasya (tithi 30) prevails at local sunset; fallback to sunrise if needed.
    """
    diwali_candidates: List[Tuple[date, float]] = []
    for kind, jd_tt in lun_unique:
        if kind == "NewMoon":
            d_local, _ = _tt_to_local_date(jd_tt, loc)
            if d_local.year == year and d_local.month in (10, 11):
                diwali_candidates.append((d_local, jd_tt))
    if not diwali_candidates:
        guess_ut = to_julian_day(datetime(year, 11, 15, tzinfo=timezone.utc))
        nm_tt = find_phase_time_tt_near(jd_tt_from_jd_ut(guess_ut), 0.0, loc)
        diwali_candidates.append((_tt_to_local_date(nm_tt, loc)[0], nm_tt))

    target_jd = to_julian_day(datetime(year, 11, 1, tzinfo=timezone.utc))
    diwali_candidates.sort(key=lambda x: abs(x[1] - target_jd))
    seed_date = diwali_candidates[0][0]

    chosen = seed_date
    checks: List[Tuple[str, str, int]] = []
    t_sunset = tithi_at_local_sunset(seed_date, loc)
    checks.append((seed_date.isoformat(), "sunset", t_sunset))
    if t_sunset != 30:
        found = None
        for delta in (1, -1, 2, -2):
            try_dt = seed_date + timedelta(days=delta)
            t_sunset = tithi_at_local_sunset(try_dt, loc)
            checks.append((try_dt.isoformat(), "sunset", t_sunset))
            if t_sunset == 30:
                found = try_dt
                break
        if found is not None:
            chosen = found
        else:
            t_sunrise = tithi_at_local_sunrise(seed_date, loc)
            checks.append((seed_date.isoformat(), "sunrise", t_sunrise))
            if t_sunrise == 30:
                chosen = seed_date
            else:
                for delta in (1, -1, 2, -2):
                    try_dt = seed_date + timedelta(days=delta)
                    t_sunrise = tithi_at_local_sunrise(try_dt, loc)
                    checks.append((try_dt.isoformat(), "sunrise", t_sunrise))
                    if t_sunrise == 30:
                        chosen = try_dt
                        break

    rationale = "New moon in Oct/Nov; chose date where tithi 30 (Amavasya) prevails at sunset."
    detail = FestivalDetail(
        name="Diwali",
        local_date=chosen,
        iso=chosen.isoformat(),
        rationale=rationale,
        metadata={
            "candidates": [(d.isoformat(), jd) for d, jd in diwali_candidates],
            "tithi_checks": checks,
        },
    )
    return detail


def compute_holi_detail(year: int, loc: Location, lun_unique: List[Tuple[str, float]]) -> FestivalDetail:
    """Compute Holi (Phalguna Purnima) as the date of the March full moon (simplified)."""
    holi_tt = None
    chosen_local = None
    for kind, jd_tt in lun_unique:
        if kind == "FullMoon":
            d_local, _ = _tt_to_local_date(jd_tt, loc)
            if d_local.year == year and d_local.month in (2, 3, 4):
                if d_local.month == 3:
                    holi_tt = jd_tt
                    chosen_local = d_local
                    break
                if holi_tt is None:
                    holi_tt = jd_tt
                    chosen_local = d_local
    if holi_tt is None:
        holi_guess_tt = jd_tt_from_jd_ut(to_julian_day(datetime(year, 3, 15, tzinfo=timezone.utc)))
        holi_tt = find_phase_time_tt_near(holi_guess_tt, 180.0, loc)
        chosen_local = _tt_to_local_date(holi_tt, loc)[0]
    return FestivalDetail(
        name="Holi",
        local_date=chosen_local,
        iso=chosen_local.isoformat(),
        rationale="Full moon around March (Phalguna Purnima)",
        metadata={"phase_tt": holi_tt},
    )


def compute_maha_shivaratri_detail(year: int, loc: Location, lun_unique: List[Tuple[str, float]]) -> FestivalDetail:
    """Compute Maha Shivaratri as the day before the Feb/Mar new moon (simplified)."""
    nm_choice = None
    nm_tt = None
    for kind, jd_tt in lun_unique:
        if kind == "NewMoon":
            d_local, _ = _tt_to_local_date(jd_tt, loc)
            if d_local.year == year and d_local.month in (2, 3):
                nm_choice = d_local
                nm_tt = jd_tt
                break
    if nm_choice is None:
        nm_tt = find_phase_time_tt_near(jd_tt_from_jd_ut(to_julian_day(datetime(year, 2, 15, tzinfo=timezone.utc))), 0.0, loc)
        nm_choice = _tt_to_local_date(nm_tt, loc)[0]
    observance = nm_choice - timedelta(days=1)
    return FestivalDetail(
        name="Maha Shivaratri",
        local_date=observance,
        iso=observance.isoformat(),
        rationale="Day before the new moon in Phalguna (Feb/Mar)",
        metadata={"new_moon_local": nm_choice.isoformat(), "new_moon_tt": nm_tt},
    )


def compute_navratri_start_detail(year: int, loc: Location, lun_unique: List[Tuple[str, float]]) -> FestivalDetail:
    """Compute Navratri start as the day after Ashwin Amavasya (Sep/Oct new moon)."""
    nav_start = None
    nm_tt = None
    for kind, jd_tt in lun_unique:
        if kind == "NewMoon":
            d_local, _ = _tt_to_local_date(jd_tt, loc)
            if d_local.year == year and d_local.month in (9, 10):
                nav_start = d_local + timedelta(days=1)
                nm_tt = jd_tt
                break
    if nav_start is None:
        nm_tt = find_phase_time_tt_near(jd_tt_from_jd_ut(to_julian_day(datetime(year, 9, 15, tzinfo=timezone.utc))), 0.0, loc)
        nav_start = _tt_to_local_date(nm_tt, loc)[0] + timedelta(days=1)
    return FestivalDetail(
        name="Navratri (Start)",
        local_date=nav_start,
        iso=nav_start.isoformat(),
        rationale="Day after Ashwin Amavasya (Sep/Oct new moon)",
        metadata={"ashwin_new_moon_tt": nm_tt},
    )


def compute_guru_purnima_detail(year: int, loc: Location, lun_unique: List[Tuple[str, float]]) -> FestivalDetail:
    """Compute Guru Purnima as the July full moon."""
    guru = None
    fm_tt = None
    for kind, jd_tt in lun_unique:
        if kind == "FullMoon":
            d_local, _ = _tt_to_local_date(jd_tt, loc)
            if d_local.year == year and d_local.month == 7:
                guru = d_local
                fm_tt = jd_tt
                break
    if guru is None:
        fm_tt = find_phase_time_tt_near(jd_tt_from_jd_ut(to_julian_day(datetime(year, 7, 15, tzinfo=timezone.utc))), 180.0, loc)
        guru = _tt_to_local_date(fm_tt, loc)[0]
    return FestivalDetail(
        name="Guru Purnima",
        local_date=guru,
        iso=guru.isoformat(),
        rationale="Full moon in July",
        metadata={"full_moon_tt": fm_tt},
    )


def compute_raksha_bandhan_detail(year: int, loc: Location, lun_unique: List[Tuple[str, float]]) -> FestivalDetail:
    """Compute Raksha Bandhan as the August full moon."""
    raksha = None
    fm_tt = None
    for kind, jd_tt in lun_unique:
        if kind == "FullMoon":
            d_local, _ = _tt_to_local_date(jd_tt, loc)
            if d_local.year == year and d_local.month == 8:
                raksha = d_local
                fm_tt = jd_tt
                break
    if raksha is None:
        fm_tt = find_phase_time_tt_near(jd_tt_from_jd_ut(to_julian_day(datetime(year, 8, 15, tzinfo=timezone.utc))), 180.0, loc)
        raksha = _tt_to_local_date(fm_tt, loc)[0]
    return FestivalDetail(
        name="Raksha Bandhan",
        local_date=raksha,
        iso=raksha.isoformat(),
        rationale="Full moon in August",
        metadata={"full_moon_tt": fm_tt},
    )


def compute_karwa_chauth_detail(year: int, loc: Location, diwali_detail: FestivalDetail) -> FestivalDetail:
    """Compute Karwa Chauth approximately as 4 days before Diwali (placeholder rule)."""
    try:
        di = datetime.fromisoformat(diwali_detail.iso)
        kc = (di - timedelta(days=4)).date()
    except Exception:
        kc = None
    return FestivalDetail(
        name="Karwa Chauth",
        local_date=kc,
        iso=kc.isoformat() if kc else None,
        rationale="Approximate: 4 days before Diwali",
        metadata={"based_on": "Diwali", "diwali": diwali_detail.iso},
    )


def compute_makar_sankranti_detail(year: int, loc: Location) -> FestivalDetail:
    """Compute Makar Sankranti as sidereal Sun's ingress into Capricorn (270° Lahiri)."""
    jan_guess_tt = jd_tt_from_jd_ut(to_julian_day(datetime(year, 1, 14, tzinfo=timezone.utc)))
    ingress_tt = find_solar_sidereal_ingress_tt_near(jan_guess_tt, 270.0)
    local_date, _ = _tt_to_local_date(ingress_tt, loc)
    return FestivalDetail(
        name="Makar Sankranti",
        local_date=local_date,
        iso=local_date.isoformat(),
        rationale="Sidereal Sun enters Capricorn (270° Lahiri)",
        metadata={"ingress_tt": ingress_tt},
    )


def compute_vishuva_detail(year: int, loc: Location) -> FestivalDetail:
    """Compute March equinox date approximately by minimizing |λ☉| over ±3 days."""
    march_guess_tt = jd_tt_from_jd_ut(to_julian_day(datetime(year, 3, 20, tzinfo=timezone.utc)))
    best_j = None
    best_diff = 1e9
    for i in range(-3, 4):
        j = march_guess_tt + i
        diff = abs(((sun_ecliptic_longitude_deg(j) - 0.0 + 180.0) % 360.0) - 180.0)
        if diff < best_diff:
            best_diff = diff
            best_j = j
    local_date, _ = _tt_to_local_date(best_j, loc)
    return FestivalDetail(
        name="Vishuva (March Equinox approx)",
        local_date=local_date,
        iso=local_date.isoformat(),
        rationale="Approximate March equinox from solar longitude",
        metadata={"best_tt": best_j, "window_days": 3},
    )


def find_festival_details(year: int, loc: Location) -> Dict[str, FestivalDetail]:
    """Compute detailed festival info for the given year and location.

    This orchestrates precomputations (lunations) and calls dedicated per-festival
    functions. The result is a name→FestivalDetail mapping.
    """
    lun_unique = _precompute_lunations(year, loc)

    diwali = compute_diwali_detail(year, loc, lun_unique)
    holi = compute_holi_detail(year, loc, lun_unique)
    shiv = compute_maha_shivaratri_detail(year, loc, lun_unique)
    nav = compute_navratri_start_detail(year, loc, lun_unique)
    guru = compute_guru_purnima_detail(year, loc, lun_unique)
    raksha = compute_raksha_bandhan_detail(year, loc, lun_unique)
    makar = compute_makar_sankranti_detail(year, loc)
    vishuva = compute_vishuva_detail(year, loc)
    karwa = compute_karwa_chauth_detail(year, loc, diwali)

    details = {
        diwali.name: diwali,
        holi.name: holi,
        shiv.name: shiv,
        nav.name: nav,
        guru.name: guru,
        raksha.name: raksha,
        karwa.name: karwa,
        makar.name: makar,
        vishuva.name: vishuva,
    }
    return details


def find_festivals_high_accuracy(year: int, loc: Location) -> dict:
    """Backward-compatible simple mapping of festival name → ISO date string.

    Internally calls the detailed API and strips to date strings for
    compatibility with existing consumers.
    """
    details = find_festival_details(year, loc)
    simple = {}
    for name, det in details.items():
        simple[name] = det.iso
    return simple