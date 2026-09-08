from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers.simulations import router as simulations_router
from app.routers.layers import router as layers_router
from app.routers.runs import router as runs_router
from app.routers.analysis import router as analysis_router
from app.routers.exports import router as exports_router
from app.routers.live import router as live_router
from app.routers.hydro import router as hydro_router, sim_hydro_router
from app.routers.rainfall import router as rainfall_router
from app.routers.elevation import router as elevation_router, dem_router
from app.routers.flood import router as flood_router
from app.routers.api_v1 import router as api_v1_router

app = FastAPI(title="MATSYA")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(simulations_router)
app.include_router(layers_router)
app.include_router(runs_router)
app.include_router(analysis_router)
app.include_router(exports_router)
app.include_router(live_router)
app.include_router(hydro_router)
app.include_router(sim_hydro_router)
app.include_router(elevation_router)
app.include_router(rainfall_router)
app.include_router(dem_router)
app.include_router(flood_router)
app.include_router(api_v1_router)
@app.get("/api/health")
def health(): return {"status":"ok","version":"0.1.0","engine":"anuga-mock"}


@app.on_event("startup")
async def _realtime_tick_loop():
    """Background tick loop. Opt-in only (REALTIME_LOOP=1) so tests never loop."""
    import os
    if os.getenv("REALTIME_LOOP") != "1":
        return
    import asyncio
    try:
        _every = max(1, int(os.getenv("REALTIME_TICK_MIN", "15") or 15))
    except Exception:
        _every = 15

    async def _loop():
        while True:
            try:
                from app.services.realtime.manager import tick
                tick()
            except Exception:
                pass
            try:
                await asyncio.sleep(_every * 60)
            except Exception:
                return

    try:
        asyncio.create_task(_loop())
    except Exception:
        pass
