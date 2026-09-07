"""Fixed Lahiri / whole-sign D1 calculation using Swiss Ephemeris."""

from __future__ import annotations

from threading import RLock

import swisseph as swe

from layer1.ephemeris.common import julian_day, parse_utc, q6, sign_for


VEDIC_CONFIG_VERSION = "vedic-d1@1"
CLASSICAL_BODIES = {
    "sun": swe.SUN,
    "moon": swe.MOON,
    "mercury": swe.MERCURY,
    "venus": swe.VENUS,
    "mars": swe.MARS,
    "jupiter": swe.JUPITER,
    "saturn": swe.SATURN,
    "rahu": swe.MEAN_NODE,
}
NAKSHATRAS = (
    "ashvini", "bharani", "krittika", "rohini", "mrigashira", "ardra",
    "punarvasu", "pushya", "ashlesha", "magha", "purva_phalguni",
    "uttara_phalguni", "hasta", "chitra", "svati", "vishakha", "anuradha",
    "jyeshtha", "mula", "purva_ashadha", "uttara_ashadha", "shravana",
    "dhanishtha", "shatabhisha", "purva_bhadrapada", "uttara_bhadrapada", "revati",
)
NAKSHATRA_LORDS = (
    "ketu", "venus", "sun", "moon", "mars", "rahu", "jupiter", "saturn", "mercury",
)
_SIDEREAL_LOCK = RLock()


def nakshatra_for(longitude: float) -> dict:
    """Divide the normalized zodiac into 27 equal mansions and 108 quarters."""

    # A tiny negative float can wrap to exactly 360.0 after modulo rounding.
    # Keep that point in the final quarter rather than indexing past the table.
    quarter = min(107, int((longitude % 360.0) * 3.0 / 10.0))
    index = quarter // 4
    return {
        "index": index + 1,
        "name": NAKSHATRAS[index],
        "pada": quarter % 4 + 1,
        "lord": NAKSHATRA_LORDS[index % 9],
    }


def summarize_vedic_natal_chart(birth: dict) -> dict:
    """Return D1 only; the caller normalizes unknown civil times to local noon.

    Sidereal positions are requested directly, not obtained by subtracting a
    rounded ayanamsha from tropical results. Swiss Ephemeris documents the
    nutation distinction in its programming manual, sections 12 and 15:
    https://www.astro.com/swisseph/swephprg.htm
    """

    time_known = bool(birth["time_known"])
    lat, lon = float(birth["lat"]), float(birth["lon"])
    if time_known and abs(lat) >= 90:
        raise ValueError("an ascendant is undefined at a geographic pole")
    jd = julian_day(parse_utc(birth["utc_iso"]))
    flags = [] if time_known else ["no_birth_time", "nakshatra_time_uncertain"]
    raw_planets = {}
    houses = {}
    ascendant = None
    first_sign = None

    # Keep mode changes scoped to this calculation. The pinned native library
    # supports thread-local state; the lock also serializes this module's users.
    # Tropical callers never request FLG_SIDEREAL. Reset the library's default
    # in finally so subsequent calls on the same worker do not inherit Lahiri.
    with _SIDEREAL_LOCK:
        swe.set_sid_mode(swe.SIDM_LAHIRI)
        try:
            _, ayanamsha = swe.get_ayanamsa_ex_ut(jd, swe.FLG_SWIEPH)
            for name, body in CLASSICAL_BODIES.items():
                values, returned_flags = swe.calc_ut(
                    jd, body, swe.FLG_SWIEPH | swe.FLG_SPEED | swe.FLG_SIDEREAL
                )
                raw_planets[name] = (values[0] % 360.0, values[3])
                if returned_flags & swe.FLG_MOSEPH:
                    flags.append("ephemeris_fallback_moshier")
            rahu_longitude, rahu_speed = raw_planets["rahu"]
            raw_planets["ketu"] = ((rahu_longitude + 180.0) % 360.0, rahu_speed)

            if time_known:
                cusps, angles = swe.houses_ex(jd, lat, lon, b"W", swe.FLG_SIDEREAL)
                longitude = angles[0] % 360.0
                first_sign = int(longitude // 30)
                ascendant = {
                    "longitude_deg": longitude,
                    "sign": sign_for(longitude),
                    "house": 1,
                }
                houses = {
                    str(number): {"lon": q6(cusp) % 360.0, "size": 30.0}
                    for number, cusp in enumerate(cusps, start=1)
                }
        except swe.Error as exc:
            raise ValueError("sidereal ephemeris calculation is unavailable") from exc
        finally:
            swe.set_sid_mode(swe.SIDM_FAGAN_BRADLEY)

    return {
        "system": "vedic",
        "zodiac_system": "sidereal",
        "ayanamsha": "lahiri",
        "ayanamsha_deg": q6(ayanamsha),
        "node_type": "mean",
        "house_system": "whole_sign",
        "config_version": VEDIC_CONFIG_VERSION,
        "planets": {
            name: {
                "longitude_deg": longitude,
                "sign": sign_for(longitude),
                "house": (int(longitude // 30) - first_sign) % 12 + 1
                if first_sign is not None else None,
                "retrograde": speed < 0,
                "nakshatra": nakshatra_for(longitude),
            }
            for name, (longitude, speed) in raw_planets.items()
        },
        "ascendant": ascendant,
        "houses": houses,
        "birth_data_precision": "known" if time_known else "placeholder",
        "degraded_flags": sorted(set(flags)),
    }
