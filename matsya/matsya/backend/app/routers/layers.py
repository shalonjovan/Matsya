from fastapi import APIRouter, HTTPException, Query
from app.services.simulation_store import store
from app.services.hydro.asset_loader import load_assets
import geopandas as gpd
import time

# Simple cache for layers GeoJSON — 30s TTL
_layers_cache = {"drains": {"data": None, "ts": 0}, "waterbodies": {"data": None, "ts": 0}, "rivers": {"data": None, "ts": 0}}

router = APIRouter(prefix="/api", tags=["layers"])

LAYERS = [
    {"id":"depth","group":"Flood","label":"Flood depth","unit":"m","visible":True,"opacity":0.8},
    {"id":"velocity","group":"Flood","label":"Velocity","unit":"m/s","visible":False,"opacity":0.8},
    {"id":"direction","group":"Flood","label":"Flow direction","unit":"deg","visible":False},
    {"id":"arrival","group":"Flood","label":"Flood arrival time","unit":"min","visible":False},
    {"id":"duration","group":"Flood","label":"Flood duration","unit":"hr","visible":False},
    {"id":"hazard","group":"Flood","label":"Flood hazard","unit":"-","visible":False},
    {"id":"elevation","group":"Terrain","label":"Elevation","unit":"m","visible":False,"opacity":0.7},
    {"id":"drains","group":"Drainage","label":"Drains (all 10257)","visible":True,"opacity":0.7},
    {"id":"micro","group":"Drainage","label":"Micro drains (37)","visible":True},
    {"id":"macro","group":"Drainage","label":"Macro drains (15)","visible":True},
    {"id":"storm","group":"Drainage","label":"Storm drains","visible":True},
    {"id":"conduits","group":"Drainage","label":"Conduits","visible":True},
    {"id":"junctions","group":"Drainage","label":"Junctions","visible":True},
    {"id":"rivers","group":"Water","label":"Rivers (876)","visible":True},
    {"id":"canals","group":"Water","label":"Canals","visible":True},
    {"id":"waterBodies","group":"Water","label":"Water bodies (4086)","visible":True},
    {"id":"sea","group":"Water","label":"Sea","visible":True},
    {"id":"roads","group":"Infrastructure","label":"Roads","visible":True},
    {"id":"buildings","group":"Infrastructure","label":"Buildings","visible":True},
    {"id":"admin","group":"Other","label":"Administrative boundaries","visible":False},
    {"id":"landCover","group":"Other","label":"Land cover","visible":False},
]

@router.get("/simulations/{sim_id}/layers")
def list_layers(sim_id: str):
    sim = store.get(sim_id)
    if not sim: raise HTTPException(404, "simulation not found")
    return LAYERS

@router.get("/layers/drains")
def get_drains(limit: int = Query(10257, ge=1, le=20000)):
    """All drains from drains.kml 10257 — for Drains layer (cached 30s)"""
    now = time.time()
    # Check cache for full data (limit 10257)
    if limit == 10257 and _layers_cache["drains"]["data"] is not None and (now - _layers_cache["drains"]["ts"] < 30):
        return _layers_cache["drains"]["data"]
    try:
        data = load_assets("assets")
        gdf = data.get("drains_all")
        if gdf is None or len(gdf)==0:
            import pandas as pd
            gdf = gpd.GeoDataFrame(pd.concat([data.get("micro", gpd.GeoDataFrame()), data.get("macro", gpd.GeoDataFrame())]), crs="EPSG:4326")
        total = len(gdf)
        # For cache, store full
        if limit >= total:
            # Build full features
            features=[]
            for _, row in gdf.iterrows():
                try:
                    features.append({"type":"Feature","geometry": row.geometry.__geo_interface__, "properties": {"id": int(row["id"]) if "id" in row and row["id"] is not None else None}})
                except: pass
            result = {"type":"FeatureCollection","features":features, "total": total}
            if limit == 10257:
                _layers_cache["drains"]["data"] = result
                _layers_cache["drains"]["ts"] = now
            return result
        # limit < total
        gdf_limited = gdf.head(limit)
        features=[]
        for _, row in gdf_limited.iterrows():
            try:
                features.append({"type":"Feature","geometry": row.geometry.__geo_interface__, "properties": {"id": int(row["id"]) if "id" in row and row["id"] is not None else None}})
            except: pass
        return {"type":"FeatureCollection","features":features, "total": total}
    except Exception as e:
        raise HTTPException(500, str(e))

@router.get("/layers/waterbodies")
def get_waterbodies(limit: int = Query(200, ge=1, le=5000)):
    """Water bodies from chennai_waterbodies.kml 4086 — for Water layer (cached 30s)"""
    now = time.time()
    if _layers_cache["waterbodies"]["data"] is not None and (now - _layers_cache["waterbodies"]["ts"] < 30):
        cached = _layers_cache["waterbodies"]["data"]
        if limit >= cached["total"]:
            return cached
        # slice
        return {"type":"FeatureCollection","features": cached["features"][:limit], "total": cached["total"]}
    try:
        data = load_assets("assets")
        gdf = data.get("waterbodies")
        if gdf is None or len(gdf)==0:
            raise HTTPException(404, "no waterbodies")
        total_wb = len(data["waterbodies"])
        if len(gdf) > limit:
            gdf = gdf.head(limit)
        features=[]
        for _, row in gdf.iterrows():
            try:
                features.append({"type":"Feature","geometry": row.geometry.__geo_interface__, "properties": {"id": int(row["id"]) if "id" in row and row["id"] is not None else None}})
            except: pass
        return {"type":"FeatureCollection","features":features, "total": total_wb}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))

@router.get("/layers/rivers")
def get_rivers(limit: int = Query(200, ge=1, le=2000)):
    try:
        data = load_assets("assets")
        gdf = data.get("rivers")
        if gdf is None or len(gdf)==0:
            raise HTTPException(404, "no rivers")
        if len(gdf) > limit:
            gdf = gdf.head(limit)
        features=[]
        for _, row in gdf.iterrows():
            try:
                features.append({"type":"Feature","geometry": row.geometry.__geo_interface__, "properties": {"id": int(row["id"]) if "id" in row and row["id"] is not None else None}})
            except: pass
        return {"type":"FeatureCollection","features":features, "total": len(data["rivers"])}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))

# Keep old per-simulation geojson stub for compatibility
@router.get("/simulations/{sim_id}/layers/{layer_id}/geojson")
def layer_geojson(sim_id: str, layer_id: str):
    sim = store.get(sim_id)
    if not sim: raise HTTPException(404, "simulation not found")
    if layer_id in ["roads","rivers","canals","drains","conduits","drains_all","waterbodies","waterBodies"]:
        # redirect to new endpoints
        if layer_id in ["drains","drains_all"]:
            return get_drains(limit=100)
        if layer_id in ["waterbodies","waterBodies"]:
            return get_waterbodies(limit=100)
        if layer_id=="rivers":
            return get_rivers(limit=100)
        return {"type":"FeatureCollection","features":[]}
    raise HTTPException(404, "layer not found")
