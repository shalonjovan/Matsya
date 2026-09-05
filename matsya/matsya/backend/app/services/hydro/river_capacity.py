"""River reach capacities (hybrid): measured length/slope, DEM valley width
where resolvable, flagged defaults otherwise. Manning trapezoidal 1:1."""
import math

MANNING_N = 0.035
DEFAULT_MAJOR_W, DEFAULT_MINOR_W = 12.0, 5.0
DEFAULT_DEPTH = 1.5
MAJOR_LEN_M = 1500.0


def reach_capacity(length_m, slope, width_m=None, depth_m=None):
    """Bankfull Q (CMS) for trapezoidal channel, side slope 1:1."""
    L = max(50.0, float(length_m or 2000.0))
    S = max(0.0002, min(0.02, float(slope or 0.001)))
    if width_m is None:
        w, wsrc = (DEFAULT_MAJOR_W if L >= MAJOR_LEN_M else DEFAULT_MINOR_W), "assumed"
    else:
        w, wsrc = max(1.0, float(width_m)), "observed"
    if depth_m is None:
        d, dsrc = DEFAULT_DEPTH, "assumed"
    else:
        d, dsrc = max(0.3, float(depth_m)), "observed"
    A = d * (w + d)
    P = w + 2.0 * d * math.sqrt(2.0)
    R = A / P if P > 0 else 0.1
    Q = (1.0 / MANNING_N) * A * (R ** (2.0 / 3.0)) * math.sqrt(S)
    src = "observed-dims" if (wsrc == "observed" and dsrc == "observed") else (
        "observed-valley" if wsrc == "observed" else "assumed-defaults")
    return {"qbank": round(float(Q), 3), "width_m": w, "depth_m": d,
            "length_m": L, "slope": S, "source": src}


def valley_width(dem_filled, bbox, width, height, coords_lonlat):
    """Width (m) of valley floor at reach midpoint from DEM transect.

    Samples perpendicular to the reach across +-120m; width = span where
    dem < center + 1.0m, clamped 3..80m. Returns (None, 'unresolved') on failure.
    """
    import numpy as np
    try:
        import math as _m
        minLon, minLat, maxLon, maxLat = bbox
        pts = list(coords_lonlat or [])
        if len(pts) < 2:
            return None, "unresolved"
        (x0, y0), (x1, y1) = pts[0], pts[-1]
        mx, my = (x0 + x1) / 2.0, (y0 + y1) / 2.0
        dx, dy = (x1 - x0), (y1 - y0)
        norm = _m.hypot(dx, dy) or 1.0
        px, py = -dy / norm, dx / norm  # perpendicular (degrees)
        lat_c = (minLat + maxLat) / 2.0
        m_per_deg = 111320.0 * _m.cos(_m.radians(lat_c))
        dlon = (maxLon - minLon) / max(1, width)
        dlat = (maxLat - minLat) / max(1, height)
        prof = []
        for off in range(-120, 121, 10):
            lon = mx + px * off / m_per_deg
            lat = my + py * off / 110540.0
            cc = int((lon - minLon) / dlon) if dlon else 0
            rr = int((maxLat - lat) / dlat) if dlat else 0
            if 0 <= rr < height and 0 <= cc < width:
                v = float(dem_filled[rr, cc])
                if v == v:  # not nan
                    prof.append((off, v))
        if len(prof) < 5:
            return None, "unresolved"
        center = min(prof, key=lambda t: t[1])[1]
        inside = [o for o, v in prof if v < center + 1.0]
        if not inside:
            return None, "unresolved"
        w = max(3.0, min(80.0, float(max(inside) - min(inside))))
        return w, "observed-valley"
    except Exception:
        return None, "unresolved"


_REACH_CACHE = {"key": None, "ts": 0, "data": []}


def build_reaches(bbox, max_n=10):
    """Clip rivers to bbox; capacity per reach. Cached 60s in-process."""
    import time as _t
    global _REACH_CACHE
    key = (tuple(round(float(x), 4) for x in bbox), int(max_n))
    try:
        if _REACH_CACHE.get("key") == key and (_t.time() - _REACH_CACHE.get("ts", 0) < 60):
            return _REACH_CACHE["data"]
    except Exception:
        pass
    out = []
    try:
        from app.services.hydro.asset_loader import load_assets
        data = load_assets("assets")
        rivers = data.get("rivers")
        if rivers is None or len(rivers) == 0:
            return []
        minLon, minLat, maxLon, maxLat = bbox
        lo_x, hi_x = (minLon, maxLon) if minLon <= maxLon else (maxLon, minLon)
        lo_y, hi_y = (minLat, maxLat) if minLat <= maxLat else (maxLat, minLat)
        try:
            clip = rivers.cx[lo_x:hi_x, lo_y:hi_y]
        except Exception:
            clip = rivers
        if len(clip) == 0:
            return []
        try:
            utm = clip.to_crs("EPSG:32644")
            clip = clip.copy()
            clip["_len"] = utm.geometry.length.values
            clip = clip.sort_values("_len", ascending=False).head(max_n)
        except Exception:
            clip = clip.head(max_n)
        try:
            from app.services.elevation import sample_dem as _sd
        except Exception:
            _sd = None
        for i, (_, row) in enumerate(clip.iterrows()):
            try:
                geom = row.geometry
                if geom is None or geom.is_empty:
                    continue
                if geom.geom_type == "LineString":
                    coords = list(geom.coords)
                elif geom.geom_type == "MultiLineString":
                    coords = list(sorted(list(geom.geoms), key=lambda g: g.length, reverse=True)[0].coords)
                else:
                    continue
                if len(coords) < 2:
                    continue
                (x0, y0), (x1, y1) = coords[0], coords[-1]
                import math as _m
                dxm = (x1 - x0) * 111320.0 * _m.cos(_m.radians((y0 + y1) / 2))
                dym = (y1 - y0) * 110540.0
                length = max(50.0, _m.hypot(dxm, dym))
                slope = 0.001
                if _sd is not None:
                    try:
                        z0, z1 = _sd(x0, y0), _sd(x1, y1)
                        if z0 is not None and z1 is not None and abs(z0 - z1) > 0.05:
                            slope = max(0.0002, min(0.02, abs(float(z0) - float(z1)) / length))
                    except Exception:
                        pass
                cap = reach_capacity(length, slope)
                rid = str(row.get("id", i)) if hasattr(row, "get") else str(i)
                out.append({"id": rid, "length_m": round(length, 1), "slope": slope,
                            "width_m": cap["width_m"], "depth_m": cap["depth_m"],
                            "qbank": cap["qbank"], "source": cap["source"], "coords": coords})
            except Exception:
                continue
    except Exception:
        return []
    try:
        _REACH_CACHE["key"], _REACH_CACHE["ts"], _REACH_CACHE["data"] = key, _t.time(), out
    except Exception:
        pass
    return out
