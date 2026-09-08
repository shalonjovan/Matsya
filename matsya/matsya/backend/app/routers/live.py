
from fastapi import APIRouter

router = APIRouter(prefix="/api/live", tags=["live"])

@router.get("/status")
def status():
    # real realtime-sim status; legacy mock keys kept for the LiveStatus UI
    try:
        from app.services.realtime.manager import get_status, TICK_MINUTES
        st = get_status(TICK_MINUTES)
    except Exception:
        st = {"simId": None, "live": False, "lastTickAt": None, "nextTickAt": None,
              "windowHrs": 12, "rainNowMmHr": 0.0, "source": "none", "tickMinutes": 15}
    try:
        _rain = f"{float(st.get('rainNowMmHr', 0.0))} mm/hr"
    except Exception:
        _rain = "0 mm/hr"
    _live = bool(st.get("live"))
    out = {
        "connected": True,
        "rainfall": _rain if _live else "42 mm/hr",
        "floodedArea": "3.4 km²",
        "activeAlerts": 0 if _live else 2,
        # mock alerts/messages only when no live sim exists (never mix fabricated
        # emergencies with real status)
        "alerts": [] if _live else [
            {"level":"Critical","message":"Adyar River approaching overflow level.","lat":13.02,"lon":80.26},
            {"level":"Warning","message":"Velachery drain D-42 surcharged.","lat":12.98,"lon":80.21}
        ],
        "messages": [] if _live else [
            {"type":"info","message":"New rainfall data available"},
            {"type":"info","message":"Simulation updated"}
        ],
    }
    out.update({k: st.get(k) for k in ("simId", "live", "lastTickAt", "nextTickAt", "windowHrs", "rainNowMmHr", "source", "tickMinutes")})
    return out
