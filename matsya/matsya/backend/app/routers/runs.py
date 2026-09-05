
from fastapi import APIRouter, HTTPException
from app.services.simulation_store import store
from app.services.engine import swmm_runner as engine

router = APIRouter(prefix="/api/simulations/{sim_id}", tags=["runs"])

@router.post("/run", status_code=202)
def start_run(sim_id: str):
    sim = store.get(sim_id)
    if not sim: raise HTTPException(404, "simulation not found")
    # check missing datasets §5.2 but allow run
    run_id = engine.run_simulation(sim_id, sim.model_dump() if hasattr(sim,"model_dump") else sim)
    return {"runId": run_id, "status":"Running", "simId": sim_id}

@router.get("/runs/{run_id}")
def get_run(sim_id: str, run_id: str):
    r = engine.get_run(run_id)
    if not r or r["simId"] != sim_id: raise HTTPException(404, "run not found")
    return r

@router.get("/runs")
def list_runs(sim_id: str):
    sim = store.get(sim_id)
    if not sim: raise HTTPException(404, "simulation not found")
    return engine.list_runs(sim_id)
