"""Controlled vocabulary mirrored verbatim from the KB specification.

When Track A produces ``kb/schema/controlled-vocab.yaml``, CI must compare
these values against that source of truth before release.
"""

SYSTEMS = ("western", "vedic")
TECHNIQUES = (
    "foundation", "natal", "transit", "progression", "solar_return",
    "lunar_return", "profection",
)
PLANETS = (
    "sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn",
    "uranus", "neptune", "pluto",
)
SIGNS = (
    "aries", "taurus", "gemini", "cancer", "leo", "virgo", "libra",
    "scorpio", "sagittarius", "capricorn", "aquarius", "pisces",
)
ASPECTS = ("conjunction", "opposition", "square", "trine", "sextile")
HOUSES = tuple(range(1, 13))
ANGLES = ("asc", "mc", "ic", "dsc")
LIFE_AREAS = (
    "career", "wealth", "relationships", "family", "health", "self",
    "spirituality", "community",
)
TIME_SCALES = ("days", "weeks", "months", "year", "multi_year")
POLARITIES = ("supportive", "challenging", "neutral", "growth")
INTENSITIES = ("low", "medium", "high")
TARGET_TYPES = ("planet", "angle", "house")

DRIVER_KINDS = (
    "transit_to_natal", "transit_through_house", "profection",
    "progressed_moon_house", "progressed_moon_sign",
    "progressed_sun_sign_change", "solar_return_asc",
    "solar_return_asc_ruler_house", "solar_return_moon_house",
    "solar_return_stellium_house", "lunar_return_moon_house", "foundation",
)
PHASES = ("applying", "exact", "separating")
TONES = ("grounded", "descriptive", "actionable", "cautious")
TIME_STANCES = ("reviewing", "encountering", "integrating")
WHY_HIGH_INTENSITY = (
    "profection_year_lord_hit", "multiple_outer_transits", "stationary_body",
    "return_year_amplifier", "saturn_return", "eclipse_reinforcement",
)

