def test_domain_inputs_from_sim_bbox():
    from app.services.engine.anuga_domain import build_domain_inputs
    out = build_domain_inputs([80.15, 13.08, 80.20, 13.13],
                              {"rateMmHr": 50, "durationHr": 1},
                              {"links": [{"from": "drain:0", "to": "wb:5"}]},
                              "/tmp/anuga-dom-test")
    import os
    assert os.path.exists(out["elevation_tif"]) and os.path.exists(out["manning_tif"])
    assert out["crs"] == "EPSG:32644" and out["cell_m"] > 0
    assert isinstance(out["culverts"], list) and len(out["culverts"]) == 1
    assert "assumed" in out["audit"] or "observed" in out["audit"]

def test_domain_inputs_variable_rain():
    from app.services.engine.anuga_domain import build_domain_inputs
    rain = {"mode": "variable", "totalTime": 2, "curve": {"values": [10.0] * 12}}
    out = build_domain_inputs([80.15, 13.08, 80.20, 13.13], rain, {"links": []}, "/tmp/anuga-dom-test2")
    assert len(out["rain_series"]) == 12
    assert out["rain_series"][0][1] == 10.0
