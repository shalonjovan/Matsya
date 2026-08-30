
from fastapi import APIRouter

router = APIRouter(prefix="/api/live", tags=["live"])

@router.get("/status")
def status():
    return {
        "connected": True,
        "rainfall": "42 mm/hr",
        "floodedArea": "3.4 km²",
        "activeAlerts": 2,
        "alerts": [
            {"level":"Critical","message":"Adyar River approaching overflow level.","lat":13.02,"lon":80.26},
            {"level":"Warning","message":"Velachery drain D-42 surcharged.","lat":12.98,"lon":80.21}
        ],
        "messages": [
            {"type":"info","message":"New rainfall data available"},
            {"type":"info","message":"Simulation updated"}
        ]
    }
