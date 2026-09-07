# Rain Fixes Implementation Plan (4 fixes, 5 phases)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the stuck processing overlay, scope zone drawing to the sim domain, add per-zone variable hyetographs, and add base/zones rainfall source toggles — each phase independently committable, no merge to main.

**Architecture:** Frontend-first for the overlay and domain marking (both are UI-state bugs); backend extends the existing zone pipeline (`parse_zones` → `zone_rate_steps` → gridded paint / SWMM regimes) with variable curves reusing `rainfall_curve.interpolate`; source toggles are two booleans threaded through flood, SWMM, and analysis with backward-compatible defaults.

**Tech Stack:** FastAPI + pytest (backend), React 18 + Vite + Leaflet + leaflet-draw + vitest (frontend).

**Spec:** This document is the spec (bounded fixes; user pre-authorized implementation after planning).

## Global Constraints

- Branch: `variable-rain`. Do NOT merge to main until the user says so.
- Backend zoneless output must stay bit-identical (`test_zoneless_output_identical`, SWMM golden tests).
- Zone cap stays 12 (`MAX_ZONES`, `MAX_RAIN_ZONES`, pydantic `check_zones` — do not raise).
- Canonical zone amount key is `"amount"` (never `amountMm`); geometry passes through as a full GeoJSON Polygon dict.
- One commit per phase; commit message exact text given per phase.
- Backend uvicorn runs WITHOUT `--reload` — restart it after backend edits (`pkill -f 'uvicorn app.main'` then relaunch, or `kill <pid>`). Frontend Vite HMR picks up edits automatically.
- TDD: RED test first, stash-verify it fails for the right reason, then GREEN. Update an existing test only when its API contract deliberately changes (note the reason inline).

**Server processes (review stack, leave running):**
- Backend: `python -m uvicorn app.main:app --host 0.0.0.0 --port 8000`, cwd `matsya/matsya/backend`, log `/tmp/opencode/matsya-backend.log`
- Frontend: `npx vite --port 5173`, cwd `matsya/matsya/frontend`, log `/tmp/opencode/matsya-frontend.log`

---

## Phase 1: Processing overlay strands on settled sims (fix #1)

**Root cause (proven, not guessed):** `MapView.tsx` shows `#processing-overlay` when `status === "Running" || !elevation?.stats || !flood?.stats`, and the 1.5s poll only dismisses when **both** stats exist. Store evidence: sim `7dee2ffe` ("stale") is `Completed` with `elevation: null` — `_bg_gen` marks Completed even when `ensure_elevation` fails, so the dismiss condition can never become true. The 30s `setTimeout(clearInterval)` then strands the overlay permanently with no recovery path. The screenshot (flood visibly rendered behind the spinner) matches this state exactly.

**Files:**
- Modify: `matsya/matsya/frontend/src/components/MapView.tsx` (overlay condition ~line 62, poll loop ~lines 73-97)
- Test: `matsya/matsya/frontend/src/tests/MapView.test.tsx` (append new tests)

**Interfaces:**
- Consumes: sim JSON shape `{id, status, elevation: {stats} | null, flood: {stats} | null}` (unchanged)
- Produces: `needsProcessing` rule + warning-chip state (internal to MapView; no external API change)

- [ ] **Step 1: Write failing tests** — append to `MapView.test.tsx`:

```tsx
it("does not strand the overlay on Completed sims with partial data", async ()=>{
  const sim:any={id:"9", status:"Completed",
    area:{bbox:[80.15,13.08,80.20,13.13]},
    elevation:null, flood:{floodUri:"/api/simulations/9/flood?time=0", stats:{maxDepth:0.5}}}
  global.fetch = vi.fn((url)=>{
    if(String(url).includes("/api/simulations/9") && !String(url).includes("/flood"))
      return Promise.resolve({ok:true, json:()=>Promise.resolve(sim)} as any)
    return Promise.resolve({ok:true, json:()=>Promise.resolve({drains:{features:[]}, waterbodies:{features:[]}})} as any)
  }) as any
  const {container}=render(<MapView simulation={sim} time={0} />)
  await waitFor(()=> expect(container.querySelector("#processing-overlay")).not.toBeInTheDocument(), {timeout:5000})
})

it("shows the overlay while Running and clears it when data arrives", async ()=>{
  let pollCount = 0
  const running:any={id:"8", status:"Running", area:{bbox:[80.15,13.08,80.20,13.13]}, elevation:null, flood:null}
  const done:any={id:"8", status:"Completed", area:{bbox:[80.15,13.08,80.20,13.13]},
    elevation:{elevationUri:"/e", stats:{mean:5}}, flood:{floodUri:"/f", stats:{maxDepth:0.5}}}
  global.fetch = vi.fn((url)=>{
    if(String(url).includes("/api/simulations/8") && !String(url).includes("/flood")){
      pollCount++
      return Promise.resolve({ok:true, json:()=>Promise.resolve(pollCount < 2 ? running : done)} as any)
    }
    return Promise.resolve({ok:true, json:()=>Promise.resolve({drains:{features:[]}, waterbodies:{features:[]}})} as any)
  }) as any
  const {container}=render(<MapView simulation={running} time={0} />)
  await waitFor(()=> expect(container.querySelector("#processing-overlay")).toBeInTheDocument(), {timeout:5000})
  await waitFor(()=> expect(container.querySelector("#processing-overlay")).not.toBeInTheDocument(), {timeout:10000})
})
```

- [ ] **Step 2: Run to verify they fail** — `npx vitest run src/tests/MapView.test.tsx` in `matsya/matsya/frontend`. Expected: first test FAILs (overlay present), second passes (current code handles this path).
- [ ] **Step 3: Implement** — in `MapView.tsx`, replace the `isProcessing` computation:

```tsx
const hasData = !!(simulation as any)?.elevation?.stats && !!(simulation as any)?.flood?.stats
const isSettled = ["Completed", "Error"].includes((simulation as any)?.status)
const needsProcessing = !hasData && !isSettled
```

Gate overlay creation on `needsProcessing` (not `isProcessing`). In the poll callback, dismiss when `!!(sim.elevation?.stats && sim.flood?.stats) || ["Completed","Error"].includes(sim.status)`; when dismissing with missing data, set a warning state instead of silently succeeding:

```tsx
const [dataWarn, setDataWarn] = useState<string | null>(null)
// on dismiss with gaps:
const missing = [!sim.elevation?.stats && "elevation", !sim.flood?.stats && "flood"].filter(Boolean)
if (missing.length) setDataWarn(`${missing.join(" + ")} unavailable — showing available layers`)
```

On 30s timeout: dismiss overlay AND set `dataWarn` to `"Still processing — showing available layers"` (never strand the spinner). Render the warning as a dismissible amber chip (absolute top-center, `z-[500]`, × button clears `dataWarn`). Keep the existing flood/terrain overlay update block inside the dismiss path unchanged.

- [ ] **Step 4: Run tests** — `npx vitest run src/tests/MapView.test.tsx` → all PASS. Then `npx vitest run` (full frontend) → 30+ PASS.
- [ ] **Step 5: Manual verify** — open `http://localhost:5173`, select the "stale" sim (or any Completed sim): no spinner, warning chip only if data missing. Fresh sim: spinner shows, clears on completion.
- [ ] **Step 6: Commit** — `git add matsya/matsya/frontend/src/components/MapView.tsx matsya/matsya/frontend/src/tests/MapView.test.tsx && git commit -m "fix(map): dismiss processing overlay for settled sims with partial data"`

---

## Phase 2: Simulation-domain marking on the zone draw map (fix #2)

**Files:**
- Modify: `matsya/matsya/frontend/src/components/ZoneRain.tsx` (map init effect, CREATED handler)
- Test: `matsya/matsya/frontend/src/tests/ZoneRain.test.tsx` (append helper tests)

**Interfaces:**
- Consumes: `bbox` prop (already passed), `ZONE_PALETTE` (already imported)
- Produces: `polygonIntersectsBbox(polygon, bbox) => boolean` (exported pure helper)

- [ ] **Step 1: Write failing tests** — helper does not exist yet:

```tsx
import { polygonIntersectsBbox } from "../components/ZoneRain"
const BBOX: [number,number,number,number] = [80.15, 13.08, 80.20, 13.13]
const inside = { type: "Polygon", coordinates: [[[80.16,13.09],[80.17,13.09],[80.17,13.10],[80.16,13.10],[80.16,13.09]]] }
const outside = { type: "Polygon", coordinates: [[[80.30,13.30],[80.31,13.30],[80.31,13.31],[80.30,13.31],[80.30,13.30]]] }
// straddles the east edge: vertices outside, crosses the bbox
const straddle = { type: "Polygon", coordinates: [[[80.19,13.09],[80.25,13.09],[80.25,13.10],[80.19,13.10],[80.19,13.09]]] }
// bbox corner inside polygon, no polygon vertex inside bbox
const engulf = { type: "Polygon", coordinates: [[[80.10,13.00],[80.30,13.00],[80.30,13.20],[80.10,13.20],[80.10,13.00]]] }

it("classifies inside/straddle/engulf as intersecting, outside as not", ()=>{
  expect(polygonIntersectsBbox(inside, BBOX)).toBe(true)
  expect(polygonIntersectsBbox(straddle, BBOX)).toBe(true)
  expect(polygonIntersectsBbox(engulf, BBOX)).toBe(true)
  expect(polygonIntersectsBbox(outside, BBOX)).toBe(false)
  expect(polygonIntersectsBbox(null, BBOX)).toBe(false)
})
```

- [ ] **Step 2: Run to verify it fails** — import error, 0 tests collected.
- [ ] **Step 3: Implement helper** — vertex-in-bbox OR bbox-corner-in-polygon (ray cast) OR segment intersection (orientation test). ~45 lines, no dependencies.
- [ ] **Step 4: Domain marking + guard in the map effect** — after tile layer, before draw control:

```tsx
try {
  ;(L as any).rectangle([[minLat, minLon], [maxLat, maxLon]], {
    color: "#06b6d4", weight: 2, dashArray: "6, 6", fill: false, interactive: false,
  }).addTo(map).bindTooltip("Simulation domain", { sticky: true })
} catch {}
```

In the CREATED handler, after `toGeoJSON`, before `buildZone`:

```tsx
if (!polygonIntersectsBbox(gj, bbox)) {
  setDrawError("Region is outside the simulation domain (cyan box) — draw inside it.")
  drawn.clearLayers()
  return
}
```

Update the section hint text to mention the cyan domain box. Backend already clips via rasterize grid bounds, so this is a UX guard, not a physics change.
- [ ] **Step 5: Run tests** — `npx vitest run src/tests/ZoneRain.test.tsx` → all PASS (old + new); full `npx vitest run` → PASS.
- [ ] **Step 6: Commit** — `git add matsya/matsya/frontend/src/components/ZoneRain.tsx matsya/matsya/frontend/src/tests/ZoneRain.test.tsx && git commit -m "feat(zones): show simulation domain on zone map, reject outside regions"`

---

## Phase 3: Per-zone advanced (variable) rainfall — backend (fix #3a)

**Files:**
- Modify: `matsya/matsya/backend/app/models/simulation.py` (doc comment only — zones stay `list[dict]`, validator stays count-only; strict per-zone validation lives in `parse_zones` so old clients never 422)
- Modify: `matsya/matsya/backend/app/services/rainfall_zones.py` (parse variable fields, add `zone_step_rates`)
- Modify: `matsya/matsya/backend/app/services/flood.py` (`zone_rates` scalar list → `zone_rate_steps` matrix)
- Modify: `matsya/matsya/backend/app/services/engine/swmm_inp.py` (`_zone_regimes` variable branch)
- Test: `matsya/matsya/backend/app/tests/test_rainfall_zones.py`, `matsya/matsya/backend/app/tests/test_swmm_zones.py` (append)

**Zone variable contract (mirrors top-level variable rainfall):** `{id, mode: "variable", points: [{time, amount}...] (≥2, finite), totalTime (>0), maxRain (≥0), unit: "rate"|"total", polygon}`. Constant zones unchanged (`{id, amount, unit, polygon}`, no `mode` or `mode: "constant"`).

**Interfaces:**
- Consumes: `rainfall_curve.interpolate(points, totalTime, maxRain, unit, steps) -> {"values": [...]}` (existing)
- Produces: `zone_step_rates(zone, steps, duration_hr) -> list[float]` (mm/hr per flood step); stats zone entries gain `mode`, `peakMmHr`

- [ ] **Step 1: Write failing tests** — append to `test_rainfall_zones.py`:

```python
def test_variable_zone_parses_and_integrates():
    import numpy as np
    from app.services.flood import generate_flood
    poly_w = {"type": "Polygon", "coordinates": [[[80.15, 13.08], [80.175, 13.08], [80.175, 13.13], [80.15, 13.13], [80.15, 13.08]]]}
    rf = {"rateMmHr": 10, "durationHr": 1, "zones": [
        {"id": "wb", "mode": "variable", "unit": "rate", "totalTime": 1, "maxRain": 200,
         "points": [{"time": 0, "amount": 0}, {"time": 0.5, "amount": 200}, {"time": 1, "amount": 0}],
         "polygon": poly_w}]}
    kw = dict(width=20, height=20, steps=6)
    snaps, _, st = generate_flood([80.15, 13.08, 80.20, 13.13], rf, **kw)
    base, _, _ = generate_flood([80.15, 13.08, 80.20, 13.13], {"rateMmHr": 10, "durationHr": 1}, **kw)
    last, lastb = np.asarray(snaps[-1]), np.asarray(base[-1])
    assert last[:, :10].mean() > lastb[:, :10].mean() * 2.0
    assert st["mass_error"] < 0.25
    z = next(z for z in st["zones"] if z["id"] == "wb")
    assert z["mode"] == "variable" and z["peakMmHr"] > z["rateMmHr"] > 0

def test_variable_zone_invalid_points_dropped():
    from app.services.rainfall_zones import parse_zones
    poly = {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]}
    rf = {"rateMmHr": 10, "durationHr": 1, "zones": [
        {"id": "bad", "mode": "variable", "points": [{"time": 0, "amount": 5}], "polygon": poly}]}
    zones, dropped = parse_zones(rf)
    assert zones == [] and dropped == ["bad"]
```

Append to `test_swmm_zones.py`:

```python
def test_variable_zone_regime_is_time_varying(tmp_path):
    from app.services.engine.swmm_inp import build_inp
    poly = {"type": "Polygon", "coordinates": [[[80.15, 13.08], [80.175, 13.08], [80.175, 13.13], [80.15, 13.13], [80.15, 13.08]]]}
    drains = [{"id": "DW", "length_m": 100.0, "slope": 0.01, "z0": 10.0, "z1": 9.0,
               "x0": 80.16, "y0": 13.10, "x1": 80.161, "y1": 13.101}]
    rf = {"rateMmHr": 10, "durationHr": 1, "zones": [
        {"id": "wb", "mode": "variable", "unit": "rate", "totalTime": 1, "maxRain": 200,
         "points": [{"time": 0, "amount": 0}, {"time": 0.5, "amount": 200}, {"time": 1, "amount": 0}],
         "polygon": poly}]}
    text = open(build_inp(drains, rf, [80.15, 13.08, 80.20, 13.13], str(tmp_path / "zv.inp"))).read()
    rows = [l for l in text.splitlines() if l.startswith("RAIN_Z0")]
    vals = [float(l.split()[-1]) for l in rows]
    assert len(set(round(v, 1) for v in vals)) > 2 and max(vals) > 100
```

- [ ] **Step 2: Run to verify they fail** — `KeyError`/assertion (no variable support): `zone_step_rates` missing, `mode` never parsed (dropped or treated constant).
- [ ] **Step 3: Implement `rainfall_zones.py`** — in `parse_zones`, branch on `z.get("mode") == "variable"`: validate points (list ≥2, each finite time/amount), `totalTime > 0`, `maxRain >= 0`, `unit in ("rate","total")`, polygon as today; store `{id, mode:"variable", points, totalTime, maxRain, unit, polygon}`; invalid → dropped. Add:

```python
def zone_step_rates(zone, steps, duration_hr):
    """mm/hr per flood step. Constant: flat (total spread over duration). Variable: interpolated curve padded/truncated to steps."""
    import numpy as np  # noqa (kept for symmetry; not strictly needed)
    n = max(1, int(steps))
    if (zone or {}).get("mode") == "variable":
        from app.services.rainfall_curve import interpolate
        try:
            res = interpolate(zone["points"], totalTime=zone["totalTime"], maxRain=zone["maxRain"], unit=zone.get("unit", "rate"), steps=n)
            vals = [float(v) for v in list(res["values"])[:n]]
            while len(vals) < n:
                vals.append(vals[-1] if vals else 0.0)
            return vals
        except Exception:
            return [0.0] * n
    try:
        dur = max(1e-9, float(duration_hr or 1.0))
        r = float(zone.get("amount", 0.0)) if str(zone.get("unit", "rate")) == "rate" else float(zone.get("amount", 0.0)) / dur
    except Exception:
        r = 0.0
    return [r] * n
```

- [ ] **Step 4: Implement `flood.py`** — replace the `zone_rates` scalar build with `zone_rate_steps = [zone_step_rates(z, steps, duration) for z in zone_list]` (import inside function as today). Per-step paint loop becomes `rate_grid[_zm] = float(zone_rate_steps[_zi][i])` (iterate `enumerate(zip(zone_masks, zone_rate_steps))`). Stats: `rateMmHr` = mean of steps, add `mode` (default `"constant"`) and `peakMmHr` = max. Keep the zoneless path byte-identical (all new code inside `if has_zones`).
- [ ] **Step 5: Implement `swmm_inp.py`** — in `_zone_regimes`, branch per zone: variable → `vals = zone_step_rates(...)`? NO — SWMM needs its own clock: `res = interpolate(points, totalTime=zone.totalTime, maxRain, unit, steps=max(12, int(totalTime*12)))`, then `series = [(i*Tv/max(1,len-1), v) for i,v in enumerate(vals)]` with `Tv = zone.totalTime`, stamped by existing `_stamp_lines`. Constant → flat as today. `end_h` stays base-driven.
- [ ] **Step 6: Run tests** — new tests PASS; full zone files PASS; regression `test_flood_service test_coupled_flood test_point_flood test_simulation_rainfall test_rainfall_curve test_swmm_inp test_swmm_runner` PASS. Restart backend, smoke `totalRainMm`/zones via API.
- [ ] **Step 7: Commit** — `git add matsya/matsya/backend/app/services/rainfall_zones.py matsya/matsya/backend/app/services/flood.py matsya/matsya/backend/app/services/engine/swmm_inp.py matsya/matsya/backend/app/tests/test_rainfall_zones.py matsya/matsya/backend/app/tests/test_swmm_zones.py && git commit -m "feat(rain): per-zone variable hyetographs in flood and SWMM"`

---

## Phase 4: Per-zone advanced rainfall — UI (fix #3b)

**Files:**
- Modify: `matsya/matsya/frontend/src/components/ZoneRain.tsx` (entry mode tabs, curve inputs, list labels, `buildZone` signature)
- Test: `matsya/matsya/frontend/src/tests/ZoneRain.test.tsx` (update + extend)

**Interfaces:**
- Consumes: `RainfallGraph` (`{totalTime, maxRain, unit, points, onChange}` — existing), `RainfallZone` type (extended with optional `mode/points/totalTime/maxRain`; update `types/simulation.ts` in this phase)
- Produces: zone objects with either constant or variable payload (backend Phase 3 contract)

- [ ] **Step 1: Update tests first** — `buildZone` new signature `buildZone(spec, existing)` where `spec = {kind, amount?, unit?, points?, totalTime?, maxRain?, polygon}`. Rewrite the three `buildZone` tests to the spec form and add: variable spec with 1 point → null; variable spec valid → zone with `mode:"variable"`; list renders "var curve" label. Run → fail (old signature).
- [ ] **Step 2: Implement** — entry tabs `Value | Curve` above amount inputs. Curve mode: totalTime/maxRain/unit inputs + `RainfallGraph` (local points state, default `[{time:0,amount:0},{time:1,amount:100}]`). On CREATED polygon: build from active tab; invalid → `drawError`. `buildZone(spec, existing)`: value branch = current validation; curve branch validates points ≥2 finite, totalTime > 0, maxRain ≥ 0 (mirror backend); id allocation unchanged (smallest free `z{n}`). List label: value → `"200 mm/hr"` / `"60 mm total"`; curve → `"var curve peak {max(points.amount)} {unit}"`. Keep `polygonIntersectsBbox` guard from Phase 2 (applies to both tabs).
- [ ] **Step 3: Update `types/simulation.ts`** — `RainfallZone` gains optional `mode?: "constant"|"variable"; points?: {time:number,amount:number}[]; totalTime?: number; maxRain?: number`.
- [ ] **Step 4: Run** — `npx vitest run src/tests/ZoneRain.test.tsx` PASS; full suite PASS; `npx tsc --noEmit` clean. Manual: draw a curve zone, verify payload in devtools + backend `stats.zones[].mode`.
- [ ] **Step 5: Commit** — `git add matsya/matsya/frontend/src/components/ZoneRain.tsx matsya/matsya/frontend/src/tests/ZoneRain.test.tsx matsya/matsya/frontend/src/types/simulation.ts && git commit -m "feat(zones): per-zone variable hyetograph entry"`

---

## Phase 5: Rainfall source toggles — base vs zones (fix #4)

**Semantics (defaults preserve current behavior):** `rainfall.useBase = true`, `rainfall.useZones = true` when omitted.
- both on (or omitted): today's behavior — base everywhere + zones override.
- `useBase: false` + zones: base rate/curve zeroed outside zones (zones-only storm).
- `useZones: false`: zones stored but ignored — output identical to zoneless request.
- both false: zero rain event — dry run (`totalRainMm` 0; snapshots dry; no div-zero: existing guards cover `dt`, mass denominator, shares fallback).

**Files:**
- Modify: `matsya/matsya/backend/app/models/simulation.py` (`Rainfall` += `useBase: bool = True`, `useZones: bool = True`)
- Modify: `matsya/matsya/backend/app/services/flood.py` (flag parse + base zeroing + effective `has_zones`)
- Modify: `matsya/matsya/backend/app/services/engine/swmm_inp.py` (same flags)
- Modify: `matsya/matsya/backend/app/services/analysis.py` (`rainfallZone` → None when `useZones` false)
- Modify: `matsya/matsya/frontend/src/components/CreateWizard.tsx` (toggles + payload + validation)
- Test: backend `test_rainfall_zones.py`/`test_swmm_zones.py` (append); frontend `CreateWizard.test.tsx` (append)

**Interfaces:**
- Consumes: `parse_zones` output (unchanged), `zone_step_rates` (Phase 3)
- Produces: effective rain = f(useBase, useZones) — documented above

- [ ] **Step 1: Backend failing tests** — append to `test_rainfall_zones.py`:

```python
def test_use_base_false_runs_zones_only():
    import numpy as np
    from app.services.flood import generate_flood
    poly_w = {"type": "Polygon", "coordinates": [[[80.15, 13.08], [80.175, 13.08], [80.175, 13.13], [80.15, 13.13], [80.15, 13.08]]]}
    kw = dict(width=20, height=20, steps=3)
    rf = {"rateMmHr": 10, "durationHr": 1, "useBase": False,
          "zones": [{"id": "w", "amount": 200, "unit": "rate", "polygon": poly_w}]}
    snaps, _, st = generate_flood([80.15, 13.08, 80.20, 13.13], rf, **kw)
    last = np.asarray(snaps[-1])
    assert abs(st["totalRainMm"] - 100.0) < 1.0  # 200mm over half the domain
    assert last[:, 10:].mean() < 0.5  # east gets advected water only (both-on funnels ~1.4m here)

def test_use_zones_false_ignores_zones():
    import numpy as np
    from app.services.flood import generate_flood
    poly_w = {"type": "Polygon", "coordinates": [[[80.15, 13.08], [80.175, 13.08], [80.175, 13.13], [80.15, 13.13], [80.15, 13.08]]]}
    kw = dict(width=20, height=20, steps=3)
    rf = {"rateMmHr": 10, "durationHr": 1, "useZones": False,
          "zones": [{"id": "w", "amount": 200, "unit": "rate", "polygon": poly_w}]}
    s1, _, st1 = generate_flood([80.15, 13.08, 80.20, 13.13], rf, **kw)
    s2, _, st2 = generate_flood([80.15, 13.08, 80.20, 13.13], {"rateMmHr": 10, "durationHr": 1}, **kw)
    assert np.array_equal(np.asarray(s1), np.asarray(s2))
    assert st1["totalRainMm"] == st2["totalRainMm"]

def test_both_sources_off_is_dry():
    import numpy as np
    from app.services.flood import generate_flood
    rf = {"rateMmHr": 10, "durationHr": 1, "useBase": False, "useZones": False, "zones": []}
    snaps, _, st = generate_flood([80.15, 13.08, 80.20, 13.13], rf, width=20, height=20, steps=3)
    assert st["totalRainMm"] == 0.0
    assert float(np.asarray(snaps[-1]).max()) == 0.0
```

- [ ] **Step 2: Run to verify they fail** — flags ignored: `totalRainMm` 105 not 100; zones applied despite `useZones:false`.
- [ ] **Step 3: Implement `flood.py`** — after rainfall parse, read flags (dict or model):

```python
try:
    _rfd = rainfall if isinstance(rainfall, dict) else rainfall.model_dump(mode="json")
except Exception:
    _rfd = {}
use_base = bool((_rfd or {}).get("useBase", True))
use_zones_flag = bool((_rfd or {}).get("useZones", True))
```

Zero the base when disabled (right after `rates`/`total_rain` are derived — set `rates = [0.0]*steps; rate = 0.0; total_rain = 0.0` when `not use_base`; zoned accum adds on top). Effective zones: `has_zones = len(zone_list) > 0 and use_zones_flag` (single-line change at the existing assignment). Both-off flows through existing zero-guards.
- [ ] **Step 4: Implement `swmm_inp.py`** — in `build_inp`: `zone_series, zones = ([], []) if not useZones else _zone_regimes(...)`; base `series = [(t, 0.0) for t,v in series] if not useBase else series`. Read flags from `rainfall` dict with `.get(..., True)` defaults (runner passes dicts; guard non-dict).
- [ ] **Step 5: Implement `analysis.py`** — in the `rainfallZone` block, return None when stored rainfall has `useZones == False`.
- [ ] **Step 6: Backend verify** — new tests PASS; full zone + regression suites PASS; restart backend; API smoke: zoned sim with `useBase:false` shows dry east.
- [ ] **Step 7: Frontend failing tests** — append to `CreateWizard.test.tsx`: toggles render on step 3 defaulting ON (`getByLabelText("Base rainfall")` checked, `getByLabelText("Spatial zones")` checked); unchecking both and submitting shows "Enable at least one rainfall source". (Use `aria-pressed` toggle buttons + `aria-label`; assert `aria-pressed` values.)
- [ ] **Step 8: Implement `CreateWizard.tsx`** — `useBase`/`useZones` state (default true; restore from `editSim?.rainfall`); toggle-button row above `<ZoneRain>`; zones toggle disabled when `zones.length === 0` (title hint "Draw a zone first"); when zones toggle off, hide the `ZoneRain` section (state kept); payload adds `useBase, useZones`; submit validation: `if (!useBase && !useZones) error`. Quick-Run gate includes the same condition.
- [ ] **Step 9: Frontend verify** — new + full suite PASS, tsc clean. Manual: toggle combos, check payload + east-dry result.
- [ ] **Step 10: Commit** — `git add` the six files + `git commit -m "feat(rain): base/zones rainfall source toggles"`

---

## Final regression (end of Phase 5)

- `python -m pytest app/tests/test_rainfall_zones.py app/tests/test_swmm_zones.py app/tests/test_swmm_inp.py app/tests/test_swmm_runner.py app/tests/test_flood_service.py app/tests/test_coupled_flood.py app/tests/test_point_flood.py app/tests/test_simulation_rainfall.py app/tests/test_rainfall_curve.py` (backend, cwd `matsya/matsya/backend`)
- `npx vitest run` + `npx tsc --noEmit` (frontend, cwd `matsya/matsya/frontend`)
- Restart backend + smoke review on :5173. NO merge to main.
