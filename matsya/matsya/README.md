# MATSYA — matsya/matsya

Map-first flood simulation platform with Minecraft-style world management. Implements PRD `prd(2).md` MVP §28 inside `matsya/matsya`.

**Stack:** FastAPI (Python 3.12) + React 18 + Vite + Tailwind + Leaflet 1.9 + Zustand + TanStack Query. ANUGA primary engine (mocked as inertial 180×180 @30m, swappable to real ANUGA/TELEMAC/LISFLOOD).

**Structure:**
```
matsya/matsya/
├── backend/       # FastAPI — /api/health, /api/simulations CRUD, /api/simulations/{id}/layers|runs|point|affected-areas|report|export, /api/live/status
│   ├── app/models/simulation.py  # Simulation{area{bbox}, rainfall, terrain, drainage, ... status Ready/Running/...}
│   ├── app/services/simulation_store.py # JSON file store backend/data/simulations/{id}.json
│   ├── app/services/package_service.py  # .matsya ZIP (metadata.json + version 1.0)
│   ├── app/services/engine/anuga_runner.py # mock 180×180×73, pako stub, background thread
│   └── app/services/analysis.py   # point, affected-areas, roads, drains (no invented capacity)
├── frontend/      # React — SelectSimulation world cards → CreateWizard → MapShell (map-first)
│   ├── src/components/SelectSimulation.tsx # grid cards, status badges, Open/Create/Edit/Rename/Duplicate/Delete/Import/Export
│   ├── src/components/CreateWizard.tsx     # 4-step: Name → Area (Nominatim bbox) → Data checklist → Advanced cfl
│   ├── src/components/MapShell.tsx         # 70% map + 30% panels
│   ├── src/components/MapView.tsx          # Leaflet hot tiles, canvas heatmap, click → /point
│   ├── src/components/LayerPanel.tsx       # 6 groups Flood/Terrain/Drainage/Water/Infra/Other §9
│   ├── src/components/Timeline.tsx         # 73 steps play/pause §12-13
│   ├── src/components/PointInspector.tsx   # lat/lon/elev/depth/vel §10
│   ├── src/components/SearchBar.tsx        # Nominatim + coords §11
│   ├── src/components/AffectedAreas.tsx    # ranked Velachery 1.24m §14
│   ├── src/components/InfraImpact.tsx      # roads/drains §15
│   ├── src/components/Reports.tsx          # §23 + export §24 pdf/csv/geojson/png/matsya
│   └── src/components/LiveStatus.tsx       # Connected/Offline §17-19
└── shared/matsya.schema.json
```

**Run (dev):**
```bash
# backend
cd matsya/matsya/backend && pip install -r requirements.txt && uvicorn app.main:app --reload  # :8000
# frontend
cd matsya/matsya/frontend && npm install && npm run dev  # :5173 proxy /api → :8000
# tests
cd matsya/matsya/backend && python -m pytest -q  # 7 passed
cd matsya/matsya/frontend && npm run test && npm run build  # 9 passed, 47 modules
```

**Run (docker):**
```bash
cd matsya/matsya && docker-compose up --build  # :8000 + :5173
```

**Demo seed:** Chennai big square 80.15-80.20,13.08-13.13 180×180 @30m seeded from `test/TELEMAC-2D/test-2.0/input/dem_clipped.tif`, `assets/roads.geojson`, drains KML.

**API quick:**
```bash
curl http://localhost:8000/api/health
curl -X POST http://localhost:8000/api/simulations -H Content-Type:application/json -d '{"name":"Chennai","area":{"bbox":[80.15,13.08,80.20,13.13],"crs":"EPSG:4326"},"rainfall":{"rateMmHr":50,"durationHr":1}}'
curl -X POST http://localhost:8000/api/simulations/{id}/run
curl http://localhost:8000/api/simulations/{id}/layers | jq
curl "http://localhost:8000/api/simulations/{id}/point?lat=13.10&lon=80.17&time=0"
```

**Phases implemented:** 0 scaffold → 1 world mgmt → 2 map-shell → 3 layers → 4 engine/timeline → 5 point/search → 6 analysis → 7 reports → 8 live/docker. ANUGA mock flag `anuga_mock=True` in `backend/app/config.py`.
