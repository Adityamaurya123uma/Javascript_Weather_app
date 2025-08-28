import math

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