"""Flood router — serve stored flood PNG per time step."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response
from pathlib import Path
import json

from app.services.simulation_store import store

router = APIRouter(prefix="/api/simulations/{sim_id}/flood", tags=["flood"])


@router.get("/stats")
def get_flood_stats(sim_id: str):
    """Return stored flood stats incl. mass_error, wbCount, surchargedDrains."""
    try:
        sim = store.get(sim_id)
    except FileNotFoundError:
        raise HTTPException(404, "simulation not found")
    except Exception as e:
        raise HTTPException(404, f"simulation not found: {e}")
    # prefer in-memory stats on sim
    try:
        if sim.flood is not None and getattr(sim.flood, "stats", None):
            s = sim.flood.stats
            if isinstance(s, dict):
                return s
            try:
                return s.model_dump(mode="json")  # type: ignore
            except Exception:
                pass
            try:
                return dict(vars(s))
            except Exception:
                pass
    except Exception:
        pass
    # fall back to flood.json on disk
    candidates = [
        store.base_path / f"{sim_id}" / "flood" / "flood.json",
        Path(f"matsya/matsya/backend/data/simulations/{sim_id}/flood/flood.json"),
        Path(f"backend/data/simulations/{sim_id}/flood/flood.json"),
    ]
    for p in candidates:
        try:
            if p.exists():
                return json.loads(p.read_text())
        except Exception:
            continue
    raise HTTPException(404, f"flood stats not found for {sim_id}")


@router.get("")
def get_flood(sim_id: str, time: int = 0, palette: str = "blue"):
    # Validate sim exists
    try:
        sim = store.get(sim_id)
    except FileNotFoundError:
        raise HTTPException(404, "simulation not found")
    except Exception as e:
        raise HTTPException(404, f"simulation not found: {e}")

    # Clamp time to valid range if stats available
    try:
        if sim.flood and sim.flood.steps:
            max_steps = sim.flood.steps
            if time < 0:
                time = 0
            elif time >= max_steps:
                time = max_steps - 1
    except Exception:
        pass

    # Variant palette: render on the fly from stored snapshots (never the stored bytes)
    if (palette or "blue") != "blue":
        from app.services.flood import DEPTH_PALETTES, render_depth_png
        if palette not in DEPTH_PALETTES:
            raise HTTPException(400, f"unknown palette {palette!r} (expected one of {sorted(DEPTH_PALETTES)})")
        import numpy as _np
        _snaps = None
        for p in [store.base_path / f"{sim_id}" / "flood" / "snapshots.npy",
                  Path(f"matsya/matsya/backend/data/simulations/{sim_id}/flood/snapshots.npy"),
                  Path(f"backend/data/simulations/{sim_id}/flood/snapshots.npy"),
                  Path(f"data/simulations/{sim_id}/flood/snapshots.npy"),
                  Path(__file__).resolve().parents[2] / "data" / "simulations" / f"{sim_id}" / "flood" / "snapshots.npy"]:
            try:
                if p.exists():
                    _snaps = [a for a in _np.load(str(p))]
                    break
            except Exception:
                continue
        if not _snaps:
            raise HTTPException(404, f"flood snapshots not found for {sim_id}")
        try:
            _stats = None
            _fobj = getattr(sim, "flood", None)
            _s = getattr(_fobj, "stats", None) if _fobj is not None else None
            if isinstance(_s, dict):
                _stats = _s
            elif _s is not None:
                try:
                    _stats = _s.model_dump(mode="json")
                except Exception:
                    try:
                        _stats = dict(vars(_s))
                    except Exception:
                        _stats = None
        except Exception:
            _stats = None
        try:
            _png = render_depth_png(_snaps[max(0, min(time, len(_snaps) - 1))], _stats, palette)
        except ValueError as e:
            raise HTTPException(400, str(e))
        return Response(content=_png, media_type="image/png")

    # Candidates for PNG
    candidates = [
        store.base_path / f"{sim_id}" / "flood" / f"{time}.png",
        Path(f"matsya/matsya/backend/data/simulations/{sim_id}/flood/{time}.png"),
        Path(f"backend/data/simulations/{sim_id}/flood/{time}.png"),
        Path(f"data/simulations/{sim_id}/flood/{time}.png"),
        Path(__file__).resolve().parents[2] / "data" / "simulations" / f"{sim_id}" / "flood" / f"{time}.png",
    ]
    for p in candidates:
        if p.exists():
            return FileResponse(str(p), media_type="image/png")

    # Try to generate on the fly via ensure_flood if missing
    try:
        from app.services.flood import ensure_flood, generate_flood
        # If sim.flood is None, try to ensure
        if sim.flood is None or sim.flood.stats is None:
            try:
                ensure_flood(sim)
                try:
                    store._save(sim)
                except Exception:
                    pass
                # retry candidates
                for p in candidates:
                    if p.exists():
                        return FileResponse(str(p), media_type="image/png")
            except Exception:
                pass
        # fallback: generate directly and return bytes
        # try to generate flood png on fly
        try:
            bbox = sim.area.bbox if hasattr(sim.area, "bbox") else [80.15, 13.08, 80.20, 13.13]
            # rainfall
            try:
                if hasattr(sim.rainfall, "rateMmHr"):
                    rainfall = {"rateMmHr": sim.rainfall.rateMmHr, "durationHr": sim.rainfall.durationHr}
                else:
                    rainfall = sim.rainfall  # type: ignore
            except Exception:
                rainfall = {"rateMmHr": 50, "durationHr": 1}
            _, pngs, _ = generate_flood(bbox, rainfall, width=180, height=180, steps=3)
            idx = max(0, min(time, len(pngs) - 1))
            return Response(content=pngs[idx], media_type="image/png")
        except Exception as e:
            pass
    except Exception as e:
        pass

    raise HTTPException(404, f"flood not found for time={time}: {candidates[0]}")
