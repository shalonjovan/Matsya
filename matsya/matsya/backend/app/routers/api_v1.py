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
