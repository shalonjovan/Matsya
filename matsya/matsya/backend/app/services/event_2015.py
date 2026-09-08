"""2015 Chennai flood replay: observed fixture + Dec-1 event sim builder.

Observed facts live in event_2015.json (sourced, never modeled). The event
sim runs the REAL flood pipeline with a Dec-1-pattern storm — no fake flood
arrays anywhere. Geographic caveat: the DEM tile starts at lat 13.0, so
Tambaram/Velachery/Pallikaranai are excluded from the comparison set.
"""
import json
import pathlib

_FIXTURE_CACHE: dict = {}


def _fixture_path():
    return pathlib.Path(__file__).parent.parent / "data" / "event_2015.json"


def load_fixture():
    """Observed 2015 facts. Never raises (empty refs on failure)."""
    try:
        if _FIXTURE_CACHE.get("f"):
            return _FIXTURE_CACHE["f"]
        f = json.loads(_fixture_path().read_text())
        _FIXTURE_CACHE["f"] = f
        return f
    except Exception:
        return {"rainfallStations": [], "release": {}, "impacts": [],
                "referenceLocalities": [], "excludedLocalities": [],
                "replayBbox": [80.15, 13.08, 80.20, 13.13]}


def _bbox_in_dem(bbox):
    try:
        from app.services.elevation import sample_dem
        minLon, minLat, maxLon, maxLat = bbox
        for lon, lat in ((minLon, minLat), (maxLon, minLat), (minLon, maxLat), (maxLon, maxLat)):
            if sample_dem(float(lon), float(lat)) is None:
                return False
        return True
    except Exception:
        return False


def _dec1_points():
    # synthetic double-peak disaggregation of the ~490mm IMD daily total
    return [{"time": 0, "amount": 0}, {"time": 6, "amount": 60},
            {"time": 10, "amount": 160}, {"time": 14, "amount": 200},
            {"time": 18, "amount": 90}, {"time": 22, "amount": 30},
            {"time": 24, "amount": 0}]


def build_event_sim(name_suffix=""):
    """Create the Dec-1 replay sim (south 490mm / north 300mm zones, 24h)."""
    f = load_fixture()
    bbox = list(f.get("replayBbox") or [80.17, 13.0, 80.27, 13.1])
    if not _bbox_in_dem(bbox):
        # shrink north edge stays; lift south edge into tile
        bbox = [bbox[0], 13.02, bbox[2], bbox[3]]
    minLon, minLat, maxLon, maxLat = bbox
    midLat = (minLat + maxLat) / 2.0
    _ring_s = [[minLon, minLat], [maxLon, minLat], [maxLon, midLat], [minLon, midLat], [minLon, minLat]]
    _ring_n = [[minLon, midLat], [maxLon, midLat], [maxLon, maxLat], [minLon, maxLat], [minLon, midLat]]
    south = {"id": "dec1-south", "mode": "variable", "unit": "total",
             "totalTime": 24, "maxRain": 490, "points": _dec1_points(),
             "polygon": {"type": "Polygon", "coordinates": [_ring_s]}}
    north = {"id": "dec1-north", "amount": 300, "unit": "total",
             "polygon": {"type": "Polygon", "coordinates": [_ring_n]}}
    name = "Chennai Dec 2015 (replay)" + (f" {name_suffix}" if name_suffix else "")
    from app.services.simulation_store import store
    return store.create({
        "name": name,
        "area": {"bbox": bbox, "crs": "EPSG:4326"},
        "rainfall": {"mode": "variable", "totalTime": 24, "maxRain": 490,
                     "unit": "total", "points": _dec1_points(),
                     "zones": [south, north]},
    })
