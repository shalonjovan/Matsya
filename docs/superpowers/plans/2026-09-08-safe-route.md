# Safe Route Sidebar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sidebar "Safe Route" tab — click a map point, get the nearest reachable safe spaces ranked with fastest routes drawn on the map.

**Architecture:** New `safe_spaces.py` service composes existing primitives (segment dryness, DEM elevation, lake masks, `find_routes` verification); new `POST /api/v1/safe-spaces` endpoint; new `SafeRoute.tsx` panel in a `ROUTES` sidebar tab; route polylines via a new `routeGroup` layer driven by a `route` prop (not the dead `matsya-flyto` pattern).

**Tech Stack:** FastAPI + pytest, React 18 + Leaflet, heapq routing (existing).

**Spec:** Chat plan 2026-09-08 (hybrid safe-space, button + top-3). User answers: hybrid definition, explicit button, ranked top-3.

## Global Constraints

- Branch: `safe-route`. Do NOT merge to main until the user says so.
- One commit per phase; exact messages below.
- Backend uvicorn runs WITHOUT `--reload` — restart after backend edits: `pkill -f 'uvicorn app.main'` (tolerate timeouts), then `setsid nohup python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/opencode/matsya-backend.log 2>&1 < /dev/null & disown` from `matsya/matsya/backend`. Frontend Vite HMR auto-reloads.
- TDD: RED first, verify fails correctly, then GREEN. No production code without a failing test.
- Safe-space definition (frozen): dry (`peakCm < thresholdCm` all steps, `firstFlooded is None`) + high (DEM elevation rank) + not-water (outside lake masks) + reachable (`safest` route exists). Candidates: dry road segments first, then dry off-road cells near roads; top-3 by routed ETA.
- Units: cm, m, minutes, lon/lat EPSG:4326. Envelope `{v, generatedAt, disclaimer, data}` on new endpoints.
- Live stack: backend `:8000`, frontend `:5173`.

---

### Phase 1: `safe_spaces` service + endpoint

**Files:**
- Create: `matsya/matsya/backend/app/services/safe_spaces.py`, `matsya/matsya/backend/app/tests/test_api_v1_safe_spaces.py`
- Modify: `matsya/matsya/backend/app/routers/api_v1.py` (append route)
- Test: `test_api_v1_safe_spaces.py`

**Interfaces:**
- Consumes: `segment_series` (road_segments), `load_snapshots` (snapshots), `sample_dem` (elevation), `_waterbodies_in_bbox` + `_rasterize_masks` (flood — read import paths first), `find_routes` + `snap_point` (safe_routes), `_lat_lon_to_row_col` (analysis).
- Produces: `find_candidates(sim, bbox, threshold_cm) -> [{kind, lat, lon, elevationM, peakCm, name}]`; `rank_safe_spaces(sim, bbox, origin, depart_min, threshold_cm, limit=3) -> [{rank, kind, name, lat, lon, elevationM, peakCm, route|None}]`; `POST /api/v1/safe-spaces` envelope.

- [ ] **Step 1: Write failing tests** — create `test_api_v1_safe_spaces.py` with `SIM = "72b53b60-54ad-4b1b-a500-378498b329c4"`:
  - shape: POST valid origin → 200, envelope `v == "1"`, `spaces` list length ≤ 3, each has `{rank, kind, name, lat, lon, elevationM, peakCm, route}` with `route.etaMin >= 0` and lon-first `path`.
  - ordering: ETAs ascending across spaces.
  - dryness: every space has `peakCm < 15.0`.
  - unknown sim → 404; origin `{lat: 0, lon: 0}` → 422; flooded-basin sim (all wet — use a 200mm/hr constant sim id created in-test via POST then deleted, or a synthetic unit test of `rank_safe_spaces` with empty candidates) → `spaces == []`.
- [ ] **Step 2: Run to verify they fail** — 404 (no route), right reason.
- [ ] **Step 3: Implement `find_candidates`** — dry segments: `segment_series(thresholdCm, limit=4000)` rows with `peakCm < threshold` and `firstFlooded is None` → attach `sample_dem(midpoint)` (skip None elev), name from segment `name`+`locality`, kind `"road"`. Dry cells: stack max-over-time grid, cells with max < threshold/100, stride 6 cells, exclude lake-mask cells (rasterize wb infos on the snap grid via flood helpers — read `_rasterize_masks` signature first), attach DEM via grid sampling (sample_dem per cell, stride keeps it ≤ ~300 calls), kind `"ground"`, name `"High ground"`. Cap 60 candidates (segments first). Never raises (empty list on failure).
- [ ] **Step 4: Implement `rank_safe_spaces`** — sort candidates by elevation desc, take first 8; `snap_point` pre-check (skip unsnappable); `find_routes` safest per candidate; keep successes; sort by `route.etaMin`; assign rank 1-based; return first `limit`. Route embedded verbatim from `find_routes` (`etaMin, maxDepthCm, path, segmentIds, floodDelayMin, avoidedSegments`).
- [ ] **Step 5: Wire router** — `POST /safe-spaces` body `{simId, origin: {lat, lon}, departAtMin = 0, thresholdCm = 15, limit = 3}`; 422 on bad origin/missing simId; `_get_sim` 404; envelope; 200 with `spaces: []` when none reachable.
- [ ] **Step 6: Run tests** — new suite PASS; full v1 suites PASS; smoke live, confirm top-1 ETA ascending + dry.
- [ ] **Step 7: Commit Phase 1** — `git add matsya/matsya/backend/app/services/safe_spaces.py matsya/matsya/backend/app/routers/api_v1.py matsya/matsya/backend/app/tests/test_api_v1_safe_spaces.py && git commit -m "feat(api-v1): safe-space search endpoint"`

---

### Phase 2: Sidebar panel + map overlays

**Files:**
- Create: `matsya/matsya/frontend/src/components/SafeRoute.tsx`, `matsya/matsya/frontend/src/tests/SafeRoute.test.tsx`
- Modify: `matsya/matsya/frontend/src/components/MapShell.tsx` (ROUTES tab + panel + route state), `matsya/matsya/frontend/src/components/MapView.tsx` (routeGroup + route prop effect)
- Test: `SafeRoute.test.tsx`

**Interfaces:**
- Consumes: `selectedPoint {lat, lon}` (MapShell state), `simulation.id`, `time` (as departAtMin — check Timeline units first: minutes or frame index? read MapShell time handling), `POST /api/v1/safe-spaces`.
- Produces: `route = {safest: [[lon,lat]...], fastest: [[lon,lat]...], dest: {lat, lon}} | null` passed to MapView.

- [ ] **Step 1: Write failing tests** — `SafeRoute.test.tsx`: renders origin inputs prefilled from prop, threshold select, Find button; mocked fetch returning 2 spaces → cards with names + ETAs; clicking a card calls `onSelectRoute` with the space's route. MapView route test: render with `route` prop (leaflet mocked as in existing MapView tests — read how they handle the async init first) → polyline added. Run → fail (no component/prop).
- [ ] **Step 2: Implement `SafeRoute.tsx`** — props `{simulation, time, origin}`; local threshold + loading + error + spaces states; origin lat/lon inputs synced from prop via useEffect; POST on button; ranked cards (kind badge road/ground, name, ETA min, peak cm, elevation m); card click → `onSelectRoute(space)`; empty result → "No reachable safe space — try a higher threshold"; fetch failure → honest error line (never fabricated data).
- [ ] **Step 3: Wire `MapShell.tsx`** — `activeTab` union += `"ROUTES"`; tab button (Navigation icon) after INSPECTOR; panel `{(activeTab === "ALL" || activeTab === "ROUTES") && <SafeRoute simulation time origin={selectedPoint} onSelectRoute={setRoute} />}`; `const [route, setRoute] = useState(null)`; pass `route` to MapView; clear route on sim change (key already recreates MapView per sim — also reset `route` state alongside).
- [ ] **Step 4: Wire `MapView.tsx`** — init: `layerRefs.current.routeGroup = L.layerGroup().addTo(map)`; effect on `[route]`: clear group; if route: safest polyline cyan solid weight 4, fastest amber dashed (skip if identical to safest), destination circleMarker; `map.fitBounds`; cleanup removes group content on unmount. Convert API lon/lat to Leaflet lat/lon.
- [ ] **Step 5: Run tests** — new suites PASS; full frontend + tsc PASS; manual: click map → ROUTES tab → Find → cards → click → polylines drawn.
- [ ] **Step 6: Commit Phase 2** — `git add matsya/matsya/frontend/src/components/SafeRoute.tsx matsya/matsya/frontend/src/tests/SafeRoute.test.tsx matsya/matsya/frontend/src/components/MapShell.tsx matsya/matsya/frontend/src/components/MapView.tsx && git commit -m "feat(ui): safe route sidebar panel and map overlays"`

---

### Phase 3: Regression + docs

- [ ] **Step 1: Full verification** — `python -m pytest app/tests/ -q` (backend), `npx vitest run` + `npx tsc --noEmit` (frontend); restart backend; smoke safe-spaces + sidebar flow live on `:5173`.
- [ ] **Step 2: Docs** — `matsya/API_V1.md` gains safe-spaces endpoint section (contract + curl example). Commit with any test fixes: `git commit -m "docs(api-v1): safe-spaces contract"`. NO merge to main.
