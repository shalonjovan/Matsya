"""Road segmentation + per-segment flood series for the public v1 API.

Segments are ≤50m slices of roads.geojson geometry clipped to the sim bbox,
with stable ids (road_id#index). Depths are conservative: max over the
segment's sampled grid cells.
"""
import math

SEGMENT_M = 50.0
MAX_SEGMENTS = 4000

_ROADS_CACHE: dict = {}


def _haversine_m(lon1, lat1, lon2, lat2):
    try:
        _r = 6371000.0
        _p1, _p2 = math.radians(lat1), math.radians(lat2)
        _dp = math.radians(lat2 - lat1)
        _dl = math.radians(lon2 - lon1)
        _a = math.sin(_dp / 2) ** 2 + math.cos(_p1) * math.cos(_p2) * math.sin(_dl / 2) ** 2
        return 2 * _r * math.asin(min(1.0, math.sqrt(max(0.0, _a))))
    except Exception:
        return 0.0


def _roads_gdf():
    try:
        if _ROADS_CACHE.get("gdf") is not None:
            return _ROADS_CACHE["gdf"]
        from app.services.hydro.asset_loader import load_assets
        gdf = load_assets("assets").get("roads")
        if gdf is not None and len(gdf):
            _ROADS_CACHE["gdf"] = gdf
            return gdf
    except Exception:
        pass
    return None


def build_segments(bbox):
    """Split clipped roads into segments. Returns (segments list, truncated bool)."""
    try:
        minLon, minLat, maxLon, maxLat = [float(x) for x in bbox]
    except Exception:
        return [], False
    gdf = _roads_gdf()
    if gdf is None or not len(gdf):
        return [], False
    # clip margin (1%) — prefilter roads BEFORE segmenting so the segment
    # budget is spent inside the bbox, not on citywide file order
    _mlon = (maxLon - minLon) * 0.01
    _mlat = (maxLat - minLat) * 0.01

    def _inbox(pt):
        try:
            return minLon - _mlon <= float(pt[0]) <= maxLon + _mlon and \
                minLat - _mlat <= float(pt[1]) <= maxLat + _mlat
        except Exception:
            return False

    segs = []
    truncated = False
    try:
        for _, row in gdf.iterrows():
            try:
                _g = row.geometry
                if _g is None or _g.is_empty:
                    continue
                _lines = list(_g.geoms) if _g.geom_type == "MultiLineString" else [_g]
                _hit = False
                _parts = []
                for _ln in _lines:
                    try:
                        _cs = [(float(p[0]), float(p[1])) for p in list(_ln.coords)]
                    except Exception:
                        continue
                    if not _cs:
                        continue
                    _parts.append(_cs)
                    if any(_inbox(_p) for _p in _cs):
                        _hit = True
                if not _hit:
                    continue
                _rid = str(row.get("road_id", "") if hasattr(row, "get") else "") or "road"
                _rnm = str(row.get("road_name", "") if hasattr(row, "get") else "").strip() or _rid
                _rlc = str(row.get("locality", "") if hasattr(row, "get") else "").strip()
                _idx = 0
                for _cs in _parts:
                    # walk the line, cutting every SEGMENT_M
                    _run = [_cs[0]]
                    _acc = 0.0
                    for _a, _b in zip(_cs, _cs[1:]):
                        _d = _haversine_m(_a[0], _a[1], _b[0], _b[1])
                        if _acc + _d >= SEGMENT_M and len(_run) > 1:
                            _run.append(_b)
                            if any(_inbox(_p) for _p in _run):
                                segs.append(_finish(_rid, _rnm, _rlc, _run, _idx))
                                _idx += 1
                            _run = [_b]
                            _acc = 0.0
                        else:
                            _run.append(_b)
                            _acc += _d
                    if len(_run) > 1 and any(_inbox(_p) for _p in _run):
                        segs.append(_finish(_rid, _rnm, _rlc, _run, _idx))
                        _idx += 1
                    if len(segs) >= MAX_SEGMENTS:
                        truncated = True
                        break
                if truncated:
                    break
            except Exception:
                continue
    except Exception:
        pass
    for s in segs:
        try:
            del s["poly"]
        except Exception:
            pass
    return segs, truncated


def _finish(rid, rnm, rlc, run, idx):
    _length = sum(_haversine_m(a[0], a[1], b[0], b[1]) for a, b in zip(run, run[1:]))
    _mid = run[len(run) // 2]
    return {"segmentId": f"{rid}#{idx:04d}", "roadId": rid, "name": rnm, "locality": rlc,
            "midpoint": {"lat": round(_mid[1], 6), "lon": round(_mid[0], 6)},
            "lengthM": round(_length, 1), "poly": run}


def segment_series(sim, bbox=None, thresholdCm=15.0, minPeakCm=0.0, limit=500):
    """Per-segment per-step depths. Returns (rows list, meta dict). Never raises."""
    from app.services.snapshots import load_snapshots
    try:
        snaps, mpf, _bb = load_snapshots(sim)
        _bbox = list(bbox) if bbox else list(_bb)
    except Exception:
        return [], {"count": 0, "total": 0, "truncated": False}
    if not snaps:
        return [], {"count": 0, "total": 0, "truncated": False}
    try:
        import numpy as _np
        from app.services.analysis import _lat_lon_to_row_col
        stack = _np.asarray([_np.asarray(s, dtype=float) for s in snaps])
        rows, cols = stack.shape[1], stack.shape[2]
        segs, _trunc = build_segments(_bbox)
        out = []
        for s in segs:
            try:
                _lat, _lon = s["midpoint"]["lat"], s["midpoint"]["lon"]
                _r, _c = _lat_lon_to_row_col(_lat, _lon, _bbox, rows, cols)
                _ser = []
                for _k in range(stack.shape[0]):
                    _d = round(float(stack[_k, _r, _c]) * 100.0, 1)
                    _t = round(_k * mpf, 1)
                    _ser.append({"t": _t, "depthCm": _d, "passable": bool(_d < thresholdCm)})
                _peak = max((p["depthCm"] for p in _ser), default=0.0)
                if _peak < minPeakCm:
                    continue
                _wet = [p["t"] for p in _ser if not p["passable"]]
                out.append({**{k: v for k, v in s.items()},
                            "peakCm": _peak,
                            "firstFlooded": _wet[0] if _wet else None,
                            "series": _ser})
            except Exception:
                continue
        out.sort(key=lambda r: r["peakCm"], reverse=True)
        total = len(out)
        return out[:max(1, int(limit or 500))], {"count": min(total, max(1, int(limit or 500))),
                                                 "total": total, "truncated": total > int(limit or 500),
                                                 "thresholdCm": thresholdCm, "steps": stack.shape[0]}
    except Exception:
        return [], {"count": 0, "total": 0, "truncated": False}
