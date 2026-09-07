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
            amount = float(z.get("amount"))
            unit = z.get("unit", "rate")
            poly = z.get("polygon") or {}
            if not (amount >= 0 and unit in ("rate", "total")
                    and poly.get("type") == "Polygon"
                    and isinstance(poly.get("coordinates"), list) and poly["coordinates"]
                    and isinstance(poly["coordinates"][0], list) and len(poly["coordinates"][0]) >= 4):
                dropped.append(zid)
                continue
            zones.append({"id": zid, "amount": amount, "unit": unit, "polygon": poly})
        except Exception:
            try:
                dropped.append(str((z or {}).get("id", "?")))
            except Exception:
                dropped.append("?")
    return zones[:MAX_ZONES], dropped


def _grid_transform(bbox, width, height):
    from rasterio.transform import from_bounds
    minLon, minLat, maxLon, maxLat = [float(x) for x in bbox]
    return from_bounds(minLon, minLat, maxLon, maxLat, width, height)


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
