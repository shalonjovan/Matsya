import json
import uuid
import time
import threading
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
        # Set initial status to Processing for elevation/flood
        try:
            sim.status = StatusEnum.Running
            sim.metadata.status = StatusEnum.Running
        except: pass
        # Save immediately with Processing status so frontend can poll
        self._save(sim)
        _list_cache["data"] = None
        # Run heavy generation in background thread to avoid blocking POST
        def _bg_gen(sid, sim_data):
            try:
                # Need to reload sim from data
                s = Simulation.model_validate(sim_data)
                s.id = sid
                # rainfall curve
                try:
                    if s.rainfall and s.rainfall.mode == "variable" and s.rainfall.points:
                        from app.services.rainfall_curve import interpolate
                        totalTime = s.rainfall.totalTime or 6
                        maxRain = s.rainfall.maxRain or 100
                        unit = s.rainfall.unit or "rate"
                        steps = max(12, int(totalTime * 12))
                        res = interpolate(s.rainfall.points, totalTime=totalTime, maxRain=maxRain, unit=unit, steps=steps)
                        s.rainfall.curve = res
                except Exception as e:
                    print(f"bg rainfall curve failed: {e}")
                # elevation
                try:
                    from app.services.elevation import ensure_elevation
                    ensure_elevation(s)
                except Exception as e:
                    print(f"bg elevation failed: {e}")
                # flood
                try:
                    from app.services.flood import ensure_flood
                    ensure_flood(s)
                except Exception as e:
                    print(f"bg flood failed: {e}")
                # Mark completed
                try:
                    s.status = StatusEnum.Completed
                    s.metadata.status = StatusEnum.Completed
                    s.metadata.updated = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
                except: pass
                # Save again with completed status and elevation/flood
                try:
                    # Need to save via store (use self)
                    self._save(s)
                    _list_cache["data"] = None
                except Exception as e:
                    print(f"bg save failed: {e}")
            except Exception as e:
                print(f"bg gen failed: {e}")
                import traceback
                traceback.print_exc()
        # Start background thread
        try:
            # Pass sim data as dict to avoid race
            sim_data = sim.model_dump(mode="python")
            thread = threading.Thread(target=_bg_gen, args=(sim.id, sim_data), daemon=True)
            thread.start()
        except Exception as e:
            print(f"bg thread start failed: {e}")
            # Fallback to synchronous
            try:
                from app.services.elevation import ensure_elevation
                ensure_elevation(sim)
            except: pass
            try:
                from app.services.flood import ensure_flood
                ensure_flood(sim)
            except: pass
            self._save(sim)
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
        # hydrate flood from disk if missing
        try:
            if sim.flood is None or sim.flood.stats is None:
                flood_dir = self.base_path / f"{sim_id}" / "flood"
                json_path = flood_dir / "flood.json"
                png_path = flood_dir / "0.png"
                if json_path.exists():
                    try:
                        stats = json.loads(json_path.read_text())
                        from app.models.simulation import Flood

                        sim.flood = Flood(
                            floodUri=f"/api/simulations/{sim_id}/flood?time=0",
                            stats=stats,
                            width=stats.get("width", 180) if isinstance(stats, dict) else 180,
                            height=stats.get("height", 180) if isinstance(stats, dict) else 180,
                            steps=stats.get("steps", 3) if isinstance(stats, dict) else 3,
                        )
                    except Exception:
                        pass
                elif png_path.exists():
                    try:
                        from app.models.simulation import Flood

                        sim.flood = Flood(
                            floodUri=f"/api/simulations/{sim_id}/flood?time=0",
                            stats={"maxDepth": 0.5, "floodedArea": 0.1},
                            width=180,
                            height=180,
                            steps=3,
                        )
                    except Exception:
                        pass
                else:
                    # legacy fallback
                    for legacy_json in [
                        Path(f"matsya/matsya/backend/data/simulations/{sim_id}/flood/flood.json"),
                        Path(f"backend/data/simulations/{sim_id}/flood/flood.json"),
                        Path(f"data/simulations/{sim_id}/flood/flood.json"),
                    ]:
                        if legacy_json.exists():
                            try:
                                stats = json.loads(legacy_json.read_text())
                                from app.models.simulation import Flood

                                sim.flood = Flood(
                                    floodUri=f"/api/simulations/{sim_id}/flood?time=0",
                                    stats=stats,
                                    width=stats.get("width", 180) if isinstance(stats, dict) else 180,
                                    height=stats.get("height", 180) if isinstance(stats, dict) else 180,
                                    steps=stats.get("steps", 3) if isinstance(stats, dict) else 3,
                                )
                                break
                            except Exception:
                                continue
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
        # Recalculate elevation if bbox changed
        try:
            old_bbox = existing.area.bbox if hasattr(existing.area, "bbox") else None
            new_bbox = updated_sim.area.bbox if hasattr(updated_sim.area, "bbox") else None
            if old_bbox != new_bbox:
                from app.services.elevation import ensure_elevation
                ensure_elevation(updated_sim)
        except Exception as e:
            print(f"elevation recalc on update failed: {e}")
        # Recalculate flood if bbox or rainfall changed
        try:
            old_rain = existing.rainfall.model_dump() if hasattr(existing, "rainfall") and existing.rainfall else None
            new_rain = updated_sim.rainfall.model_dump() if hasattr(updated_sim, "rainfall") and updated_sim.rainfall else None
            old_bbox2 = existing.area.bbox if hasattr(existing.area, "bbox") else None
            new_bbox2 = updated_sim.area.bbox if hasattr(updated_sim.area, "bbox") else None
            if old_rain != new_rain or old_bbox2 != new_bbox2:
                from app.services.flood import ensure_flood
                ensure_flood(updated_sim)
        except Exception as e:
            print(f"flood recalc on update failed: {e}")
        # Recalculate rainfall curve if rainfall changed and mode variable
        try:
            if updated_sim.rainfall and updated_sim.rainfall.mode == "variable" and updated_sim.rainfall.points:
                from app.services.rainfall_curve import interpolate
                totalTime = updated_sim.rainfall.totalTime or 6
                maxRain = updated_sim.rainfall.maxRain or 100
                unit = updated_sim.rainfall.unit or "rate"
                steps = max(12, int(totalTime * 12))
                res = interpolate(updated_sim.rainfall.points, totalTime=totalTime, maxRain=maxRain, unit=unit, steps=steps)
                updated_sim.rainfall.curve = res
        except Exception as e:
            print(f"rainfall curve recalc on update failed: {e}")
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
        # ensure flood for duplicated simulation
        try:
            from app.services.flood import ensure_flood

            ensure_flood(new_sim)
        except Exception as e:
            print(f"flood generation failed for duplicate {new_id}: {e}")
        # ensure rainfall curve for duplicated variable mode
        try:
            if new_sim.rainfall and new_sim.rainfall.mode == "variable" and new_sim.rainfall.points:
                from app.services.rainfall_curve import interpolate
                totalTime = new_sim.rainfall.totalTime or 6
                maxRain = new_sim.rainfall.maxRain or 100
                unit = new_sim.rainfall.unit or "rate"
                steps = max(12, int(totalTime * 12))
                res = interpolate(new_sim.rainfall.points, totalTime=totalTime, maxRain=maxRain, unit=unit, steps=steps)
                new_sim.rainfall.curve = res
        except Exception as e:
            print(f"rainfall curve for duplicate failed: {e}")
        self._save(new_sim)
        _list_cache["data"] = None
        return new_sim


# Singleton store used by router
store = SimulationStore()
