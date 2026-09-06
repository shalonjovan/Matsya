def test_anuga_wets_local_dem_patch():
    from app.services.engine.anuga_smoke import run_puddle
    res = run_puddle(bbox=[80.15, 13.08, 80.20, 13.13], rain_mmhr=50.0, minutes=30)
    assert res["solved"] is True
    assert res["max_depth_m"] > 0.0
    assert res["wet_fraction"] > 0.0
