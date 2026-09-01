from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers.simulations import router as simulations_router
from app.routers.layers import router as layers_router
from app.routers.runs import router as runs_router
from app.routers.analysis import router as analysis_router
from app.routers.exports import router as exports_router
from app.routers.live import router as live_router
from app.routers.hydro import router as hydro_router, sim_hydro_router
from app.routers.elevation import router as elevation_router, dem_router

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
app.include_router(dem_router)
@app.get("/api/health")
def health(): return {"status":"ok","version":"0.1.0","engine":"anuga-mock"}
