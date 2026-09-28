"""Singleton realtime sim: sliding ±12h window rebuilt from the weather feed.

Exactly one sim (REALTIME_ID) exists. Each tick rewrites its rainfall from
the feed window, stamps live lake levels, and reruns the real flood
pipeline. Normal sim flows never touch this id (routers refuse it).
"""
from datetime import datetime, timezone, timedelta

REALTIME_ID = "realtime-chennai-01"
WINDOW_HOURS = 12
# Whole Chennai (from assets/chennai_border.geojson envelope) — live sim covers the city
DEFAULT_BBOX = [80.13968, 13.01593, 80.28967, 13.14146]
TICK_MINUTES = 15
CROWD_KINDS = ("drain", "flooded", "other")
CROWD_MAX = 200
CROWD_TTL_HRS = 48
CROWD_HALF_LIFE_HRS = 6.0


def _utcnow():
    try:
        return datetime.now(timezone.utc)
    except Exception:
        return datetime.now()


def add_crowd_report(sim_id, lat, lon, depth_cm, kind="other", note="", radius_m=0.0):
    """Validate + persist a crowd report. Returns report dict. Raises ValueError."""
    from app.services.simulation_store import store
    try:
        lat, lon = float(lat), float(lon)
        depth_cm = float(depth_cm)
        radius_m = float(radius_m or 0.0)
    except Exception:
        raise ValueError("lat/lon/depthCm/radiusM must be numbers")
    if kind not in CROWD_KINDS:
        raise ValueError(f"kind must be one of {list(CROWD_KINDS)}")
    if not (0 <= depth_cm <= 500):
        raise ValueError("depthCm must be 0-500")
    if not (0 <= radius_m <= 1000):
        raise ValueError("radiusM must be 0-1000")
    sim = store.get(sim_id)  # FileNotFoundError propagates -> 404
    try:
        _bb = sim.get("area", {}).get("bbox") if isinstance(sim, dict) else sim.area.bbox
        minLon, minLat, maxLon, maxLat = [float(x) for x in _bb]
    except Exception:
        raise ValueError("simulation has no usable bbox")
    if not (minLat <= lat <= maxLat and minLon <= lon <= maxLon):
        raise ValueError("report point is outside the simulation domain")
    import uuid
    rep = {"id": uuid.uuid4().hex[:12], "lat": lat, "lon": lon, "depthCm": depth_cm,
           "kind": kind, "note": str(note or "")[:280], "radiusM": radius_m,
           "createdAt": _utcnow().isoformat()}
    try:
        _res = sim.get("results", {}) if isinstance(sim, dict) else (sim.results or {})
        _res = dict(_res) if isinstance(_res, dict) else {}
    except Exception:
        _res = {}
    reps = [r for r in (_res.get("crowd") or []) if isinstance(r, dict)]
    reps.append(rep)
    reps = reps[-CROWD_MAX:]
    try:
        store.update(sim_id, {"results": {"crowd": reps}})
    except Exception as e:
        raise ValueError(f"persist failed: {e}")
    return rep


def list_crowd_reports(sim_id):
    """Reports with ageHrs; prunes >48h old (persisted). Never raises."""
    from app.services.simulation_store import store
    try:
        sim = store.get(sim_id)
    except Exception:
        return []
    try:
        _res = sim.get("results", {}) if isinstance(sim, dict) else (sim.results or {})
        reps = [r for r in ((_res or {}).get("crowd") or []) if isinstance(r, dict)]
    except Exception:
        return []
    now = _utcnow()
    out, kept = [], []
    for r in reps:
        try:
            _age = (now - datetime.fromisoformat(str(r.get("createdAt")))).total_seconds() / 3600.0
            _age = max(0.0, _age)
        except Exception:
            _age = 0.0
        if _age > CROWD_TTL_HRS:
            continue
        kept.append(r)
        out.append({**r, "ageHrs": round(_age, 2)})
    if len(kept) != len(reps):
        try:
            store.update(sim_id, {"results": {"crowd": kept}})
        except Exception:
            pass
    return out


def apply_crowd_overlay(sim_id):
    """Pin reported depths onto snapshots (6h half-life decay). Returns summary."""
    from app.services.simulation_store import store
    from app.services.snapshots import load_snapshots
    from app.services.analysis import _lat_lon_to_row_col
    reps = list_crowd_reports(sim_id)
    if not reps:
        return {"applied": 0, "pruned": 0}
    sim = store.get(sim_id)
    snaps, _, bbox = load_snapshots(sim)
    if not snaps:
        return {"applied": 0, "pruned": 0}
    import numpy as _np
    applied = 0
    arrs = [_np.asarray(s, dtype=float) for s in snaps]
    rows, cols = arrs[0].shape
    try:
        minLon, minLat, maxLon, maxLat = [float(x) for x in bbox]
        _mx = (maxLon - minLon) / max(1, cols)
        _my = (maxLat - minLat) / max(1, rows)
        _lat0 = (minLat + maxLat) / 2.0
        import math as _math
        _kx = 111320.0 * max(0.2, _math.cos(_math.radians(_lat0)))
    except Exception:
        _mx, _my, _kx = 0.0, 0.0, 111320.0
    for r in reps:
        try:
            _rlat, _rlon = float(r["lat"]), float(r["lon"])
            _rr, _cc = _lat_lon_to_row_col(_rlat, _rlon, list(bbox), rows, cols)
            # disc cells within radiusM (haversine approx on the grid)
            try:
                _rad = max(0.0, float(r.get("radiusM", 0.0) or 0.0))
            except Exception:
                _rad = 0.0
            _cells = [(_rr, _cc)]
            if _rad > 0 and _mx > 0 and _my > 0:
                import math as _math2
                _dr = int(_rad / (111320.0 * _my)) + 1
                _dc = int(_rad / (_kx * _mx)) + 1
                for _i in range(max(0, _rr - _dr), min(rows, _rr + _dr + 1)):
                    for _j in range(max(0, _cc - _dc), min(cols, _cc + _dc + 1)):
                        try:
                            _dy = (_i - _rr) * _my * 111320.0
                            _dx = (_j - _cc) * _mx * _kx
                            if _math2.hypot(_dx, _dy) <= _rad:
                                _cells.append((_i, _j))
                        except Exception:
                            continue
            _rep_m = float(r["depthCm"]) / 100.0
            if _rep_m <= 0:
                # authoritative dry observation: clear the disc while the report lives
                for a in arrs:
                    for (_i, _j) in _cells:
                        a[_i, _j] = 0.0
            else:
                _target = _rep_m * (0.5 ** (float(r.get("ageHrs", 0.0)) / CROWD_HALF_LIFE_HRS))
                for a in arrs:
                    for (_i, _j) in _cells:
                        if _target > float(a[_i, _j]):
                            a[_i, _j] = _target
            applied += 1
        except Exception:
            continue
    try:
        _npy = store.base_path / f"{sim_id}" / "flood" / "snapshots.npy"
        _npy.parent.mkdir(parents=True, exist_ok=True)
        _np.save(str(_npy), _np.array(arrs, dtype="float32"))
    except Exception:
        pass
    # re-render stored tiles so the map stops flashing stale colors
    try:
        from app.services.flood import render_depth_png
        _f = sim.get("flood") if isinstance(sim, dict) else getattr(sim, "flood", None)
        _st = (_f.get("stats") if isinstance(_f, dict) else getattr(_f, "stats", None)) or {}
        if not isinstance(_st, dict) and hasattr(_st, "model_dump"):
            _st = _st.model_dump(mode="json")
        _fdir = store.base_path / f"{sim_id}" / "flood"
        for _k, _a in enumerate(arrs):
            try:
                (_fdir / f"{_k}.png").write_bytes(render_depth_png(_a, _st, "blue"))
            except Exception:
                continue
    except Exception:
        pass
    return {"applied": applied, "pruned": 0}


def _window(now):
    return now - timedelta(hours=WINDOW_HOURS), now + timedelta(hours=WINDOW_HOURS)


def tick(now=None, source=None, bbox=None):
    """Rebuild the realtime sim from the feed window. Returns tick report.

    source=None reads REALTIME_SOURCE env (default "dummy"). Unknown names
    and ANY fetch failure fall back to dummy, reported as "dummy-fallback".
    """
    import os
    from app.services.realtime.weather import get_source, is_known, DummyWeather
    from app.services.simulation_store import store
    now = now or _utcnow()
    bbox = list(bbox or DEFAULT_BBOX)
    w0, w1 = _window(now)
    name = source or os.getenv("REALTIME_SOURCE", "dummy") or "dummy"
    label = name
    try:
        src = get_source(name) if is_known(name) else DummyWeather()
        if not is_known(name):
            label = "dummy-fallback"
        feed = src.fetch(w0, w1, bbox)
    except Exception:
        feed = DummyWeather().fetch(w0, w1, bbox)
        label = "dummy-fallback"
    rain = (feed or {}).get("rain") or []
    # polygon cells -> zones (variable-curve cells pass through, else constant
    # rate); whole-bbox base cell -> base rate
    base_rate = 0.0
    zones = []
    for i, cell in enumerate(rain):
        try:
            _poly = (cell or {}).get("polygon")
            if _poly is None:
                base_rate = float((cell or {}).get("rateMmHr", 0.0) or 0.0)
                continue
            if str((cell or {}).get("mode", "constant")) == "variable":
                zones.append({
                    "id": str((cell or {}).get("id", f"rt-{i}")),
                    "mode": "variable",
                    "unit": str((cell or {}).get("unit", "rate") or "rate"),
                    "totalTime": float((cell or {}).get("totalTime") or 2 * WINDOW_HOURS),
                    "maxRain": float((cell or {}).get("maxRain", 0.0) or 0.0),
                    "points": [{"time": float(p.get("time", 0) or 0),
                                "amount": float(p.get("amount", 0) or 0)}
                               for p in ((cell or {}).get("points") or [])],
                    "polygon": _poly,
                })
            else:
                _r = float((cell or {}).get("rateMmHr", 0.0) or 0.0)
                zones.append({"id": str((cell or {}).get("id", f"rt-{i}")),
                              "amount": _r, "unit": "rate", "polygon": _poly})
        except Exception:
            continue
    from app.services.rainfall_zones import MAX_LIVE_ZONES
    rainfall = {"mode": "constant", "rateMmHr": base_rate, "durationHr": 2 * WINDOW_HOURS,
                "constantRate": base_rate, "zones": zones,
                "maxZones": MAX_LIVE_ZONES}
    states = {}
    for lake in (feed.get("lakes") or []):
        try:
            states[str(lake.get("id"))] = {"fillPct": float(lake.get("fillPct", 60.0))}
        except Exception:
            continue
    live_meta = {"windowStart": w0.isoformat(), "windowEnd": w1.isoformat(),
                 "tickAt": now.isoformat(), "source": label,
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
        }, background=False)  # tick runs the pipeline itself, no bg thread (avoids resurrects)
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
        # pipeline done synchronously: mark Completed (no bg thread will do it)
        try:
            from app.models.simulation import StatusEnum
            sim.status = StatusEnum.Completed
            try:
                sim.metadata.status = StatusEnum.Completed
            except Exception:
                pass
        except Exception:
            pass
        try:
            store._save(sim)
        except Exception:
            pass
    except Exception as e:
        return {"simId": REALTIME_ID, "tickAt": now.isoformat(), "rainCells": len(zones),
                "lakesApplied": len(states), "totalRainMm": None, "error": str(e)}
    # re-apply crowd overlay (reports persist on the record across recomputes)
    try:
        apply_crowd_overlay(REALTIME_ID)
    except Exception:
        pass
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
                _zz = z or {}
                _peak = max(_peak, float(_zz.get("amount", 0.0) or 0.0),
                            float(_zz.get("maxRain", 0.0) or 0.0))
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
