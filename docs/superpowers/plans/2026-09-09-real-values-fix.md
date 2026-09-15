# Real-Values Whole-Chennai + Uniform Cell + Undefined Fix Plan (Option A)

> For agentic workers: use subagent-driven-development or executing-plans. Checkbox syntax.

**Goal:** Live sim covers whole Chennai as one seamless flood, hero shows real mm/hr.

**Architecture:** Expand DEFAULT_BBOX to chennai_border envelope (80.139,13.015,80.289,13.141), OpenMeteoWeather grid=1 single variable zone, hide debug zone rectangles, fix hero rainfall formatter.

**Tech Stack:** FastAPI + React, no new deps.

**Spec:** User screenshot 2026-09-09: 9-way split, demo tile 80.15/13.08/80.20/13.13, undefined mm/hr. Option A approved in Build Mode.

## Global Constraints
- Branch real-values, no merge until user says.
- Backend uvicorn --reload off -> manual restart.
- TDD, one commit per phase.
- No new deps.

### Phase 1: Whole-Chennai bbox
Files: matsya/matsya/backend/app/services/realtime/manager.py:11, tests
- Replace DEFAULT_BBOX with CHENNAI_BBOX loaded from assets/chennai_border.geojson (fallback to current if missing). DEFAULT_BBOX = CHENNAI_BBOX.
- Tests: assert south<13.03, north>13.13, tick zones rain area >95% bbox.

### Phase 2: Single uniform cell
Files: matsya/matsya/backend/app/services/realtime/weather.py OpenMeteoWeather grid default 1
- Change __init__ grid default 3->1. Tick will then create 1 zone covering whole bbox.
- Tests: openmeteo tick yields 1 zone, polygon covers bbox.

### Phase 3: undefined mm/hr
Files: matsya/matsya/frontend/src/components/SelectSimulation.tsx hero, LiveStatus.tsx
- Hero: use live status rainNowMmHr if available else max over zones points else rateMmHr. Never undefined.
- Tests: liveSim variable zones still renders number mm/hr.

### Phase 4: Hide debug grid
Files: matsya/matsya/frontend/src/components/MapView.tsx
- Ensure rainfall zone debug rectangles are not added to flood overlay; move to optional layer off by default.
- Tests: no dashed rectangles visible by default.

### Phase 5: Verification
- pytest + vitest, restart backend, tick openmeteo, curl health, visual :5173.
