"""Singleton realtime sim: sliding ±12h window rebuilt from the weather feed.

Exactly one sim (REALTIME_ID) exists. Each tick rewrites its rainfall from
the feed window, stamps live lake levels, and reruns the real flood
pipeline. Normal sim flows never touch this id (routers refuse it).
"""
from datetime import datetime, timezone, timedelta

REALTIME_ID = "realtime-chennai-01"
WINDOW_HOURS = 12
DEFAULT_BBOX = [80.15, 13.08, 80.20, 13.13]
TICK_MINUTES = 15


def _now():
    try:
        return datetime.now(timezone.utc)
    except Exception:
        return datetime.now()


def _window(now):
    return now - timedelta(hours=WINDOW_HOURS), now + timedelta(hours=WINDOW_HOURS)


def tick(now=None, source="dummy", bbox=None):
    """Rebuild the realtime sim from the feed window. Returns tick report."""
    from app.services.realtime.weather import get_source
    from app.services.simulation_store import store
    now = now or _now()
    bbox = list(bbox or DEFAULT_BBOX)
    w0, w1 = _window(now)
    feed = get_source(source).fetch(w0, w1, bbox)
    rain = feed.get("rain") or []
    # polygon cells -> rate zones; whole-bbox base cell -> base rate
    base_rate = 0.0
    zones = []
    for i, cell in enumerate(rain):
        try:
            _r = float(cell.get("rateMmHr", 0.0) or 0.0)
            _poly = cell.get("polygon")
            if _poly is None:
                base_rate = _r
            else:
                zones.append({"id": f"rt-{i}", "amount": _r, "unit": "rate", "polygon": _poly})
        except Exception:
            continue
    rainfall = {"mode": "constant", "rateMmHr": base_rate, "durationHr": 2 * WINDOW_HOURS,
                "constantRate": base_rate, "zones": zones}
    states = {}
    for lake in (feed.get("lakes") or []):
        try:
            states[str(lake.get("id"))] = {"fillPct": float(lake.get("fillPct", 60.0))}
        except Exception:
            continue
    live_meta = {"windowStart": w0.isoformat(), "windowEnd": w1.isoformat(),
                 "tickAt": now.isoformat(), "source": feed.get("source", source),
                 "rainCells": len(zones), "lakesApplied": len(states)}
    try:
        _exists = store.get(REALTIME_ID)
        _exists = True
    except Exception:
        _exists = False
    if not _exists:
        sim = store.create({
            "id": REALTIME_ID,
            "name": "Live \u2014 Chennai",
            "area": {"bbox": bbox, "crs": "EPSG:4326"},
            "rainfall": rainfall,
            "hydro": {"enabled": True, "version": "1.1", "waterbodyStates": states},
            "results": {"live": live_meta},
            "live": True,
        })
    else:
        sim = store.update(REALTIME_ID, {
            "name": "Live \u2014 Chennai",
            "area": {"bbox": bbox, "crs": "EPSG:4326"},
            "rainfall": rainfall,
            "hydro": {"enabled": True, "version": "1.1", "waterbodyStates": states},
            "results": {"live": live_meta},
            "live": True,
        })
    # rerun the real pipeline synchronously (tick is the update path)
    try:
        from app.services.flood import ensure_flood
        from app.services.elevation import ensure_elevation
        try:
            ensure_elevation(sim)
        except Exception:
            pass
        ensure_flood(sim)
        try:
            store._save(sim)
        except Exception:
            pass
    except Exception as e:
        return {"simId": REALTIME_ID, "tickAt": now.isoformat(), "rainCells": len(zones),
                "lakesApplied": len(states), "totalRainMm": None, "error": str(e)}
    try:
        _st = sim.flood.stats if hasattr(sim, "flood") and sim.flood is not None else {}
        _total = (_st.get("totalRainMm") if isinstance(_st, dict) else getattr(_st, "totalRainMm", None))
    except Exception:
        _total = None
    return {"simId": REALTIME_ID, "tickAt": now.isoformat(), "rainCells": len(zones),
            "lakesApplied": len(states), "totalRainMm": _total}


def get_status(tick_minutes=TICK_MINUTES):
    """Live status for the UI. Never raises."""
    try:
        from app.services.simulation_store import store
        sim = store.get(REALTIME_ID)
        _res = sim.results if hasattr(sim, "results") else None
        _live = (_res.get("live") if isinstance(_res, dict) else {}) or {}
        _rf = sim.rainfall if hasattr(sim, "rainfall") else {}
        _rfd = _rf if isinstance(_rf, dict) else (_rf.model_dump(mode="json") if hasattr(_rf, "model_dump") else {})
        _base = float((_rfd or {}).get("rateMmHr") or 0.0)
        _peak = _base
        try:
            for z in ((_rfd or {}).get("zones") or []):
                _peak = max(_peak, float((z or {}).get("amount", 0.0) or 0.0))
        except Exception:
            pass
        _tick_at = _live.get("tickAt")
        _next = None
        try:
            if _tick_at:
                _dt = datetime.fromisoformat(str(_tick_at))
                _next = (_dt + timedelta(minutes=int(tick_minutes))).isoformat()
        except Exception:
            pass
        return {"simId": REALTIME_ID, "live": True, "lastTickAt": _tick_at,
                "nextTickAt": _next, "windowHrs": WINDOW_HOURS,
                "rainNowMmHr": round(_peak, 2),
                "source": _live.get("source", "dummy"), "tickMinutes": int(tick_minutes)}
    except Exception:
        return {"simId": REALTIME_ID, "live": False, "lastTickAt": None,
                "nextTickAt": None, "windowHrs": WINDOW_HOURS,
                "rainNowMmHr": 0.0, "source": "none", "tickMinutes": int(tick_minutes)}
