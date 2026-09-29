# Real Open-Meteo Weather Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the dummy drizzle feed with real Open-Meteo precipitation for the Chennai live sim, keeping the dummy as offline fallback.

**Architecture:** New `OpenMeteoWeather(WeatherSource)` in the realtime package fetches hourly `precipitation` for a 3×3 grid over the bbox (`past_days=1` + `forecast_days=1`, `timezone=auto`), slices the ±12h window, and emits one variable-curve zone per grid cell (hourly mm → per-hour rates, truthful spatiotemporal nowcast). Manager selects source via `REALTIME_SOURCE` env (default `dummy`); any fetch failure falls back to dummy with source `"dummy-fallback"`. Lake fills stay assumed (Open-Meteo publishes no reservoir levels — documented, empty list = global fill default).

**Tech Stack:** FastAPI + pytest, stdlib `urllib` only (no new deps).

**Spec:** Open-Meteo Forecast API docs (https://open-meteo.com/en/docs) — `GET https://api.open-meteo.com/v1/forecast?latitude=..&longitude=..&hourly=precipitation&past_days=1&forecast_days=1&timezone=auto`; hourly precipitation = preceding-hour mm sum; multi-location returns a list; no key for non-commercial use. Verified live 2026-09-09 (Chennai raining).

## Global Constraints

- Branch: `real-values`. Do NOT merge to main until the user says so.
- One commit per phase; exact messages below.
- Backend uvicorn runs WITHOUT `--reload` — restart after backend edits.
- TDD: RED test first (stubbed HTTP only — tests never touch the network), verify fails correctly, then GREEN.
- No new dependencies (stdlib urllib with 15s timeout).
- Respect fair use: 5-minute response cache in the source; single request per tick (all grid points in one comma-separated call).
- Dummy stays default; openmeteo is opt-in via env (tests + existing behavior untouched).

---

### Phase 1: OpenMeteoWeather source

**Files:**
- Modify: `matsya/matsya/backend/app/services/realtime/weather.py` (append class + registry entry)
- Create: `matsya/matsya/backend/app/tests/test_realtime_openmeteo.py`
- Test: `test_realtime_openmeteo.py`

**Interfaces:**
- Consumes: Open-Meteo HTTPS JSON (via injected fetcher for tests).
- Produces: `OpenMeteoWeather(WeatherSource)` with `__init__(timeout=15, grid=3, cache_s=300, _fetch=None)`; `fetch(window_start, window_end, bbox)` returning the standard contract (`rain` zones as variable-curve cells, `lakes: []`, `source: "openmeteo"`); registry gains `"openmeteo"`.

Cell → zone mapping (exact): grid points at bbox fractions `(i+0.5)/grid`; each cell is the sub-bbox around its point; hourly `precipitation` values sliced to `[window_start, window_end)` map to `points: [{time: hrs-since-window-start, amount: mm}]`, `totalTime: 24`, `maxRain: max(values)`, `unit: "rate"` (hourly mm IS mm/hr), `mode: "variable"`, `id: f"om-{i}"`. Missing/null values → 0.0. Negative values → 0.0 (never negative rain). Cache key `(hour-floor now, bbox rounded)` for 300s; on ANY exception raise (manager converts to dummy fallback — decided there, not here).

- [ ] **Step 1: Write failing tests**:

```python
SAMPLE = {"latitude": 13.08, "longitude": 80.15, "hourly": {
    "time": ["2026-09-08T18:00", "2026-09-08T19:00", "2026-09-08T20:00", "2026-09-08T21:00"],
    "precipitation": [0.0, 2.5, None, 0.4]}}

def _stub_factory(payloads):
    def _fetch(url, timeout=15):
        return payloads
    return _fetch

def test_openmeteo_maps_cells_to_zones():
    from datetime import datetime, timezone
    from app.services.realtime.weather import OpenMeteoWeather
    w0 = datetime(2026, 9, 8, 18, 0, tzinfo=timezone.utc)
    w1 = datetime(2026, 9, 8, 22, 0, tzinfo=timezone.utc)
    src = OpenMeteoWeather(grid=1, _fetch=_stub_factory([SAMPLE]))
    d = src.fetch(w0, w1, [80.15, 13.08, 80.20, 13.13])
    assert d["source"] == "openmeteo"
    assert len(d["zones" if "zones" in d else "rain"]) >= 1
    z = (d.get("zones") or d["rain"])[0]
    assert z["mode"] == "variable" and z["unit"] == "rate"
    assert [p["amount"] for p in z["points"]] == [0.0, 2.5, 0.0, 0.4]
    assert d["lakes"] == []

def test_openmeteo_negative_and_null_safe():
    from datetime import datetime, timezone
    from app.services.realtime.weather import OpenMeteoWeather
    bad = {"latitude": 13.08, "longitude": 80.15, "hourly": {
        "time": ["2026-09-08T18:00"], "precipitation": [-3.0]}}
    src = OpenMeteoWeather(grid=1, _fetch=_stub_factory([bad]))
    d = src.fetch(datetime(2026, 9, 8, 18, 0, tzinfo=timezone.utc),
                  datetime(2026, 9, 8, 19, 0, tzinfo=timezone.utc),
                  [80.15, 13.08, 80.20, 13.13])
    assert (d.get("zones") or d["rain"])[0]["points"][0]["amount"] == 0.0

def test_openmeteo_registered():
    from app.services.realtime import weather
    assert isinstance(weather.get_source("openmeteo"), weather.WeatherSource)
```

- [ ] **Step 2: Run to verify they fail** — import/class error, right reason.
- [ ] **Step 3: Implement** exactly per interfaces above (contract key MUST be `"rain"` to match `WeatherSource` — fix the test's `"zones" if` hedge to plain `d["rain"]` when implementing; zones ride as list items with mode/points fields, which `parse_zones` already accepts).
- [ ] **Step 4: Run tests** — PASS.
- [ ] **Step 5: Commit Phase 1** — `git add matsya/matsya/backend/app/services/realtime/weather.py matsya/matsya/backend/app/tests/test_realtime_openmeteo.py && git commit -m "feat(realtime): Open-Meteo precipitation source"`

---

### Phase 2: Manager wiring (env select + offline fallback)

**Files:**
- Modify: `matsya/matsya/backend/app/services/realtime/manager.py` (`tick` source handling), `matsya/matsya/backend/app/tests/test_realtime_manager.py` (append)
- Test: manager tests

**Interfaces:**
- Consumes: `get_source`, `REALTIME_SOURCE` env.
- Produces: `tick(now=None, source=None)` — `source=None` reads `REALTIME_SOURCE` env (default `"dummy"`); unknown names fall back to dummy; ANY fetch exception → dummy feed with `source` reported as `"dummy-fallback"` in `live_meta` + status. Empty lake list → `waterbodyStates` stays `{}` (global fill default — no crash, no fake fills).

- [ ] **Step 1: Write failing tests**:

```python
def test_tick_unknown_source_falls_back_to_dummy():
    from app.services.realtime.manager import tick, REALTIME_ID
    from app.services.simulation_store import store
    import shutil
    try:
        try: store.delete(REALTIME_ID)
        except Exception: pass
        r = tick(source="no-such-source")
        assert r["simId"] == REALTIME_ID
        s = store.get(REALTIME_ID)
        _res = s.results if hasattr(s, "results") else {}
        assert (_res.get("live") or {})["source"] == "dummy-fallback"
    finally:
        try: store.delete(REALTIME_ID)
        except Exception: pass
        try: shutil.rmtree(store.base_path / REALTIME_ID, ignore_errors=True)
        except Exception: pass

def test_tick_empty_lakes_ok():
    from app.services.realtime import weather
    from app.services.realtime.manager import tick, REALTIME_ID
    from app.services.simulation_store import store
    import shutil
    class NoLakes(weather.WeatherSource):
        def fetch(self, w0, w1, bbox):
            return {"rain": [{"t0": w0.isoformat(), "t1": w1.isoformat(), "rateMmHr": 0.2, "polygon": None}], "lakes": [], "source": "t"}
    weather._REGISTRY["t-nolakes"] = NoLakes
    try:
        try: store.delete(REALTIME_ID)
        except Exception: pass
        r = tick(source="t-nolakes")
        assert r["lakesApplied"] == 0 and r["simId"] == REALTIME_ID
    finally:
        try: store.delete(REALTIME_ID)
        except Exception: pass
        try: shutil.rmtree(store.base_path / REALTIME_ID, ignore_errors=True)
        except Exception: pass
        try: del weather._REGISTRY["t-nolakes"]
        except Exception: pass
```

- [ ] **Step 2: Run to verify they fail** — unknown source raises KeyError/AttributeError (not dummy-fallback); check current behavior first and assert the NEW behavior.
- [ ] **Step 3: Implement** — `tick(now=None, source=None)`: resolve `source = source or os.getenv("REALTIME_SOURCE", "dummy")`; `get_source` unknown → dummy with note; wrap `fetch` in try/except → on failure use `DummyWeather().fetch` and set `source_label = "dummy-fallback"`; `live_meta["source"] = source_label`; lake loop already tolerates empty lists (verify — no change if so).
- [ ] **Step 4: Run tests** — PASS; regression `test_realtime_weather` + `test_realtime_crowd` PASS.
- [ ] **Step 5: Commit Phase 2** — `git add matsya/matsya/backend/app/services/realtime/manager.py matsya/matsya/backend/app/tests/test_realtime_manager.py && git commit -m "feat(realtime): env-selected source with offline fallback"`

---

### Phase 3: Live verification + review (no merge)

- [ ] **Step 1: Live check** — restart backend on the branch, `REALTIME_SOURCE=openmeteo tick()` via python, confirm `source: openmeteo`, rain cells = 9, status endpoint shows real rain-now; one normal-tick regression (dummy default unchanged).
- [ ] **Step 2: Docs** — `matsya/API_V1.md` gains a short "Live weather source" note (env var, fallback, lake caveat). Commit docs: `git commit -m "docs(realtime): Open-Meteo source note"`.
- [ ] **Step 3: Confirm no merge** — stay on `real-values`. Report live rain-now number + tick result.
