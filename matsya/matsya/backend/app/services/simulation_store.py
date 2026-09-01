import json
import uuid
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from pydantic import ValidationError

from app.models.simulation import Simulation, StatusEnum
from app.config import settings

# Simple cache for list() — 5s TTL
_list_cache = {"data": None, "ts": 0, "count": 0}


def _resolve_storage_path(raw: str | Path | None = None) -> Path:
    if raw is None:
        raw = settings.storage_path
    p = Path(raw)
    if p.is_absolute():
        return p
    # Resolve relative to backend root (matsya/matsya/backend)
    # __file__ is .../backend/app/services/simulation_store.py -> parents[2] is backend
    try:
        backend_root = Path(__file__).resolve().parents[2]
        candidate = (backend_root / p).resolve()
        return candidate
    except Exception:
        return p.resolve()


class SimulationStore:
    def __init__(self, storage_path: str | Path | None = None):
        self.base_path = _resolve_storage_path(storage_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _file(self, sim_id: str) -> Path:
        return self.base_path / f"{sim_id}.json"

    def _save(self, sim: Simulation) -> None:
        self.base_path.mkdir(parents=True, exist_ok=True)
        path = self._file(sim.id)
        data = sim.model_dump(mode="json")
        path.write_text(json.dumps(data, indent=2))

    def list(self) -> List[Simulation]:
        # Check cache (5s TTL, also invalidate if file count changed)
        now = time.time()
        try:
            file_count = len(list(self.base_path.glob("*.json"))) if self.base_path.exists() else 0
        except:
            file_count = 0
        if _list_cache["data"] is not None and (now - _list_cache["ts"] < 5) and _list_cache["count"] == file_count:
            return _list_cache["data"]
        sims: List[Simulation] = []
        if not self.base_path.exists():
            _list_cache["data"] = sims
            _list_cache["ts"] = now
            _list_cache["count"] = file_count
            return sims
        # Use faster file reading and minimal validation for list (summary only)
        for f in self.base_path.glob("*.json"):
            try:
                raw = json.loads(f.read_text())
                # For list, we don't need full validation of all fields, just basic
                sim = Simulation.model_validate(raw)
                sims.append(sim)
            except Exception:
                continue
        # Sort by updated descending for deterministic order
        try:
            sims.sort(key=lambda s: s.metadata.updated, reverse=True)
        except Exception:
            pass
        _list_cache["data"] = sims
        _list_cache["ts"] = now
        _list_cache["count"] = file_count
        return sims

    def create(self, data: dict) -> Simulation:
        sim = Simulation.model_validate(data)
        # ensure elevation (hypsometric PNG) on creation
        try:
            from app.services.elevation import ensure_elevation

            ensure_elevation(sim)
        except Exception as e:
            print(f"elevation generation failed: {e}")
            import traceback

            traceback.print_exc()
        self._save(sim)
        _list_cache["data"] = None
        return sim

    def get(self, sim_id: str) -> Simulation:
        path = self._file(sim_id)
        if not path.exists():
            raise FileNotFoundError(sim_id)
        raw = json.loads(path.read_text())
        sim = Simulation.model_validate(raw)
        # hydrate elevation from disk if missing (ensure elevation.json is loaded)
        try:
            if sim.elevation is None or sim.elevation.stats is None:
                elev_dir = self.base_path / f"{sim_id}"
                json_path = elev_dir / "elevation.json"
                png_path = elev_dir / "elevation.png"
                if json_path.exists():
                    try:
                        stats = json.loads(json_path.read_text())
                        from app.models.simulation import Elevation

                        sim.elevation = Elevation(
                            elevationUri=f"/api/simulations/{sim_id}/elevation",
                            stats=stats,
                            width=stats.get("width", 180) if isinstance(stats, dict) else 180,
                            height=stats.get("height", 180) if isinstance(stats, dict) else 180,
                        )
                    except Exception:
                        pass
                elif png_path.exists():
                    pass
                else:
                    # legacy fallback for double-nested check
                    legacy_json = Path(f"matsya/matsya/backend/data/simulations/{sim_id}/elevation.json")
                    if legacy_json.exists():
                        try:
                            stats = json.loads(legacy_json.read_text())
                            from app.models.simulation import Elevation

                            sim.elevation = Elevation(
                                elevationUri=f"/api/simulations/{sim_id}/elevation",
                                stats=stats,
                                width=stats.get("width", 180) if isinstance(stats, dict) else 180,
                                height=stats.get("height", 180) if isinstance(stats, dict) else 180,
                            )
                        except Exception:
                            pass
        except Exception:
            pass
        return sim

    def update(self, sim_id: str, patch: dict) -> Simulation:
        existing = self.get(sim_id)

        # Use python mode to keep datetime objects for merging
        base = existing.model_dump(mode="python")

        def deep_merge(target: dict, patch_dict: dict) -> dict:
            for k, v in patch_dict.items():
                if k == "id":
                    continue
                if isinstance(v, dict) and isinstance(target.get(k), dict):
                    deep_merge(target[k], v)
                else:
                    target[k] = v
            return target

        merged = deep_merge(base, patch or {})
        merged["id"] = sim_id

        now = datetime.now(timezone.utc)
        if "metadata" not in merged or merged["metadata"] is None:
            merged["metadata"] = {}
        # Ensure metadata dict has correct types; set updated
        merged["metadata"]["updated"] = now

        updated_sim = Simulation.model_validate(merged)
        # Ensure metadata updated is exactly now (model_validate may parse string)
        updated_sim.metadata.updated = now
        # Also keep top-level status in sync if needed? Don't force
        self._save(updated_sim)
        _list_cache["data"] = None
        return updated_sim

    def delete(self, sim_id: str) -> None:
        path = self._file(sim_id)
        if not path.exists():
            raise FileNotFoundError(sim_id)
        path.unlink()
        _list_cache["data"] = None

    def duplicate(self, sim_id: str, name: str | None = None) -> Simulation:
        orig = self.get(sim_id)
        data = orig.model_dump(mode="python")
        new_id = str(uuid.uuid4())
        data["id"] = new_id
        if name:
            data["name"] = name
        else:
            data["name"] = f"{orig.name}_copy"
        now = datetime.now(timezone.utc)
        if "metadata" not in data or data["metadata"] is None:
            data["metadata"] = {}
        data["metadata"]["created"] = now
        data["metadata"]["updated"] = now
        data["metadata"]["status"] = "Ready"
        data["status"] = "Ready"
        # Purge results if needed? Keep as is but status Reset to Ready
        new_sim = Simulation.model_validate(data)
        new_sim.metadata.created = now
        new_sim.metadata.updated = now
        new_sim.metadata.status = StatusEnum.Ready
        new_sim.status = StatusEnum.Ready
        # ensure elevation for duplicated simulation (regenerate for new id)
        try:
            from app.services.elevation import ensure_elevation

            ensure_elevation(new_sim)
        except Exception as e:
            print(f"elevation generation failed for duplicate {new_id}: {e}")
        self._save(new_sim)
        _list_cache["data"] = None
        return new_sim


# Singleton store used by router
store = SimulationStore()
