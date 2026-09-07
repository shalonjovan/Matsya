
from fastapi import APIRouter, HTTPException
from app.services.simulation_store import store
from app.services import analysis

router = APIRouter(prefix="/api/simulations/{sim_id}", tags=["analysis"])

@router.get("/point")
def point(sim_id: str, lat: float, lon: float, time: int = 0):
    sim = store.get(sim_id)
    if not sim: raise HTTPException(404, "simulation not found")
    return analysis.point_query(lat, lon, time, sim)

@router.get("/affected-areas")
def affected(sim_id: str):
    sim = store.get(sim_id)
    if not sim: raise HTTPException(404, "simulation not found")
    return analysis.affected_areas(sim)

@router.get("/roads")
def roads(sim_id: str):
    sim = store.get(sim_id)
    if not sim: raise HTTPException(404, "simulation not found")
    return analysis.road_impact(sim)

@router.get("/drains")
def drains(sim_id: str):
    sim = store.get(sim_id)
    if not sim: raise HTTPException(404, "simulation not found")
    return analysis.drain_impact(sim)

@router.get("/report")
def report(sim_id: str):
    sim = store.get(sim_id)
    if not sim: raise HTTPException(404, "simulation not found")
    areas = analysis.affected_areas(sim)
    roads = analysis.road_impact(sim)
    # stats: sim flood stats first (computed), ANUGA runs legacy, never invented
    try:
        _fst = sim.flood.stats if hasattr(sim, "flood") and sim.flood is not None else None
        _fst = _fst if isinstance(_fst, dict) else (_fst.model_dump(mode="json") if _fst is not None and hasattr(_fst, "model_dump") else {})
    except Exception:
        _fst = {}
    stats = dict(_fst or {})
    if not stats:
        try:
            from app.services.engine import anuga_runner as engine
            runs = engine.list_runs(sim_id)
            if runs and "results" in runs[-1]:
                stats = dict(runs[-1]["results"]["stats"])
        except Exception:
            pass
    try:
        _mpf = float(stats.get("minutesPerFrame", 5.0) or 5.0)
        _steps = int(stats.get("steps", 0) or 0)
        _n = _steps * _mpf
        floodDuration = "%dh %02dm" % (int(_n // 60), int(_n % 60)) if _steps else None
    except Exception:
        floodDuration = None
    # hydro stats if available
    hydro_stats=None
    try:
        from app.services.hydro.asset_loader import load_assets
        from app.services.hydro.snap import snap_drains_to_waterbodies
        data = load_assets("assets")
        snap_res = snap_drains_to_waterbodies(data["micro"], data["macro"], data["rivers"], data["waterbodies"], tol=50)
        hydro_stats={"snapped": snap_res["stats"]["snapped_to_waterbody"], "waterbodies": len(data["waterbodies"]), "rivers": len(data["rivers"]), "maxStage": None}
    except: hydro_stats=None
    return {
        "simulation": {"name": sim.name, "area": sim.area.model_dump() if hasattr(sim.area,"model_dump") else sim.area, "rainfall": sim.rainfall.model_dump() if hasattr(sim.rainfall,"model_dump") else sim.rainfall, "duration": getattr(sim.rainfall,"durationHr",1)},
        "floodStats": {"maxDepth": stats.get("maxDepth"), "floodedArea": stats.get("floodedArea"), "totalRainMm": stats.get("totalRainMm"), "mass_error": stats.get("mass_error"), "wbCount": stats.get("wbCount"), "surchargedDrains": stats.get("surchargedDrains"), "floodDuration": floodDuration},
        "spatial": {"affectedAreas": areas, "roads": roads},
        "hydraulic": {"surchargedDrains": stats.get("surchargedDrains", 0), "overtoppedLakes": stats.get("overtoppedLakes", 0), "overtoppedRivers": stats.get("overtoppedRivers", []), "spillVolumeM3": stats.get("spillVolumeM3", 0)},
        "hydro": hydro_stats
    }
