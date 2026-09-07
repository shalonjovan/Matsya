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
