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


FORMULA = ("similarityPct = round(50*recall + 50*bandAgreement); "
           "recall = reported severe|moderate localities with modeled max >= 15cm / total; "
           "bandAgreement = exact band matches / total; "
           "bands: severe >= 100cm, moderate 15-100cm, mild < 15cm (snapshot max at locality cell)")
WET_CM = 15.0


def _band(depth_cm):
    try:
        _d = float(depth_cm)
    except Exception:
        return "mild"
    if _d >= 100.0:
        return "severe"
    if _d >= WET_CM:
        return "moderate"
    return "mild"


def compare(sim_id):
    """Reference-vs-modeled agreement. Never raises (empty result on failure)."""
    from app.services.snapshots import load_snapshots
    from app.services.analysis import _lat_lon_to_row_col
    try:
        from app.services.simulation_store import store
        sim = store.get(sim_id)
    except Exception:
        return {"localities": [], "recall": 0.0, "bandAgreement": 0.0,
                "similarityPct": 0, "formula": FORMULA, "wetThresholdCm": WET_CM,
                "error": "simulation not found"}
    try:
        f = load_fixture()
        locs = f.get("referenceLocalities") or []
        snaps, _, bbox = load_snapshots(sim)
        if not snaps:
            return {"localities": [], "recall": 0.0, "bandAgreement": 0.0,
                    "similarityPct": 0, "formula": FORMULA, "wetThresholdCm": WET_CM,
                    "error": "snapshots unavailable"}
        import numpy as _np
        stack = _np.asarray([_np.asarray(s, dtype=float) for s in snaps])
        rows, cols = stack.shape[1], stack.shape[2]
        out = []
        for loc in locs:
            try:
                _r, _c = _lat_lon_to_row_col(float(loc["lat"]), float(loc["lon"]),
                                             list(bbox), rows, cols)
                _mx = round(float(stack[:, _r, _c].max()) * 100.0, 1)
                _mb = _band(_mx)
                out.append({"name": loc.get("name"), "lat": loc.get("lat"), "lon": loc.get("lon"),
                            "reportedBand": loc.get("reportedBand"), "basis": loc.get("basis"),
                            "source": loc.get("source"), "modeledMaxCm": _mx, "modeledBand": _mb,
                            "match": bool(_mb == loc.get("reportedBand"))})
            except Exception:
                continue
        _sig = [loc for loc in out if loc.get("reportedBand") in ("severe", "moderate")]
        _recall = (sum(1 for loc in _sig if loc["modeledMaxCm"] >= WET_CM) / max(1, len(_sig)))
        _agree = (sum(1 for loc in out if loc["match"]) / max(1, len(out)))
        return {"localities": out, "recall": round(_recall, 3), "bandAgreement": round(_agree, 3),
                "similarityPct": int(round(50 * _recall + 50 * _agree)),
                "formula": FORMULA, "wetThresholdCm": WET_CM}
    except Exception:
        return {"localities": [], "recall": 0.0, "bandAgreement": 0.0,
                "similarityPct": 0, "formula": FORMULA, "wetThresholdCm": WET_CM,
                "error": "comparison failed"}
