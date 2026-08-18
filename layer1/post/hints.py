"""Compliance-oriented narrative hint generation."""

from __future__ import annotations

AREA_HINTS = {
    "career": {
        "avoid": ["specific_job_title", "specific_salary", "employer_name", "firing_prediction"],
        "encourage": ["long_term_commitment", "structural_dialogue", "self_recalibration", "authority_relationships"],
    },
    "wealth": {
        "avoid": ["stock_ticker", "market_direction", "buy_sell_timing", "specific_amounts"],
        "encourage": ["budget_review", "value_alignment", "long_term_planning"],
    },
    "relationships": {
        "avoid": ["ex_partner_name", "third_party_behavior_prediction", "marriage_outcome_assertion"],
        "encourage": ["boundary_setting", "structural_conversation", "commitment_clarification"],
    },
    "family": {
        "avoid": ["family_health_diagnosis", "family_lifespan_prediction"],
        "encourage": ["intergenerational_dialogue", "home_base_maintenance"],
    },
}


def build_hints(area: str, polarity: str, mode: str, drivers: list[dict], truncated: int = 0) -> dict:
    base = AREA_HINTS[area]
    hints = {
        "tone": "cautious" if polarity == "challenging" else "grounded",
        "time_stance": "reviewing" if mode == "retrospective" else "encountering",
        "avoid": list(base["avoid"]),
        "encourage": list(base["encourage"] if polarity in ("challenging", "growth") else base["encourage"][:1]),
        "trigger_chain": any(driver.get("year_lord_match") for driver in drivers),
    }
    if any(
        driver.get("transiting_body") == "saturn"
        and driver.get("aspect") == "conjunction"
        and driver.get("natal_target") == "saturn"
        for driver in drivers
    ):
        hints["why_high_intensity"] = "saturn_return"
    elif hints["trigger_chain"]:
        hints["why_high_intensity"] = "profection_year_lord_hit"
    elif sum(1 for driver in drivers if driver.get("transiting_body") in ("saturn", "uranus", "neptune", "pluto")) >= 2:
        hints["why_high_intensity"] = "multiple_outer_transits"
    elif any(driver.get("stationary") for driver in drivers):
        hints["why_high_intensity"] = "stationary_body"
    if truncated:
        hints["truncated_driver_count"] = truncated
    return hints
