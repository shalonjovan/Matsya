# Layers and Map Fix — Full Blown Multi-Phasal Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development

**Goal:** Fix three bugs: (1) drains/waterbodies only 200 shown not entirety 10257/4086, (2) simulation list slow, (3) map vanishes on back/refresh/another simulation.

**Architecture:** Backend adds pagination/caching and correct limits; frontend MapView properly tears down and rebuilds on simulation change with full data and layer groups; simulation list uses TanStack Query caching and backend pagination.

**Spec:** User bug reports + assets counts.

## Global Constraints
- Drains layer must show entirety 10257 from drains.kml, not 200.
- Water layer must show entirety 4086 from chennai_waterbodies.kml, not 200.
- Hydro must still show 52 micro+macro.
- Simulation list must load <500ms with 50+ sims.
- Map must survive hash navigation, refresh, and simulation switch without blank.

---

### Phase 1 — Fix Drains/Water Entirety

#### Task 1.1: Backend remove limit or increase, handle large GeoJSON efficiently
**Files:** `matsya/matsya/backend/app/routers/layers.py`
**Interfaces:** `GET /api/layers/drains?limit=all`, `GET /api/layers/waterbodies?limit=all`
- Change default limit from 200 to 20000, and handle `limit=all` to return all, with simplification (Douglas-Peucker) for perf if needed.
- Test: `curl /api/layers/drains?limit=10257` returns 10257, `waterbodies?limit=4086` returns 4086.

#### Task 1.2: Frontend MapView fetch entirety
**Files:** `matsya/matsya/frontend/src/components/MapView.tsx`
**Interfaces:** Change `fetch("/api/layers/drains?limit=200")` to `fetch("/api/layers/drains?limit=10257")` and similarly waterbodies 4086, but with progressive loading or chunking to avoid blocking.
- Implement chunked loading: fetch in batches of 500 and add to layer incrementally, or use `limit=10257` directly if performant.
- Test: Map shows all drains.

---

### Phase 2 — Fix Simulation List Slowness

#### Task 2.1: Backend caching and pagination
**Files:** `matsya/matsya/backend/app/services/simulation_store.py` `matsya/matsya/backend/app/routers/simulations.py`
**Interfaces:** Add `GET /api/simulations?limit=20&offset=0` with pagination, and in-memory cache with TTL 5s, or use `functools.lru_cache`.
- Test: time `curl /api/simulations` <500ms.

#### Task 2.2: Frontend caching with TanStack Query
**Files:** `matsya/matsya/frontend/src/hooks/useSimulation.ts`
**Interfaces:** Use `useQuery` with `staleTime: 30000` and `cacheTime`, not `useEffect` + `fetch` on every mount.
- Test: second load from cache <100ms.

---

### Phase 3 — Fix Map Vanishing

#### Task 3.1: MapView proper teardown on simulation change
**Files:** `matsya/matsya/frontend/src/components/MapView.tsx`
**Interfaces:** `useEffect([simulation.id])` should cleanup old map and reinitialize, not just `fitBounds`.
- Current bug: `if (mapRef.current) { fitBounds; return; }` prevents reloading layers for new simulation, and when navigating back, the div is new but mapRef still points to old map which is detached.
- Fix: watch `simulation.id`, cleanup: `map.remove()`, `mapRef.current=null`, `layerRefs.current={}`, then re-init. Also handle `simulation` null.
- Test: open sim A → map shows, back → select list, open sim B → map shows B, refresh → map shows, not blank.

#### Task 3.2: App hash routing robust
**Files:** `matsya/matsya/frontend/src/App.tsx`
**Interfaces:** Ensure `worldId` state syncs with hash and `currentSim` fetch handles 404, and MapShell remounts on id change via `key={worldId}`.
- Test: hash change triggers remount.

#### Task 3.3: Leaflet CSS and container size after navigation
**Files:** `matsya/matsya/frontend/src/components/MapShell.tsx`, `MapView.tsx`
**Interfaces:** Ensure `invalidateSize` called after navigation and after layers toggled.
- Test: no diagonal tiles after back.

---

### Phase 4 — Verification
**Files:** Run `pytest -q`, `npm run test`, `npm run build`, `docker-compose up`, manual check.

