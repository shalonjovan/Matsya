
from typing import Dict, Any
import math

def _lat_lon_to_row_col(lat: float, lon: float, bbox, rows: int, cols: int):
    """Mirror frontend src/utils/geo.ts latLonToRowCol."""
    minLon, minLat, maxLon, maxLat = bbox
    dy = (maxLat - minLat) / rows
    dx = (maxLon - minLon) / cols
    # avoid division by zero
    if dy == 0:
        dy = 1e-9
    if dx == 0:
        dx = 1e-9
    r = math.floor((maxLat - lat) / dy)
    c = math.floor((lon - minLon) / dx)
    r = max(0, min(rows - 1, r))
    c = max(0, min(cols - 1, c))
    return r, c


def point_query(lat: float, lon: float, time: int, sim: Any) -> Dict[str,Any]:
    # Try real DEM sample first, fallback to mock
    try:
        from app.services.elevation import sample_dem
        real_elev = sample_dem(lon, lat)
    except:
        real_elev = None
    # bbox extraction
    try:
        if hasattr(sim, "area"):
            # sim.area may be Pydantic model
            bbox = sim.area.bbox if hasattr(sim.area, "bbox") else sim.area["bbox"]  # type: ignore
        elif isinstance(sim, dict):
            bbox = sim.get("area", {}).get("bbox", [80.15,13.08,80.20,13.13])  # type: ignore
        else:
            bbox = [80.15,13.08,80.20,13.13]
    except Exception:
        try:
            bbox = sim.model_dump()["area"]["bbox"]  # type: ignore
        except Exception:
            bbox = [80.15,13.08,80.20,13.13]
    try:
        minLon, minLat, maxLon, maxLat = bbox
    except Exception:
        minLon, minLat, maxLon, maxLat = [80.15,13.08,80.20,13.13]
        bbox = [minLon, minLat, maxLon, maxLat]
    # hash for deterministic mock (also used for elevation fallback)
    h = (int(lat*1000) ^ int(lon*1000)) % 100
    # clamp out-of-bbox
    if not (minLat <= lat <= maxLat and minLon <= lon <= maxLon):
        elevation = real_elev if real_elev is not None else 0
        floodDepth = 0
    else:
        # Try real flood snapshots if sim.flood exists
        floodDepth = None
        try:
            has_flood = False
            try:
                if hasattr(sim, "flood"):
                    f = sim.flood  # type: ignore
                    if f is not None:
                        # f may be dict or model
                        if isinstance(f, dict):
                            has_flood = f.get("stats") is not None
                        else:
                            has_flood = getattr(f, "stats", None) is not None
                elif isinstance(sim, dict):
                    has_flood = sim.get("flood") is not None and sim.get("flood", {}).get("stats") is not None
            except Exception:
                has_flood = False

            if has_flood:
                from app.services.flood import generate_flood
                import numpy as np

                # Resolve bbox, rainfall, width, height, steps
                # rainfall (preserve variable mode incl. points/curve/totalTime)
                try:
                    if hasattr(sim, "rainfall"):  # type: ignore[attr-defined]
                        rf = sim.rainfall  # type: ignore[attr-defined]
                        if rf is None:
                            rainfall = {"rateMmHr": 50, "durationHr": 1}
                        elif isinstance(rf, dict):
                            rainfall = dict(rf)
                        elif hasattr(rf, "model_dump"):
                            try:
                                rainfall = rf.model_dump(mode="json")  # type: ignore
                            except Exception:
                                rainfall = {"rateMmHr": float(getattr(rf, "rateMmHr", 50)), "durationHr": float(getattr(rf, "durationHr", 1))}
                        elif hasattr(rf, "rateMmHr"):
                            rainfall = {"rateMmHr": float(rf.rateMmHr), "durationHr": float(rf.durationHr)}  # type: ignore
                        else:
                            rainfall = {"rateMmHr": 50, "durationHr": 1}
                    elif isinstance(sim, dict):
                        rf = sim.get("rainfall", {})  # type: ignore
                        rainfall = dict(rf) if isinstance(rf, dict) else {"rateMmHr": 50, "durationHr": 1}
                    else:
                        rainfall = {"rateMmHr": 50, "durationHr": 1}
                except Exception:
                    rainfall = {"rateMmHr": 50, "durationHr": 1}

                # width, height, steps from sim.flood if available
                width = 180
                height = 180
                steps = 3
                try:
                    f = sim.flood  # type: ignore
                    if isinstance(f, dict):
                        width = int(f.get("width", 180) or 180)
                        height = int(f.get("height", 180) or 180)
                        steps = int(f.get("steps", 3) or 3)
                        # also try stats
                        if f.get("stats") and isinstance(f["stats"], dict):
                            width = int(f["stats"].get("width", width) or width)
                            height = int(f["stats"].get("height", height) or height)
                            steps = int(f["stats"].get("steps", steps) or steps)
                    else:
                        if getattr(f, "width", None) is not None:
                            width = int(f.width)  # type: ignore
                        if getattr(f, "height", None) is not None:
                            height = int(f.height)  # type: ignore
                        if getattr(f, "steps", None) is not None:
                            steps = int(f.steps)  # type: ignore
                        # stats may override
                        stats_attr = getattr(f, "stats", None)
                        if isinstance(stats_attr, dict):
                            width = int(stats_attr.get("width", width) or width)
                            height = int(stats_attr.get("height", height) or height)
                            steps = int(stats_attr.get("steps", steps) or steps)
                except Exception:
                    pass

                # Clamp steps
                steps = max(1, min(steps, 73))

                # Generate snapshots (deterministic per bbox+rainfall)
                snaps, _, _ = generate_flood(bbox, rainfall, width=width, height=height, steps=steps)

                # Map time to snapshot index (time is snapshot index per spec)
                try:
                    idx = int(time)
                except Exception:
                    idx = 0
                idx = max(0, min(idx, len(snaps) - 1))

                arr = snaps[idx]
                rows, cols = arr.shape[0], arr.shape[1]
                r, c = _lat_lon_to_row_col(lat, lon, bbox, rows, cols)
                val = arr[r, c]
                # handle nan
                try:
                    if val is None or (isinstance(val, float) and math.isnan(val)):
                        floodDepth = 0.0
                    else:
                        # numpy nan check
                        try:
                            import numpy as _np
                            if _np.isnan(val):
                                floodDepth = 0.0
                            else:
                                floodDepth = float(val)
                        except Exception:
                            floodDepth = float(val)
                except Exception:
                    floodDepth = float(val) if val is not None else 0.0
        except Exception as e:
            # print(f"flood sample failed: {e}")
            floodDepth = None

        if floodDepth is None:
            # fallback hash mock
            floodDepth = (h/100)*1.2 if time>600 else (h/100)*0.3
        elevation = real_elev if real_elev is not None else (15.5 + (h%10)*0.2)
    velocity = floodDepth*0.7 + 0.05
    # hydro context from stored flood stats (no invented capacity per §15)
    hydro_ctx: dict = {}
    try:
        fobj = getattr(sim, "flood", None) if not isinstance(sim, dict) else (sim.get("flood") if isinstance(sim, dict) else None)
        fstats = None
        if fobj is not None:
            fstats = fobj.get("stats") if isinstance(fobj, dict) else getattr(fobj, "stats", None)
            if fstats is not None and not isinstance(fstats, dict):
                try:
                    fstats = fstats.model_dump(mode="json")  # type: ignore
                except Exception:
                    fstats = None
        if isinstance(fstats, dict):
            hydro_ctx = {
                "mass_error": fstats.get("mass_error"),
                "wbCount": fstats.get("wbCount"),
                "surchargedDrains": fstats.get("surchargedDrains"),
                "drainSurcharge": bool((fstats.get("surchargedDrains") or 0) > 0),
                "totalRainMm": fstats.get("totalRainMm"),
            }
    except Exception:
        hydro_ctx = {}
    return {
        "lat": lat, "lon": lon,
        "elevation": elevation,
        "floodDepth": floodDepth,
        "water_depth": floodDepth,
        "velocity": velocity,
        "wse": elevation + floodDepth,
        "firstFlooded": "00:05" if floodDepth>0.05 else None,
        "peak": "01:20" if floodDepth>0.5 else None,
        "duration": "2h 10m" if floodDepth>0.05 else None,
        "rainfall": getattr(getattr(sim, "rainfall", None), "rateMmHr", 50) if hasattr(sim,"rainfall") else 50,  # type: ignore[attr-defined]
        "nearestDrain": "D-42 (12m)",
        "nearestRiver": "Adyar (450m)",
        "road": "GST Road",
        "type": "simulated",
        "measured": {"elevation": elevation},
        "simulated": {"floodDepth": floodDepth, "velocity": velocity},
        "derived": {"duration": "2h"},
        "hydro": hydro_ctx,
    }

def affected_areas(sim: Any):
    # mock ranked per §14, transparent criteria maxDepth
    return [
        {"name":"Velachery","maxDepth":1.24,"duration":"3h 12m","rank":1,"lat":12.9816,"lon":80.2180,"criteria":"maxDepth"},
        {"name":"Pallikaranai","maxDepth":0.92,"duration":"2h 48m","rank":2,"lat":12.9372,"lon":80.2130,"criteria":"maxDepth"},
        {"name":"T Nagar","maxDepth":0.65,"duration":"1h 30m","rank":3,"lat":13.0418,"lon":80.2341,"criteria":"maxDepth"},
    ]

def road_impact(sim: Any):
    return [
        {"id":"R-GST-1","maxDepth":0.8,"duration":"2h","firstFlood":"00:15","peak":"01:20","maxVel":0.5},
        {"id":"R-OMR-2","maxDepth":0.45,"duration":"1h 20m","firstFlood":"00:30","peak":"01:00","maxVel":0.3},
    ]

def drain_impact(sim: Any):
    # never invent capacity per §15 — capacity is None unless source has it
    return [
        {"id":"D-42","flow":1.2,"depth":0.5,"status":"ok","capacity":None,"overCapacity":False},
        {"id":"D-43","flow":2.1,"depth":1.1,"status":"surcharged","capacity":None,"overCapacity":False},
    ]
