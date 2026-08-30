from fastapi import APIRouter, HTTPException, Body, status
from pydantic import ValidationError

from app.services.simulation_store import store

router = APIRouter(prefix="/api/simulations", tags=["simulations"])


def _validation_error_detail(e: ValidationError):
    try:
        errs = e.errors()
        for err in errs:
            ctx = err.get("ctx")
            if ctx and "error" in ctx:
                ctx["error"] = str(ctx["error"])
        return errs
    except Exception:
        return str(e)


@router.get("", response_model=list)
@router.get("/", response_model=list, include_in_schema=False)
def list_simulations():
    sims = store.list()
    return [s.model_dump(mode="json") for s in sims]


@router.post("", status_code=status.HTTP_201_CREATED)
@router.post("/", status_code=status.HTTP_201_CREATED, include_in_schema=False)
def create_simulation(payload: dict = Body(...)):
    try:
        sim = store.create(payload)
        return sim.model_dump(mode="json")
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=_validation_error_detail(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Import stub must be before {sim_id} routes to avoid shadowing
@router.post("/import")
def import_stub():
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get("/{sim_id}")
def get_simulation(sim_id: str):
    try:
        sim = store.get(sim_id)
        return sim.model_dump(mode="json")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Simulation not found")


@router.patch("/{sim_id}")
def update_simulation(sim_id: str, payload: dict = Body(...)):
    try:
        sim = store.update(sim_id, payload)
        return sim.model_dump(mode="json")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Simulation not found")
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=_validation_error_detail(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{sim_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_simulation(sim_id: str):
    try:
        store.delete(sim_id)
        return None
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Simulation not found")


@router.post("/{sim_id}/duplicate", status_code=status.HTTP_201_CREATED)
def duplicate_simulation(sim_id: str, payload: dict = Body(default={})):
    try:
        name = None
        if isinstance(payload, dict):
            name = payload.get("name")
        sim = store.duplicate(sim_id, name)
        return sim.model_dump(mode="json")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Simulation not found")
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=_validation_error_detail(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Export stub for Task 1.2
@router.post("/{sim_id}/export")
def export_stub(sim_id: str):
    raise HTTPException(status_code=501, detail="Not implemented")
