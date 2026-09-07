"""Safe-space search: dry + high + not-water + reachable candidates, ranked by routed ETA.

Safe space (frozen): peak depth below threshold across all steps AND
firstFlooded is None (dry), high DEM elevation (ranked), outside lake
masks (excluded), with a verified safest route from the origin (reachable).
"""
import math

MAX_CANDIDATES = 60


def _cell_lonlat(bbox, rows, cols, r, c):
    try:
        minLon, minLat, maxLon, maxLat = [float(x) for x in bbox]
        return (minLon + (c + 0.5) / cols * (maxLon - minLon),
                maxLat - (r + 0.5) / rows * (maxLat - minLat))
    except Exception:
        return None


def find_candidates(sim, bbox, threshold_cm=15.0):
    """Candidate safe spaces. Never raises (empty list on failure)."""
    out: list = []
    try:
        from app.services.road_segments import segment_series
        rows, _meta = segment_series(sim, bbox=list(bbox), thresholdCm=float(threshold_cm),
                                     minPeakCm=0.0, limit=4000)
    except Exception:
        rows = []
    try:
        from app.services.elevation import sample_dem
    except Exception:
        sample_dem = None  # type: ignore
    for s in rows or []:
        try:
            if float(s.get("peakCm", 1e9)) >= float(threshold_cm):
                continue
            if s.get("firstFlooded") is not None:
                continue
            _m = s.get("midpoint") or {}
            _elev = sample_dem(float(_m["lon"]), float(_m["lat"])) if sample_dem else None
            if _elev is None:
                continue
            out.append({"kind": "road", "lat": float(_m["lat"]), "lon": float(_m["lon"]),
                        "elevationM": round(float(_elev), 2), "peakCm": float(s.get("peakCm", 0.0)),
                        "name": str(s.get("name") or s.get("segmentId"))})
        except Exception:
            continue
        if len(out) >= MAX_CANDIDATES:
            break
    # dry off-road cells (stride 6), excluding lake masks
    try:
        from app.services.snapshots import load_snapshots
        import numpy as _np
        snaps, _, _bb = load_snapshots(sim)
        if snaps:
            stack = _np.asarray([_np.asarray(a, dtype=float) for a in snaps])
            peak = stack.max(axis=0)
            rows_n, cols_n = peak.shape
            _cut = float(threshold_cm) / 100.0
            _lake = None
            try:
                from app.services.flood import _dem_for_bbox, _waterbodies_in_bbox, _rasterize_masks
                _dem = _dem_for_bbox(list(bbox), cols_n, rows_n)
                _infos = _waterbodies_in_bbox(list(bbox), _dem, cols_n, rows_n)
                _masks = _rasterize_masks(_infos, list(bbox), cols_n, rows_n) or []
                if _masks:
                    _lake = _np.asarray(_masks[0], dtype=bool)
                    for _m in _masks[1:]:
                        _lake = _lake | _np.asarray(_m, dtype=bool)
            except Exception:
                _lake = None
            for _r in range(0, rows_n, 6):
                for _c in range(0, cols_n, 6):
                    try:
                        if float(peak[_r, _c]) >= _cut:
                            continue
                        if _lake is not None and bool(_lake[_r, _c]):
                            continue
                        _ll = _cell_lonlat(list(bbox), rows_n, cols_n, _r, _c)
                        if not _ll:
                            continue
                        _elev = sample_dem(_ll[0], _ll[1]) if sample_dem else None
                        if _elev is None:
                            continue
                        out.append({"kind": "ground", "lat": round(_ll[1], 6), "lon": round(_ll[0], 6),
                                    "elevationM": round(float(_elev), 2),
                                    "peakCm": round(float(peak[_r, _c]) * 100.0, 1),
                                    "name": "High ground"})
                    except Exception:
                        continue
                    if len(out) >= MAX_CANDIDATES:
                        break
                if len(out) >= MAX_CANDIDATES:
                    break
    except Exception:
        pass
    return out


def rank_safe_spaces(sim, bbox, origin, depart_min=0.0, threshold_cm=15.0, limit=3):
    """Top candidates by verified safest-route ETA. Returns (spaces, reason).

    Single full Dijkstra from the origin over unblocked edges, then every
    dry candidate reachable in that flooded graph is ranked by ETA. Never raises.
    """
    try:
        cands = find_candidates(sim, bbox, threshold_cm)
    except Exception:
        return [], "candidate search failed"
    if not cands:
        return [], "no dry candidate locations"
    try:
        from app.services.safe_routes import earliest_arrival, reconstruct_route, snap_point, build_graph
        from app.services.road_segments import segment_series
        from app.services.snapshots import load_snapshots as _ls
        _snaps, _mpf, _ = _ls(sim)
        rows, _m = segment_series(sim, bbox=list(bbox), thresholdCm=float(threshold_cm),
                                  minPeakCm=0.0, limit=4000)
        _by_id = {s["segmentId"]: s.get("series") or [] for s in rows}
        nodes, adj = build_graph(sim, list(bbox), _by_id)
    except Exception:
        return [], "routable network unavailable"
    try:
        _olat, _olon = float(origin["lat"]), float(origin["lon"])
        _depart = float(depart_min or 0.0)
        _thresh = float(threshold_cm)
    except Exception:
        return [], "invalid origin"
    try:
        _src = snap_point(nodes, _olat, _olon)
        if _src is None:
            return [], "origin outside routable network (200m)"
        _full = earliest_arrival(nodes, adj, _src, None, _depart, _mpf, _thresh, True, full=True)
        if not _full:
            return [], "no reachable safe space"
        _dist, _prev = _full
    except Exception:
        return [], "no reachable safe space"
    ranked = []
    for cand in cands:
        try:
            _nid = snap_point(nodes, float(cand["lat"]), float(cand["lon"]))
            if _nid is None:
                continue
            try:
                if float(_dist.get(_nid, float("inf"))) == float("inf"):
                    continue
            except Exception:
                continue
            _route = reconstruct_route(nodes, _dist, _prev, _src, _nid, _depart, _mpf)
            if not _route:
                continue
            ranked.append({**cand, "route": {
                "etaMin": _route.get("etaMin"), "maxDepthCm": _route.get("maxDepthCm"),
                "path": _route.get("path"), "segmentIds": _route.get("segmentIds"),
                "floodDelayMin": 0.0, "avoidedSegments": []}})
        except Exception:
            continue
    ranked.sort(key=lambda r: (float(r["route"]["etaMin"]), -float(r.get("elevationM", 0) or 0)))
    out = []
    for _i, _r in enumerate(ranked[:max(1, int(limit or 3))]):
        out.append({"rank": _i + 1, **_r})
    if not out:
        return [], "no reachable safe space"
    return out, None
