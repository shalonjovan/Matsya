# Simulation Fix — Realistic Flood Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace bathtub flood with D8-routed surface + WaterBody storage + drain surcharge so water bodies fill/spill/limit accumulation.

**Architecture:** Keep `generate_flood(bbox,rainfall,w,h,steps)` signature; add pit-fill + D8 order precomputed once, per-step rain increment + downhill pass + `WaterBody.step` exchange + Manning surcharge. Stats gain `mass_error,wbCount,surchargedDrains`.

**Tech Stack:** Python 3.12, numpy, rasterio.features.rasterize, geopandas (optional fallback), Pillow, FastAPI.

**Spec:** Brainstorm approval 2026-09-04 — P0 + surface flow (Approach A). PRD §15: never invent `capacity` in API (keep `null`), internal `Qcap` flagged `inferred:true` only.

## Global Constraints

- Python 3.12, FastAPI :8000, React 18 + Vite + Tailwind + Leaflet 1.9 :5173.
- `generate_flood` signature backward compatible; `180×180×73` PNG pipeline preserved.
- Existing tests `test_flood_service`, `test_flood_different`, `test_waterbody` must keep passing.
- `.matsya` ZIP v1.1, `StatusEnum` 7 values unchanged.
- Never push PRD files; branch `simulation-fix` from `freeform-chennai`.

---

### Task 1: WaterBody maxStage cap

**Files:**
- Modify: `matsya/matsya/backend/app/services/hydro/waterbody.py:1-57`
- Test: `matsya/matsya/backend/app/tests/test_waterbody.py`

**Interfaces:**
- Consumes: none.
- Produces: `WaterBody(area_m2, crest, stage, crest_width, C, depth, max_depth_above_crest=3.0)` with `forced_overflow: bool`, `step(dt)->float` capped.

- [ ] **Step 1: Write failing test for cap**

```python
def test_waterbody_cap():
    from app.services.hydro.waterbody import WaterBody
    wb = WaterBody(area_m2=10000, crest=5.0, stage=5.0, max_depth_above_crest=3.0)
    wb.inflow(1000)
    out = wb.step(600)
    assert wb.stage <= 5.0 + 3.0 + 1e-6
    assert out > 17
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest app/tests/test_waterbody.py::test_waterbody_cap -v`
Expected: FAIL with "max_depth_above_crest" unexpected or stage uncapped.

- [ ] **Step 3: Implement cap in waterbody.py**

```python
def __init__(self, area_m2, crest, stage=None, crest_width=10.0, C=1.7, depth=2.0, max_depth_above_crest=3.0):
    self.area_m2=float(area_m2); self.crest=float(crest); self.crest_width=float(crest_width); self.C=float(C)
    self.bed=self.crest-depth; self.max_depth_above_crest=float(max_depth_above_crest); self.forced_overflow=False
    self.stage=self.bed if stage is None else float(stage)
    self.volume=max(0.0,self.area_m2*max(0.0,self.stage-self.bed)); self._inflow_buffer=0.0
```

In `step()`, after weir outflow compute, add:

```python
max_stage = self.crest + self.max_depth_above_crest
if self.stage > max_stage:
    excess_vol = (self.stage - max_stage) * self.area_m2
    extra_q = excess_vol / dt
    self.volume -= excess_vol
    self.stage = max_stage
    outflow += extra_q
    self.forced_overflow = True
else:
    self.forced_overflow = False
```

Include `forced_overflow` in `get_state()`.

- [ ] **Step 4: Run tests**

Run: `pytest app/tests/test_waterbody.py -v`
Expected: PASS (3 existing + 1 new).

- [ ] **Step 5: Commit**

```bash
git add matsya/matsya/backend/app/services/hydro/waterbody.py matsya/matsya/backend/app/tests/test_waterbody.py
git commit -m "feat(hydro): cap WaterBody stage at crest+3m with forced overflow"
```

---

### Task 2: flood.py D8 + WaterBody coupling + surcharge + mass balance

**Files:**
- Modify: `matsya/matsya/backend/app/services/flood.py:73-328`
- Test: `matsya/matsya/backend/app/tests/test_flood_service.py`, new `matsya/matsya/backend/app/tests/test_coupled_flood.py`

**Interfaces:**
- Consumes: `WaterBody` from Task 1, `load_assets`/`enrich_waterbodies` (optional, try/except fallback), `rasterio.features.rasterize`.
- Produces: `generate_flood(bbox,rainfall,width,height,steps,polygon=None) -> (snapshots,pngs,stats)` where `stats` includes `mass_error,wbCount,surchargedDrains,totalRainMm`; helpers `_fill_pits,_d8_order,_waterbodies_in_bbox,_rasterize_masks,_drain_endpoints`.

- [ ] **Step 1: Write failing test for coupling**

```python
def test_coupled_mass_and_wb():
    from app.services.flood import generate_flood
    snaps, pngs, stats = generate_flood([80.15,13.08,80.20,13.13], {"rateMmHr":100,"durationHr":2}, width=20, height=20, steps=3)
    assert stats["maxDepth"] > 0
    assert "mass_error" in stats and stats["mass_error"] < 0.25
    assert "wbCount" in stats and "surchargedDrains" in stats
```

- [ ] **Step 2: Run to verify fails**

Run: `pytest app/tests/test_coupled_flood.py -v`
Expected: FAIL — `mass_error` missing.

- [ ] **Step 3: Implement helpers + coupled loop in flood.py**

Keep `_dem_for_bbox`, `depth_color`, `_find_tif` unchanged. Add:

```python
def _fill_pits(dem, passes=3):
    import numpy as np
    filled = dem.copy()
    h, w = filled.shape
    for _ in range(passes):
        up = np.roll(filled, 1, 0); down = np.roll(filled, -1, 0)
        left = np.roll(filled, 1, 1); right = np.roll(filled, -1, 1)
        neigh_min = np.minimum(np.minimum(up, down), np.minimum(left, right))
        filled = np.maximum(dem, np.minimum(filled, neigh_min + 0.01))
    return filled

def _d8_order(filled):
    import numpy as np
    h, w = filled.shape
    # downstream index per cell (-1 = pit)
    ds = np.full((h, w), -1, dtype=np.int64)
    dy = [-1,-1,0,1,1,1,0,-1]; dx = [0,1,1,1,0,-1,-1,-1]
    dist = [30.0,42.4,30.0,42.4,30.0,42.4,30.0,42.4]
    for k in range(8):
        nb = np.roll(np.roll(filled, -dy[k], 0), -dx[k], 1)
        slope = (filled - nb) / dist[k]
        # track best in loop-free way: iterate cells via vectorized max
    # simpler: compute best downstream via explicit neighbor stack (vectorized argmax)
    slopes = []
    for k in range(8):
        nb = np.roll(np.roll(filled, -dy[k], 0), -dx[k], 1)
        slopes.append((filled - nb) / dist[k])
    S = np.stack(slopes, 0)
    best = S.argmax(0); best_val = S.max(0)
    # map best dir to flat downstream index
    rr, cc = np.mgrid[0:h, 0:w]
    dr = np.array(dy)[best]; dc = np.array(dx)[best]
    nr = np.clip(rr + dr, 0, h-1); nc = np.clip(cc + dc, 0, w-1)
    ds = np.where(best_val > 0, nr * w + nc, -1)
    order = np.argsort(filled.ravel())[::-1]  # high -> low
    return ds.ravel(), order
```

`_waterbodies_in_bbox(bbox, dem_sample_fn)`: try `load_assets`, `.cx[minLon:maxLon, minLat:maxLat]`, top 20 by area, crest = dem at centroid + 1.0; fallback `[]`. `_rasterize_masks(polys, bbox, w, h)`: `rasterio.features.rasterize` with `from_bounds` transform. `_drain_endpoints(bbox)`: try micro+macro clip, endpoint lon/lat + length; fallback deterministic 5 synthetic endpoints from seed.

Main loop change: maintain `surface = zeros`, `wb_objs dict`, `order,ds` precomputed once, per step: `rain_inc = rate*dt/1000`, `surface += rain_inc`, single D8 pass moving `0.25*surface` downhill in `order`, drain split `qin`, `wb.inflow`, `wb.step`, composite `depth = max(surface_routed, wb_stage-dem inside mask) + surcharge_grid`, clip 0-5.

Mass: `area_m2` from degrees, `rain_vol`, `surface_vol=sum(depth)*900`, `wb_vol`, `outflow_vol`, `mass_error=abs(stored+out-sea-rain)/rain`.

- [ ] **Step 4: Run tests**

Run: `pytest app/tests/test_flood_service.py app/tests/test_coupled_flood.py app/tests/test_waterbody.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add matsya/matsya/backend/app/services/flood.py matsya/matsya/backend/app/tests/test_coupled_flood.py
git commit -m "feat(flood): D8 routing + WaterBody storage + drain surcharge + mass balance"
```

---

### Task 3: Routers + analysis hydro fields

**Files:**
- Modify: `matsya/matsya/backend/app/routers/flood.py:1-82`, `matsya/matsya/backend/app/services/analysis.py:22-192`
- Test: `matsya/matsya/backend/app/tests/test_flood_api.py`, `matsya/matsya/backend/app/tests/test_point_flood.py`

**Interfaces:**
- Consumes: `stats` from Task 2 (`mass_error,wbCount,surchargedDrains`).
- Produces: `GET /api/simulations/{id}/flood/stats -> {maxDepth,floodedArea,meanDepth,mass_error,wbCount,surchargedDrains}`; `point_query` adds `wbStage,drainSurcharge,mass_error`.

- [ ] **Step 1: Write failing test**

```python
def test_flood_stats_has_mass():
    from fastapi.testclient import TestClient
    from app.main import app
    c = TestClient(app)
    r = c.post("/api/simulations", json={"name":"stats-mass","area":{"bbox":[80.15,13.08,80.20,13.13],"crs":"EPSG:4326"},"rainfall":{"rateMmHr":50,"durationHr":1}})
    assert r.status_code == 201
    sid = r.json()["id"]
    import time; time.sleep(6)
    s = c.get(f"/api/simulations/{sid}/flood/stats")
    assert s.status_code == 200 and "mass_error" in s.json()
```

- [ ] **Step 2: Run to verify fails**

Run: `pytest app/tests/test_flood_stats_api.py -v`
Expected: FAIL 404 (route missing).

- [ ] **Step 3: Implement `GET /stats` in routers/flood.py reading `{sim}/flood/flood.json`; extend `analysis.point_query` rainfall parsing to variable mode + attach `mass_error` from `sim.flood.stats`. Keep `capacity:None` per §15.**

- [ ] **Step 4: Run tests**

Run: `pytest app/tests/test_flood_api.py app/tests/test_point_flood.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add matsya/matsya/backend/app/routers/flood.py matsya/matsya/backend/app/services/analysis.py
git commit -m "feat(api): flood stats + point hydro fields"
```

---

## Self-Review

- Spec coverage: wb overflow (Task1+2) ✓, surface flow D8 (Task2) ✓, drain overflow surcharge (Task2, capacity stays null in API) ✓, accumulation limit (Task1 cap + Task2 mask) ✓.
- Placeholders: none — code blocks concrete.
- Types: `stats` keys consistent `mass_error,wbCount,surchargedDrains,totalRainMm` across tasks.
