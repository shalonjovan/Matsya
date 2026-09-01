"""Package service for .matsya ZIP per prd §6."""
import io
import json
import zipfile

from app.models.simulation import Simulation
from app.models.matsya_package import MATSYA_VERSION


def create_matsya(sim: Simulation) -> bytes:
    """Create .matsya ZIP bytes from Simulation.

    ZIP layout per §6:
    - metadata.json (sim.model_dump + matsya_version)
    - terrain/terrain.json + terrain/dem.tif placeholder
    - rainfall.json
    - drainage/drainage.json
    - rivers/rivers.json
    - canals/canals.json
    - waterbodies/waterbodies.json
    - roads/roads.json
    - buildings/buildings.json
    - boundaries/boundaries.json
    - parameters/parameters.json
    - results/results.json
    - matsya_version (plain text)
    """
    data = sim.model_dump(mode="json")
    data["matsya_version"] = MATSYA_VERSION

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        # core metadata
        z.writestr("metadata.json", json.dumps(data, indent=2))
        z.writestr("matsya_version", MATSYA_VERSION)

        # auxiliary JSON files derived from simulation dump
        # terrain
        terrain_val = data.get("terrain")
        z.writestr("terrain/terrain.json", json.dumps(terrain_val if terrain_val is not None else {}, indent=2))
        # placeholder dem.tif (empty bytes, real DEM would be binary tif)
        z.writestr("terrain/dem.tif", b"")

        # rainfall (required)
        z.writestr("rainfall.json", json.dumps(data.get("rainfall", {}), indent=2))

        # drainage
        drainage_val = data.get("drainage")
        z.writestr("drainage/drainage.json", json.dumps(drainage_val if drainage_val is not None else {}, indent=2))

        # rivers
        rivers_val = data.get("rivers")
        z.writestr("rivers/rivers.json", json.dumps(rivers_val if rivers_val is not None else {}, indent=2))

        # canals
        canals_val = data.get("canals")
        z.writestr("canals/canals.json", json.dumps(canals_val if canals_val is not None else {}, indent=2))

        # waterBodies (note camelCase)
        wb_val = data.get("waterBodies")
        z.writestr("waterbodies/waterbodies.json", json.dumps(wb_val if wb_val is not None else {}, indent=2))

        # roads
        roads_val = data.get("roads")
        z.writestr("roads/roads.json", json.dumps(roads_val if roads_val is not None else {}, indent=2))

        # buildings
        buildings_val = data.get("buildings")
        z.writestr("buildings/buildings.json", json.dumps(buildings_val if buildings_val is not None else {}, indent=2))

        # boundaries
        boundaries_val = data.get("boundaries")
        z.writestr("boundaries/boundaries.json", json.dumps(boundaries_val if boundaries_val is not None else {}, indent=2))

        # parameters
        params_val = data.get("parameters")
        z.writestr("parameters/parameters.json", json.dumps(params_val if params_val is not None else {}, indent=2))

        # results
        results_val = data.get("results")
        z.writestr("results/results.json", json.dumps(results_val if results_val is not None else {}, indent=2))

        # hydro (v1.1) — ensure hydro files exist even if simulation has no hydro
        hydro_val = data.get("hydro")
        if hydro_val is None:
            hydro_val = {"enabled": False, "version": "1.1"}
        z.writestr("hydro/graph.json", json.dumps(hydro_val.get("graphStats", {}) if isinstance(hydro_val, dict) else {}, indent=2))
        z.writestr("hydro/snap.json", json.dumps(hydro_val.get("drainToWaterbody", {}) if isinstance(hydro_val, dict) else {}, indent=2))
        z.writestr("hydro/waterbodies.geojson", json.dumps({"type":"FeatureCollection","features":[]}, indent=2))

        # elevation (per-simulation hypsometric) — include if elevation exists, else placeholder
        elev_val = data.get("elevation")
        if elev_val and isinstance(elev_val, dict) and elev_val.get("stats"):
            z.writestr("elevation/elevation.json", json.dumps(elev_val.get("stats", {}), indent=2))
            # try to include actual PNG if exists
            try:
                sim_id = data.get("id", "unknown")
                from pathlib import Path
                # Try to find elevation.png
                candidates = [
                    Path(f"matsya/matsya/backend/data/simulations/{sim_id}/elevation.png"),
                    Path(f"backend/data/simulations/{sim_id}/elevation.png"),
                    Path(f"data/simulations/{sim_id}/elevation.png"),
                ]
                found = None
                for cand in candidates:
                    if cand.exists():
                        found = cand
                        break
                if found:
                    z.writestr(f"elevation/elevation.png", found.read_bytes())
                else:
                    # placeholder empty png
                    z.writestr("elevation/elevation.png", b"")
            except:
                z.writestr("elevation/elevation.png", b"")
        else:
            z.writestr("elevation/elevation.json", json.dumps({}, indent=2))
            z.writestr("elevation/elevation.png", b"")

    buf.seek(0)
    return buf.read()


def read_matsya(data: bytes) -> Simulation:
    """Read and validate .matsya ZIP bytes → Simulation.

    Validates:
    - ZIP must be valid (otherwise ValueError)
    - must contain metadata.json
    - metadata.json must be valid JSON
    - must contain matsya_version == MATSYA_VERSION (checked in JSON and/or matsya_version file)
    - JSON must be valid Simulation (model_validate)
    Raises ValueError on missing/corruption/version mismatch/incomplete.
    """
    if not data:
        raise ValueError("empty package")

    try:
        buf = io.BytesIO(data)
        with zipfile.ZipFile(buf, "r") as z:
            namelist = z.namelist()

            if "metadata.json" not in namelist:
                raise ValueError("missing metadata.json")

            try:
                raw = z.read("metadata.json")
            except Exception as e:
                raise ValueError(f"corrupted metadata.json: {e}")

            try:
                # raw is bytes
                text = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else str(raw)
                obj = json.loads(text)
            except Exception as e:
                raise ValueError(f"corrupted metadata.json: {e}")

            # version validation
            version = obj.get("matsya_version")
            if version is None and "matsya_version" in namelist:
                try:
                    v_raw = z.read("matsya_version")
                    version = v_raw.decode("utf-8").strip() if isinstance(v_raw, (bytes, bytearray)) else str(v_raw).strip()
                except Exception:
                    version = None

            if version is None:
                raise ValueError("missing matsya_version")

            # Support 1.0 -> 1.1 migration: 1.0 is allowed but will be upgraded to 1.1
            if version not in (MATSYA_VERSION, "1.0"):
                raise ValueError(f"unsupported version: {version}")
            # If 1.0, upgrade obj to 1.1 by adding hydro defaults
            if version == "1.0":
                obj["matsya_version"] = MATSYA_VERSION
                if "hydro" not in obj or obj["hydro"] is None:
                    obj["hydro"] = {"enabled": False, "version": "1.1"}

            # Validate simulation fields via Pydantic
            try:
                sim = Simulation.model_validate(obj)
            except Exception as e:
                raise ValueError(f"invalid simulation data: {e}")

            return sim

    except ValueError:
        raise
    except zipfile.BadZipFile as e:
        raise ValueError(f"corrupted zip: {e}")
    except Exception as e:
        # any other unexpected error wrap as ValueError for contract
        raise ValueError(str(e))
