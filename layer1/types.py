"""Typed representations of the Layer 1 input and activation contracts."""

from __future__ import annotations

from typing import Dict, List, Optional, TypedDict, Union

JsonScalar = Union[str, int, float, bool, None]


class BirthData(TypedDict):
    utc_iso: str
    time_known: bool
    lat: float
    lon: float
    tz_iana: str


class WindowInput(TypedDict):
    start_utc: str
    end_utc: str
    granularity: str


class Config(TypedDict):
    version: str
    zodiac_system: str
    house_system: str
    profection_rulership: str
    node_type: str


class ComputeInput(TypedDict):
    birth: BirthData
    window: WindowInput
    mode: str
    locale: str
    config: Config


class LocalizedText(TypedDict):
    locale: str
    text: str


class Provenance(TypedDict):
    se_version: str
    se_ephe_files_sha256: str
    deltat_source: str
    tzdb_version: str
    immanuel_version: str


class RetrogradePass(TypedDict):
    peak_utc: str
    phase: str
    orb_factor_at_peak: float


class ActivationWindow(TypedDict):
    start_utc: str
    end_utc: str
    peak_utc: str
    peak_precision_hours: int
    retrograde_passes: List[RetrogradePass]


class EphemerisSnapshot(TypedDict):
    transiting_lon_deg: float
    transiting_speed_deg_per_day: float
    natal_target_lon_deg: float
    angular_distance_deg: float
    retrograde: bool


class Driver(TypedDict, total=False):
    driver_id: str
    kind: str
    technique: str
    transiting_body: str
    transiting_sign: str
    transiting_house: int
    aspect: str
    natal_target: Optional[str]
    target_type: str
    house: int
    sign: Optional[str]
    orb_deg: float
    phase: str
    transiting_retrograde: bool
    stationary: bool
    weight: float
    kb_lookup_id: str
    keywords: List[str]
    ephemeris_snapshot: Optional[EphemerisSnapshot]
    profection_house: int
    profection_lord_traditional: str
    profection_lord_modern: str
    profection_lord_active: str


class NarrativeHints(TypedDict, total=False):
    tone: str
    time_stance: str
    avoid: List[str]
    encourage: List[str]
    trigger_chain: bool
    why_high_intensity: str
    truncated_driver_count: int


class Activation(TypedDict):
    activation_id: str
    config_version: str
    provenance: Provenance
    zodiac_system: str
    house_system: str
    mode: str
    primary_life_area: str
    life_area_scores: Dict[str, float]
    time_scale: str
    window: ActivationWindow
    polarity: str
    polarity_mix: Dict[str, float]
    intensity: float
    confidence: float
    birth_data_precision: str
    house_precision: str
    techniques: List[str]
    headline: LocalizedText
    one_line: LocalizedText
    drivers: List[Driver]
    kb_context_ids: List[str]
    narrative_hints: NarrativeHints
    degraded_flags: List[str]
