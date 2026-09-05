from pydantic import BaseModel, Field, field_validator
from enum import Enum
import uuid
from datetime import datetime, timezone
from typing import Any


class StatusEnum(str, Enum):
    Ready = "Ready"
    Running = "Running"
    Completed = "Completed"
    Incomplete = "Incomplete"
    Error = "Error"
    Live = "Live"
    Offline = "Offline"


class Area(BaseModel):
    bbox: list[float]  # [minLon, minLat, maxLon, maxLat]
    crs: str = "EPSG:4326"
    polygon: dict | None = None

    @field_validator("bbox")
    @classmethod
    def check_bbox(cls, v: list[float]) -> list[float]:
        assert len(v) == 4 and v[0] < v[2] and v[1] < v[3], "invalid bbox"
        return v

    @field_validator("polygon")
    @classmethod
    def check_polygon(cls, v):
        if v is None:
            return v
        # Basic GeoJSON Polygon validation: type Polygon, coordinates [[[lon,lat]]], closed ring
        assert isinstance(v, dict), "polygon must be GeoJSON dict"
        assert v.get("type") == "Polygon", "polygon type must be Polygon"
        coords = v.get("coordinates")
        assert isinstance(coords, list) and len(coords) > 0, "polygon coordinates missing"
        ring = coords[0]
        assert len(ring) >= 4, "polygon ring must have >=4 points"
        assert ring[0] == ring[-1], "polygon ring must be closed (first == last)"
        # Each point [lon,lat]
        for pt in ring:
            assert isinstance(pt, list) and len(pt) >= 2, "polygon point must be [lon,lat]"
            lon, lat = pt[0], pt[1]
            assert -180 <= lon <= 180 and -90 <= lat <= 90, f"invalid lon/lat {pt}"
        return v


class Terrain(BaseModel):
    demUri: str | None = None
    res: float | None = None


class Rainfall(BaseModel):
    # Constant mode (legacy)
    rateMmHr: float | None = None
    durationHr: float | None = None
    # Variable mode
    mode: str = "constant"  # "constant" | "variable"
    constantRate: float | None = None
    totalTime: float | None = None
    maxRain: float | None = None
    unit: str | None = "rate"  # "rate" | "total"
    points: list[dict] | None = None
    curve: dict | None = None

    @classmethod
    def model_validate(cls, obj, *args, **kwargs):
        # Handle legacy rateMmHr/durationHr without mode
        if isinstance(obj, dict) and "mode" not in obj:
            if "rateMmHr" in obj and obj["rateMmHr"] is not None:
                obj = obj.copy()
                obj["mode"] = "constant"
                obj["constantRate"] = obj["rateMmHr"]
                # keep durationHr as is
        return super().model_validate(obj, *args, **kwargs)


class Drainage(BaseModel):
    uri: str | None = None
    conduitCount: int | None = None


class Parameters(BaseModel):
    cfl: float | None = None
    dt: float | None = None
    theta: float | None = None
    initialFillPct: float = Field(default=75.0, ge=0.0, le=100.0)


class Metadata(BaseModel):
    created: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: StatusEnum = StatusEnum.Ready


class HydroConfig(BaseModel):
    enabled: bool = False
    version: str = "1.1"
    drainToWaterbody: dict[str, str] | None = None
    waterbodyStates: dict[str, dict] | None = None
    graphStats: dict | None = None


class Elevation(BaseModel):
    elevationUri: str | None = None
    stats: dict | None = None
    width: int | None = None
    height: int | None = None


class Flood(BaseModel):
    floodUri: str | None = None
    stats: dict | None = None
    width: int | None = None
    height: int | None = None
    steps: int | None = None


class Simulation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    area: Area
    terrain: Terrain | None = None
    rainfall: Rainfall

    @field_validator("rainfall", mode="before")
    @classmethod
    def check_rainfall(cls, v):
        if isinstance(v, dict) and "mode" not in v and "rateMmHr" in v and v["rateMmHr"] is not None:
            v = v.copy()
            v["mode"] = "constant"
            v["constantRate"] = v["rateMmHr"]
        return v
    drainage: Drainage | None = None
    rivers: Any | None = None
    canals: Any | None = None
    waterBodies: Any | None = None
    roads: Any | None = None
    buildings: Any | None = None
    landCover: Any | None = None
    boundaries: Any | None = None
    parameters: Parameters | None = None
    results: dict | None = None
    elevation: Elevation | None = None
    flood: Flood | None = None
    hydro: HydroConfig | None = None
    metadata: Metadata = Field(default_factory=Metadata)
    status: StatusEnum = StatusEnum.Ready
