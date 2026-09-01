"""Elevation router — serve stored hypsometric PNG and DEM sample."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path
import json

from app.services.simulation_store import store

router = APIRouter(prefix="/api/simulations/{sim_id}/elevation", tags=["elevation"])
dem_router = APIRouter(prefix="/api/dem", tags=["dem"])

@router.get("")
def get_elevation(sim_id: str):
    sim = store.get(sim_id) if store else None
    if sim is None:
        # try to load directly
        try:
            sim = store.get(sim_id)
        except:
            raise HTTPException(404, "simulation not found")
    # Try to find elevation.png
    # store.base_path is backend/data/simulations, so {id}/elevation.png
    candidates = [
        store.base_path / f"{sim_id}" / "elevation.png",
        Path(f"matsya/matsya/backend/data/simulations/{sim_id}/elevation.png"),
        Path(f"backend/data/simulations/{sim_id}/elevation.png"),
        Path(f"data/simulations/{sim_id}/elevation.png"),
        Path(__file__).resolve().parents[2] / "data" / "simulations" / f"{sim_id}" / "elevation.png",
        Path(__file__).resolve().parents[5] / "assets" / f"elevation_{sim_id}.png",
    ]
    # If not found and sim has no elevation, try to generate on fly via ensure_elevation
    for p in candidates:
        if p.exists():
            return FileResponse(str(p), media_type="image/png")
    # Try to generate on the fly
    try:
        from app.services.elevation import ensure_elevation
        # Ensure sim has elevation
        if sim.elevation is None or sim.elevation.stats is None:
            ensure_elevation(sim)
            # Save updated sim?
            try:
                store._save(sim)
            except: pass
        # Try again
        for p in candidates:
            if p.exists():
                return FileResponse(str(p), media_type="image/png")
        # If still not found, try to generate via clip_and_render directly
        from app.services.elevation import clip_and_render
        bbox = sim.area.bbox if hasattr(sim.area, "bbox") else [80.15,13.08,80.20,13.13]
        _, png, stats = clip_and_render(bbox, 180, 180)
        from fastapi.responses import Response
        return Response(content=png, media_type="image/png")
    except Exception as e:
        raise HTTPException(404, f"elevation not found: {e}")

@router.get("/info")
def get_elevation_info(sim_id: str):
    sim = store.get(sim_id)
    if not sim:
        raise HTTPException(404, "simulation not found")
    if sim.elevation and sim.elevation.stats:
        return sim.elevation.stats
    # try to load from disk
    for p in [store.base_path / f"{sim_id}" / "elevation.json", Path(f"matsya/matsya/backend/data/simulations/{sim_id}/elevation.json")]:
        if p.exists():
            try:
                return json.loads(p.read_text())
            except: pass
    raise HTTPException(404, "elevation info not found")

@dem_router.get("/sample")
def dem_sample(lon: float, lat: float):
    try:
        from app.services.elevation import sample_dem
        elev = sample_dem(lon, lat)
        if elev is None:
            return JSONResponse({"elevation": None, "lon": lon, "lat": lat})
        return {"elevation": elev, "lon": lon, "lat": lat}
    except Exception as e:
        raise HTTPException(500, str(e))
