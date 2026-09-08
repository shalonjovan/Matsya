"""Versioned public API (v1, open reads). Legacy /api/* paths are untouched."""
from fastapi import APIRouter, HTTPException, Query
from app.services.simulation_store import store

router = APIRouter(prefix="/api/v1", tags=["api-v1"])

DISCLAIMER = "Model output \u2014 verify on the ground before operational use."


def v1_envelope(data):
    try:
        from datetime import datetime, timezone
        _now = datetime.now(timezone.utc).isoformat()
    except Exception:
        _now = ""
    return {"v": "1", "generatedAt": _now, "disclaimer": DISCLAIMER, "data": data}


def _get_sim(sim_id: str):
    try:
        sim = store.get(sim_id)
    except FileNotFoundError:
        raise HTTPException(404, "simulation not found")
    except Exception as e:
        raise HTTPException(500, str(e))
    if not sim:
        raise HTTPException(404, "simulation not found")
    return sim


@router.get("/simulations/{sim_id}/roads/segments")
def road_segments(sim_id: str, thresholdCm: float = 15.0,
                  minPeakCm: float = 0.0, limit: int = Query(500, ge=1, le=4000)):
    sim = _get_sim(sim_id)
    from app.services.road_segments import segment_series
    try:
        _bb = sim.get("area", {}).get("bbox") if isinstance(sim, dict) else sim.area.bbox
    except Exception:
        _bb = [80.15, 13.08, 80.20, 13.13]
    rows, meta = segment_series(sim, bbox=list(_bb), thresholdCm=thresholdCm,
                                minPeakCm=minPeakCm, limit=limit)
    return v1_envelope({"segments": rows, "meta": meta})


def _flood_stats(sim):
    try:
        _f = sim.get("flood") if isinstance(sim, dict) else getattr(sim, "flood", None)
        _st = _f.get("stats") if isinstance(_f, dict) else getattr(_f, "stats", None)
        if _st is not None and not isinstance(_st, dict) and hasattr(_st, "model_dump"):
            _st = _st.model_dump(mode="json")
        return dict(_st or {})
    except Exception:
        return {}


def _node_states(sim):
    """(nodes, reaches, source). Persisted SWMM volumes win; else depth-inferred (honest)."""
    stats = _flood_stats(sim)
    persisted = stats.get("swmmNodes")
    if isinstance(persisted, list) and persisted and stats.get("swmmCoupled"):
        nodes = [{"id": str(n.get("id")), "floodVolumeM3": n.get("floodVolumeM3"),
                  "surcharged": bool((n.get("floodVolumeM3") or 0) > 0),
                  "capacityUsedPct": None} for n in persisted]
        return nodes, "swmm"
    from app.services import analysis as _analysis
    try:
        _d = _analysis.drain_impact(sim) or []
    except Exception:
        _d = []
    nodes = [{"id": d.get("id"), "floodVolumeM3": None,
              "surcharged": bool(d.get("status") == "surcharged"),
              "capacityUsedPct": None} for d in _d]
    return nodes, "inferred-depth"


def _reaches(bbox, stats):
    try:
        from app.services.hydro.river_capacity import build_reaches
        _raw = build_reaches(list(bbox), max_n=10) or []
    except Exception:
        return []
    _over = set((stats or {}).get("overtoppedRivers", []) or [])
    out = []
    for _rr in _raw:
        try:
            _rid = str(_rr.get("id"))
            out.append({"id": _rid,
                        "bankStatus": "overtopped" if _rid in _over else "within-banks"})
        except Exception:
            continue
    return out


@router.get("/simulations/{sim_id}/drainage/nodes")
def drainage_nodes(sim_id: str):
    sim = _get_sim(sim_id)
    try:
        _bb = sim.get("area", {}).get("bbox") if isinstance(sim, dict) else sim.area.bbox
    except Exception:
        _bb = [80.15, 13.08, 80.20, 13.13]
    nodes, source = _node_states(sim)
    reaches = _reaches(list(_bb), _flood_stats(sim))
    return v1_envelope({"nodes": nodes, "reaches": reaches, "source": source})


@router.get("/alerts")
def alerts(simId: str, withinMin: float = 30.0, thresholdCm: float = 15.0):
    sim = _get_sim(simId)
    from app.services.road_segments import segment_series
    try:
        _bb = sim.get("area", {}).get("bbox") if isinstance(sim, dict) else sim.area.bbox
    except Exception:
        _bb = [80.15, 13.08, 80.20, 13.13]
    rows, _meta = segment_series(sim, bbox=list(_bb), thresholdCm=thresholdCm,
                                 minPeakCm=0.0, limit=4000)
    flooded, upcoming = [], []
    for s in rows:
        try:
            _ser = s.get("series") or []
            if not _ser:
                continue
            if not _ser[0].get("passable", True):
                flooded.append(s["segmentId"])
                continue
            for p in _ser[1:]:
                try:
                    if not p.get("passable", True) and float(p.get("t", 1e9)) <= float(withinMin):
                        upcoming.append({"segmentId": s["segmentId"], "etaMin": float(p["t"])})
                        break
                except Exception:
                    continue
        except Exception:
            continue
    nodes, _src = _node_states(sim)
    surcharged = [n["id"] for n in nodes if n.get("surcharged")]
    return v1_envelope({
        "floodedNow": flooded[:500],
        "floodingWithinMin": upcoming[:500],
        "surchargedNodes": surcharged[:500],
        "truncated": len(flooded) > 500 or len(upcoming) > 500 or len(surcharged) > 500,
    })


@router.post("/routes/safe")
def safe_route(body: dict):
    _o = (body or {}).get("origin") or {}
    _d = (body or {}).get("destination") or {}
    if not isinstance(_o, dict) or not isinstance(_d, dict):
        raise HTTPException(422, "origin/destination as {lat, lon} are required")
    if any(_o.get(k) is None for k in ("lat", "lon")) or any(_d.get(k) is None for k in ("lat", "lon")):
        raise HTTPException(422, "origin/destination as {lat, lon} are required")
    try:
        _olat, _olon = float(_o.get("lat") or 0), float(_o.get("lon") or 0)
        _dlat, _dlon = float(_d.get("lat") or 0), float(_d.get("lon") or 0)
    except Exception:
        raise HTTPException(422, "origin/destination as {lat, lon} are required")
    try:
        _sim_id = str((body or {}).get("simId", ""))
    except Exception:
        _sim_id = ""
    if not _sim_id:
        raise HTTPException(422, "simId is required")
    try:
        _depart = float((body or {}).get("departAtMin", 0.0) or 0.0)
        _thresh = float((body or {}).get("thresholdCm", 15.0) or 15.0)
    except Exception:
        raise HTTPException(422, "departAtMin/thresholdCm must be numbers")
    sim = _get_sim(_sim_id)
    try:
        _bb = sim.get("area", {}).get("bbox") if isinstance(sim, dict) else sim.area.bbox
    except Exception:
        _bb = [80.15, 13.08, 80.20, 13.13]
    from app.services.safe_routes import find_routes
    res = find_routes(sim, list(_bb),
                      {"lat": _olat, "lon": _olon}, {"lat": _dlat, "lon": _dlon},
                      depart_min=_depart, threshold_cm=_thresh)
    if res.get("reason") in ("origin outside routable network (200m)",
                             "destination outside routable network (200m)"):
        raise HTTPException(422, res["reason"])
    return v1_envelope(res)


@router.post("/event/2015/replay", status_code=201)
def replay_2015(body: dict | None = None):
    from app.services.event_2015 import build_event_sim
    try:
        _suffix = str(((body or {}).get("nameSuffix")) or "")
    except Exception:
        _suffix = ""
    try:
        sim = build_event_sim(_suffix)
        _sid = getattr(sim, "id", None)
        if _sid is None and isinstance(sim, dict):
            _sid = sim.get("id")
    except Exception as e:
        raise HTTPException(400, f"replay sim failed: {e}")
    return v1_envelope({"simId": _sid})


@router.get("/event/2015/facts")
def event_2015_facts():
    from app.services.event_2015 import load_fixture
    return v1_envelope(load_fixture())


@router.get("/event/2015/compare")
def event_2015_compare(simId: str):
    from app.services.event_2015 import compare
    try:
        _s = store.get(simId)
    except FileNotFoundError:
        raise HTTPException(404, "simulation not found")
    except Exception as e:
        raise HTTPException(500, str(e))
    if not _s:
        raise HTTPException(404, "simulation not found")
    return v1_envelope(compare(simId))


@router.post("/safe-spaces")
def safe_spaces(body: dict):
    _o = (body or {}).get("origin") or {}
    if not isinstance(_o, dict) or _o.get("lat") is None or _o.get("lon") is None:
        raise HTTPException(422, "origin as {lat, lon} is required")
    try:
        _sim_id = str((body or {}).get("simId", ""))
    except Exception:
        _sim_id = ""
    if not _sim_id:
        raise HTTPException(422, "simId is required")
    try:
        _olat, _olon = float(_o.get("lat") or 0), float(_o.get("lon") or 0)
        _depart = float((body or {}).get("departAtMin", 0.0) or 0.0)
        _thresh = float((body or {}).get("thresholdCm", 15.0) or 15.0)
        _limit = int((body or {}).get("limit", 3) or 3)
    except Exception:
        raise HTTPException(422, "departAtMin/thresholdCm/limit must be numbers")
    if not (-90 <= _olat <= 90 and -180 <= _olon <= 180):
        raise HTTPException(422, "origin outside valid lon/lat range")
    sim = _get_sim(_sim_id)
    try:
        _bb = sim.get("area", {}).get("bbox") if isinstance(sim, dict) else sim.area.bbox
    except Exception:
        _bb = [80.15, 13.08, 80.20, 13.13]
    from app.services.safe_spaces import rank_safe_spaces, nearest_road_point, SNAP_FALLBACK_M
    _origin = {"lat": _olat, "lon": _olon}
    _snapped = None
    spaces, reason = rank_safe_spaces(sim, list(_bb), _origin,
                                      depart_min=_depart, threshold_cm=_thresh,
                                      limit=max(1, min(10, _limit)))
    if reason == "origin outside routable network (200m)":
        # fallback: nearest mapped road within 2 km, explicitly disclosed —
        # road coverage is sparse in places, and a click in a gap should still help
        try:
            _near = nearest_road_point(sim, list(_bb), _olat, _olon)
        except Exception:
            _near = None
        if _near is not None and float(_near.get("distanceM", 1e9)) <= float(SNAP_FALLBACK_M):
            _origin = {"lat": float(_near["lat"]), "lon": float(_near["lon"])}
            _snapped = {"lat": float(_near["lat"]), "lon": float(_near["lon"]),
                        "distanceM": float(_near["distanceM"])}
            spaces, reason = rank_safe_spaces(sim, list(_bb), _origin,
                                              depart_min=_depart, threshold_cm=_thresh,
                                              limit=max(1, min(10, _limit)))
        else:
            raise HTTPException(422, "No mapped roads within 2 km of that point — try a point near a road")
    return v1_envelope({"spaces": spaces, "reason": reason, "originSnapped": _snapped})


@router.post("/nowcasts", status_code=201)
def create_nowcast(body: dict):
    """Radar nowcast cells in, running zoned sim out. Cells follow zone rules (cap 12)."""
    try:
        _name = str((body or {}).get("name", "nowcast") or "nowcast")
        _bbox = list((body or {}).get("bbox") or [80.15, 13.08, 80.20, 13.13])
        _issued = str((body or {}).get("issuedAt", "") or "")
        _cells = list((body or {}).get("cells") or [])
        _base = float((body or {}).get("baseRateMmHr", 0.0) or 0.0)
        _dur = float((body or {}).get("durationHr", 1.0) or 1.0)
    except Exception:
        raise HTTPException(422, "name/bbox/cells with issuedAt are required")
    if not _cells:
        raise HTTPException(422, "cells must be a non-empty list")
    from app.services.rainfall_zones import parse_zones, paint_rate_grid
    zones, dropped = parse_zones({"zones": _cells})
    try:
        from app.services.simulation_store import store as _store
        sim = _store.create({
            "name": f"{_name} (radar {_issued})" if _issued else _name,
            "area": {"bbox": _bbox, "crs": "EPSG:4326"},
            "rainfall": {"mode": "constant", "rateMmHr": _base, "durationHr": _dur,
                         "constantRate": _base, "zones": zones},
        })
    except Exception as e:
        raise HTTPException(400, f"simulation create failed: {e}")
    try:
        import numpy as _np
        _grid = paint_rate_grid(_base, zones, _bbox, 180, 180, _dur)
        _total = round(float(_np.mean(_grid)), 2)
    except Exception:
        _total = None
    try:
        _sid = getattr(sim, "id", None)
        if _sid is None and isinstance(sim, dict):
            _sid = sim.get("id")
    except Exception:
        _sid = None
    return v1_envelope({"simId": _sid, "acceptedCells": len(zones),
                        "droppedCells": list(dropped or []), "totalRainMm": _total})


@router.post("/crowd/reports", status_code=201)
def create_crowd_report(body: dict):
    from app.services.realtime.manager import REALTIME_ID, add_crowd_report
    try:
        _sid = str((body or {}).get("simId") or REALTIME_ID)
        _lat = (body or {}).get("lat")
        _lon = (body or {}).get("lon")
        _depth = (body or {}).get("depthCm")
        _kind = str((body or {}).get("kind", "other") or "other")
        _note = str((body or {}).get("note", "") or "")
    except Exception:
        raise HTTPException(422, "lat/lon/depthCm/kind are required")
    if _lat is None or _lon is None or _depth is None:
        raise HTTPException(422, "lat/lon/depthCm are required")
    try:
        rep = add_crowd_report(_sid, _lat, _lon, _depth, _kind, _note)
    except FileNotFoundError:
        raise HTTPException(404, "simulation not found")
    except ValueError as e:
        raise HTTPException(422, str(e))
    # apply immediately so the reporter sees it (next tick re-applies anyway)
    try:
        from app.services.realtime.manager import apply_crowd_overlay
        apply_crowd_overlay(_sid)
    except Exception:
        pass
    return v1_envelope({"reportId": rep["id"]})


@router.get("/crowd/reports")
def get_crowd_reports(simId: str = ""):
    from app.services.realtime.manager import REALTIME_ID, list_crowd_reports
    _sid = simId or REALTIME_ID
    try:
        from app.services.simulation_store import store
        store.get(_sid)
    except FileNotFoundError:
        raise HTTPException(404, "simulation not found")
    except Exception as e:
        raise HTTPException(500, str(e))
    return v1_envelope({"reports": list_crowd_reports(_sid)})
