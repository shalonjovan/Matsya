# UI Refresh (origin/ui look onto freeform-chennai) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port the `origin/ui` command-center look (carbon/hydro dark theme, Inter + JetBrains Mono, lucide icons, glass panels) onto `feature/freeform-chennai` frontend without changing any behavior, wiring, or backend code.

**Architecture:** Restyle-don't-replace per component: keep every freeform-chennai hook, handler, endpoint, prop, and state machine verbatim; swap only JSX class strings, icons, and static copy for the `origin/ui` versions. Foundations (tokens, fonts, CSS) land first so later phases consume them. Each phase ends with `tsc + vite build` and the vitest subset for touched files, then a commit.

**Tech Stack:** React 18 + Vite 5 + Tailwind 3.4 + Leaflet 1.9 + leaflet-draw 1.0.4 + lucide-react (new) + vitest 2.1.8. No Next.js.

**Spec:** User directive 2026-09-05 (4 locked decisions: new `feature/ui-refresh` branch; skip Next.js `app/` dir + `next` dep; add `lucide-react`; restyle-don't-replace so Rect/Chennai tabs, RainfallGraph, polygon support, hydro layers, `/flood/stats` all keep working) + component diff-maps of `feature/freeform-chennai...origin/ui` (shell, wizard, map, panels analyses in session context).

## Global Constraints

- Backend (`matsya/matsya/backend/**`) and `shared/matsya.schema.json` are UNTOUCHED — zero diffs allowed there.
- No Next.js: do NOT port `frontend/app/`, `next.config.mjs`, `next-env.d.ts`, or the `next` dependency/scripts.
- Keep `leaflet-draw`, `@types/leaflet-draw`, `react-leaflet`, `vite` — `origin/ui` package.json drops `leaflet-draw`; do NOT port that removal.
- Keep all `/api/*` URLs, `?limit=10257` / `?limit=4086`, `?time=` / `?v=` cache-bust params, hash routes (`#/`, `#/world/:id`, `#/world/demo`), `key={simulation.id}` remounts, polling intervals (1500ms / 30s cap).
- Keep `drainage.capacity ?? "—"` (never invent capacity per §15) and base footnote semantics.
- `RainfallGraph` viewBox numbers (`width=400,height=200,pad=30`) and `data-testid` attributes (`rect-map`, `rainfall-graph`, `import-input`, `map-view`) are UNCHANGED — mouse math and tests depend on them.
- Prune dead lucide imports on port (`tsc` passes anyway since `noUnusedLocals:false`, but keep it clean).
- Commit per phase; push only when user says merge.

---

### Task 0: Branch + dependencies + design tokens

**Files:**
- Create branch: `feature/ui-refresh` from `feature/freeform-chennai`
- Modify: `matsya/matsya/frontend/package.json`
- Modify: `matsya/matsya/frontend/index.html`
- Modify: `matsya/matsya/frontend/tailwind.config.js`
- Modify: `matsya/matsya/frontend/src/index.css` (check existence on base first; base may only have tailwind directives)

**Interfaces:**
- Consumes: nothing (first task).
- Produces: `glass-panel`, `glass-card`, `focus-ring`, `pulse-radar`, `carbon.*` / `hydro.*` palette, `font-sans`/`font-mono`, dark Leaflet overrides, `lucide-react` importable — every later task relies on these exact names.

- [ ] **Step 1: Create the branch**

```bash
git checkout -b feature/ui-refresh feature/freeform-chennai
git branch --show-current
```

Expected: prints `feature/ui-refresh`.

- [ ] **Step 2: Add lucide-react (only new dep)**

Run: `npm install lucide-react --save` (from `matsya/matsya/frontend/`)

Then verify `package.json` diff contains ONLY the lucide line:

Run: `git diff -- matsya/matsya/frontend/package.json`
Expected: one added line `"lucide-react": "^0.4xx.x"` under dependencies; `leaflet-draw`, `react-leaflet`, scripts unchanged. If installer rewrites other versions, revert hunks so the diff is lucide-only.

- [ ] **Step 3: Port index.html chrome**

Replace `<html lang="en">` with `<html lang="en" class="dark">`, title with `MATSYA // Urban Flood Simulation & Command Center`, add the 3 font `<link>` lines (preconnect × 2 + Inter/JetBrains Mono stylesheet), and set body class to `bg-[#0B0F17] text-slate-100 antialiased selection:bg-cyan-500/30 selection:text-cyan-200`. Keep `<div id="root">` and `<script type="module" src="/src/main.tsx">` exactly.

- [ ] **Step 4: Port tailwind.config.js**

Get the exact file via `git show origin/ui:matsya/matsya/frontend/tailwind.config.js` and copy it verbatim (keep the `"./app/**"` content glob — harmless for Vite, matches ui file exactly). It defines `darkMode: "class"`, `fontFamily.sans/mono`, and the `carbon` + `hydro` palettes.

- [ ] **Step 5: Port index.css**

Get exact file via `git show origin/ui:matsya/matsya/frontend/src/index.css` and write it over base (base is tailwind directives only — nothing to preserve). This provides `.glass-panel`, `.glass-card` (+hover), `.focus-ring`, `.pulse-radar`, dark `.leaflet-*` overrides, thin scrollbars, reduced-motion guard.

- [ ] **Step 6: Verify tokens + build**

Run: `npx tsc --noEmit` from `matsya/matsya/frontend/`
Expected: PASS with no errors.

Run: `npm run build` from `matsya/matsya/frontend/`
Expected: `tsc && vite build` succeeds, `dist/` emitted.

- [ ] **Step 7: Commit**

```bash
git add matsya/matsya/frontend/package.json matsya/matsya/frontend/index.html matsya/matsya/frontend/tailwind.config.js matsya/matsya/frontend/src/index.css
git diff --cached --name-only | grep -i prd; echo prd-clean
git commit -m "feat(ui-refresh): tokens, fonts, dark chrome, lucide-react"
```

---

### Task 1: Shell — App, MapShell, SelectSimulation

**Files:**
- Modify: `matsya/matsya/frontend/src/App.tsx`
- Modify: `matsya/matsya/frontend/src/components/MapShell.tsx`
- Modify: `matsya/matsya/frontend/src/components/SelectSimulation.tsx`
- Test: `matsya/matsya/frontend/src/tests/SelectSimulation.test.tsx` (existing — must keep passing)

**Interfaces:**
- Consumes: Task 0 tokens (`glass-panel`, `focus-ring`, `font-mono`, cyan/slate classes) + `lucide-react` icons.
- Produces: dark ops header, tabbed slide-over sidebar contract (`activeTab`, `sidebarOpen=true` default), `statusBadgeStyles` badge+dot map — Tasks 2–4 reuse these patterns.

- [ ] **Step 1: Restyle App.tsx, keep logic verbatim**

Keep exactly: `getWorldIdFromHash`, all 5 `useState`s, `hashchange` effect, `navigateSelect/navigateWorld/handleOpen/handleCreate/handleEdit/handleCreated`, demo fallback (`#/world/demo`), render tree with `key={currentSim.id}` on `MapShell`, `CreateWizard` props. Do NOT port ui's `if (!r.ok)` auto-redirect-to-first-sim (logic change, not style).

Port from ui: root `min-h-screen bg-[#070A0F] text-slate-100 flex flex-col selection:bg-cyan-500 selection:text-black`; header `h-16 flex items-center justify-between px-5 bg-slate-950/90 border-b border-slate-800/80 sticky top-0 z-30 backdrop-blur-xl` with brand block `w-9 h-9 rounded-xl bg-gradient-to-tr from-cyan-600 via-cyan-500 to-blue-600 ... border border-cyan-400/30` + `<Waves className="w-5 h-5 text-white animate-pulse" />`, `v2.0-HYDRA` badge `px-1.5 py-0.5 rounded bg-cyan-500/10 text-cyan-400 text-[10px] font-mono font-bold border border-cyan-500/20 tracking-wider`; segmented switcher `flex items-center bg-slate-900/90 p-1 rounded-xl border border-slate-800 font-mono text-xs` with active `bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 shadow-sm`; IST clock block `hidden lg:flex items-center gap-2 px-3 py-1.5 bg-slate-900/80 rounded-xl border border-slate-800 text-xs font-mono text-slate-300` with `toLocaleTimeString("en-IN",{hour12:false})` + 1s interval; `New Scenario` gradient button; main `flex-1 ${!showSelect && worldId ? "p-0" : "p-4 sm:p-6 max-w-7xl mx-auto w-full"}`; loading card `p-8 glass-panel rounded-2xl border border-slate-800 text-center max-w-lg mx-auto my-12 space-y-4` with `<Cpu className="w-6 h-6 animate-pulse" />`.

Import only used icons: `Waves, Map as MapIcon, LayoutGrid, Plus, Clock, Cpu` (drop ui's unused `Radio, ShieldCheck, Compass`).

- [ ] **Step 2: Restyle MapShell.tsx, keep logic verbatim**

Keep exactly: `layers` initial object (all 11 keys + opacities), `MapView key={simulation.id}` + all props, every child with exact props (`HydroLayer simId`, `LayerPanel onChange={setLayers}`, `Timeline max={72}`, `PointInspector point`, `WaterbodyInspector waterbodyId`, `AffectedAreas/InfraImpact/Reports simulation`).

Port from ui: shell `flex flex-col h-[calc(100vh-64px)] gap-0 bg-[#070A0F] text-slate-100 overflow-hidden`, viewport `flex-1 relative bg-slate-950 min-h-0 min-w-0`; SearchBar wrapper `absolute top-3 left-3 z-[400] space-y-2`; sidebar toggle `absolute bottom-4 right-4 z-[400]` + `p-3 rounded-xl glass-panel text-slate-300 hover:text-white shadow-xl transition hover:border-cyan-500/50 focus-ring` with `PanelRightClose/PanelRightOpen`; aside tab system with `activeTab ("LAYERS"|"INSPECTOR"|"IMPACTS"|"REPORTS"|"ALL", default "LAYERS")`, `sidebarOpen` default `true`, tab classes active `bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 shadow-sm` / inactive `text-slate-400 hover:text-white`, icons `Layers/Crosshair/AlertTriangle/FileText`, scroll `flex-1 overflow-y-auto divide-y divide-slate-800/80`, mobile backdrop `fixed inset-0 bg-black/60 backdrop-blur-sm z-[450] md:hidden` + mobile header `ANALYTICAL TELEMETRY`; selection handlers that also `setActiveTab("INSPECTOR"); setSidebarOpen(true)`; KEEP `<LiveStatus/>` reachable (ui comments it out — restore the `absolute top-3 right-3 z-[400] hidden sm:block` badge rather than dropping it). Drop ui's unused `Maximize2, Minimize2, ListFilter` imports.

- [ ] **Step 3: Restyle SelectSimulation.tsx, keep wiring verbatim**

Keep exactly: `useSimulations()` + `refetch()` after every mutation, all 5 API helpers, `accept=".matsya,.zip"` + `data-testid="import-input"`, `handleOpen/handleCreate/handleDuplicate/handleExport/handleImportClick/Change` bodies, `handleEdit(sim){ if(onEdit) onEdit(sim); else openRenameModal(sim) }`, `formatBbox/formatRainfall/getStatus`, `statusFilter` default `"ALL"`.

Port from ui: hero `relative overflow-hidden rounded-2xl bg-gradient-to-r from-slate-900 via-slate-900/90 to-cyan-950/40 border border-slate-800 p-6 shadow-2xl` + blur dot + `GCC Spatial Intelligence Network` eyebrow + Create/Import buttons; telemetry counters `grid grid-cols-2 sm:grid-cols-4 gap-4 mt-6 pt-6 border-t border-slate-800/80 text-xs` (static `10,257 Conduits` / `4,086 Tanks & Lakes` stay hardcoded with a `/* static marketing numbers */` comment); toolbar with search input `w-full bg-slate-950/80 border border-slate-700/80 rounded-lg pl-9 pr-3 py-1.5 text-xs ...` + filter pills active `bg-cyan-500/20 text-cyan-300 border border-cyan-500/40`; cards `group glass-card rounded-2xl border border-slate-800 hover:border-cyan-500/50 ...` with banner `h-20 ... bg-gradient-to-br from-slate-800 via-slate-850 to-slate-900` + dot overlay `bg-[radial-gradient(#38bdf8_1px,transparent_1px)] [background-size:12px_12px] opacity-10`, gradient Open button, 4-col Edit/Copy/Export/Delete grid; `statusBadgeStyles` map (Ready emerald / Running cyan animate-ping / Completed blue / Incomplete amber / Error rose / Live purple animate-pulse / Offline slate) replacing `statusColor`; delete/rename modals with `role="dialog" aria-modal="true"` + icon medallions; Escape-key dismiss effect; error banner `role="alert"`. Drop unused `CheckCircle2` import. Keep `title` attributes on action buttons.

- [ ] **Step 4: Run shell tests + build**

Run: `npx tsc --noEmit` — Expected: PASS.
Run: `npm run test -- src/tests/SelectSimulation.test.tsx src/tests/health.test.tsx` — Expected: PASS (update tests ONLY if they assert exact old class strings; behavior assertions stay untouched).

- [ ] **Step 5: Commit**

```bash
git add matsya/matsya/frontend/src/App.tsx matsya/matsya/frontend/src/components/MapShell.tsx matsya/matsya/frontend/src/components/SelectSimulation.tsx
git commit -m "feat(ui-refresh): shell restyle - header, sidebar tabs, sim manager"
```

---

### Task 2: Wizard — CreateWizard, SearchBar, RainfallGraph

**Files:**
- Modify: `matsya/matsya/frontend/src/components/CreateWizard.tsx`
- Modify: `matsya/matsya/frontend/src/components/SearchBar.tsx` (replace with ui version verbatim + keep `§11` scope hint in placeholder)
- Modify: `matsya/matsya/frontend/src/components/RainfallGraph.tsx` (color/class literals ONLY — no geometry changes)
- Test: `matsya/matsya/frontend/src/tests/CreateWizard.test.tsx`, `matsya/matsya/frontend/src/tests/RainfallGraph.test.tsx` (existing — must keep passing)

**Interfaces:**
- Consumes: Task 0 tokens + `lucide-react`.
- Produces: dark wizard shell pattern + `areaMode` tab style reused by rainfall mode toggle; restyled `RainfallGraph` used by wizard only.

- [ ] **Step 1: Restyle CreateWizard shell, restore ALL base state**

Start from the BASE file (not ui's). Add `useRef` to react imports; add `import RainfallGraph from "./RainfallGraph"`, `import { randomPreset } from "../utils/rainfall"`, and lucide `X, MapPin, CloudRain, Layers, Sliders, Search, CheckCircle2, AlertTriangle, ArrowRight, ArrowLeft, Zap, Database` (use `Compass` too, for the Chennai tab).

Restore/keep base states: `step, name (default ""), minLon/minLat/maxLon/maxLat, polygon, rate/duration (with constantRate fallback), rainfallMode, totalTime, maxRain, unit, points, cfl, search, searchResults, searching, error, saving, areaMode, rectMapRef/rectMapInstance/rectLayerRef`, helpers `bboxFromPolygon, areaKm2`.

Port ui chrome: backdrop `fixed inset-0 bg-black/80 backdrop-blur-md flex items-center justify-center z-[9999] p-3 sm:p-4` + dialog `glass-panel rounded-2xl shadow-2xl w-full max-w-3xl max-h-[90vh] flex flex-col border border-slate-700/80 overflow-hidden` + `role="dialog" aria-modal="true"` + Escape listener; header `p-4 sm:p-6 border-b border-slate-800 ... bg-slate-950/40` with `SCENARIO CONFIGURATOR` eyebrow + `<X/>` close; stepper pills with `stepMeta` icons (Scenario/CloudRain, Area Bounds/MapPin, Datasets/Layers, Physics/Sliders), active `bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-sm`; error `p-3.5 bg-rose-950/50 border border-rose-800 text-rose-300 rounded-xl text-xs flex items-center gap-2.5` + AlertTriangle; body `p-4 sm:p-6 space-y-5 sm:space-y-6 flex-1 overflow-y-auto`; footer `p-4 border-t border-slate-800 bg-slate-950/60 flex justify-between items-center` with Back/Next + emerald `Quick Run` (`<Zap/>`) + gradient final Run; keep ui `PRESETS` + `HOTSPOTS` + drainage checklist + `<HydroBadge/>`.

- [ ] **Step 2: Restore freeform step-2 (area) inside ui styling**

Tab row reusing stepper strings: container `flex gap-1.5 p-1.5 bg-slate-950/60 border border-slate-800 rounded-xl`, active `bg-cyan-500/20 text-cyan-300 border border-cyan-500/40`, inactive `text-slate-400 hover:text-white`, icons `Search/MapPin/Compass` for search/rect/chennai. Search tab: ui input wrapper + button classes but BASE `handleSearch` (limit 5 + Chennai fuzzy + `setSearchResults`) + results `<ul className="mt-2 border border-slate-800 rounded-xl bg-slate-950/80 max-h-48 overflow-auto divide-y divide-slate-800/80">` rows `px-3 py-2 hover:bg-slate-800/70 cursor-pointer` wired to BASE `handleSelectSearch`. Rect tab: ui coord grid card `grid grid-cols-2 gap-3 p-4 bg-slate-950/60 rounded-xl border border-slate-800` with mono inputs + `onChange` clearing polygon, then `<div ref={rectMapRef} data-testid="rect-map" className="w-full h-[300px] rounded-xl border border-slate-800 bg-slate-950" />` + BBox readout `font-mono text-[11px] text-cyan-400` + Clear (ui secondary style); restore the ENTIRE base rect-map `useEffect` verbatim (dynamic leaflet + leaflet-draw imports, HOT tiles, FeatureGroup, Draw control rectangle-only, CREATED/EDITED/DELETED handlers, 200ms invalidateSize, cleanup). Chennai tab: full-width emerald button + asset note + polygon badge `p-2.5 rounded-xl bg-emerald-950/40 border border-emerald-800 text-emerald-300 text-xs font-mono`; restore BASE `handleChennai` verbatim. Summary card `p-3 rounded-xl bg-slate-950/60 border border-slate-800 text-[11px] font-mono text-slate-300` showing Polygon N points / Rectangle BBox / ~km². Submit gate uses base `areaValid` (`polygon || bbox`), NOT ui's `bboxValid`-only.

- [ ] **Step 3: Restore variable-rain step-3 inside ui styling**

Keep ui checklist + `<HydroBadge/>` + drain warning + constant inputs verbatim. Insert mode toggle above constant inputs (Default active cyan / Advanced active `bg-emerald-500/20 text-emerald-300 border border-emerald-500/40`). Advanced branch: `totalTime/maxRain/unit` mono dark inputs + `<RainfallGraph totalTime={parseFloat(totalTime)||6} maxRain={parseFloat(maxRain)||100} unit={unit} points={points} onChange={setPoints} />` wrapped in `rounded-xl border border-slate-800 overflow-hidden` + Random button `px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white rounded-xl text-xs font-semibold` picking `["burst","gradual","double-peak","random"]`. Checklist Rainfall row shows variable `✓ N points` when active. `handleSubmit` = BASE version (variable-aware payload with `polygon`, `mode/totalTime/maxRain/unit/points`, PATCH-vs-POST, resets `setStep(1); setPolygon(null)`).

- [ ] **Step 4: Replace SearchBar with ui version**

Copy `origin/ui` `SearchBar.tsx` verbatim (`glass-panel rounded-xl shadow-2xl p-2.5 border border-slate-700/80 ...`, `matsya-flyto` dispatch, coords fast-path, limit 5, clear-X, outside-click/Escape dismiss, listbox a11y). Only change: placeholder keeps road/river scope hint (`Search places, roads, rivers, or lat,lon...`). Leave its commented hotspot chips commented.

- [ ] **Step 5: Restyle RainfallGraph literals only**

Change ONLY these literals (keep `width=400,height=200,pad=30`, all handlers, scales, `data-testid="rainfall-graph"`): wrapper `rounded-xl border border-slate-800 bg-slate-950/60 p-2`; svg `w-full h-auto rounded-lg border border-slate-800 bg-slate-950`; axes `#64748B`; grid `#1E293B`; curve `#22D3EE`; circles `dragging ? #FB7185 : #22D3EE` stroke `#0B0F17`; labels `#94A3B8`; helpers `text-[11px] text-slate-400 mt-1` + `text-[11px] font-mono text-slate-500`.

- [ ] **Step 6: Run wizard tests + build**

Run: `npx tsc --noEmit` — Expected: PASS.
Run: `npm run test -- src/tests/CreateWizard.test.tsx src/tests/RainfallGraph.test.tsx` — Expected: PASS (update tests ONLY if they assert exact old class strings; behavior assertions like variable payload must pass unchanged — a posting test that checks `mode:"variable"` + `polygon` in payload validates the restore).

- [ ] **Step 7: Commit**

```bash
git add matsya/matsya/frontend/src/components/CreateWizard.tsx matsya/matsya/frontend/src/components/SearchBar.tsx matsya/matsya/frontend/src/components/RainfallGraph.tsx
git commit -m "feat(ui-refresh): wizard restyle, freeform area + variable rain preserved"
```

---

### Task 3: Map — MapView basemap/AOI, LayerPanel, Timeline

**Files:**
- Modify: `matsya/matsya/frontend/src/components/MapView.tsx`
- Modify: `matsya/matsya/frontend/src/components/LayerPanel.tsx`
- Modify: `matsya/matsya/frontend/src/components/Timeline.tsx`
- Test: `matsya/matsya/frontend/src/tests/MapView.test.tsx`, `matsya/matsya/frontend/src/tests/LayerPanel.test.tsx`, `matsya/matsya/frontend/src/tests/Timeline.test.tsx` (existing — must keep passing)

**Interfaces:**
- Consumes: Task 0 tokens + Task 1 sidebar context (MapView renders inside `bg-slate-950` viewport).
- Produces: basemap-switch contract (`basemap` state, `baseLayer` ref) and timeline keyboard/speed behavior; nothing else downstream.

- [ ] **Step 1: MapView — add ui basemap + AOI, RESTORE processing polling**

Keep 100%: `divRef/mapRef/layerRefs/prevSimIdRef`, `[simulation?.id]` effect with teardown + `cancelled`, bbox bounds, `L.map(div,{zoomControl:true,preferCanvas:true})`, flood/terrain `imageOverlay` URL builders (`?time=${timeIdx}&v=${...}`, `&v=${...}` with `encodeURIComponent`), offline canvas fallbacks, ALL `layerRefs` keys, ALL fetches (`/api/layers/drains?limit=10257`, `/api/hydro/graph` + `slice(0,50)`/`slice(0,100)`, `/api/layers/waterbodies?limit=4086`, point probe), `invalidateSize 100/500/1000 + ResizeObserver`, second `[layers,time]` effect verbatim.

Add from ui: `BASEMAP_TILES` (dark/hot/satellite Esri+HOT URLs + attributions), `useState basemap="hot"`, `layerRefs.current.baseLayer`, third `[basemap]` switching effect with `bringToBack`, AOI `L.rectangle(bounds,{color:"#06b6d4",weight:1.5,fill:false,dashArray:"6, 6",interactive:false})` + `layerRefs.current.aoiBoundary`; wrapper `relative` + inner `bg-[#070A0F] leaflet-container` (keep `data-testid="map-view"` + inline style); floating selector `absolute bottom-4 left-4 z-[400] flex items-center gap-1 p-1 rounded-xl glass-panel border border-slate-700/80 shadow-2xl text-[11px] font-mono` with Dark/HOT/Satellite buttons (active `bg-cyan-500/20 text-cyan-300 font-bold border border-cyan-500/40 shadow-sm`).

CRITICAL restore (ui deleted it): re-insert the base `isProcessing` + 1500ms poll / 30s cap block after base-layer creation — same `id="processing-overlay"`, same `?v=${mean}` / `?time=${time}&v=${maxDepth}` reload, same visibility guard. Restyle its classes to dark (`bg-slate-900/95 text-slate-100 border-slate-700`) but keep text `Processing elevation & flood...`. Do NOT add `basemap` to the first-effect deps.

- [ ] **Step 2: LayerPanel — restyle cards, fix count, keep wiring**

Keep verbatim: `useState/useEffect` controlled sync, `update()` merge, all 7 group `id`s, `floodLegend` computation, compact depth legend. Port ui: container `p-3.5 border-b border-slate-800/80 bg-slate-950/60`, header `text-xs uppercase text-slate-400 font-mono font-semibold tracking-wider flex items-center gap-1.5` + `<Layers className="w-3.5 h-3.5 text-cyan-400" />` + count `{groups.length} Groups` (FIX ui's hardcoded `6 Groups` — array has 7), cards `p-2.5 rounded-xl border transition-all duration-150` + visible `bg-slate-900/80 border-slate-800 shadow-sm` / hidden `bg-slate-950/40 border-slate-900/60 opacity-60`, dark checkbox `w-3.5 h-3.5 rounded border-slate-700 bg-slate-950 text-cyan-500 accent-cyan-500`, slider `w-14 h-1 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-cyan-400` + `%` value label, per-group lucide icon+color (`depth:Waves/cyan, terrain:Mountain/emerald, drainage:GitFork/indigo, hydro:Droplets/blue, water:Waves/sky, infra:Building2/slate, other:Layers/slate-500`). Keep verbose legends commented (declutter) — optionally expose terrain `min→max` as `<details>`. Remove dead `Eye,EyeOff` imports and unwired `legendGradient` fields.

- [ ] **Step 3: Timeline — restyle + keep math, prune dead icons**

Keep verbatim: props `{time,onChange,max=72}`, `*5`-minute math with `padStart`, wrap `(time+1)%(max+1)`, clamps, default 350ms play speed, ui's speed cycle (350→150→50), keyboard effect (Space/Arrows + INPUT guard + cleanup). Port ui: container `bg-slate-950 border-t border-slate-800/90 px-4 py-2.5 select-none` + `role="region" aria-label="Simulation temporal controls"`, Play `min-h-[38px] rounded-xl` amber-when-playing / cyan-when-paused, step buttons with arrow titles, speed `1x/2x/5x` toggle, slider `w-full h-2 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-cyan-400` + aria-valuetext, clock `flex items-center gap-2 px-3 py-1.5 bg-slate-900/90 rounded-xl border border-slate-800 font-mono` + `<Clock/>` + `HRS` suffix. Import ONLY `Clock` from lucide (drop dead `Play,Pause,ChevronLeft,ChevronRight,FastForward` unless wiring the icon components). Keep milestone/telemetry blocks commented.

- [ ] **Step 4: Run map tests + build**

Run: `npx tsc --noEmit` — Expected: PASS.
Run: `npm run test -- src/tests/MapView.test.tsx src/tests/LayerPanel.test.tsx src/tests/Timeline.test.tsx` — Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add matsya/matsya/frontend/src/components/MapView.tsx matsya/matsya/frontend/src/components/LayerPanel.tsx matsya/matsya/frontend/src/components/Timeline.tsx
git commit -m "feat(ui-refresh): map restyle - basemap switch, AOI, panels, timeline"
```

---

### Task 4: Panels — 8 inspectors with hydro slots

**Files:**
- Modify: `AffectedAreas.tsx`, `InfraImpact.tsx`, `Reports.tsx`, `LiveStatus.tsx`, `HydroBadge.tsx`, `HydroLayer.tsx`, `WaterbodyInspector.tsx`, `PointInspector.tsx` (all under `matsya/matsya/frontend/src/components/`)
- Test: `matsya/matsya/frontend/src/tests/AffectedAreas.test.tsx`, `HydroLayer.test.tsx`, `LiveStatus.test.tsx`, `PointInspector.test.tsx`, `WaterbodyInspector.test.tsx` (existing — must keep passing)

**Interfaces:**
- Consumes: Task 0–1 tokens (`glass-panel`, pill/card/banner/table/empty-loading patterns).
- Produces: nothing downstream (leaf components). Leaves `mass_error/wbCount/surchargedDrains` visible where base backend provides them.

- [ ] **Step 1: Port the 6 simple panels (visual swap, logic verbatim)**

For `HydroBadge` (keep `/api/hydro/check` + all fields + loading branch; card `p-3 rounded-xl border border-slate-800 bg-slate-950/70 text-xs font-mono space-y-1`, `<ShieldCheck/>`, valid emerald/amber; drop unused `CheckCircle2,AlertTriangle`), `HydroLayer` (keep dual `/api/hydro/summary`+`/graph` fetch + `alive` + `simId` dep; header `<Droplets/>` + `Verified`, chips blue/sky/cyan; drop unused `GitFork,ArrowRight`; keep graph fetch wired even though counts stay commented), `AffectedAreas` (keep `/affected-areas` + fallback + `matsya-flyto` payload + server rank order; rows `p-2.5 rounded-xl bg-slate-900/80 border border-slate-800 hover:border-cyan-500/50 ...` + depth pill rose-if-`Number(maxDepth)>=1.0`-else-amber as DISPLAY ONLY; icons `AlertTriangle/Navigation/MapPin`), `InfraImpact` (keep `/roads` + `/drains` + fallbacks + `capacity ?? "—"`; table kit classes + `Building2/Navigation/GitFork`; drop unused `AlertCircle`; restore base footnote wording `Capacity never invented per §15 — shown as — when missing.` in `font-mono text-[10px]` styling instead of ui's reworded comment), `Reports` (keep `/report` + `??` defaults + 5 export formats + `window.open(...export?format=...)`; summary card + `formatIcons` map; leave a second summary line slot for future `mass_error/wbCount` in `text-[11px] font-mono`), `LiveStatus` (keep `navigator.onLine` + listeners + `/api/live/status` + `liveMetrics` state with `"42 mm/hr"/"3.4 km²"` defaults — ui is NEWER here, keep ui version; `glass-panel` + dot + pill + alert cards; keep ONLY `AlertTriangle` import).

- [ ] **Step 2: WaterbodyInspector — port + keep NaN hardening**

Keep: `/api/hydro/waterbodies?limit=100` + `String()` id match + `arr[0]` fallback + all field fallbacks. Port ui cards/banner/spill pill (`Overtopping Spill` rose if `head>0` else `Retaining` cyan). MUST keep ui's null-hardening (`crest = wb.crest ?? wb.spill_crest ?? 5`, `areaM2 = wb.area_m2 ?? 50000`, `head.toFixed(2)`) — base arithmetic NaNs/throws on missing fields. Keep `dem_elev/centroid/spill_crest` rendered. Drop the 5 unused icon imports, keep `Droplets`.

- [ ] **Step 3: PointInspector — port + hydro slot + provenance**

Keep all `?.toFixed ??` chains + `water_depth` fallback; normalize `const floodDepth = point.floodDepth ?? point.water_depth ?? 0` for the hazard badge (High ≥0.5 rose / Moderate ≥0.15 amber / else emerald — display only). Port coords banner + elevation/depth cards + velocity row + temporal row + icons (`Crosshair/Mountain/Waves/Gauge/Clock`; drop `ShieldAlert,ShieldCheck`). Un-comment `nearestDrain` into a styled `text-[10px] font-mono` row (don't leave dead). Restore measured/simulated/derived provenance as `title` attributes or tiny captions (spec §10). ADD hydro slot: if `point.hydro` present, render `mass_error • wbCount • surcharged` line in temporal-banner style `p-2 rounded-lg bg-slate-900/50 border border-slate-800/80 text-[11px] text-slate-400 font-mono`; if absent render nothing (works against old backends too).

- [ ] **Step 4: Run panel tests + build**

Run: `npx tsc --noEmit` — Expected: PASS.
Run: `npm run test -- src/tests/AffectedAreas.test.tsx src/tests/HydroLayer.test.tsx src/tests/LiveStatus.test.tsx src/tests/PointInspector.test.tsx src/tests/WaterbodyInspector.test.tsx` — Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add matsya/matsya/frontend/src/components/AffectedAreas.tsx matsya/matsya/frontend/src/components/InfraImpact.tsx matsya/matsya/frontend/src/components/Reports.tsx matsya/matsya/frontend/src/components/LiveStatus.tsx matsya/matsya/frontend/src/components/HydroBadge.tsx matsya/matsya/frontend/src/components/HydroLayer.tsx matsya/matsya/frontend/src/components/WaterbodyInspector.tsx matsya/matsya/frontend/src/components/PointInspector.tsx
git commit -m "feat(ui-refresh): panels restyle with hydro slots preserved"
```

---

### Task 5: Final verification + push-ready

**Files:**
- None (verification only) unless fixes are needed — then amend the owning phase's files, never backend.

**Interfaces:**
- Consumes: Tasks 0–4.
- Produces: push-ready `feature/ui-refresh`, backend diff provably empty.

- [ ] **Step 1: Prove backend untouched**

Run: `git diff --stat feature/freeform-chennai -- matsya/matsya/backend matsya/matsya/shared`
Expected: EMPTY output. If anything shows, revert it — restyle tasks must not touch implementation.

- [ ] **Step 2: Full frontend verification**

Run: `npm run test` (full vitest suite) from `matsya/matsya/frontend/`
Expected: all suites PASS (13+ files). On failure, fix the port (never weaken a behavior assertion to fit styling).

Run: `npm run build`
Expected: `tsc && vite build` succeeds.

- [ ] **Step 3: Visual side-by-side check**

With `:8881` (this branch) and `:8882` (`origin/ui` worktree) running: open SelectSimulation, CreateWizard (all 4 steps incl. Rect draw + Chennai + Advanced graph), MapShell (all sidebar tabs, basemap switch Dark/HOT/Satellite, timeline play + speed, layer toggles), and one point-click inspection. Confirm: (a) visual parity with `:8882`, (b) freeform-only features work (rectangle draw sets bbox, Chennai sets polygon, variable rain posts `mode:"variable"`, hydro layers render, `/flood/stats` values show in point panel).

- [ ] **Step 4: Report**

Report: vitest count, build status, backend-diff empty proof, and any deliberate deviations from `origin/ui` visuals (e.g. restored LiveStatus badge, `7 Groups` fix, kept `§15` footnote wording). Do NOT merge or push — branch stays for user review.

## Self-Review

- Spec coverage: new branch ✓ (T0), skip Next.js ✓ (T0 — `app/`, `next.config.mjs`, `next` dep never touched), lucide-react ✓ (T0), restyle-don't-replace ✓ (every task has keep/port lists; CreateWizard variable+polygon T2, MapView polling T3, hydro slots T4).
- Placeholder scan: all steps carry exact class strings, file paths, commands, and expected outputs. No TBD/TODO.
- Type consistency: token names (`glass-panel`, `focus-ring`, `carbon`, `hydro`, `statusBadgeStyles`) defined in T0 and referenced identically in T1–T4; endpoint/param names (`?limit=10257`, `max=72`, `?time=&?v=`) match across T1/T3/T4; `Rainfall` wide shape and `utils/rainfall.ts` untouched so T2 props typecheck.
