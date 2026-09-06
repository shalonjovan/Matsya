"""Tutorial-grade ANUGA puddle on real Chennai DEM (Phase 1 — not the product path).

Runs the solver in the isolated py3.11 venv as a subprocess. Uses ONLY the
API mapped in Phase 0 (rectangular_cross_domain, set_quantity,
Reflective_boundary, Rate_operator, evolve, quantities[].centroid_values).
"""
import json
import os
import pathlib
import subprocess
import tempfile

DEFAULT_ANUGA_PYTHON = os.path.expanduser("~/.venvs/matsya-anuga/bin/python")

DRIVER = r'''
import json, os, sys
import numpy as np
import anuga
from anuga import rectangular_cross_domain, Reflective_boundary
from anuga.operators.rate_operators import Rate_operator

workdir, grid_npy, meta_json, rain_mmhr, minutes, manning = sys.argv[1:7]
rain_mmhr, minutes, manning = float(rain_mmhr), float(minutes), float(manning)
meta = json.load(open(meta_json))
g = np.load(grid_npy)  # (rows, cols) elevation, meters MSL; may contain nan
rows, cols = g.shape
# local meters, origin bottom-left; row 0 of the array is the north edge
dx_m, dy_m = meta["dx_m"], meta["dy_m"]
Lx, Ly = cols * dx_m, rows * dy_m
finite = np.isfinite(g)
fill = float(np.nanmean(g)) if finite.any() else 5.0

def elev(x, y):
    xa, ya = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    c = np.clip((xa / dx_m).astype(int), 0, cols - 1)
    r = np.clip(((Ly - ya) / dy_m).astype(int), 0, rows - 1)
    v = g[r, c]
    return np.where(np.isfinite(v), v, fill)

Lx, Ly = cols * dx_m, rows * dy_m
n = 40
domain = rectangular_cross_domain(n, n, len1=Lx, len2=Ly)
domain.set_name("puddle")
domain.set_datadir(workdir)
domain.store = False
domain.set_quantity("elevation", elev)
domain.set_quantity("friction", manning)
domain.set_quantity("stage", float(np.nanmin(g)) - 0.5 if finite.any() else 0.0)
Br = Reflective_boundary(domain)
domain.set_boundary({"left": Br, "right": Br, "top": Br, "bottom": Br})
Rate_operator(domain, rate=rain_mmhr / 1000.0 / 3600.0)

minutes = max(5.0, minutes)
for t in domain.evolve(yieldstep=300, finaltime=minutes * 60.0):
    pass
stage = np.asarray(domain.quantities["stage"].centroid_values)
ev = np.asarray(domain.quantities["elevation"].centroid_values)
depth = np.maximum(0.0, stage - ev)
print("RESULT max_depth_m=%.4f wet_fraction=%.3f ncells=%d" % (
    float(depth.max()), float((depth > 0.01).mean()), depth.size))
np.save(os.path.join(workdir, "depths.npy"), depth)
'''


def _anuga_python():
    p = os.environ.get("ANUGA_PYTHON", DEFAULT_ANUGA_PYTHON)
    if p and os.path.isfile(p) and os.access(p, os.X_OK):
        return p
    return None


def _clip_dem_patch(bbox, size_m=500.0):
    """Clip CartoDEM around bbox center. Returns (grid, meta). Raises on failure."""
    import numpy as np
    import rasterio
    from rasterio.windows import from_bounds
    from rasterio.enums import Resampling
    tif = None
    for cand in (pathlib.Path("assets/CartoDEM_30m_Chennai_EGM96_MSL.tif"),
                 pathlib.Path("/app/assets/CartoDEM_30m_Chennai_EGM96_MSL.tif")):
        if cand.exists():
            tif = cand
            break
    if tif is None:
        # resolve like flood.py: search parents for assets/
        here = pathlib.Path(__file__).resolve()
        for _ in range(8):
            cand = here / "assets" / "CartoDEM_30m_Chennai_EGM96_MSL.tif"
            if cand.exists():
                tif = cand
                break
            here = here.parent
    if tif is None:
        raise FileNotFoundError("CartoDEM TIF not found")
    minLon, minLat, maxLon, maxLat = bbox
    cx, cy = (minLon + maxLon) / 2.0, (minLat + maxLat) / 2.0
    import math
    m_per_deg = 111320.0 * math.cos(math.radians(cy))
    m_per_lat = 110540.0
    dlon = size_m / m_per_deg
    dlat = size_m / m_per_lat
    with rasterio.open(tif) as src:
        win = from_bounds(cx - dlon / 2, cy - dlat / 2, cx + dlon / 2, cy + dlat / 2, src.transform)
        arr = src.read(1, window=win, boundless=True, fill_value=float("nan")).astype(float)
        if src.nodata is not None:
            arr = np.where(arr == src.nodata, np.nan, arr)
        arr = np.where(arr < 0, np.nan, arr)
        t = src.window_transform(win)
        # pixel size in METERS (source may be geographic degrees)
        if src.crs and src.crs.is_projected:
            dx_m, dy_m = abs(t.a), abs(t.e)
        else:
            dx_m, dy_m = abs(t.a) * m_per_deg, abs(t.e) * m_per_lat
    if not np.isfinite(arr).any():
        raise ValueError("DEM patch has no valid cells")
    return arr, {"dx_m": float(dx_m), "dy_m": float(dy_m)}


def run_puddle(bbox, rain_mmhr=50.0, minutes=30, manning=0.035, timeout=600):
    """Rain onto a 500m Chennai DEM patch. Returns {solved, max_depth_m, wet_fraction, ...}."""
    py = _anuga_python()
    if py is None:
        return {"solved": False, "error": "anuga-unavailable: set ANUGA_PYTHON to a python with anuga installed"}
    try:
        grid, meta = _clip_dem_patch(list(bbox))
    except Exception as e:
        return {"solved": False, "error": "dem-clip-failed: %s" % e}
    tmp = tempfile.mkdtemp(prefix="anuga-puddle-")
    try:
        grid_path = str(pathlib.Path(tmp) / "elev.npy")
        meta_path = str(pathlib.Path(tmp) / "meta.json")
        import numpy as np
        np.save(grid_path, grid)
        pathlib.Path(meta_path).write_text(json.dumps(meta))
        drv = str(pathlib.Path(tmp) / "driver.py")
        pathlib.Path(drv).write_text(DRIVER)
        proc = subprocess.run([py, drv, tmp, grid_path, meta_path,
                               str(rain_mmhr), str(minutes), str(manning)],
                              capture_output=True, text=True, timeout=timeout)
        out = (proc.stdout or "") + (proc.stderr or "")
        import re
        m = re.search(r"RESULT max_depth_m=([0-9.\-eE]+) wet_fraction=([0-9.\-eE]+) ncells=(\d+)", out)
        if proc.returncode != 0 or not m:
            return {"solved": False, "error": "solver-failed rc=%s tail=%s" % (proc.returncode, out[-500:])}
        return {"solved": True, "max_depth_m": float(m.group(1)),
                "wet_fraction": float(m.group(2)), "ncells": int(m.group(3)),
                "depths_npy": str(pathlib.Path(tmp) / "depths.npy")}
    except subprocess.TimeoutExpired:
        return {"solved": False, "error": "solver-timeout after %ss" % timeout}
    except Exception as e:
        return {"solved": False, "error": "runner-error: %s" % e}
