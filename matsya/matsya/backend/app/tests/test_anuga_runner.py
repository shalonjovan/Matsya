def test_anuga_sync_dry_storm_dry_map():
    from app.services.engine.anuga_runner import run_anuga_sync
    r = run_anuga_sync([80.15, 13.08, 80.20, 13.13], {"rateMmHr": 0, "durationHr": 1},
                       {"links": []}, "/tmp/anuga-dry")
    assert r["solved"] is True
    assert r["stats"]["maxDepth"] < 1e-6

def test_anuga_sync_storm_wets_map():
    from app.services.engine.anuga_runner import run_anuga_sync
    r = run_anuga_sync([80.15, 13.08, 80.20, 13.13], {"rateMmHr": 100, "durationHr": 2},
                       {"links": []}, "/tmp/anuga-wet")
    assert r["solved"] is True
    assert r["stats"]["maxDepth"] > 0.0
    assert r["stats"]["mass_error"] < 0.25
