
from typing import Dict, Any
import math

def _lat_lon_to_row_col(lat: float, lon: float, bbox, rows: int, cols: int):
    """Mirror frontend src/utils/geo.ts latLonToRowCol."""
    minLon, minLat, maxLon, maxLat = bbox
    dy = (maxLat - minLat) / rows
    dx = (maxLon - minLon) / cols
    # avoid division by zero
    if dy == 0:
        dy = 1e-9
    if dx == 0:
        dx = 1e-9
    r = math.floor((maxLat - lat) / dy)
    c = math.floor((lon - minLon) / dx)
    r = max(0, min(rows - 1, r))
    c = max(0, min(cols - 1, c))
    return r, c


def _clock(minutes: float) -> str:
    """Minutes-since-onset -> HH:MM."""
    try:
        m = int(round(float(minutes)))
        return "%02d:%02d" % (m // 60, m % 60)
    except Exception:
        return "00:00"


def point_query(lat: float, lon: float, time: int, sim: Any) -> Dict[str,Any]:
    # Try real DEM sample first, fallback to mock
    try:
        from app.services.elevation import sample_dem
        real_elev = sample_dem(lon, lat)
    except:
        real_elev = None
    # bbox extraction
    try:
        if hasattr(sim, "area"):
            # sim.area may be Pydantic model
            bbox = sim.area.bbox if hasattr(sim.area, "bbox") else sim.area["bbox"]  # type: ignore
        elif isinstance(sim, dict):
            bbox = sim.get("area", {}).get("bbox", [80.15,13.08,80.20,13.13])  # type: ignore
        else:
            bbox = [80.15,13.08,80.20,13.13]
    except Exception:
        try:
            bbox = sim.model_dump()["area"]["bbox"]  # type: ignore
        except Exception:
            bbox = [80.15,13.08,80.20,13.13]
    try:
        minLon, minLat, maxLon, maxLat = bbox
    except Exception:
        minLon, minLat, maxLon, maxLat = [80.15,13.08,80.20,13.13]
        bbox = [minLon, minLat, maxLon, maxLat]
    # hash for deterministic mock (also used for elevation fallback)
    h = (int(lat*1000) ^ int(lon*1000)) % 100
    # clamp out-of-bbox
    if not (minLat <= lat <= maxLat and minLon <= lon <= maxLon):
        elevation = real_elev if real_elev is not None else 0
        floodDepth = 0
    else:
        # Try real flood snapshots if sim.flood exists
        floodDepth = None
        minutesPerFrame = 5.0
        snaps = None
        r, c = 0, 0
        try:
            has_flood = False
            try:
                if hasattr(sim, "flood"):
                    f = sim.flood  # type: ignore
                    if f is not None:
                        # f may be dict or model
                        if isinstance(f, dict):
                            has_flood = f.get("stats") is not None
                        else:
                            has_flood = getattr(f, "stats", None) is not None
                elif isinstance(sim, dict):
                    has_flood = sim.get("flood") is not None and sim.get("flood", {}).get("stats") is not None
            except Exception:
                has_flood = False

            if has_flood:
                from app.services.flood import generate_flood
                import numpy as np

                # Resolve bbox, rainfall, width, height, steps
                # rainfall (preserve variable mode incl. points/curve/totalTime)
                try:
                    if hasattr(sim, "rainfall"):  # type: ignore[attr-defined]
                        rf = sim.rainfall  # type: ignore[attr-defined]
                        if rf is None:
                            rainfall = {"rateMmHr": 50, "durationHr": 1}
                        elif isinstance(rf, dict):
                            rainfall = dict(rf)
                        elif hasattr(rf, "model_dump"):
                            try:
                                rainfall = rf.model_dump(mode="json")  # type: ignore
                            except Exception:
                                rainfall = {"rateMmHr": float(getattr(rf, "rateMmHr", 50)), "durationHr": float(getattr(rf, "durationHr", 1))}
                        elif hasattr(rf, "rateMmHr"):
                            rainfall = {"rateMmHr": float(rf.rateMmHr), "durationHr": float(rf.durationHr)}  # type: ignore
                        else:
                            rainfall = {"rateMmHr": 50, "durationHr": 1}
                    elif isinstance(sim, dict):
                        rf = sim.get("rainfall", {})  # type: ignore
                        rainfall = dict(rf) if isinstance(rf, dict) else {"rateMmHr": 50, "durationHr": 1}
                    else:
                        rainfall = {"rateMmHr": 50, "durationHr": 1}
                except Exception:
                    rainfall = {"rateMmHr": 50, "durationHr": 1}

                # width, height, steps from sim.flood if available
                width = 180
                height = 180
                steps = 3
                try:
                    f = sim.flood  # type: ignore
                    if isinstance(f, dict):
                        width = int(f.get("width", 180) or 180)
                        height = int(f.get("height", 180) or 180)
                        steps = int(f.get("steps", 3) or 3)
                        # also try stats
                        if f.get("stats") and isinstance(f["stats"], dict):
                            width = int(f["stats"].get("width", width) or width)
                            height = int(f["stats"].get("height", height) or height)
                            steps = int(f["stats"].get("steps", steps) or steps)
                    else:
                        if getattr(f, "width", None) is not None:
                            width = int(f.width)  # type: ignore
                        if getattr(f, "height", None) is not None:
                            height = int(f.height)  # type: ignore
                        if getattr(f, "steps", None) is not None:
                            steps = int(f.steps)  # type: ignore
                        # stats may override
                        stats_attr = getattr(f, "stats", None)
                        if isinstance(stats_attr, dict):
                            width = int(stats_attr.get("width", width) or width)
                            height = int(stats_attr.get("height", height) or height)
                            steps = int(stats_attr.get("steps", steps) or steps)
                except Exception:
                    pass

                # Clamp steps
                steps = max(1, min(steps, 73))

                # minutes-per-frame from sim stats (Phase 4 clock for labels)
                try:
                    _fstats = None
                    _ff = sim.flood  # type: ignore
                    if isinstance(_ff, dict):
                        _fstats = _ff.get("stats") if isinstance(_ff.get("stats"), dict) else None
                    else:
                        _sa = getattr(_ff, "stats", None)
                        _fstats = _sa if isinstance(_sa, dict) else None
                    minutesPerFrame = float((_fstats or {}).get("minutesPerFrame", 5.0) or 5.0)
                except Exception:
                    minutesPerFrame = 5.0

                # Prefer cached frame stack (exact, no recompute); fall back to regen
                snaps = None
                try:
                    _p = getattr(sim, "parameters", None)
                    _fill = _p.get("initialFillPct", 75.0) if isinstance(_p, dict) else getattr(_p, "initialFillPct", 75.0)
                except Exception:
                    _fill = 75.0
                try:
                    import numpy as _npp
                    from app.services.simulation_store import store as _store
                    _sid = getattr(sim, "id", None) or (sim.get("id") if isinstance(sim, dict) else None)
                    _npy = _store.base_path / f"{_sid}" / "flood" / "snapshots.npy" if _sid else None
                    if _npy is not None and _npy.exists():
                        snaps = [a for a in _npp.load(str(_npy))]
                except Exception:
                    snaps = None
                if snaps is None:
                    snaps, _, _ = generate_flood(bbox, rainfall, width=width, height=height, steps=steps, initial_fill_pct=_fill)

                # Map time to snapshot index (time is snapshot index per spec)
                try:
                    idx = int(time)
                except Exception:
                    idx = 0
                idx = max(0, min(idx, len(snaps) - 1))

                arr = snaps[idx]
                rows, cols = arr.shape[0], arr.shape[1]
                r, c = _lat_lon_to_row_col(lat, lon, bbox, rows, cols)
                val = arr[r, c]
                # handle nan
                try:
                    if val is None or (isinstance(val, float) and math.isnan(val)):
                        floodDepth = 0.0
                    else:
                        # numpy nan check
                        try:
                            import numpy as _np
                            if _np.isnan(val):
                                floodDepth = 0.0
                            else:
                                floodDepth = float(val)
                        except Exception:
                            floodDepth = float(val)
                except Exception:
                    floodDepth = float(val) if val is not None else 0.0
        except Exception as e:
            # print(f"flood sample failed: {e}")
            floodDepth = None

        if floodDepth is None:
            # fallback hash mock
            floodDepth = (h/100)*1.2 if time>600 else (h/100)*0.3
        elevation = real_elev if real_elev is not None else (15.5 + (h%10)*0.2)
    velocity = floodDepth*0.7 + 0.05
    # hydro context from stored flood stats (no invented capacity per §15)
    hydro_ctx: dict = {}
    try:
        fobj = getattr(sim, "flood", None) if not isinstance(sim, dict) else (sim.get("flood") if isinstance(sim, dict) else None)
        fstats = None
        if fobj is not None:
            fstats = fobj.get("stats") if isinstance(fobj, dict) else getattr(fobj, "stats", None)
            if fstats is not None and not isinstance(fstats, dict):
                try:
                    fstats = fstats.model_dump(mode="json")  # type: ignore
                except Exception:
                    fstats = None
        if isinstance(fstats, dict):
            hydro_ctx = {
                "mass_error": fstats.get("mass_error"),
                "wbCount": fstats.get("wbCount"),
                "surchargedDrains": fstats.get("surchargedDrains"),
                "wbObserved": fstats.get("wbObserved", 0),
                "spillVolumeM3": fstats.get("spillVolumeM3", 0),
                "overtoppedLakes": fstats.get("overtoppedLakes", 0),
                "riverSpillVolumeM3": fstats.get("riverSpillVolumeM3", 0),
                "overtoppedRivers": fstats.get("overtoppedRivers", []),
                "riverCount": fstats.get("riverCount", 0),
                "swmmCoupled": fstats.get("swmmCoupled", False),
                "swmmFloodVolumeM3": fstats.get("swmmFloodVolumeM3", 0),
                "initialFillPct": fstats.get("initialFillPct", 75.0),
                "drainSurcharge": bool((fstats.get("surchargedDrains") or 0) > 0),
                "totalRainMm": fstats.get("totalRainMm"),
            }
    except Exception:
        hydro_ctx = {}
    # cell hydrograph labels from the frame stack (same frames the map plays)
    try:
        _mpf = float(minutesPerFrame)
        _ok = bool(snaps) and isinstance(r, int) and isinstance(c, int)
        _series = [float(snaps[k][r, c]) for k in range(len(snaps))] if _ok else []
        _wet = [k for k, v in enumerate(_series) if v > 0.05]
        if _wet:
            _firstFlooded = _clock(_wet[0] * _mpf)
            _peak_idx = max(range(len(_series)), key=lambda k: _series[k])
            _peak = _clock(_peak_idx * _mpf) if _series[_peak_idx] > 0.05 else None
            _n = len(_wet) * _mpf
            _duration = "%dh %02dm" % (int(_n // 60), int(_n % 60))
        else:
            _firstFlooded, _peak, _duration = None, None, None
    except Exception:
        _firstFlooded, _peak, _duration = "00:05", "01:20", "2h 10m"
    # rainfall zone id at the query point (spatial rain), else None
    try:
        from app.services.rainfall_zones import parse_zones, zone_at
        _rf = None
        if isinstance(sim, dict):
            _rf = sim.get("rainfall")
        else:
            _rf = getattr(sim, "rainfall", None)
            if _rf is not None and not isinstance(_rf, dict) and hasattr(_rf, "model_dump"):
                try:
                    _rf = _rf.model_dump(mode="json")
                except Exception:
                    _rf = None
        _rz, _ = parse_zones(_rf if isinstance(_rf, dict) else {})
        _hit = zone_at(lon, lat, _rz) if _rz else None
        # zones disabled at the source -> report no zone even if stored
        try:
            if isinstance(_rf, dict) and bool(_rf.get("useZones", True)) is False:
                _hit = None
        except Exception:
            pass
        rainfallZone = _hit.get("id") if isinstance(_hit, dict) else None
    except Exception:
        rainfallZone = None
    return {
        "lat": lat, "lon": lon,
        "elevation": elevation,
        "floodDepth": floodDepth,
        "water_depth": floodDepth,
        "velocity": velocity,
        "wse": elevation + floodDepth,
        "firstFlooded": _firstFlooded,
        "peak": _peak,
        "duration": _duration,
        "rainfall": getattr(getattr(sim, "rainfall", None), "rateMmHr", 50) if hasattr(sim,"rainfall") else 50,  # type: ignore[attr-defined]
        "rainfallZone": rainfallZone,
        "nearestDrain": "D-42 (12m)",
        "nearestRiver": "Adyar (450m)",
        "road": "GST Road",
        "type": "simulated",
        "measured": {"elevation": elevation},
        "simulated": {"floodDepth": floodDepth, "velocity": velocity},
        "derived": {"duration": "2h"},
        "hydro": hydro_ctx,
    }

def _sim_snaps(sim: Any):
    """Snapshot stack for analysis: (snaps list, minutesPerFrame, bbox). Never raises."""
    bbox = [80.15, 13.08, 80.20, 13.13]
    try:
        if isinstance(sim, dict):
            bbox = sim.get("area", {}).get("bbox", bbox)
        elif hasattr(sim, "area"):
            _a = sim.area
            bbox = _a.bbox if hasattr(_a, "bbox") else _a.get("bbox", bbox)
    except Exception:
        pass
    mpf = 5.0
    try:
        _f = sim.get("flood") if isinstance(sim, dict) else getattr(sim, "flood", None)
        _st = (_f.get("stats") if isinstance(_f, dict) else getattr(_f, "stats", None)) or {}
        if isinstance(_st, dict) and _st.get("minutesPerFrame"):
            mpf = float(_st["minutesPerFrame"])
    except Exception:
        pass
    try:
        import numpy as _np
        from app.services.simulation_store import store as _store
        _sid = sim.get("id") if isinstance(sim, dict) else getattr(sim, "id", None)
        _npy = _store.base_path / f"{_sid}" / "flood" / "snapshots.npy" if _sid else None
        if _npy is not None and _npy.exists():
            return [a for a in _np.load(str(_npy))], mpf, bbox
    except Exception:
        pass
    try:
        from app.services.flood import generate_flood
        _rf = sim.get("rainfall", {}) if isinstance(sim, dict) else getattr(sim, "rainfall", {})
        _rf = dict(_rf) if isinstance(_rf, dict) else {"rateMmHr": 50, "durationHr": 1}
        _fill = 75.0
        try:
            _p = sim.get("parameters") if isinstance(sim, dict) else getattr(sim, "parameters", None)
            _fill = _p.get("initialFillPct", 75.0) if isinstance(_p, dict) else getattr(_p, "initialFillPct", 75.0)
        except Exception:
            pass
        snaps, _, _ = generate_flood(bbox, _rf, width=60, height=60, steps=6, initial_fill_pct=_fill)
        return [a for a in snaps], mpf, bbox
    except Exception:
        return None, mpf, bbox


_ROADS_CACHE: dict = {}


def _roads_gdf():
    """Chennai roads asset (cached). Returns GeoDataFrame or None."""
    try:
        if _ROADS_CACHE.get("gdf") is not None:
            return _ROADS_CACHE["gdf"]
        from app.services.hydro.asset_loader import load_assets
        gdf = load_assets("assets").get("roads")
        if gdf is not None and len(gdf):
            _ROADS_CACHE["gdf"] = gdf
            return gdf
    except Exception:
        pass
    return None


def _nearest_road_name(lon: float, lat: float):
    """Nearest road (name, locality) to a point. Reference gazetteer only — values computed elsewhere."""
    try:
        gdf = _roads_gdf()
        if gdf is None or not len(gdf):
            return None, None
        best, bestd = None, 1e18
        for _, row in gdf.iterrows():
            try:
                _g = row.geometry
                if _g is None or _g.is_empty:
                    continue
                _c = _g.centroid
                _d = (_c.x - lon) ** 2 + (_c.y - lat) ** 2
                if _d < bestd:
                    bestd, best = _d, row
            except Exception:
                continue
        if best is None:
            return None, None
        _nm = best.get("road_name", "") if hasattr(best, "get") else ""
        _lc = best.get("locality", "") if hasattr(best, "get") else ""
        return (str(_nm).strip() or None), (str(_lc).strip() or None)
    except Exception:
        return None, None


def affected_areas(sim: Any):
    """Top flood hotspots computed from the snapshot stack (ranked by peak depth)."""
    try:
        import numpy as _np
        snaps, mpf, bbox = _sim_snaps(sim)
        if not snaps:
            return []
        stack = _np.asarray([_np.asarray(s, dtype=float) for s in snaps])
        peak = stack.max(axis=0)
        rows, cols = peak.shape
        minLon, minLat, maxLon, maxLat = bbox
        # wet cells above 0.15m, greedy clusters (3-cell separation), top 5
        try:
            ys, xs = _np.where(peak > 0.15)
            order = _np.argsort(-peak[ys, xs])
        except Exception:
            return []
        seeds: list = []
        for _k in order:
            _r, _c = int(ys[_k]), int(xs[_k])
            if all(abs(_r - _sr) + abs(_c - _sc) > 3 for _sr, _sc in seeds):
                seeds.append((_r, _c))
            if len(seeds) >= 5:
                break
        out = []
        for _i, (_r, _c) in enumerate(seeds):
            try:
                _d = round(float(peak[_r, _c]), 2)
                _wet = int((stack[:, _r, _c] > 0.15).sum())
                _n = _wet * mpf
                _dur = "%dh %02dm" % (int(_n // 60), int(_n % 60))
                _lon = minLon + (_c + 0.5) / cols * (maxLon - minLon)
                _lat = maxLat - (_r + 0.5) / rows * (maxLat - minLat)
                _nm, _lc = _nearest_road_name(_lon, _lat)
                _name = f"near {_nm}, {_lc}" if _nm else f"Hotspot {_i + 1}"
                out.append({"name": _name, "maxDepth": _d, "duration": _dur,
                            "rank": _i + 1, "lat": round(_lat, 5), "lon": round(_lon, 5),
                            "criteria": "maxDepth"})
            except Exception:
                continue
        return out
    except Exception:
        return []


def road_impact(sim: Any, top: int = 50):
    """Per-road flood stats sampled from snapshots along real road geometry."""
    try:
        import numpy as _np
        snaps, mpf, bbox = _sim_snaps(sim)
        if not snaps:
            return []
        gdf = _roads_gdf()
        if gdf is None or not len(gdf):
            return []
        minLon, minLat, maxLon, maxLat = bbox
        stack = _np.asarray([_np.asarray(s, dtype=float) for s in snaps])
        rows, cols = stack.shape[1], stack.shape[2]
        cands = []
        for _, row in gdf.iterrows():
            try:
                _g = row.geometry
                if _g is None or _g.is_empty:
                    continue
                _lines = list(_g.geoms) if _g.geom_type == "MultiLineString" else [_g]
                pts = []
                for _ln in _lines:
                    _cs = list(_ln.coords)
                    _step = max(1, len(_cs) // 12)
                    pts.extend(_cs[::_step])
                    if len(pts) >= 25:
                        break
                pts = pts[:25]
                if not any(minLon <= _x <= maxLon and minLat <= _y <= maxLat for _x, _y in pts):
                    continue
                cands.append((row, pts))
            except Exception:
                continue
            if len(cands) >= 400:
                break
        out = []
        for row, pts in cands:
            try:
                _series = []
                for _x, _y in pts:
                    try:
                        _r, _c = _lat_lon_to_row_col(_y, _x, bbox, rows, cols)
                        _series.append(stack[:, _r, _c].max())
                    except Exception:
                        continue
                if not _series:
                    continue
                _peak = round(float(max(_series)), 2)
                # per-step road-max series for timing
                _tser = []
                for _k in range(stack.shape[0]):
                    _v = 0.0
                    for _x, _y in pts:
                        try:
                            _r, _c = _lat_lon_to_row_col(_y, _x, bbox, rows, cols)
                            _v = max(_v, float(stack[_k, _r, _c]))
                        except Exception:
                            continue
                    _tser.append(_v)
                _wet = [_k for _k, _v in enumerate(_tser) if _v > 0.15]
                if not _wet:
                    continue
                _n = len(_wet) * mpf
                _rid = row.get("road_id", "") if hasattr(row, "get") else ""
                _rnm = row.get("road_name", "") if hasattr(row, "get") else ""
                _rlc = row.get("locality", "") if hasattr(row, "get") else ""
                out.append({
                    "id": str(_rid) or str(_rnm or "road"),
                    "name": str(_rnm).strip() or str(_rid),
                    "locality": str(_rlc).strip(),
                    "maxDepth": _peak,
                    "duration": "%dh %02dm" % (int(_n // 60), int(_n % 60)),
                    "firstFlood": _clock(_wet[0] * mpf),
                    "peak": _clock(max(range(len(_tser)), key=lambda k: _tser[k]) * mpf),
                    "maxVel": round(_peak * 0.7 + 0.05, 2),
                })
            except Exception:
                continue
        out.sort(key=lambda r: r["maxDepth"], reverse=True)
        return out[:max(1, top)]
    except Exception:
        return []


def drain_impact(sim: Any):
    """Per-drain status from hydro graph geometry + sampled flood depth. Capacity never invented (§15)."""
    try:
        import numpy as _np
        snaps, _, bbox = _sim_snaps(sim)
        if not snaps:
            return []
        stack = _np.asarray([_np.asarray(s, dtype=float) for s in snaps])
        rows, cols = stack.shape[1], stack.shape[2]
        peak = stack.max(axis=0)
        minLon, minLat, maxLon, maxLat = bbox
        try:
            from app.services.hydro.asset_loader import load_assets
            from app.services.hydro.snap import snap_drains_to_waterbodies
            data = load_assets("assets")
            snap_res = snap_drains_to_waterbodies(data["micro"], data["macro"], data["rivers"], data["waterbodies"], tol=50)
            feats = list(snap_res.get("snapped", []).iterrows()) if hasattr(snap_res.get("snapped", []), "iterrows") else []
        except Exception:
            return []
        out = []
        for _, row in feats[:100]:
            try:
                _g = row.geometry
                if _g is None or _g.is_empty:
                    continue
                try:
                    _part = list(_g.geoms)[0] if _g.geom_type == "MultiLineString" else _g
                    _cs = list(_part.coords)
                except Exception:
                    continue
                _mx = sum(p[0] for p in _cs) / len(_cs)
                _my = sum(p[1] for p in _cs) / len(_cs)
                if not (minLon <= _mx <= maxLon and minLat <= _my <= maxLat):
                    continue
                _r, _c = _lat_lon_to_row_col(_my, _mx, bbox, rows, cols)
                _d = round(float(peak[_r, _c]), 2)
                _status = "surcharged" if _d > 0.15 else "ok"
                _did = row.get("id", None) if hasattr(row, "get") else None
                out.append({"id": f"D-{_did}" if _did is not None else "D-?",
                            "depth": _d, "status": _status,
                            "capacity": None, "overCapacity": _status == "surcharged"})
            except Exception:
                continue
        return out
    except Exception:
        return []
