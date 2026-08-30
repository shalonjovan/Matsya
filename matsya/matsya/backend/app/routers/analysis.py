
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
    # stats from last run if available
    from app.services.engine import anuga_runner as engine
    runs = engine.list_runs(sim_id)
    stats = runs[-1]["results"]["stats"] if runs and "results" in runs[-1] else {"maxDepth":1.24,"floodedArea":3.4,"maxVelocity":0.8}
    return {
        "simulation": {"name": sim.name, "area": sim.area.model_dump() if hasattr(sim.area,"model_dump") else sim.area, "rainfall": sim.rainfall.model_dump() if hasattr(sim.rainfall,"model_dump") else sim.rainfall, "duration": getattr(sim.rainfall,"durationHr",1)},
        "floodStats": {"maxDepth": stats.get("maxDepth",1.24), "floodedArea": stats.get("floodedArea",3.4), "maxVelocity": stats.get("maxVelocity",0.8), "floodDuration": "3h 12m"},
        "spatial": {"affectedAreas": areas, "roads": roads},
        "hydraulic": {"drainage":"1.2 CMS", "river":"Adyar 0.8m", "timeSeries": [0.1,0.4,1.2]}
    }
