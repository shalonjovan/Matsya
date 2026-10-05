# MATSYA — Urban Flood Nowcasting System

**SIH 2026 · Problem Statement SIH26085 (Software)** — *Urban Flood Nowcasting System (Drainage and Rainfall Coupling)*, Disaster Management, Ministry of Earth Sciences (MoES).
**Team Blastorz P74, SSN College of Engineering.**

MATSYA answers the question rainfall forecasts can't: **given the rain falling NOW, where will the water go?** It routes live gridded rainfall through a city's actual drains, lakes, rivers, and elevation — every 15 minutes — and outputs street-level flood depth, surcharged drains, safe refuges with routes, and time-stamped alerts. Fully deterministic, no black box: every number traces to rain, terrain, drains, or lakes.

---

## Features

- **Live rain grid** — Chennai tiled 12×12 (144 cells, ~1.25 km each), each with its own 24 h hyetograph from Open-Meteo; ±12 h sliding window re-ticked every 15 min, with labeled offline fallback.
- **Drainage-coupled flood engine** — 180×180 volume-preserving surface model (D8 downhill + pairwise leveling) coupled one-way to real **EPA-SWMM** (`pyswmm`) dynamic-wave drain solving; Manning-capacity fallback when the solver is absent.
- **Lake-aware** — 4,086 water bodies as broad-crested-weir storage tanks (surveyed bathymetry where available, otherwise stamped `assumed`).
- **Click-to-inspect** — click any map point for elevation/depth/velocity/hydrograph; click any rain cell for its live + future hourly curve that follows the timeline slider; clicked points get a map pin.
- **Decision support** — earliest-arrival safe-refuge routing (Dijkstra, flood-blocked edges), affected-area hotspots, road/drain impact tables, per-segment flood alerts, one-click exports (CSV/GeoJSON/PDF/PNG/.matsya), crowd-sourced depth reports pinned onto the flood field with decay.
- **2015 replay** — December-2015-like storm through the same engine, scored against recorded localities.
- **Togglable rain grid, NOW-marked timeline, light/dark classy theme.**

---

## Repository layout

```
.
├── assets/                     # Chennai GIS data (all tracked except the 254 MB staged zip)
│   ├── CartoDEM_30m_Chennai_EGM96_MSL.tif   # 30 m elevation, 13–14°N tile
│   ├── *.kml                   # drains (10,257), water bodies (4,086), rivers (876), canals
│   ├── roads.geojson + chennai_border.geojson
│   └── waterbodies/enrich/     # surveyed bathymetry rasters, lake volume tables
├── matsya/matsya/
│   ├── backend/                # FastAPI (app/) + requirements.txt + Dockerfile
│   │   ├── app/main.py         # routes, health, opt-in realtime tick loop
│   │   ├── app/routers/        # simulations, layers, runs, analysis, exports,
│   │   │                       #   live, hydro, rainfall, elevation, flood, api_v1
│   │   ├── app/services/       # flood core, rainfall zones/curves, elevation,
│   │   │                       #   hydro (graph/snap/rivers/lakes), SWMM engine,
│   │   │                       #   realtime tick, safe routes, crowd reports, 2015 event
│   │   └── data/simulations/   # 3 shipped sims (see below); rest is runtime-local
│   └── frontend/               # React 18 + Vite + Tailwind + Leaflet
│       └── src/                # App/MapShell/MapView/Timeline/panels/inspectors/utils
├── matsya/API_V1.md            # public v1 API reference
└── matsya/docker-compose.yml   # one-command run
```

## Shipped simulations (`backend/data/simulations/`)

| id | name | what it is |
|---|---|---|
| `realtime-chennai-01` | Live — Chennai | Live singleton, re-ticked every 15 min when `REALTIME_LOOP=1` |
| `967a5235-…` | Chennai_demo | Whole-Chennai 24 h variable storm, 73 frames |
| `72709d73-…` | chennai-demo-2 | Whole-Chennai storm, 24 frames |

> The live sim is rewritten by the tick loop at runtime — that's live state, not something to commit.

---

## Setup

### Prerequisites

- Python 3.12+ with `pip`
- Node.js 18+ with `npm`
- (Optional) Docker + Docker Compose

### 1. Backend — `:8000`

```bash
cd matsya/matsya/backend
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Verify: `curl http://localhost:8000/api/health` → `{"status":"ok", ...}`.

### 2. Frontend — `:5173`

```bash
cd matsya/matsya/frontend
npm install        # or: npm ci  (package-lock.json is committed)
npm run dev        # :5173, proxies /api → :8000
```

Open `http://localhost:5173/` → landing page → **Simulations** → open **Live — Chennai**.

### 3. Docker (alternative)

```bash
cd matsya/matsya && docker-compose up --build   # :8000 + :5173
```

### Environment variables

| var | default | effect |
|---|---|---|
| `REALTIME_SOURCE` | `dummy` | `openmeteo` = real Open-Meteo precipitation; anything else/failed fetch falls back to the labeled deterministic dummy |
| `REALTIME_LOOP` | off | `1` = tick the live sim every `REALTIME_TICK_MIN` (default 15) on server boot |
| `VITE_API_URL` | `http://localhost:8000` | backend target for the Vite `/api` proxy |

Live mode: `REALTIME_SOURCE=openmeteo REALTIME_LOOP=1 uvicorn app.main:app --host 0.0.0.0 --port 8000`

---

## API cheat sheet

```bash
curl http://localhost:8000/api/health
curl http://localhost:8000/api/live/status
curl http://localhost:8000/api/simulations | python3 -c "import json,sys; [print(s['id'],s['name'],s['status']) for s in json.load(sys.stdin)]"
curl "http://localhost:8000/api/simulations/realtime-chennai-01/point?lat=13.08&lon=80.21&time=36"
curl -X POST http://localhost:8000/api/simulations -H Content-Type:application/json -d '{"name":"Chennai","area":{"bbox":[80.15,13.08,80.20,13.13],"crs":"EPSG:4326"},"rainfall":{"rateMmHr":50,"durationHr":1}}'
```

Full v1 reference (routes, safe spaces, alerts, nowcasts, crowd reports, 2015 replay): [`matsya/API_V1.md`](matsya/API_V1.md).

---

## How it works (60 seconds)

1. **Rain** — Open-Meteo hourly precipitation sliced per grid cell into 24 h hyetographs (±12 h window).
2. **Surface** — rain lands on a 180×180 grid over 30 m CartoDEM; D8 downhill flow + pairwise leveling move it volume-preservingly.
3. **Drains** — 30% of step rain enters the network: SWMM dynamic-wave solves up to 40 reaches; node floods splat onto the map; excess over Manning capacity ponds at inlets.
4. **Lakes & rivers** — lakes fill as weir tanks and spill onto shorelines; rivers route via Muskingum and overtop onto valleys.
5. **Output** — 73 snapshot frames → PNG tiles + stats → point probes, hotspots, safe routes, alerts, exports. Crowd reports pin observed depths onto the field.

---

## Team

Team Blastorz P74 — SSN College of Engineering · SIH 2026 · MoES (NCMRWF).
