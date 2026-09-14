def _clean():
    import shutil
    from app.services.simulation_store import store
    from app.services.realtime.manager import REALTIME_ID
    try:
        store.delete(REALTIME_ID)
    except Exception:
        pass
    try:
        shutil.rmtree(store.base_path / REALTIME_ID, ignore_errors=True)
    except Exception:
        pass


def test_tick_creates_singleton():
    from app.services.realtime.manager import tick, REALTIME_ID
    from app.services.simulation_store import store
    _clean()
    try:
        r = tick()
        assert r["simId"] == REALTIME_ID
        s = store.get(REALTIME_ID)
        _live = s.live if hasattr(s, "live") else s.get("live")
        assert _live is True
        r2 = tick()
        assert r2["simId"] == REALTIME_ID  # still one sim
    finally:
        _clean()


def test_tick_applies_lake_states():
    from app.services.realtime.manager import tick
    from app.services.simulation_store import store
    from app.services.realtime.manager import REALTIME_ID
    _clean()
    try:
        tick()
        s = store.get(REALTIME_ID)
        hydro = s.hydro if hasattr(s, "hydro") else s.get("hydro")
        states = hydro.get("waterbodyStates") if isinstance(hydro, dict) else hydro.waterbodyStates
        assert isinstance(states, dict) and len(states) >= 1
    finally:
        _clean()


def test_live_status_real():
    from fastapi.testclient import TestClient
    from app.main import app
    from app.services.realtime.manager import tick, REALTIME_ID
    _clean()
    try:
        tick()
        r = TestClient(app).get("/api/live/status")
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["simId"] == REALTIME_ID and j["live"] is True and j["lastTickAt"]
    finally:
        _clean()


def test_realtime_sim_protected():
    from fastapi.testclient import TestClient
    from app.main import app
    from app.services.realtime.manager import tick, REALTIME_ID
    _clean()
    try:
        tick()
        c = TestClient(app)
        assert c.delete(f"/api/simulations/{REALTIME_ID}").status_code == 400
        assert c.post(f"/api/simulations/{REALTIME_ID}/duplicate", json={}).status_code in (400, 404, 405)
    finally:
        _clean()


def test_tick_unknown_source_falls_back_to_dummy():
    from app.services.realtime.manager import tick, REALTIME_ID
    from app.services.simulation_store import store
    import shutil
    try:
        try:
            store.delete(REALTIME_ID)
        except Exception:
            pass
        r = tick(source="no-such-source")
        assert r["simId"] == REALTIME_ID
        s = store.get(REALTIME_ID)
        _res = s.results if hasattr(s, "results") else {}
        assert (_res.get("live") or {})["source"] == "dummy-fallback"
    finally:
        try:
            store.delete(REALTIME_ID)
        except Exception:
            pass
        try:
            shutil.rmtree(store.base_path / REALTIME_ID, ignore_errors=True)
        except Exception:
            pass


def test_tick_empty_lakes_ok():
    from app.services.realtime import weather
    from app.services.realtime.manager import tick, REALTIME_ID
    from app.services.simulation_store import store
    import shutil

    class NoLakes(weather.WeatherSource):
        def fetch(self, window_start, window_end, bbox):
            return {"rain": [{"t0": window_start.isoformat(), "t1": window_end.isoformat(), "rateMmHr": 0.2, "polygon": None}], "lakes": [], "source": "t"}

    weather._REGISTRY["t-nolakes"] = NoLakes
    try:
        try:
            store.delete(REALTIME_ID)
        except Exception:
            pass
        r = tick(source="t-nolakes")
        assert r["lakesApplied"] == 0 and r["simId"] == REALTIME_ID
    finally:
        try:
            store.delete(REALTIME_ID)
        except Exception:
            pass
        try:
            shutil.rmtree(store.base_path / REALTIME_ID, ignore_errors=True)
        except Exception:
            pass
        try:
            del weather._REGISTRY["t-nolakes"]
        except Exception:
            pass
