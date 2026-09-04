"""Rainfall router — curve for variable rain."""
from fastapi import APIRouter, HTTPException
from app.services.simulation_store import store

router = APIRouter(prefix="/api/simulations/{sim_id}/rainfall", tags=["rainfall"])

@router.get("/curve")
def get_curve(sim_id: str, step: float = 300):
    sim = store.get(sim_id)
    if not sim:
        raise HTTPException(404, "simulation not found")
    if not sim.rainfall or not sim.rainfall.curve:
        # Try to generate on fly if variable
        if sim.rainfall and sim.rainfall.mode == "variable" and sim.rainfall.points:
            try:
                from app.services.rainfall_curve import interpolate
                totalTime = sim.rainfall.totalTime or 6
                maxRain = sim.rainfall.maxRain or 100
                unit = sim.rainfall.unit or "rate"
                steps = max(12, int(totalTime * 3600 / step)) if step>0 else 72
                res = interpolate(sim.rainfall.points, totalTime=totalTime, maxRain=maxRain, unit=unit, steps=steps)
                return res
            except Exception as e:
                raise HTTPException(500, str(e))
        raise HTTPException(404, "curve not found")
    return sim.rainfall.curve

@router.post("/curve/generate")
def generate_curve(sim_id: str, body: dict):
    """Generate curve from points without saving simulation."""
    try:
        from app.services.rainfall_curve import interpolate
        points = body.get("points", [])
        totalTime = body.get("totalTime", 6)
        maxRain = body.get("maxRain", 100)
        unit = body.get("unit", "rate")
        steps = body.get("steps", 72)
        res = interpolate(points, totalTime=totalTime, maxRain=maxRain, unit=unit, steps=steps)
        return res
    except Exception as e:
        raise HTTPException(500, str(e))

@router.post("/random")
def random_curve(body: dict):
    try:
        from app.services.rainfall_curve import random_preset
        preset = body.get("preset", "random")
        totalTime = body.get("totalTime", 6)
        maxRain = body.get("maxRain", 100)
        unit = body.get("unit", "rate")
        pts = random_preset(preset, totalTime=totalTime, maxRain=maxRain, unit=unit)
        return {"points": pts}
    except Exception as e:
        raise HTTPException(500, str(e))
