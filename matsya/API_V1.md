# MATSYA Public API v1 — Integrator Guide

Open reads, no keys. Base URL `http://<host>:8000`. Every response is wrapped:

```json
{"v": "1", "generatedAt": "2026-09-08T04:00:00+00:00", "disclaimer": "Model output — verify on the ground before operational use.", "data": {...}}
```

Units: depths **cm**, velocities **m/s**, lengths **m**, times **minutes since onset** (`t`) plus IST clock labels (`firstFlooded`, `peak`). Coordinates are lon/lat (GeoJSON order) in EPSG:4326.

Versioning promise: additive-only under `/api/v1`. Breaking changes go to `/api/v2`. Be gentle — heavy segment dumps are capped; use `limit`/`minPeakCm`.

## Live weather source

The realtime sim (`realtime-chennai-01`) rebuilds from a weather feed each tick. Sources live in `app/services/realtime/weather.py` behind the `WeatherSource` interface; the active one is `REALTIME_SOURCE` env (default `dummy`):
- `dummy` — deterministic drizzle for tests/demos (0 base, ≤1mm/hr blips).
- `openmeteo` — real hourly precipitation from Open-Meteo (`past_days=1`, `forecast_days=2`, `timezone=UTC`, no key), one variable-curve zone per grid cell over the sim bbox.
- Any fetch failure or unknown name falls back to dummy, reported as `"dummy-fallback"` in tick/status responses.
- Lake levels: Open-Meteo publishes no reservoir levels, so live fills stay assumed (global default) — documented, not invented.

## Endpoints

### `GET /api/v1/simulations/{id}/roads/segments`
Per road-segment, per-timestep flood depths — the feed navigation apps consume for edge costs.

Params: `thresholdCm` (default 15 — below = `passable`), `minPeakCm` (default 0), `limit` (default 500, max 4000, top by `peakCm`).

```bash
curl 'http://localhost:8000/api/v1/simulations/<id>/roads/segments?limit=2&thresholdCm=15'
```

`data.segments[]`: `{segmentId, roadId, name, locality, midpoint: {lat, lon}, lengthM, peakCm, firstFlooded, series: [{t, depthCm, passable}]}`. `data.meta`: `{count, total, truncated, thresholdCm, steps}`.

### `GET /api/v1/simulations/{id}/drainage/nodes`
Drainage graph state. `data.nodes[]`: `{id, floodVolumeM3, surcharged, capacityUsedPct}` — capacity is never invented (`null` unless computed). `data.reaches[]`: `{id, bankStatus: overtopped|within-banks}`. `data.source`: `swmm` (persisted SWMM volumes, new sims) or `inferred-depth` (sampled ponding, older sims).

### `GET /api/v1/alerts?simId=&withinMin=30&thresholdCm=15`
`{floodedNow: [segmentId], floodingWithinMin: [{segmentId, etaMin}], surchargedNodes: [id], truncated}` — the machine version of the dashboard's critical banner.

### `POST /api/v1/routes/safe`
Flood-safe routing. Body:

```json
{"origin": {"lat": 13.10, "lon": 80.19}, "destination": {"lat": 13.12, "lon": 80.20},
 "departAtMin": 0, "simId": "<id>", "thresholdCm": 15.0}
```

Returns `{"fastest": route, "safest": route|null, "reason": null|string}` where route is `{path: [[lon, lat]...], segmentIds, etaMin, floodDelayMin, maxDepthCm, avoidedSegments}`. Assumptions: 30 km/h urban speed, 200 m snap tolerance (else 422), unknown sim 404, cut-off destination 200 with `reason` (never 500).

### `POST /api/v1/nowcasts` (201)
Radar nowcast in, running sim out. Body: `{name, bbox, issuedAt, cells: [{amount, unit, polygon}...], baseRateMmHr = 0, durationHr = 1}`. Cells follow zone rules (cap 12 — extras reported, never silently applied). Returns `{simId, acceptedCells, droppedCells, totalRainMm}`. Poll `GET /api/simulations/{simId}` until `status == "Completed"`, then query the feeds above.

### `POST /api/v1/safe-spaces`
Nearest reachable safe spaces + fastest routes. Body:

```json
{"simId": "<id>", "origin": {"lat": 13.10, "lon": 80.19},
 "departAtMin": 0, "thresholdCm": 15.0, "limit": 3}
```

Safe space = dry (`peakCm` below threshold all steps, never floods) + high DEM elevation + outside lake masks + reachable by verified safest route. Candidates: dry road segments first, then dry off-road cells near roads; ranked by routed ETA. Returns `{spaces: [{rank, kind: road|ground, name, lat, lon, elevationM, peakCm, route: {etaMin, maxDepthCm, path, segmentIds}}], reason, originSnapped}`. Origin beyond the 200 m snap tolerance falls back to the nearest mapped road within 2 km with `originSnapped: {lat, lon, distanceM}` disclosed; beyond 2 km → 422. Powers the sidebar Safe Route tab.
