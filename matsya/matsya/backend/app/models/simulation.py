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


class Terrain(BaseModel):
    demUri: str | None = None
    res: float | None = None


class Rainfall(BaseModel):
    rateMmHr: float
    durationHr: float


class Drainage(BaseModel):
    uri: str | None = None
    conduitCount: int | None = None


class Parameters(BaseModel):
    cfl: float | None = None
    dt: float | None = None
    theta: float | None = None


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


class Simulation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    area: Area
    terrain: Terrain | None = None
    rainfall: Rainfall
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
    hydro: HydroConfig | None = None
    metadata: Metadata = Field(default_factory=Metadata)
    status: StatusEnum = StatusEnum.Ready
