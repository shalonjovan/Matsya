"""Real ANUGA 2D runner (Slice 3). Mirrors swmm_runner shapes.

Solver runs in the isolated py3.11 venv as a subprocess (ANUGA_PYTHON).
D8 stays the product default; this module is inert until explicitly called.
"""
import json
import os
import pathlib
import subprocess
import tempfile
import threading
import time
import uuid
from datetime import datetime, timezone

DEFAULT_ANUGA_PYTHON = os.path.expanduser("~/.venvs/matsya-anuga/bin/python")

_runs: dict = {}

DRIVER = r'''
import json, os, sys
import numpy as np
import anuga
from anuga import rectangular_cross_domain, Reflective_boundary
from anuga.operators.rate_operators import Rate_operator

# Observed API (installed anuga 4.0.0, mapped 2026-09-06). Culvert operators
# are stubbed at the domain-builder level; this driver runs surface rain only.
workdir, elev_npy, man_npy, rain_json, duration_min, cell_m = sys.argv[1:7]
duration_min = float(duration_min)
elev = np.load(elev_npy)
man = np.load(man_npy)
rain_series = json.load(open(rain_json))  # [[minutes_since_start, mm/hr], ...]
rows, cols = elev.shape
finite = np.isfinite(elev)
fill = float(elev[finite].mean()) if finite.any() else 5.0
man_f = np.where(np.isfinite(man), man, 0.035)

Lx, Ly = cols * float(cell_m), rows * float(cell_m)

def _elevfn(x, y):
    xa, ya = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    c = np.clip((xa / float(cell_m)).astype(int), 0, cols - 1)
    r = np.clip(((Ly - ya) / float(cell_m)).astype(int), 0, rows - 1)
    v = elev[r, c]
    return np.where(np.isfinite(v), v, fill)

def _manfn(x, y):
    xa, ya = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    c = np.clip((xa / float(cell_m)).astype(int), 0, cols - 1)
    r = np.clip(((Ly - ya) / float(cell_m)).astype(int), 0, rows - 1)
    v = man_f[r, c]
    return np.where(np.isfinite(v), v, 0.035)

n = 60
domain = rectangular_cross_domain(n, n, len1=Lx, len2=Ly)
domain.set_name("matsya")
domain.set_datadir(workdir)
domain.store = False
domain.set_quantity("elevation", _elevfn)
domain.set_quantity("friction", _manfn)
domain.set_quantity("stage", float(np.nanmin(elev)) - 0.5 if finite.any() else 0.0)
Br = Reflective_boundary(domain)
domain.set_boundary({"left": Br, "right": Br, "top": Br, "bottom": Br})

rain_op = Rate_operator(domain, rate=0.0)
frames, ftimes = [], []

def _record():
    st = np.asarray(domain.quantities["stage"].centroid_values)
    ev = np.asarray(domain.quantities["elevation"].centroid_values)
    frames.append(np.maximum(0.0, st - ev).astype(np.float32))

t = 0.0
segs = sorted(rain_series, key=lambda p: p[0]) if rain_series else [[0.0, 0.0]]
for (t0, rate), (t1, _r) in zip(segs, segs[1:] + [[duration_min, 0.0]]):
    t1 = min(float(t1), duration_min)
    if t1 <= t:
        continue
    rain_op.rate = float(rate) / 1000.0 / 3600.0
    for tt in domain.evolve(yieldstep=300, finaltime=t1 * 60.0):
        _record()
    t = t1
_record()
frames = np.array(frames)
np.save(os.path.join(workdir, "depths.npy"), frames)
try:
    _areas = np.asarray(domain.areas, dtype=np.float64)
except Exception:
    _areas = np.full((frames.shape[1],), (Lx * Ly) / max(1, frames.shape[1]))
np.save(os.path.join(workdir, "areas.npy"), _areas)
cell_area = float(_areas.sum()) / max(1, _areas.size)
wet = frames > 0.05
print("RESULT frames=%d maxDepth=%.4f floodedArea=%.4f meanDepth=%.4f" % (
    len(frames), float(frames.max()),
    float((_areas * wet[-1]).sum()) / 1e6 if len(frames) else 0.0,
    float(frames[-1][frames[-1] > 0.05].mean()) if len(frames) and (frames[-1] > 0.05).any() else 0.0))
'''


def _anuga_python():
    p = os.environ.get("ANUGA_PYTHON", DEFAULT_ANUGA_PYTHON)
    if p and os.path.isfile(p) and os.access(p, os.X_OK):
        return p
    return None


def run_anuga_sync(bbox, rainfall, hydro_graph, workdir, timeout=1800):
    """Run one ANUGA 2D sim synchronously. Returns {solved, stats, depths_npy, ...}."""
    import numpy as np
    import rasterio
    from app.services.engine.anuga_domain import build_domain_inputs
    outdir = pathlib.Path(workdir)
    outdir.mkdir(parents=True, exist_ok=True)
    dom = build_domain_inputs(list(bbox), rainfall or {}, hydro_graph or {}, str(outdir / "domain"))
    with rasterio.open(dom["elevation_tif"]) as src:
        elev = src.read(1).astype(np.float64)
        res = abs(src.res[0])
    with rasterio.open(dom["manning_tif"]) as src:
        man = src.read(1).astype(np.float64)
    # rain series -> minutes
    total_min = 60.0
    try:
        if (rainfall or {}).get("mode") == "variable":
            total_min = float(rainfall.get("totalTime", 6) or 6) * 60.0
        else:
            total_min = float((rainfall or {}).get("durationHr", 1) or 1) * 60.0
    except Exception:
        pass
    series_min = []
    for t_hr, v in dom["rain_series"]:
        series_min.append([float(t_hr) * 60.0, float(v)])
    np.save(str(outdir / "elev.npy"), elev)
    np.save(str(outdir / "man.npy"), man)
    (outdir / "rain.json").write_text(json.dumps(series_min))
    (outdir / "driver.py").write_text(DRIVER)
    py = _anuga_python()
    if py is None:
        return {"solved": False, "error": "anuga-unavailable: set ANUGA_PYTHON",
                "stats": {"engine": "anuga"}}
    try:
        proc = subprocess.run(
            [py, str(outdir / "driver.py"), str(outdir),
             str(outdir / "elev.npy"), str(outdir / "man.npy"),
             str(outdir / "rain.json"), str(total_min), str(dom["cell_m"])],
            capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"solved": False, "error": "solver-timeout after %ss" % timeout,
                "stats": {"engine": "anuga"}}
    import re
    m = re.search(r"RESULT frames=(\d+) maxDepth=([0-9.\-eE]+) floodedArea=([0-9.\-eE]+) meanDepth=([0-9.\-eE]+)",
                  proc.stdout or "")
    if proc.returncode != 0 or not m:
        return {"solved": False,
                "error": "solver-failed rc=%s tail=%s" % (proc.returncode, (proc.stdout or "")[-400:] + (proc.stderr or "")[-400:]),
                "stats": {"engine": "anuga"}}
    frames, max_d, flooded, mean_d = int(m.group(1)), float(m.group(2)), float(m.group(3)), float(m.group(4))
    # mass ledger: rain in vs stored (reflective domain: outflow 0).
    # Use ANUGA's own triangle areas, NOT the input grid cells.
    try:
        _areas = np.load(str(outdir / "areas.npy")).astype(np.float64)
        mesh_area = float(_areas.sum())
    except Exception:
        _areas, mesh_area = None, 0.0
    try:
        rain_vol = 0.0
        for (t0, v0), (t1, _v1) in zip(series_min, series_min[1:] + [[total_min, 0.0]]):
            rain_vol += max(0.0, v0) / 1000.0 * max(0.0, (min(t1, total_min) - t0)) / 60.0
        rain_vol *= mesh_area if mesh_area > 0 else float(np.isfinite(elev).sum()) * (float(dom["cell_m"]) ** 2)
        _last = np.load(str(outdir / "depths.npy"))[-1].astype(np.float64)
        if _areas is not None and _areas.size == _last.size:
            stored = float((_last * _areas).sum())
        else:
            stored = float(_last.sum()) * (float(dom["cell_m"]) ** 2)
        mass_error = abs(stored - rain_vol) / max(1.0, rain_vol) if rain_vol > 0 else (0.0 if stored == 0 else 1.0)
    except Exception:
        mass_error, rain_vol = 1.0, 0.0
    stats = {"maxDepth": max_d, "floodedArea": flooded, "meanDepth": mean_d,
             "mass_error": float(min(1.0, mass_error)), "rainVolumeM3": round(rain_vol, 1),
             "engine": "anuga", "frames": frames}
    return {"solved": True, "stats": stats, "depths_npy": str(outdir / "depths.npy"),
            "audit": dom["audit"]}


def run_simulation(sim_id: str, sim: dict) -> str:
    run_id = str(uuid.uuid4())
    _runs[run_id] = {"runId": run_id, "simId": sim_id, "engine": "anuga",
                     "status": "Running", "progress": 10,
                     "created": datetime.now(timezone.utc).isoformat()}
    payload = sim.model_dump(mode="python") if hasattr(sim, "model_dump") else dict(sim)

    def bg():
        try:
            bbox = (payload.get("area") or {}).get("bbox", [80.15, 13.08, 80.20, 13.13])
            rainfall = payload.get("rainfall") or {}
            outdir = pathlib.Path(__file__).parents[2] / "data" / "runs" / run_id
            _runs[run_id]["progress"] = 30
            res = run_anuga_sync(bbox, rainfall, {"links": []}, str(outdir))
            if not res.get("solved"):
                _runs[run_id].update({"status": "Failed",
                                      "error": res.get("error", "solver-failed"),
                                      "audit": res.get("audit", {})})
                return
            st = res["stats"]
            if st.get("mass_error", 1.0) >= 0.25:
                _runs[run_id].update({"status": "Failed",
                                      "error": "mass-error %.3f exceeds 0.25" % st["mass_error"],
                                      "results": {"times": [], "stats": st}})
                return
            (outdir / "stats.json").write_text(json.dumps(st))
            _runs[run_id].update({"status": "Completed", "progress": 100,
                                  "results": {"times": [], "stats": st}})
        except Exception as e:
            _runs[run_id].update({"status": "Failed", "error": "anuga-error: %s" % e})
    threading.Thread(target=bg, daemon=True).start()
    return run_id


def get_run(run_id: str):
    return _runs.get(run_id)


def list_runs(sim_id: str):
    return [r for r in _runs.values() if r["simId"] == sim_id]
