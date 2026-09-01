
from typing import Dict, Any

def point_query(lat: float, lon: float, time: int, sim: Any) -> Dict[str,Any]:
    # Try real DEM sample first, fallback to mock
    try:
        from app.services.elevation import sample_dem
        real_elev = sample_dem(lon, lat)
    except:
        real_elev = None
    # bbox to row/col stub, then mock depth
    bbox = sim.area.bbox if hasattr(sim,"area") else [80.15,13.08,80.20,13.13]
    minLon, minLat, maxLon, maxLat = bbox
    # clamp
    if not (minLat <= lat <= maxLat and minLon <= lon <= maxLon):
        elevation = real_elev if real_elev is not None else 0
        floodDepth = 0
    else:
        # hash for deterministic mock
        h = (int(lat*1000) ^ int(lon*1000)) % 100
        floodDepth = (h/100)*1.2 if time>600 else (h/100)*0.3
        elevation = real_elev if real_elev is not None else (15.5 + (h%10)*0.2)
    velocity = floodDepth*0.7 + 0.05
    return {
        "lat": lat, "lon": lon,
        "elevation": elevation,
        "floodDepth": floodDepth,
        "water_depth": floodDepth,
        "velocity": velocity,
        "wse": elevation + floodDepth,
        "firstFlooded": "00:05" if floodDepth>0.05 else None,
        "peak": "01:20" if floodDepth>0.5 else None,
        "duration": "2h 10m" if floodDepth>0.05 else None,
        "rainfall": getattr(sim.rainfall, "rateMmHr", 50) if hasattr(sim,"rainfall") else 50,
        "nearestDrain": "D-42 (12m)",
        "nearestRiver": "Adyar (450m)",
        "road": "GST Road",
        "type": "simulated",
        "measured": {"elevation": elevation},
        "simulated": {"floodDepth": floodDepth, "velocity": velocity},
        "derived": {"duration": "2h"}
    }

def affected_areas(sim: Any):
    # mock ranked per §14, transparent criteria maxDepth
    return [
        {"name":"Velachery","maxDepth":1.24,"duration":"3h 12m","rank":1,"lat":12.9816,"lon":80.2180,"criteria":"maxDepth"},
        {"name":"Pallikaranai","maxDepth":0.92,"duration":"2h 48m","rank":2,"lat":12.9372,"lon":80.2130,"criteria":"maxDepth"},
        {"name":"T Nagar","maxDepth":0.65,"duration":"1h 30m","rank":3,"lat":13.0418,"lon":80.2341,"criteria":"maxDepth"},
    ]

def road_impact(sim: Any):
    return [
        {"id":"R-GST-1","maxDepth":0.8,"duration":"2h","firstFlood":"00:15","peak":"01:20","maxVel":0.5},
        {"id":"R-OMR-2","maxDepth":0.45,"duration":"1h 20m","firstFlood":"00:30","peak":"01:00","maxVel":0.3},
    ]

def drain_impact(sim: Any):
    # never invent capacity per §15 — capacity is None unless source has it
    return [
        {"id":"D-42","flow":1.2,"depth":0.5,"status":"ok","capacity":None,"overCapacity":False},
        {"id":"D-43","flow":2.1,"depth":1.1,"status":"surcharged","capacity":None,"overCapacity":False},
    ]
