
from fastapi import APIRouter, HTTPException
from app.services.simulation_store import store

router = APIRouter(prefix="/api/simulations/{sim_id}/layers", tags=["layers"])

LAYERS = [
    {"id":"depth","group":"Flood","label":"Flood depth","unit":"m","visible":True,"opacity":0.8},
    {"id":"velocity","group":"Flood","label":"Velocity","unit":"m/s","visible":False,"opacity":0.8},
    {"id":"direction","group":"Flood","label":"Flow direction","unit":"deg","visible":False},
    {"id":"arrival","group":"Flood","label":"Flood arrival time","unit":"min","visible":False},
    {"id":"duration","group":"Flood","label":"Flood duration","unit":"hr","visible":False},
    {"id":"hazard","group":"Flood","label":"Flood hazard","unit":"-","visible":False},
    {"id":"elevation","group":"Terrain","label":"Elevation","unit":"m","visible":False,"opacity":0.7},
    {"id":"micro","group":"Drainage","label":"Micro drains","visible":True},
    {"id":"macro","group":"Drainage","label":"Macro drains","visible":True},
    {"id":"storm","group":"Drainage","label":"Storm drains","visible":True},
    {"id":"conduits","group":"Drainage","label":"Conduits","visible":True},
    {"id":"junctions","group":"Drainage","label":"Junctions","visible":True},
    {"id":"rivers","group":"Water","label":"Rivers","visible":True},
    {"id":"canals","group":"Water","label":"Canals","visible":True},
    {"id":"waterBodies","group":"Water","label":"Water bodies","visible":True},
    {"id":"sea","group":"Water","label":"Sea","visible":True},
    {"id":"roads","group":"Infrastructure","label":"Roads","visible":True},
    {"id":"buildings","group":"Infrastructure","label":"Buildings","visible":True},
    {"id":"admin","group":"Other","label":"Administrative boundaries","visible":False},
    {"id":"landCover","group":"Other","label":"Land cover","visible":False},
]

@router.get("")
def list_layers(sim_id: str):
    sim = store.get(sim_id)
    if not sim: raise HTTPException(404, "simulation not found")
    return LAYERS

@router.get("/{layer_id}/geojson")
def layer_geojson(sim_id: str, layer_id: str):
    sim = store.get(sim_id)
    if not sim: raise HTTPException(404, "simulation not found")
    # stub GeoJSON for vector layers
    if layer_id in ["roads","rivers","canals","drains","conduits"]:
        return {"type":"FeatureCollection","features":[]}
    raise HTTPException(404, "layer not found")
