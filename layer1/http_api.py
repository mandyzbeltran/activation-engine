"""Loopback-friendly HTTP transport for the public deterministic Layer 1 service."""

from __future__ import annotations

from datetime import date, datetime, time, timezone
import os
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, model_validator

from .api import compute_activations
from .config import CONFIG_VERSION
from .ephemeris.common import iso_z
from .ephemeris.natal import summarize_natal_chart


class BirthInput(BaseModel):
    local_date: date
    local_time: time | None = None
    time_known: bool = True
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    tz_iana: str = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def require_known_time(self):
        if self.time_known and self.local_time is None:
            raise ValueError("local_time is required when time_known is true")
        return self


class WindowInput(BaseModel):
    start_utc: datetime
    end_utc: datetime


class ActivationsRequest(BaseModel):
    birth: BirthInput
    window: WindowInput
    mode: Literal["forecast", "retrospective"] = "forecast"
    locale: Literal["zh-Hans", "en"] = "zh-Hans"


class NatalSummaryRequest(BaseModel):
    birth: BirthInput


def normalized_birth(birth: BirthInput) -> dict:
    """Convert a user's local civil birth time to the engine's UTC contract."""

    try:
        zone = ZoneInfo(birth.tz_iana)
    except ZoneInfoNotFoundError as exc:
        raise ValueError("unknown IANA timezone") from exc
    local_time = birth.local_time if birth.time_known else time(hour=12)
    if local_time is None:
        raise ValueError("local_time is required when time_known is true")
    local = datetime.combine(birth.local_date, local_time).replace(tzinfo=zone)
    return {
        "utc_iso": iso_z(local.astimezone(timezone.utc)),
        "time_known": birth.time_known,
        "lat": birth.latitude,
        "lon": birth.longitude,
        "tz_iana": birth.tz_iana,
    }


def default_config() -> dict:
    return {
        "version": CONFIG_VERSION,
        "zodiac_system": "tropical",
        "house_system": "placidus",
        "profection_rulership": "traditional",
        "node_type": "true",
    }


def create_app() -> FastAPI:
    app = FastAPI(title="Astro Layer 1", version=CONFIG_VERSION)
    origins = [
        value.strip()
        for value in os.environ.get(
            "LAYER1_CORS_ORIGINS", "http://localhost:8083,http://127.0.0.1:8083"
        ).split(",")
        if value.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @app.get("/health")
    def health():
        return {"status": "ok", "engine": "swiss_ephemeris", "config_version": CONFIG_VERSION}

    @app.post("/v1/activations")
    def activations(request: ActivationsRequest):
        try:
            birth = normalized_birth(request.birth)
            values = compute_activations({
                "birth": birth,
                "window": {
                    "start_utc": iso_z(request.window.start_utc),
                    "end_utc": iso_z(request.window.end_utc),
                    "granularity": "day",
                },
                "mode": request.mode,
                "locale": request.locale,
                "config": default_config(),
            })
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"activations": values, "data_source": "swiss_ephemeris"}

    @app.post("/v1/natal-summary")
    def natal_summary(request: NatalSummaryRequest):
        try:
            summary = summarize_natal_chart(normalized_birth(request.birth), default_config())
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"natal_summary": summary, "data_source": "swiss_ephemeris"}

    return app
