"""Clearly synthetic deterministic inputs for public Layer 1 tests."""

from layer1.config import CONFIG_VERSION


# J2000 noon at the equator and prime meridian is a technical reference point,
# not a person's birth record.
SYNTHETIC_INPUT = {
    "birth": {
        "utc_iso": "2000-01-01T12:00:00Z",
        "time_known": True,
        "lat": 0.0,
        "lon": 0.0,
        "tz_iana": "Etc/UTC",
    },
    "window": {
        "start_utc": "2026-09-01T00:00:00Z",
        "end_utc": "2026-10-01T00:00:00Z",
        "granularity": "day",
    },
    "mode": "forecast",
    "locale": "zh-Hans",
    "config": {
        "version": CONFIG_VERSION,
        "zodiac_system": "tropical",
        "house_system": "placidus",
        "profection_rulership": "traditional",
        "node_type": "true",
    },
}

SYNTHETIC_CIVIL_BIRTH = {
    "local_date": "2000-01-01",
    "local_time": "12:00:00",
    "time_known": True,
    "latitude": 0.0,
    "longitude": 0.0,
    "tz_iana": "Etc/UTC",
}
