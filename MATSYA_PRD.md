# MATSYA — Product Requirements Document

**Version:** 1.0 (living document)
**Date:** 2026-09-06
**Status:** Implements through `main @ ea58d89` (MVP → Slice 2 + live playback, all merged)
**Repo:** `https://github.com/shalonjovan/Matsya.git`

---

## 1. Product overview

### 1.1 What MATSYA is
MATSYA is an open, map-first **urban flood nowcasting twin for Chennai**. A user selects an area (drawn rectangle, searched place, or the entire Chennai boundary), sets rainfall (a constant design storm or a hand-drawn variable hyetograph), and the system computes where water goes through a coupled chain — **Rainfall → Surface → Drains → Lakes → Rivers → Sea** — then plays the flood back as a scrubbable, clickable animation (~1 frame per 15 minutes) with per-point flood histories, spill/overload readouts, and portable simulation packages.

### 1.2 Vision
Any Chennai resident, engineer, or planner can ask *"what floods, how deep, when?"* for any storm over any part of the city — and get an answer that is **computed, sourced, and honest about its own uncertainty**, not a pretty picture.

### 1.3 Goals (in priority order)
1. **G1 — Real engines.** Every displayed number is computed by hydraulic solvers (EPA SWMM for drains; weir/Muskingum/Manning for lakes/rivers) or measured from source data. No random fills, no hardcoded depths, no invented geometry — ever again.
2. **G2 — Honesty as a feature.** Missing data is declared, not fabricated: assumed values are flagged per-run, uncalibrated outputs are labeled exploratory, capacities carry `observed`/`assumed` stamps.
3. **G3 — Simulation as the fundamental object.** All state hangs off a versioned `Simulation` aggregate, portable as a `.matsya` ZIP, reproducible from its inputs.
4. **G4 — Evidence over assertions.** Mass-balance ledgers on every run; cross-validation against real solvers (TELEMAC-2D, LISFLOOD-FP, Itzi); ground-truth calibration as the terminal gate.
5. **G5 — A map you can play.** Press Play and watch onset → peak → recession with synced clocks, per-point histories, and failure-point readouts.

### 1.4 Non-goals (explicitly out of scope today)
- Live emergency dispatch or evacuation instruction (decision-support prototype; always defer to official disaster-management directions).
- Real-time sensor ingestion (no live gauges/tide feeds yet; tide/forecast inputs are roadmap).
- Survey-grade engineering design (drain geometry defaults are provisional until GCC inventory data arrives).
- 2D shallow-water product runs (validated in `test/`, not yet wired to the serving path).

---

## 2. Users and use cases

| User | Use cases |
|---|---|
| Resident | "Will my street flood in tonight's storm? When will water first reach us? How long will it stay?" (map play + point click) |
| Drainage engineer (GCC) | "Which junctions flood at 100mm/hr? Which lake spills first? What if lakes start full vs empty?" (runs, spill stats, fill %) |
| Planner / researcher | "Compare storms across areas; export evidence; reproduce a published run from its `.matsya` file" (packages, ledger) |
| Contributor | "Add a solver, a dataset, or a panel without rewriting the app" (engine/router contracts, stamped provenance) |

---

## 3. System architecture

```
┌─ Frontend (React 18 + Vite + Tailwind + Leaflet 1.9, :5173) ─────────────┐
│ SelectSimulation · CreateWizard · MapShell · MapView · Timeline · Panels  │
│ HydroLayer · WaterbodyInspector · PointInspector · RainfallGraph          │
└──────────────────────────────┬───────────────────────────────────────────┘
                               │  REST /api/* (Vite proxy / VITE_API_URL)
┌─ Backend (FastAPI, Python 3.12, :8000) ──────────────────────────────────┐
│ routers/ simulations · runs · flood · elevation · layers · hydro ·         │
│          analysis · rainfall · exports · live                             │
│ services/ flood.py (coupled loop) · elevation.py · rainfall_curve.py      │
│           engine/swmm_runner.py · engine/swmm_inp.py · engine/anuga_runner │
│           hydro/{asset_loader, dem, snap, graph, waterbody, river,         │
│                  river_capacity, waterbody_enrich, coupled_runner}         │
│           analysis.py · simulation_store.py (JSON + bg threads + heal)    │
│ data/ simulations/{id}.json + flood/{i}.png + flood.json + snapshots.npy  │
│       runs/{run_id}/network.inp + .rpt · swmm_cache/ (bbox+rainfall key)   │
└──────────────────────────────────────────────────────────────────────────┘
  Docker Compose: backend:8000 + frontend:5173, ../../assets:/app/assets:ro
```

### 3.1 Key design contracts (stable — do not break)
- **Run JSON:** `{runId, simId, engine, status: Running|Completed|Failed, progress, created, audit?, results: {times[], stats{}}}`. Polled by `useSimulationResults`; frontend-agnostic to engine.
- **Flood serving:** `GET /api/simulations/{id}/flood?time=N` → PNG (clamped to stored steps); stats carry `steps`, `minutesPerFrame`, `floodVersion`.
- **Mass closure:** every flood run reports `mass_error = |surface_Δ + lake_Δ + reach_Δ + outflow + sea − rain| / rain`, gate `< 0.25` in tests.
- **Provenance stamps:** `depth_source ∈ {assumed, observed-volume, observed-bathy}`, capacity `source ∈ {assumed-defaults, observed-valley, observed-dims}`, audit `{observed[], assumed[], missing[]}` on every SWMM run.

---

## 4. Functional requirements

### 4.1 Simulation lifecycle (FR-SIM)
- **FR-SIM-1** Create/read/update/duplicate/delete/import/export simulations via `/api/simulations`; hash routes `#/` and `#/world/{id}` (+ `#/world/demo` fallback).
- **FR-SIM-2** Status across `Ready|Running|Completed|Incomplete|Error|Live|Offline`; heavy generation runs in bg threads with frontend polling ("Processing…" states).
- **FR-SIM-3** `.matsya` portable ZIP (v1.1, `MATSYA_VERSION` + schema in `shared/matsya.schema.json`) round-trips a simulation with elevation, flood, and hydro payloads.
- **FR-SIM-4** Sims whose stored flood predates `floodVersion: 2` auto-heal to full playback on open (Running → Completed, no user action).

### 4.2 Area selection (FR-AREA)
- **FR-AREA-1** Three tabs: place search (Nominatim top-5 + local Chennai fuzzy, 5-item list), rectangle (bbox inputs + `leaflet-draw` rectangle on a 300px map, draw/edit/delete all sync coords live), Entire Chennai (`chennai_border.geojson` polygon + derived bbox).
- **FR-AREA-2** Free-form polygon supported end-to-end (TIF clip via `rasterio.mask` precedence, bbox fallback).
- **FR-AREA-3** `leaflet-draw` MUST resolve from `window.L` (UMD IIFE requirement — import object lacks the plugin); failure shows an explicit reload message, never a dead map.

### 4.3 Rainfall (FR-RAIN)
- **FR-RAIN-1** Constant mode (`rateMmHr × durationHr`) and Advanced graph mode (`totalTime`, `maxRain`, `rate|total` unit, draggable spline points, click-add / double-click-delete, burst/gradual/double-peak/random presets).
- **FR-RAIN-2** Variable curves interpolate per-timestep (CubicSpline with linear fallback, clamped) and drive rain, SWMM timeseries, and frame timing.

### 4.4 Terrain (FR-DEM)
- **FR-DEM-1** Per-simulation hypsometric PNG (180×180, vectorized ~0.1s) clipped from CartoDEM 30m, with ocean-artifact masking (`<0 → nodata`).
- **FR-DEM-2** `GET /api/dem/sample?lon&lat` point elevation; DEM sampling backs drain inverts/slopes and river slopes/valley profiles.

### 4.5 Flood computation (FR-FLOOD) — the coupled loop, per timestep
1. Rain increments surface uniformly; D8 steepest-descent pass (volume-preserving, vectorized).
2. 30% of step rain enters the drain network (or SWMM-computed equivalent when coupled).
3. Manning-capacity split per drain (1m default sections, internal only): fitted flow → lakes/rivers/sea by snap target; excess ponds at endpoints (fallback path).
4. Direct rainfall onto lake surfaces enters lake storage (surface compensated so mass closes).
5. Lakes step (weir outflow); spill ponds on 2-cell shoreline rings (`spillVolumeM3`, `overtoppedLakes`).
6. Rivers route via Muskingum with storage-based overtop (wedge vs steady-bankfull storage, fill-tied init); excess ponds on river corridors (`riverSpillVolumeM3`, `overtoppedRivers`).
7. Composite depth = max(surface, lake lift), + noise, clipped 0–5m; stats + PNG per frame.
- **FR-FLOOD-1** Deterministic per (bbox, rainfall, fill): same inputs → same outputs (seeded noise only).
- **FR-FLOOD-2** `mass_error < 0.25` on all committed scenarios.

### 4.6 Drains + SWMM (FR-SWMM)
- **FR-SWMM-1** `POST /run` executes real EPA SWMM (DYNWAVE, `pyswmm 2.1.0`-bundled solver) on bbox-clipped micro+macro drains with DEM inverts; per-node flood volumes parsed; honest `Failed` states (`blocked-no-drains-in-bbox`, `blocked-no-rainfall`, `swmm-error: …`).
- **FR-SWMM-2** Input audit on every run: `observed[]` (drain count, lengths from geometry) vs `assumed[]` (1m sections, n=0.017, DEM/slope defaults) vs `missing[]`; mode `provisional-default-geometry`.
- **FR-SWMM-3** Flood map consumes per-node floods (disk-cached by bbox+rainfall, 24h TTL): SWMM-routed volume is removed from the surface and ponded at node cells; Manning path remains as flagged fallback (`swmmCoupled` in stats).

### 4.7 Lakes (FR-LAKE)
- **FR-LAKE-1** Prismatic storage + broad-crested weir (`Q = 1.7·L·h^3/2`) + 3m forced-overflow cap; bed = crest − depth.
- **FR-LAKE-2** Observed depths: 135 lakes on surveyed bathymetric beds (123 spatial + 12 name-anchored majors: Ambattur, Chembarambakkam, Cholavaram, Korattur, Madhavaram, Kaveripakkam, Pakkam, Pulal/Redhills), each stamped; rest assumed 2m, stamped.
- **FR-LAKE-3** `parameters.initialFillPct` (0–100, default 75 = legacy `crest−0.5` for 2m lakes): `stage = bed + pct × depth`; wizard slider on Step 4; recorded in stats; 0% = empty beds, 100% = brimful.
- **FR-LAKE-4** Volume-shapefile join rules (overlap ≥0.3 of smaller + ≥2000m² shared + area ratio ≤5×; centroid-close <60m variant): zero forced matches — currently yields no volume matches (disjoint delineations, median 363m apart), bathy path carries the load.

### 4.8 Rivers (FR-RIVER)
- **FR-RIVER-1** Hybrid capacities: measured length/slope, DEM valley width where resolvable, flagged defaults otherwise; Manning bankfull Q (trapezoidal 1:1, n=0.035); cached; every reach stamped.
- **FR-RIVER-2** Muskingum routing per reach (`K = clamp(length/1.5, 60, 3600)`, `x = 0.2`), initialized at `qbank × fill_frac`; storage-based overtop ponds corridors; reach storage included in mass.
- **FR-RIVER-3** Drain-to-river inflows follow snap targets (dual-key alignment for snap's id handling); river-bound water goes to reaches, lake shares untouched.
- **FR-RIVER-4** Out of scope: backwater into SWMM outfalls (all FREE), canals (display-only; Buckingham tides unmodeled), upstream catchments.

### 4.9 Playback + timeline (FR-PLAY)
- **FR-PLAY-1** Frame rule: `steps = clamp(round(duration_hr × 60 / 15), 6, 73)` (~15 min/frame); `minutesPerFrame` + `floodVersion: 2` in stats; `snapshots.npy` cached beside PNGs (~2MB per 73-frame sim).
- **FR-PLAY-2** Timeline `max` and clock derive from the sim (`steps − 1`, `minutesPerFrame`; defaults 72/5 preserve legacy look); slider, play/step/speed/keyboard unchanged; map re-fetches `?time=` per position (existing mechanism).
- **FR-PLAY-3** Point clicks load the cached stack (no recompute) and derive `firstFlooded`/`peak` (HH:MM on the sim grid) and `duration` (`Xh Ym`) per cell; dry cells return nulls.

### 4.10 Inspection, layers, reports (FR-UI)
- **FR-UI-1** Click-to-inspect: elevation, depth, velocity, provenance captions, hydro line (mass, lakes + observed count, surcharge, lake/river/SWMM spill volumes).
- **FR-UI-2** Layer panel (7 groups, controlled toggles + opacity): flood, terrain, drainage (10,257), hydro drains (52) + waterbodies + rivers, water (4086), infra, other; basemap switch (Dark/HOT/Satellite) + AOI outline.
- **FR-UI-3** Panels: affected areas, road/drain impact (capacity `—` when unknown, §15 footnote intact), multi-format reports (pdf/csv/geojson/png/.matsya) with hydro summary, live status, hydro badge/check, waterbody inspector with observed-depth badge.
- **FR-UI-4** Wizard drain check reads live `/api/hydro/summary` with real counts; offline falls back to the legacy warning.
- **FR-UI-5** Command-center dark theme (carbon/hydro tokens, Inter + JetBrains Mono, lucide icons, glass panels); Next.js explicitly excluded (Vite-only).

---

## 5. Data requirements

| Asset | Size / count | Source role |
|---|---|---|
| `CartoDEM_30m_Chennai_EGM96_MSL.tif` | 17MB, 4.17–73.69m (mean 15.53) | Terrain, slopes, inverts, valley profiles |
| `drains.kml` | 27MB, 10,257 drains | Drainage layer (display; dense network future) |
| Micro (37) + Macro (15) drains | 127KB + 76KB | Modeled 1D network (SWMM) |
| Rivers/streams (876), Buckingham (5), Krishna (1) | 3.3MB + 17KB + 4.7KB | River layer; reaches for overload |
| `chennai_waterbodies.kml` | 18MB, 4086 polys | Lake storage (areas, names, types) |
| `chennai_border.geojson` | 411KB | Entire-city runs |
| `roads.geojson` (446) | 2.2MB | Infra layer |
| WRR Zenodo (extracted ~15MB, gitignored) | 86 bathy rasters + 90-lake shapefile + 914-lake CSV | Observed lake beds/volumes; monthly series reserved |
| IMD daily rainfall, TELEMAC/LISFLOOD/Itzi fixtures | `test/` | Validation only |

All large/raw assets are gitignored and mounted read-only into Docker (`../../assets:/app/assets:ro`).

---

## 6. API specification (10 routers)

| Method + path | Purpose |
|---|---|
| `GET /api/health` | `{status, version, engine}` |
| `POST /api/simulations` → 201 · `GET /api/simulations` · `GET/PATCH/DELETE /api/simulations/{id}` · `POST .../duplicate` · import/export | Simulation lifecycle |
| `POST /api/simulations/{id}/run` → 202 `{runId}` · `GET .../runs/{run_id}` · `GET .../runs` | SWMM runs (poll to Completed/Failed) |
| `GET /api/simulations/{id}/flood?time=N` → PNG · `GET .../flood/stats` | Playback frames + stats |
| `GET /api/simulations/{id}/elevation` → PNG · `GET /api/dem/sample?lon&lat` | Terrain |
| `GET /api/simulations/{id}/point?lat&lon&time` | Depth/velocity/provenance/hydro context |
| `GET /api/layers/drains?limit=10257` · `waterbodies?limit=4086` · `rivers` · `GET .../layers` | Static layers (30s server cache) |
| `GET /api/hydro/summary|graph|waterbodies?limit|check` · `GET .../simulations/{id}/hydro` | Hydro network + inspector data |
| `GET /api/simulations/{id}/affected-areas|roads|drains|report` | Impacts + report + exports |
| `GET /api/rainfall/curve` · `POST /api/rainfall/random` · `GET /api/live/status` | Rainfall tools + liveness |

Flood stats keys: `maxDepth, floodedArea, meanDepth, mass_error, wbCount, wbObserved, surchargedDrains, spillVolumeM3, overtoppedLakes, riverSpillVolumeM3, overtoppedRivers[], riverCount, riverAssumed, swmmCoupled, swmmFloodedNodes, swmmFloodVolumeM3, initialFillPct, totalRainMm, areaKm2, steps, minutesPerFrame, floodVersion`.

---

## 7. Non-functional requirements

- **NFR-1 Determinism:** identical inputs → identical outputs (seeded noise only).
- **NFR-2 Mass discipline:** `mass_error < 0.25` enforced by tests on all committed scenarios (observed ~0.12).
- **NFR-3 Performance budgets (measured):** 24-step full-res flood ≈ 5s; SWMM bbox run seconds (disk-cached); full backend suite ~3 min; frontend build ~2s.
- **NFR-4 Responsiveness:** heavy generation in bg threads; UI polls with Processing states; point clicks served from disk cache (no recompute).
- **NFR-5 Offline-first:** full product runs with zero network (bundled assets); live forecast/tide inputs are future *optional* layers, never requirements.
- **NFR-6 No silent invention:** every default carries a source stamp; every solver failure is a named `Failed` state, never a 500 or a guess.

---

## 8. Validation and calibration

- **In-repo gates (CI-equivalent):** 96 backend tests + 14 frontend suites (21 tests) green; `tsc` clean; Docker image builds with solver import-checked.
- **Cross-model validation (`test/`):** TELEMAC-2D big-square runs, LISFLOOD-FP comparison, Itzi Chennai config with Docker-GRASS path proven.
- **Behavioral proofs on record:** choked-vs-clean pipe flooding discrimination; monotonic rain→flow response; fill 0/75/100 spill ordering; sustained-vs-flash overtop logic; sliver-rejection in lake matching.
- **Calibration (planned, not built):** ground-truth depth labels → held-out precision/recall/MAE gate; until then all depth output is explicitly uncalibrated. Monthly lake volumes staged for seasonal init + labels.

---

## 9. Milestones

| Milestone | Content | State |
|---|---|---|
| MVP | Domain, store, packages, world/map UI, Docker | Done, on `main` |
| Hydro | Loader, snap 52→20/7/25, graph, WaterBody, Muskingum, hydro API/layers | Done |
| Per-sim terrain/flood + variable rain + freeform areas | Hypsometric + deterministic flood + graph rain + rect/Chennai | Done |
| UI refresh | Command-center theme, tabs, basemap, restyled components | Done (`feature/ui-refresh` → `main`) |
| Slice 1 — real SWMM | INP builder + audit, pyswmm runner, bbox drains, `/run` cutover | Done (`real-simulation` → `main`) |
| Lake realism | Shoreline spill, observed depths (135 lakes), fill %, live drain check | Done |
| Slice 2 — coupled map + rivers | SWMM node floods on map, river capacity/routing/overtop | Done (`slice-2` → `main @ ea58d89`) |
| Live playback | Duration frames, auto-heal, synced clock, frame labels | Done (`live-sim` → `slice-2` → `main`) |
| Slice 3 — 2D surface + backwater + catchments | Itzi/ANUGA product runs, SWMM↔river iteration, upstream inflows, canals | **Next** |
| Calibration + live inputs | Depth labels gate, seasonal init, citizen reports, forecast rain/tide | Queued |

Branch map: `main` (release) ← feature branches per stream (`feature/*`, `*-sim`, `slice-2`, `live-sim`, `real-simulation`); merge to `main` only on explicit approval; worktree at `matsya-ui` holds read-only `origin/ui`.

---

## 10. Open risks and known limits

1. **Drain geometry defaults** (1m sections) where KMLs lack dimensions — bounded by audit flags; needs GCC inventory data to retire.
2. **River overtop quiet at tested storms** — diverted inflow sits below measured-ish bankfulls (verified correct, not tuned); visible river flooding awaits upstream catchments (Slice 3).
3. **Uniform-sheet appearance** — rain falls evenly and routing is gentle; color scale normalizes against the 5m clip ceiling, flattening structure (visualization follow-up, physics intact).
4. **Uncalibrated depths** — no ground-truth gate yet; all depth claims are model outputs, labeled as such where shown.
5. **Single-node deployment** — in-memory run store (lost on restart), local disk state; multi-user/queueing is future work.
6. **Itzi/ANUGA host-blocked** (no GRASS, Python 3.14) — 2D work must go through Docker.

---

## 11. Run it

```bash
# Docker (prod-like)
cd matsya/matsya && docker-compose up -d --build   # :8000 api, :5173 app
# Dev (host)
cd matsya/matsya/backend && uvicorn app.main:app --port 8629      # feature work
cd matsya/matsya/frontend && VITE_API_URL=http://localhost:8629 npm run dev -- --port 8881
# Tests
cd matsya/matsya/backend && python -m pytest app/tests/ -q
cd matsya/matsya/frontend && npm run test && npm run build
```

## 12. Glossary

**Bankfull Q** — max river flow before spilling banks (Manning, trapezoidal 1:1). **Brimful/fill %** — lake starting level as % of depth-to-crest. **Bathymetry** — surveyed lake-bed elevations. **DYNWAVE** — SWMM dynamic-wave 1D solver. **Hypsometric** — elevation-tinted rendering. **Muskingum** — channel lag-attenuation routing (K, x). **Snap** — mapping drain endpoints to lakes/rivers/sea with tolerances. **Weir outflow** — `Q = 1.7·L·h^3/2` spill over lake crests.
