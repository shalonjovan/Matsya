"""Real SWMM engine behind the run contract (Slice 1). Mirrors anuga_runner shapes."""
import threading
import time
import uuid
import json
import pathlib
from datetime import datetime, timezone
from typing import Any

from app.services.engine import swmm_inp

_runs: dict = {}


def _parse_flooding(rpt_path):
    """Return (flooded_node_count, total_flood_volume_m3) from Node Flooding Summary."""
    try:
        text = pathlib.Path(rpt_path).read_text(errors="ignore")
    except Exception:
        return 0, 0.0
    i = text.find("Node Flooding Summary")
    if i < 0 or "No nodes were flooded" in text[i:i + 600]:
        return 0, 0.0
    count, vol = 0, 0.0
    for line in text[i:].splitlines()[6:60]:
        parts = line.split()
        if len(parts) >= 6 and parts[0][0] in "JN":
            try:
                count += 1
                vol += float(parts[5])
            except ValueError:
                continue
    return count, vol


def run_network_sync(drains, rainfall, workdir, outfall_stages=None):
    """Run one SWMM network synchronously. Returns solved + per-node floods."""
    import pathlib
    from pyswmm import Simulation, Links, Nodes
    from app.services.engine import swmm_inp
    outdir = pathlib.Path(workdir)
    outdir.mkdir(parents=True, exist_ok=True)
    inp = swmm_inp.build_inp(drains, rainfall, [80.15, 13.08, 80.20, 13.13],
                             str(outdir / "network.inp"), outfall_stages=outfall_stages)
    link_ids, node_ids = [], []
    for i in range(len(drains)):
        link_ids += ["C%d" % i, "CX%d" % i]
        node_ids += ["J%d_UP" % i, "J%d_DN" % i]
    node_vol: dict = {}
    node_peak: dict = {}
    link_peak: dict = {}
    step_times = []
    with Simulation(inp) as sim_obj:
        links, nodes = Links(sim_obj), Nodes(sim_obj)
        for step in sim_obj:
            try:
                step_times.append(sim_obj._model.getCurrentSimulationTime() if hasattr(sim_obj._model, "getCurrentSimulationTime") else len(step_times) * 300)
            except Exception:
                step_times.append(len(step_times) * 300)
            for lid in link_ids:
                try:
                    link_peak[lid] = max(link_peak.get(lid, 0.0), abs(links[lid].flow))
                except Exception:
                    pass
            for nid in node_ids:
                try:
                    q = nodes[nid].flooding or 0
                except Exception:
                    q = 0
                if q > 0:
                    node_peak[nid] = max(node_peak.get(nid, 0.0), q)
                    node_vol[nid] = node_vol.get(nid, 0.0) + q * 30.0  # routing step 30s
    rpt = inp.replace(".inp", ".rpt")
    try:
        solved = "Analysis ended" in pathlib.Path(rpt).read_text(errors="ignore")
    except Exception:
        solved = False
    floods = {nid: {"volume_m3": round(node_vol.get(nid, 0.0), 1),
                    "peak_rate": round(node_peak.get(nid, 0.0), 4)}
              for nid in node_vol if node_vol.get(nid, 0.0) > 0}
    outfall_volume_m3 = _parse_outfall_volume(rpt)
    return {"solved": bool(solved), "node_flood": floods, "link_peak": link_peak,
            "times": step_times, "rpt": rpt, "inp": inp,
            "outfall_volume_m3": outfall_volume_m3}


def _parse_outfall_volume(rpt_path):
    """Sum Total Volume (10^6 ltr) over Outfall Loading Summary rows -> m3."""
    try:
        text = pathlib.Path(rpt_path).read_text(errors="ignore")
    except Exception:
        return 0.0
    i = text.find("Outfall Loading Summary")
    if i < 0:
        return 0.0
    total = 0.0
    for line in text[i:].splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[0].startswith("O") and parts[0][1:].isdigit():
            try:
                total += float(parts[4]) * 1000.0  # 10^6 ltr -> m3
            except ValueError:
                continue
    return round(total, 1)


def run_simulation(sim_id: str, sim: Any) -> str:
    run_id = str(uuid.uuid4())
    _runs[run_id] = {"runId": run_id, "simId": sim_id, "engine": "swmm",
                     "status": "Running", "progress": 10,
                     "created": datetime.now(timezone.utc).isoformat()}
    payload = sim.model_dump(mode="python") if hasattr(sim, "model_dump") else dict(sim)

    def bg():
        try:
            drains = payload.get("_test_drains")
            if drains is None:
                drains = drains_for_bbox((payload.get("area") or {}).get("bbox", [80.15, 13.08, 80.20, 13.13]))
            rainfall = payload.get("rainfall") or {}
            audit = swmm_inp.audit_inputs(drains, rainfall)
            _runs[run_id]["audit"] = audit
            _runs[run_id]["progress"] = 30
            if not audit["ready"]:
                _runs[run_id].update({"status": "Failed",
                                      "error": audit["mode"] + ": " + "; ".join(audit["missing"])})
                return
            outdir = pathlib.Path(__file__).parents[2] / "data" / "runs" / run_id
            res = run_network_sync(drains, rainfall, str(outdir))
            _runs[run_id].update({"inp": res["inp"], "rpt": res["rpt"], "progress": 50})
            times = res["times"]
            peak_flow = round(max(res["link_peak"].values() or [0.0]), 4)
            peak_flood = round(max([v["peak_rate"] for v in res["node_flood"].values()] or [0.0]), 4)
            _runs[run_id]["progress"] = 90
            n_count = len(res["node_flood"])
            n_vol = round(sum(v["volume_m3"] for v in res["node_flood"].values()), 2)
            solved = res["solved"]
            stats = {"solved": bool(solved), "floodedNodeCount": n_count,
                     "totalFloodVolumeM3": round(n_vol, 2),
                     "peakLinkFlowCMS": round(peak_flow, 4),
                     "peakFloodRateCMS": round(peak_flood, 4), "engine": "swmm"}
            stride = max(1, len(times) // 73)
            _runs[run_id].update({"status": "Completed", "progress": 100,
                                  "results": {"times": times[::stride][:73] if times else [],
                                              "stats": stats},
                                  "rpt": res["rpt"]})
        except Exception as e:
            _runs[run_id].update({"status": "Failed", "error": "swmm-error: %s" % e})
    threading.Thread(target=bg, daemon=True).start()
    return run_id


def get_run(run_id: str):
    return _runs.get(run_id)


_SWMM_CACHE_TTL = 86400


def cached_node_floods(bbox, rainfall, limit=40):
    """Node floods for a bbox+rainfall via SWMM, cached on disk.

    Returns {"coupled": bool, "node_flood": {node: {volume_m3, peak_rate}},
    "drains": [rows with x0/y0/x1/y1]}. drains list is always fresh
    (cheap); only the solver run is cached.
    """
    import hashlib
    import json as _json
    import time as _t
    try:
        key_src = _json.dumps({"bbox": list(bbox), "rain": rainfall, "limit": limit,
                               "geom": "v1"}, sort_keys=True, default=str)
    except Exception:
        key_src = repr((bbox, str(rainfall), limit))
    h = hashlib.md5(key_src.encode()).hexdigest()[:16]
    cdir = pathlib.Path(__file__).parents[2] / "data" / "swmm_cache"
    cfile = cdir / (h + ".json")
    try:
        drains = drains_for_bbox(list(bbox), limit=limit)
    except Exception:
        drains = []
    if not drains:
        return {"coupled": False, "node_flood": {}, "drains": []}
    try:
        if cfile.exists() and (_t.time() - cfile.stat().st_mtime) < _SWMM_CACHE_TTL:
            c = _json.loads(cfile.read_text())
            if isinstance(c, dict) and "node_flood" in c:
                return {"coupled": bool(c.get("coupled")), "node_flood": c["node_flood"],
                        "drains": drains}
    except Exception:
        pass
    try:
        tmp = cdir / ("run_" + h)
        res = run_network_sync(drains, rainfall or {}, str(tmp))
        out = {"coupled": bool(res.get("solved")),
               "node_flood": res.get("node_flood", {})}
        try:
            cdir.mkdir(parents=True, exist_ok=True)
            cfile.write_text(_json.dumps(out))
        except Exception:
            pass
        out["drains"] = drains
        return out
    except Exception:
        return {"coupled": False, "node_flood": {}, "drains": drains}


def drains_for_bbox(bbox, limit=40):
    """Clip micro+macro drains to bbox; lengths from UTM geometry, inverts from DEM."""
    from app.services.hydro.asset_loader import load_assets
    try:
        data = load_assets("assets")
    except Exception:
        return []
    import geopandas as gpd
    import pandas as pd
    frames = [f for f in (data.get("micro"), data.get("macro")) if f is not None and len(f) > 0]
    if not frames:
        return []
    drains = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs="EPSG:4326")
    minLon, minLat, maxLon, maxLat = bbox
    try:
        clip = drains.cx[minLon:maxLon, minLat:maxLat]
    except Exception:
        clip = drains
    if len(clip) == 0:
        return []
    try:
        utm = clip.to_crs("EPSG:32644")
        clip = clip.copy()
        clip["_len"] = utm.geometry.length.values
        clip = clip.sort_values("_len", ascending=False).head(limit)
    except Exception:
        clip = clip.head(limit)
    try:
        from app.services.elevation import sample_dem
    except Exception:
        sample_dem = lambda lon, lat: None
    import math
    rows = []
    for i, (_, row) in enumerate(clip.iterrows()):
        try:
            geom = row.geometry
            coords = list(geom.coords) if geom.geom_type == "LineString" else list(list(geom.geoms)[0].coords)
            (x0, y0), (x1, y1) = coords[0], coords[-1]
            dx = (x1 - x0) * 111320 * math.cos(math.radians((y0 + y1) / 2))
            dy = (y1 - y0) * 110540
            length = max(20.0, math.hypot(dx, dy))
            z0 = sample_dem(x0, y0) or 10.0
            z1 = sample_dem(x1, y1) or (z0 - max(0.5, length * 0.001))
            if z1 > z0:
                z0, z1 = z1, z0
            rows.append({"id": str(row.get("id", i)), "length_m": round(length, 1),
                         "slope": round(max(0.0005, (z0 - z1) / length), 5),
                         "z0": round(z0, 2), "z1": round(z1, 2),
                         "x0": x0, "y0": y0, "x1": x1, "y1": y1})
        except Exception:
            continue
    return rows


def list_runs(sim_id: str):
    return [r for r in _runs.values() if r["simId"] == sim_id]
