from fastapi import APIRouter, HTTPException, Body, status, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import ValidationError
import io
import uuid
from datetime import datetime, timezone

from app.services.simulation_store import store
from app.services.package_service import create_matsya, read_matsya

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


# Import must be before {sim_id} routes to avoid shadowing
@router.post("/import", status_code=status.HTTP_201_CREATED)
async def import_simulation(file: UploadFile = File(...)):
    try:
        data = await file.read()
        sim = read_matsya(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Create new simulation with new id (do not reuse original id)
    try:
        payload = sim.model_dump(mode="python")
        new_id = str(uuid.uuid4())
        payload["id"] = new_id
        now = datetime.now(timezone.utc)
        if "metadata" not in payload or payload["metadata"] is None:
            payload["metadata"] = {}
        payload["metadata"]["created"] = now
        payload["metadata"]["updated"] = now
        # Ensure top-level status consistent if needed, keep as is
        new_sim = store.create(payload)
        return new_sim.model_dump(mode="json")
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=_validation_error_detail(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{sim_id}/export")
def export_simulation(sim_id: str):
    try:
        sim = store.get(sim_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Simulation not found")

    try:
        data = create_matsya(sim)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    filename = f"{sim.name}.matsya"
    # Sanitize filename for header (basic)
    filename = filename.replace('"', "_").replace("\n", "_").replace("\r", "_")
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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
        from app.services.realtime.manager import REALTIME_ID
    except Exception:
        REALTIME_ID = "realtime-chennai-01"
    if sim_id == REALTIME_ID:
        raise HTTPException(status_code=400, detail="Live realtime sim is managed by the tick loop and cannot be deleted")
    try:
        store.delete(sim_id)
        return None
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Simulation not found")


@router.post("/{sim_id}/duplicate", status_code=status.HTTP_201_CREATED)
def duplicate_simulation(sim_id: str, payload: dict = Body(default={})):
    try:
        from app.services.realtime.manager import REALTIME_ID
    except Exception:
        REALTIME_ID = "realtime-chennai-01"
    if sim_id == REALTIME_ID:
        raise HTTPException(status_code=400, detail="Live realtime sim cannot be duplicated; create a scenario sim instead")
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
