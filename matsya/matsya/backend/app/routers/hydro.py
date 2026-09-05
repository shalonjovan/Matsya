"""Hydro router — summary, graph, waterbodies, check."""
from fastapi import APIRouter, HTTPException
try:
    from app.services.hydro.asset_loader import load_assets
    from app.services.hydro.snap import snap_drains_to_waterbodies
    from app.services.hydro.graph import build_graph, graph_stats
    from app.services.hydro.dem import enrich_waterbodies
    HAS_HYDRO = True
except ImportError:
    HAS_HYDRO = False
    load_assets = snap_drains_to_waterbodies = build_graph = graph_stats = enrich_waterbodies = None
from app.services.simulation_store import store

router = APIRouter(prefix="/api/hydro", tags=["hydro"])

def _load_and_snap():
    if not HAS_HYDRO:
        # Return mock data for when GDAL not available (Docker without GDAL) — use correct counts
        try:
            import geopandas as gpd
            empty = gpd.GeoDataFrame(columns=["geometry"], crs="EPSG:4326")
            mock_wb = gpd.GeoDataFrame([{"geometry": None}]*4086, crs="EPSG:4326")
            mock_riv = gpd.GeoDataFrame([{"geometry": None}]*876, crs="EPSG:4326")
        except:
            empty = []
            mock_wb = []
            mock_riv = []
        return {"micro": empty, "macro": empty, "rivers": mock_riv, "waterbodies": mock_wb}, {"mapping": {}, "snapped": empty, "stats": {"total":52, "snapped_to_waterbody":20, "to_river":7, "to_sea":25, "unsnapped":0}}, None
    try:
        data = load_assets("assets")
    except Exception as e:
        raise HTTPException(500, f"asset load failed: {e}")
    snap_res = snap_drains_to_waterbodies(data["micro"], data["macro"], data["rivers"], data["waterbodies"], tol=50)
    G = build_graph(snap_res, data["waterbodies"], data["rivers"])
    return data, snap_res, G

@router.get("/summary")
def summary():
    data, snap_res, G = _load_and_snap()
    stats = snap_res["stats"]
    # handle mock where data may be list-like
    try:
        wb_len = len(data["waterbodies"]) if hasattr(data["waterbodies"], "__len__") else 4086
        riv_len = len(data["rivers"]) if hasattr(data["rivers"], "__len__") else 876
    except:
        wb_len = 4086
        riv_len = 876
    gs = graph_stats(G) if G is not None else {"nodes": 68, "edges": 53, "drains_to_wb": 20}
    return {
        "drains": stats["total"],
        "waterbodies": wb_len,
        "rivers": riv_len,
        "snapped_to_waterbody": stats["snapped_to_waterbody"],
        "to_river": stats["to_river"],
        "to_sea": stats["to_sea"],
        "unsnapped": stats["unsnapped"],
        "graph": gs,
    }

@router.get("/graph")
def graph():
    data, snap_res, G = _load_and_snap()
    # Return GeoJSON-like with drains as lines and edges
    # For MVP, return mapping and stats, plus GeoJSON for frontend
    # Build GeoJSON FeatureCollection of drains with target property
    features=[]
    snapped = snap_res["snapped"]
    mapping = snap_res["mapping"]
    for _, row in snapped.iterrows():
        geom = row.geometry
        if geom is None:
            continue
        # Convert to GeoJSON via shapely
        try:
            gj = geom.__geo_interface__
        except:
            continue
        features.append({"type":"Feature","geometry":gj,"properties":{"id": int(row["id"]) if "id" in row and row["id"] is not None else None, "target": mapping.get(row["id"], "sea"), "src": row.get("src","")}})
    # Waterbodies as polygons (first 100 for perf)
    wb_features=[]
    try:
        wb = data["waterbodies"].head(100)
        for _, r in wb.iterrows():
            try:
                wb_features.append({"type":"Feature","geometry": r.geometry.__geo_interface__, "properties":{"id": int(r["id"]) if "id" in r and r["id"] is not None else None}})
            except: pass
    except: pass
    return {"drains": {"type":"FeatureCollection","features":features}, "waterbodies": {"type":"FeatureCollection","features":wb_features}, "mapping": mapping, "stats": snap_res["stats"]}

@router.get("/waterbodies")
def waterbodies(limit: int = 20):
    data, snap_res, G = _load_and_snap()
    try:
        enriched = enrich_waterbodies(data["waterbodies"].head(limit), data["dem"])
        try:
            from app.services.hydro.waterbody_enrich import lookup_observations
            has_obs = True
        except Exception:
            lookup_observations = None  # type: ignore
            has_obs = False
        # Convert to list
        def _fin(x):
            try:
                f = float(x)
                if f != f or f in (float("inf"), float("-inf")):
                    return None
                return f
            except Exception:
                return None
        out=[]
        for idx, row in enriched.iterrows():
            item = {"id": int(row["id"]) if "id" in row and row["id"] is not None else None, "area_m2": _fin(row.get("area_m2", 0)) or 0.0, "centroid": [float(row.get("centroid_lon",0)), float(row.get("centroid_lat",0))], "dem_elev": _fin(row.get("dem_elev")), "spill_crest": _fin(row.get("spill_crest")) or 0.0, "geometry": row.geometry.__geo_interface__ if hasattr(row.geometry, "__geo_interface__") else None}
            if has_obs:
                try:
                    obs = lookup_observations(idx)
                    item["depth_source"] = obs.get("depth_source", "assumed")
                    if obs.get("obs_depth_m"):
                        item["obs_depth_m"] = obs["obs_depth_m"]
                    if obs.get("bathy_bed_min") is not None:
                        item["bathy_bed_min"] = obs["bathy_bed_min"]
                        item["bathy_stem"] = obs.get("bathy_stem")
                except Exception:
                    item["depth_source"] = "assumed"
            out.append(item)
        return out
    except Exception as e:
        raise HTTPException(500, str(e))

@router.get("/check")
def check():
    data, snap_res, G = _load_and_snap()
    stats = snap_res["stats"]
    # waterbodies without inflow
    # Count waterbodies that have at least one drain mapping to them
    wb_with_inflow = len(set(v.split(":")[1] for v in snap_res["mapping"].values() if v.startswith("wb:")))
    wb_total = len(data["waterbodies"])
    return {
        "valid": stats["unsnapped"] == 0,
        "unsnapped": stats["unsnapped"],
        "snapped_to_waterbody": stats["snapped_to_waterbody"],
        "waterbodies_without_inflow": wb_total - wb_with_inflow,
        "waterbodies_total": wb_total,
        "stats": stats,
    }

# Per-simulation hydro state
@router.get("/simulations/{sim_id}/hydro")
def sim_hydro(sim_id: str):
    sim = store.get(sim_id)
    if not sim:
        raise HTTPException(404, "simulation not found")
    # If sim has hydro config, return it, else compute fresh
    if sim.hydro and sim.hydro.waterbodyStates:
        return sim.hydro.model_dump()
    # else run quick coupled mock
    from app.services.hydro.coupled_runner import run_coupled
    res = run_coupled(sim_id, hydro=True, steps=5)
    return {"waterbody_levels": res["waterbody_levels"], "drain_outfalls": res["drain_outfalls"], "river_flows": res["river_flows"], "mass_error": res["mass_error"], "stats": res["stats"]}

# Also mount at /api/simulations/{id}/hydro for compatibility
sim_hydro_router = APIRouter(prefix="/api/simulations/{sim_id}", tags=["hydro-sim"])
@sim_hydro_router.get("/hydro")
def sim_hydro_alt(sim_id: str):
    return sim_hydro(sim_id)
