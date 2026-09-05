# Lake Overflow: Spill-Spreading + Initial-Fill % Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make waterbodies visibly overtop onto surrounding land (spilled volume ponds on shore cells instead of vanishing into accounting) and add a per-simulation initial-fill % parameter controlling how full lakes start.

**Architecture:** Two independent changes sharing one verification phase. (1) In `flood.py`'s timestep loop, each waterbody's weir outflow is ponded onto a precomputed 2-cell shoreline ring (falling back to the old count-as-outflow only when the ring is empty), keeping mass closed because ponded water lives in the `surface` array the mass check already measures. (2) A new `parameters.initialFillPct` (default 75 = exact legacy behavior for 2m lakes) flows model → `generate_flood(initial_fill_pct=…)` → `WaterBody` init stage → wizard slider → stats, with `analysis.py` and `coupled_runner.py` kept consistent.

**Tech Stack:** Python 3.12/3.14, numpy, FastAPI, pydantic v2, React 18 + vitest.

**Spec:** User directive 2026-09-06 ("waterbodies don't visibly overflow despite 5m depths; add initial-fill % of capacity; full multi-phase plan then implement; everything must work"). Root-cause analysis in session context: `flood.py:680-683` counts all weir outflow as system outflow while the lift composite (`:701-703`) applies only inside lake masks — spilled water has nowhere to appear on land.

## Global Constraints

- Mass must stay closed: `surface_vol + wb_Δ + sea ≈ rain_vol` with `mass_error < 0.25` on all existing flood tests; ponded spill is storage, never double-counted as outflow.
- `generate_flood` signature stays backward compatible (new kwargs have defaults); `analysis.py:138` and `ensure_flood` call sites updated to pass the fill %.
- `Parameters.initialFillPct` default `75.0` with `ge=0, le=100`; legacy 2m-lake behavior is bit-identical (0.75 × 2.0m = 1.5m above bed = crest−0.5).
- 5m display clip unchanged; `RainfallGraph` viewBox and all `data-testid`s unchanged.
- Frontend: no new dependencies; dark-theme classes match the ui-refresh system.
- Commit per phase; push only when user says merge.

---

### Phase 1: Spill spreading (pond weir outflow on shoreline ring)

**Files:**
- Modify: `matsya/matsya/backend/app/services/flood.py` (helpers + timestep loop + stats)
- Test: `matsya/matsya/backend/app/tests/test_coupled_flood.py` (append; no new file)

**Interfaces:**
- Consumes: `wb_masks` list (bool arrays or None, aligned with `wb_infos`/`wb_objs`), `cell_area`, `surface`.
- Produces: `_spill_ring(mask, radius=2) -> bool array | None`; `_pond_volume(surface, ring, vol_m3, cell_area) -> float added_depth_mean`; stats keys `spillVolumeM3: float`, `overtoppedLakes: int`. Phase 3 consumes the stats keys.

- [ ] **Step 1: Write the failing tests** (append to `test_coupled_flood.py`)

```python
def test_spill_ring_shape():
    import numpy as np
    from app.services.flood import _spill_ring
    m = np.zeros((10, 10), dtype=bool); m[4:6, 4:6] = True
    ring = _spill_ring(m, radius=1)
    assert ring is not None and ring.dtype == bool
    assert not np.any(ring & m)          # ring never overlaps the lake
    assert ring.sum() > 0                # shoreline exists
    assert _spill_ring(np.zeros((5, 5), dtype=bool)) is None  # empty mask -> None

def test_pond_volume_adds_depth():
    import numpy as np
    from app.services.flood import _pond_volume
    s = np.zeros((10, 10)); ring = np.zeros((10, 10), dtype=bool); ring[0, 0:4] = True
    mean_d = _pond_volume(s, ring, 3600.0, 900.0)   # 3600 m3 over 4 cells of 900 m2
    assert abs(mean_d - 1.0) < 1e-9
    assert abs(s[0, 0] - 1.0) < 1e-9 and s[5, 5] == 0.0

def test_heavy_rain_spills_and_stays_balanced():
    from app.services.flood import generate_flood
    _, _, stats = generate_flood([80.15, 13.08, 80.20, 13.13], {"rateMmHr": 200, "durationHr": 3},
                                 width=20, height=20, steps=3)
    assert "spillVolumeM3" in stats and "overtoppedLakes" in stats
    assert stats["spillVolumeM3"] >= 0.0 and stats["mass_error"] < 0.25
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest app/tests/test_coupled_flood.py -v` (from `matsya/matsya/backend/`)
Expected: FAIL with "cannot import name '_spill_ring'" (ImportError on collection).

- [ ] **Step 3: Implement helpers + loop wiring**

Helpers (place directly above `generate_flood`, after `_drain_endpoints`):

```python
def _spill_ring(mask, radius=2):
    """Shoreline ring: cells within `radius` of mask, excluding mask itself."""
    import numpy as np
    m = np.asarray(mask, dtype=bool)
    if not np.any(m):
        return None
    h, w = m.shape
    dilated = m.copy()
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            if dx == 0 and dy == 0:
                continue
            shifted = np.roll(np.roll(m, dy, axis=0), dx, axis=1)
            # kill wraparound rows/cols introduced by roll
            if dy > 0:
                shifted[:dy, :] = False
            elif dy < 0:
                shifted[dy:, :] = False
            if dx > 0:
                shifted[:, :dx] = False
            elif dx < 0:
                shifted[:, dx:] = False
            dilated |= shifted
    ring = dilated & ~m
    return ring if np.any(ring) else None


def _pond_volume(surface, ring, vol_m3, cell_area):
    """Spread vol_m3 evenly over ring cells as depth; returns mean added depth."""
    import numpy as np
    n = int(np.count_nonzero(ring))
    if n == 0 or vol_m3 <= 0 or cell_area <= 0:
        return 0.0
    d = float(vol_m3) / n / float(cell_area)
    surface[ring] += d
    return d
```

Precompute once after `wb_masks` is built (next to `wb_objs = []`):

```python
    wb_rings = []
    try:
        for m in (wb_masks or []):
            wb_rings.append(_spill_ring(m, radius=2) if m is not None else None)
    except Exception:
        wb_rings = [None] * len(wb_objs or [])
    spilled_total = 0.0
    overtopped = set()
```

Replace the wb-step block (currently `out_q = wb.step(dt); total_outflow_vol += ...`):

```python
        for wi, wb in enumerate(wb_objs or []):
            try:
                out_q = wb.step(dt)
                out_vol = float(out_q) * dt
                if out_vol > 0:
                    overtopped.add(wi)
                    ring = wb_rings[wi] if wi < len(wb_rings) else None
                    if ring is not None:
                        _pond_volume(surface, ring, out_vol, cell_area)
                        spilled_total += out_vol
                    else:
                        total_outflow_vol += out_vol  # no shore: legacy count-as-outflow
            except Exception:
                continue
```

Stats dict additions (next to `"surchargedDrains"`):

```python
        "spillVolumeM3": round(float(spilled_total), 1),
        "overtoppedLakes": int(len(overtopped)),
```

Why mass still closes: ponded water accumulates in `surface`, and `surface_vol = sum(surface)*cell_area` already measures it; `wb.step` already removed it from `wb.volume`, so `wb_Δ` excludes it — no double count in either direction.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest app/tests/test_coupled_flood.py app/tests/test_flood_service.py app/tests/test_waterbody.py -v`
Expected: PASS all (existing mass assertions `< 0.25` must hold with ponding active).

- [ ] **Step 5: Commit**

```bash
git add matsya/matsya/backend/app/services/flood.py matsya/matsya/backend/app/tests/test_coupled_flood.py
git commit -m "feat(real-sim): pond lake spill onto shoreline ring instead of vanishing"
```

---

### Phase 2: Initial-fill % parameter end-to-end

**Files:**
- Modify: `matsya/matsya/backend/app/models/simulation.py:85-88` (Parameters)
- Modify: `matsya/matsya/backend/app/services/flood.py` (`generate_flood` signature + creation site + `ensure_flood` extraction)
- Modify: `matsya/matsya/backend/app/services/analysis.py:138` (pass-through)
- Modify: `matsya/matsya/backend/app/services/hydro/coupled_runner.py:58,62` (same fraction)
- Modify: `matsya/matsya/shared/matsya.schema.json` (parameters block)
- Modify: `matsya/matsya/frontend/src/components/CreateWizard.tsx` (state + Step-4 slider + payload + edit-sync)
- Modify: `matsya/matsya/frontend/src/components/PointInspector.tsx` (hydro line: spill + fill)
- Test (backend): `matsya/matsya/backend/app/tests/test_coupled_flood.py` (append)
- Test (frontend): `matsya/matsya/frontend/src/tests/CreateWizard.test.tsx` (append)

**Interfaces:**
- Consumes: Phase 1 stats keys (extended here with nothing new except passthrough).
- Produces: `parameters.initialFillPct: float = 75.0 ∈ [0,100]`; `generate_flood(..., initial_fill_pct=75.0)`; wizard slider `0–100`; stats key passthrough `initialFillPct`; Phase 3 consumes all of these in E2E.

- [ ] **Step 1: Write the failing backend tests** (append to `test_coupled_flood.py`)

```python
def test_initial_fill_zero_starts_empty():
    from app.services.flood import generate_flood
    from app.services.hydro.waterbody import WaterBody
    wb = WaterBody(area_m2=10000, crest=5.0, stage=5.0 - 2.0 + 0.0 * 2.0)  # 0% of 2m
    assert wb.volume == 0.0
    _, _, s = generate_flood([80.15, 13.08, 80.20, 13.13], {"rateMmHr": 50, "durationHr": 1},
                             width=10, height=10, steps=2, initial_fill_pct=0)
    assert s["mass_error"] < 0.25

def test_initial_fill_default_matches_legacy():
    # 75% of a 2m bucket == crest-0.5, the historic hardcode
    from app.services.hydro.waterbody import WaterBody
    wb = WaterBody(area_m2=10000, crest=5.0, stage=(5.0 - 2.0) + 0.75 * 2.0)
    assert abs(wb.stage - 4.5) < 1e-9

def test_initial_fill_hundred_starts_at_brim():
    from app.services.flood import generate_flood
    _, _, s100 = generate_flood([80.15, 13.08, 80.20, 13.13], {"rateMmHr": 5, "durationHr": 1},
                                width=10, height=10, steps=2, initial_fill_pct=100)
    _, _, s0 = generate_flood([80.15, 13.08, 80.20, 13.13], {"rateMmHr": 5, "durationHr": 1},
                              width=10, height=10, steps=2, initial_fill_pct=0)
    assert s100["spillVolumeM3"] >= s0["spillVolumeM3"]
    assert s100["mass_error"] < 0.25 and s0["mass_error"] < 0.25
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest app/tests/test_coupled_flood.py -v`
Expected: FAIL with "got an unexpected keyword argument 'initial_fill_pct'".

- [ ] **Step 3: Backend implementation**

(a) `models/simulation.py`, in `Parameters`:

```python
class Parameters(BaseModel):
    cfl: float | None = None
    dt: float | None = None
    theta: float | None = None
    initialFillPct: float = Field(default=75.0, ge=0.0, le=100.0)
```

Verify no existing test posts `parameters` without the field breaking — defaults fill it, so `model_validate` stays green; confirm by running `test_simulation_model.py` after.

(b) `flood.py`, signature (line 427):

```python
def generate_flood(bbox, rainfall, width=180, height=180, steps=73, polygon=None, initial_fill_pct=75.0):
```

Parse once near `dt` computation:

```python
    try:
        fill_frac = min(1.0, max(0.0, float(initial_fill_pct) / 100.0))
    except Exception:
        fill_frac = 0.75
```

Creation site (currently `WaterBody(area_m2=..., crest=..., stage=info["crest"] - 0.5)`): compute per-info depth FIRST (existing bathy/observed/2.0 logic from the prior commit — keep it, just capture into a local `depth`), then:

```python
                bed = info["crest"] - depth
                stage0 = bed + fill_frac * depth
                wb_objs.append(WaterBody(area_m2=info["area_m2"], crest=info["crest"],
                                         stage=stage0, depth=depth))
```

Find the existing depth computation in that block and reuse its variable (do not recompute differently). Stats dict: add `"initialFillPct": round(fill_frac * 100.0, 1)` next to `"totalRainMm"`.

(c) `ensure_flood` (line ~861 area): extract before the `generate_flood(...)` call:

```python
    try:
        _p = sim.parameters
        _fill = _p.get("initialFillPct", 75.0) if isinstance(_p, dict) else getattr(_p, "initialFillPct", 75.0)
    except Exception:
        _fill = 75.0
```

and pass `initial_fill_pct=_fill`. Mirror the same extraction in `analysis.py` around line 138 (it has `sim` in scope; rainfall is already extracted there — add `_fill` the same way and pass it).

(d) `coupled_runner.py:58,62`: `stage=crest-0.5` → accept the same fraction. Minimal edit honoring dead-code status: add module-level `DEFAULT_FILL_FRac = 0.75` — no, keep it truly minimal: change `stage=crest-0.5` to `stage=crest-2.0+0.75*2.0`? That is identical math and self-documents the fraction. Do exactly that (one-line each, comment `# 75% initial fill`).

(e) `shared/matsya.schema.json`: in the `parameters` object add:

```json
"initialFillPct": { "type": "number", "minimum": 0, "maximum": 100, "default": 75.0,
  "description": "Lake initial storage as % of depth-to-crest at sim start" }
```

Locate the existing `cfl` entry and add alongside (read the file first; keep key order alphabetical if the file is).

- [ ] **Step 4: Frontend implementation**

`CreateWizard.tsx`: state `const [initialFill, setInitialFill] = useState(String((editSim as any)?.parameters?.initialFillPct ?? "75"))`; extend the `editSim` sync effect with `setInitialFill(String((editSim as any)?.parameters?.initialFillPct ?? "75"))`; payload `parameters: { cfl: parseFloat(cfl) || 0.7, initialFillPct: Math.min(100, Math.max(0, parseFloat(initialFill) || 75)) }`; Step-4 UI below the CFL block:

```tsx
<label htmlFor="wizard-fill" className="block text-xs text-slate-300">
  Lake initial fill (% of capacity)
  <span className="flex items-center gap-3">
    <input id="wizard-fill" type="range" min={0} max={100} step={5} value={initialFill}
      onChange={e => setInitialFill(e.target.value)}
      className="flex-1 h-2 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-cyan-400" />
    <span className="font-mono text-xs text-cyan-300 w-12 text-right">{initialFill}%</span>
  </span>
  <span className="text-[11px] text-slate-400 mt-1 block">0% = lakes start empty, 100% = brimful (spills on first rain). Default 75% matches historic behavior.</span>
</label>
```

`PointInspector.tsx` hydro line: append `{point.hydro.spillVolumeM3 ? ` • spill ${point.hydro.spillVolumeM3} m³` : ""}` — first read the exact current line and extend it (do not rewrite the line).

`analysis.py` hydro_ctx: add `"spillVolumeM3": fstats.get("spillVolumeM3", 0)` and `"initialFillPct": fstats.get("initialFillPct", 75.0)` next to the existing keys.

- [ ] **Step 5: Frontend test** (append to `CreateWizard.test.tsx`)

```tsx
it("sends initialFillPct in run payload", async ()=>{
  const calls: any[] = []
  vi.stubGlobal("fetch", vi.fn(async (url: any, opts: any) => {
    if (String(url).includes("/api/hydro/summary")) {
      return { ok: true, json: async () => ({ drains: 52, snapped_to_waterbody: 20, to_river: 7, to_sea: 25 }) }
    }
    calls.push(JSON.parse(opts.body))
    return { ok: true, json: async () => ({ id: "x" }) }
  }))
  render(<CreateWizard open={true} onClose={()=>{}} onCreated={()=>{}} />)
  fireEvent.change(screen.getByPlaceholderText(/Chennai Monsoon/i), { target: { value: "filltest" } })
  fireEvent.click(screen.getByLabelText("Step 4: Physics"))
  const slider = document.getElementById("wizard-fill") as HTMLInputElement
  expect(slider.value).toBe("75")
  fireEvent.change(slider, { target: { value: "40" } })
  fireEvent.click(screen.getByText("Run Simulation"))
  await screen.findByText("filltest")  // settle: name still rendered pre-close race is fine; primary assert below
  const body = calls[calls.length - 1]
  expect(body.parameters.initialFillPct).toBe(40)
})
```

Note: check the real name placeholder/step-4 aria-label in the file before running — adjust selectors to match (`wizard-sim-name` id exists; prefer `document.getElementById("wizard-sim-name")` over placeholder text). If the submit flow closes the wizard before assertion, assert on `calls` only and drop the `findByText` line.

- [ ] **Step 6: Run everything for Phase 2**

Run: `pytest app/tests/test_coupled_flood.py app/tests/test_flood_service.py app/tests/test_simulation_model.py app/tests/test_point_flood.py -v`
Expected: PASS all (model default fills the field; analysis passthrough keeps point samples identical).
Run: `npx tsc --noEmit` then `npm run test -- src/tests/CreateWizard.test.tsx`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add matsya/matsya/backend/app/models/simulation.py matsya/matsya/backend/app/services/flood.py matsya/matsya/backend/app/services/analysis.py matsya/matsya/backend/app/services/hydro/coupled_runner.py matsya/matsya/shared/matsya.schema.json matsya/matsya/frontend/src/components/CreateWizard.tsx matsya/matsya/frontend/src/components/PointInspector.tsx matsya/matsya/frontend/src/tests/CreateWizard.test.tsx
git commit -m "feat(real-sim): initial lake-fill % parameter end to end"
```

---

### Phase 3: Verification (both features, live)

**Files:** none (verification only) unless a fix is needed — then amend the owning phase.

- [ ] **Step 1: Full suites**

Run: `pytest app/tests/ -q --ignore=app/tests/test_flood_different.py` (from backend; ~2 min)
Expected: all PASS (baseline was 69 passed).
Run: `npx tsc --noEmit` + `npm run test` (frontend)
Expected: PASS, 13 files / 18+ tests.

- [ ] **Step 2: Live E2E matrix** (server on :8629, current branch code — restart it first so new `flood.py`/model loads)

```bash
for FILL in 0 75 100; do
SID=$(curl -s -X POST localhost:8629/api/simulations -H 'Content-Type: application/json' -d "{\"name\":\"fill-$FILL\",\"area\":{\"bbox\":[80.15,13.08,80.20,13.13],\"crs\":\"EPSG:4326\"},\"rainfall\":{\"rateMmHr\":100,\"durationHr\":2},\"parameters\":{\"initialFillPct\":$FILL}}") 
```

wait 15s for bg completion, then `GET /api/simulations/$SID` and record `spillVolumeM3`, `overtoppedLakes`, `maxDepth`, `mass_error`.
Expected: `spill(100%) > spill(75%) > spill(0%)` monotonic; `mass_error < 0.25` all three; `wbObserved: 2` all three. If monotonicity fails, STOP — return to Phase 1 (do not tune constants blindly).

- [ ] **Step 3: Visual check**

Open `:8881`, open the 100%-fill sim: flood must visibly extend beyond lake polygons (compare against the same-rain 0% sim side by side in two tabs). Point-click near a lake shows the spill line in the hydro slot.

- [ ] **Step 4: Commit + push + report**

```bash
git push origin real-simulation
```

Report: E2E matrix numbers, suite counts, backend-diff-vs-main stat, and the two deliberate semantics (75 default == legacy; ring fallback counts as outflow).

## Self-Review

- Spec coverage: visible overtop ✓ (P1 ponding + ring fallback), fill-% param ✓ (P2 model→engine→wizard→stats→inspector), everything-works verification ✓ (P3 suites + live matrix + visual).
- Placeholder scan: every step has exact code/commands/expected outputs; function names (`_spill_ring`, `_pond_volume`, `boundsToBboxStrings`-style reuse avoided — new names don't collide; grep for `_spill_ring` before creating to confirm absence).
- Type consistency: `initialFillPct` (camelCase, matching `rateMmHr`/`maxRain` conventions) in model, payload, stats, schema, and wizard state (`initialFill` local only); `spillVolumeM3`/`overtoppedLakes` identical in flood stats, analysis ctx, and inspector; `initial_fill_pct` (snake) only at the `generate_flood` boundary.
