"""Spatial rainfall zones: absolute amounts painted on sub-areas. Last-painted wins."""
import math

MAX_ZONES = 12
PALETTE = ["#22d3ee", "#a78bfa", "#f472b6", "#fbbf24", "#34d399", "#fb7185",
           "#60a5fa", "#f97316", "#2dd4bf", "#e879f9", "#a3e635", "#facc15"]


def parse_zones(rainfall):
    """Split valid/invalid zone dicts. Returns (zones, dropped_ids). Never raises."""
    zones, dropped = [], []
    try:
        raw = (rainfall or {}).get("zones") or []
    except Exception:
        return [], []
    for z in raw[:MAX_ZONES * 2]:
        try:
            zid = str(z.get("id", "z"))
            poly = z.get("polygon") or {}
            if not (poly.get("type") == "Polygon"
                    and isinstance(poly.get("coordinates"), list) and poly["coordinates"]
                    and isinstance(poly["coordinates"][0], list) and len(poly["coordinates"][0]) >= 4):
                dropped.append(zid)
                continue
            if str(z.get("mode", "constant")) == "variable":
                # variable hyetograph zone (mirrors top-level variable rainfall)
                pts = z.get("points") or []
                try:
                    totalTime = float(z.get("totalTime", 0) or 0)
                    maxRain = float(z.get("maxRain", 0) or 0)
                except Exception:
                    totalTime, maxRain = 0.0, 0.0
                unit = z.get("unit", "rate")
                ok = (totalTime > 0 and maxRain >= 0 and unit in ("rate", "total")
                      and isinstance(pts, list) and len(pts) >= 2)
                if ok:
                    for _p in pts:
                        try:
                            _t = float((_p or {}).get("time", 0) or 0)
                            _a = float((_p or {}).get("amount", 0) or 0)
                            assert _t >= 0 and _a >= 0
                        except Exception:
                            ok = False
                            break
                if not ok:
                    dropped.append(zid)
                    continue
                zones.append({"id": zid, "mode": "variable", "unit": unit,
                              "totalTime": totalTime, "maxRain": maxRain,
                              "points": [{"time": float(p["time"]), "amount": float(p["amount"])} for p in pts],
                              "polygon": poly})
                continue
            amount = float(z.get("amount"))
            unit = z.get("unit", "rate")
            if not (amount >= 0 and unit in ("rate", "total")):
                dropped.append(zid)
                continue
            zones.append({"id": zid, "amount": amount, "unit": unit, "polygon": poly})
        except Exception:
            try:
                dropped.append(str((z or {}).get("id", "?")))
            except Exception:
                dropped.append("?")
    if len(zones) > MAX_ZONES:
        # valid but over cap: report as dropped so callers know what was ignored
        for _z in zones[MAX_ZONES:]:
            try:
                dropped.append(str(_z.get("id", "z")))
            except Exception:
                dropped.append("?")
    return zones[:MAX_ZONES], dropped


def _grid_transform(bbox, width, height):
    from rasterio.transform import from_bounds
    minLon, minLat, maxLon, maxLat = [float(x) for x in bbox]
    return from_bounds(minLon, minLat, maxLon, maxLat, width, height)


def zone_step_rates(zone, steps, duration_hr):
    """mm/hr per flood step. Constant: flat (total spread over duration_hr).
    Variable: hyetograph interpolated over the zone's own totalTime, padded
    with the last value / truncated to steps (mirrors top-level behavior)."""
    n = max(1, int(steps or 1))
    if (zone or {}).get("mode") == "variable":
        from app.services.rainfall_curve import interpolate
        try:
            res = interpolate(zone.get("points", []), totalTime=float(zone.get("totalTime") or 1),
                              maxRain=float(zone.get("maxRain") or 0), unit=str(zone.get("unit", "rate") or "rate"),
                              steps=n)
            vals = [float(v) for v in list(res["values"])[:n]]
            while len(vals) < n:
                vals.append(vals[-1] if vals else 0.0)
            return vals
        except Exception:
            return [0.0] * n
    try:
        dur = max(1e-9, float(duration_hr or 1.0))
        amt = float((zone or {}).get("amount", 0.0) or 0.0)
        r = amt if str((zone or {}).get("unit", "rate")) == "rate" else amt / dur
    except Exception:
        r = 0.0
    return [r] * n


def zone_masks(zones, bbox, width, height):
    """Bool mask per zone in list order (last wins at paint time). Never raises."""
    import numpy as np
    from rasterio.features import rasterize
    masks = []
    try:
        transform = _grid_transform(bbox, width, height)
    except Exception:
        return [np.zeros((height, width), dtype=bool) for _ in (zones or [])]
    for z in (zones or []):
        try:
            burned = rasterize([((z or {}).get("polygon"), 1)], out_shape=(height, width),
                               transform=transform, fill=0, dtype="uint8")
            masks.append(np.asarray(burned).astype(bool) if burned is not None
                         else np.zeros((height, width), dtype=bool))
        except Exception:
            masks.append(np.zeros((height, width), dtype=bool))
    return masks


def paint_rate_grid(base_rate, zones, bbox, width, height, duration_hr):
    """Per-cell mm/hr grid. Zones painted in list order (last wins). Total unit -> rate."""
    import numpy as np
    from rasterio.features import rasterize
    g = np.full((height, width), float(base_rate or 0.0), dtype=np.float64)
    if not zones:
        return g
    try:
        dur = max(1e-6, float(duration_hr or 1.0))
    except Exception:
        dur = 1.0
    try:
        transform = _grid_transform(bbox, width, height)
    except Exception:
        return g
    for z in zones:
        try:
            rate = float(z["amount"]) if z.get("unit", "rate") == "rate" else float(z["amount"]) / dur
            burned = rasterize([(z["polygon"], 1)], out_shape=(height, width),
                               transform=transform, fill=0, dtype="uint8")
            if burned is None:
                continue
            mask = np.asarray(burned).astype(bool)
            if mask.any():
                g[mask] = rate
        except Exception:
            continue
    return g


def zone_at(lon, lat, zones):
    """Topmost (last) zone containing the point, else None. Never raises."""
    try:
        from shapely.geometry import Point, shape
        pt = Point(float(lon), float(lat))
        for z in reversed(zones or []):
            try:
                if shape(z["polygon"]).contains(pt):
                    return z
            except Exception:
                continue
    except Exception:
        pass
    return None
