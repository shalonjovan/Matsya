def test_parse_zones_validation():
    from app.services.rainfall_zones import parse_zones
    rf = {"rateMmHr": 50, "durationHr": 1, "zones": [
        {"id": "z1", "amount": 100, "unit": "rate",
         "polygon": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]}},
        {"id": "bad", "amount": -5, "unit": "rate", "polygon": {"type": "Point", "coordinates": [0, 0]}},
    ]}
    zones, dropped = parse_zones(rf)
    assert len(zones) == 1 and zones[0]["id"] == "z1"
    assert dropped == ["bad"]

def test_paint_last_wins_and_total_unit():
    import numpy as np
    from app.services.rainfall_zones import paint_rate_grid
    bbox = [0.0, 0.0, 0.02, 0.02]
    zones = [
        {"id": "a", "amount": 100, "unit": "rate",
         "polygon": {"type": "Polygon", "coordinates": [[[0, 0], [0.02, 0], [0.02, 0.02], [0, 0.02], [0, 0]]]}},
        {"id": "b", "amount": 60, "unit": "total",
         "polygon": {"type": "Polygon", "coordinates": [[[0, 0], [0.01, 0], [0.01, 0.01], [0, 0.01], [0, 0]]]}},
    ]
    g = paint_rate_grid(50.0, zones, bbox, 10, 10, 2.0)
    assert g.shape == (10, 10)
    assert abs(g[7, 2] - 30.0) < 1e-6   # b wins (last), 60mm/2hr (bottom-left quarter)
    assert abs(g[2, 7] - 100.0) < 1e-6  # a only (top-right)
    # outside both would be base 50: full-bbox a covers all, so check mean instead
    assert abs(g.mean() - (30.0 * 0.25 + 100.0 * 0.75)) < 1.0

def test_zone_at_point():
    from app.services.rainfall_zones import zone_at
    zones = [{"id": "a", "amount": 100, "unit": "rate",
              "polygon": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]}}]
    _za = zone_at(0.5, 0.5, zones)
    assert _za is not None and _za["id"] == "a"
    assert zone_at(5.0, 5.0, zones) is None

def test_zones_cap_enforced():
    from app.models.simulation import Simulation
    import pytest
    from pydantic import ValidationError
    z = [{"id": str(i), "amount": 10, "unit": "rate",
          "polygon": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]}} for i in range(13)]
    with pytest.raises(ValidationError):
        Simulation.model_validate({"name": "z", "area": {"bbox": [80.15, 13.08, 80.20, 13.13], "crs": "EPSG:4326"},
                                   "rainfall": {"rateMmHr": 50, "durationHr": 1, "zones": z}})

def test_zoneless_output_identical():
    import numpy as np
    from app.services.flood import generate_flood
    kw = dict(width=20, height=20, steps=3)
    s1, _, st1 = generate_flood([80.15, 13.08, 80.20, 13.13], {"rateMmHr": 50, "durationHr": 1}, **kw)
    rf = {"rateMmHr": 50, "durationHr": 1, "zones": []}
    s2, _, st2 = generate_flood([80.15, 13.08, 80.20, 13.13], rf, **kw)
    assert st1["totalRainMm"] == st2["totalRainMm"]
    assert np.array_equal(np.asarray(s1), np.asarray(s2))

def test_zoned_storm_wets_zone_more():
    import numpy as np
    from app.services.flood import generate_flood
    poly_w = {"type": "Polygon", "coordinates": [[[80.15, 13.08], [80.175, 13.08], [80.175, 13.13], [80.15, 13.13], [80.15, 13.08]]]}
    rf = {"rateMmHr": 10, "durationHr": 1,
          "zones": [{"id": "w", "amount": 200, "unit": "rate", "polygon": poly_w}]}
    kw = dict(width=20, height=20, steps=3)
    snaps, _, st = generate_flood([80.15, 13.08, 80.20, 13.13], rf, **kw)
    # base run on identical DEM/routing: the bbox drains eastward, so compare
    # the zone footprint against ITSELF under uniform rain (not against east cells)
    base, _, _ = generate_flood([80.15, 13.08, 80.20, 13.13], {"rateMmHr": 10, "durationHr": 1}, **kw)
    last = np.asarray(snaps[-1])
    last_base = np.asarray(base[-1])
    assert last[:, :10].mean() > last_base[:, :10].mean() * 2.0
    assert st["mass_error"] < 0.25
    assert any(z["id"] == "w" for z in st["zones"])

def test_point_query_reports_rainfall_zone():
    from app.services.analysis import point_query
    poly_w = {"type": "Polygon", "coordinates": [[[80.15, 13.08], [80.175, 13.08], [80.175, 13.13], [80.15, 13.13], [80.15, 13.08]]]}
    sim = {"area": {"bbox": [80.15, 13.08, 80.20, 13.13]},
           "rainfall": {"rateMmHr": 10, "durationHr": 1,
                        "zones": [{"id": "w", "amount": 200, "unit": "rate", "polygon": poly_w}]}}
    assert point_query(13.105, 80.16, 0, sim)["rainfallZone"] == "w"
    assert point_query(13.105, 80.19, 0, sim)["rainfallZone"] is None

def test_variable_zone_parses_and_integrates():
    import numpy as np
    from app.services.flood import generate_flood
    poly_w = {"type": "Polygon", "coordinates": [[[80.15, 13.08], [80.175, 13.08], [80.175, 13.13], [80.15, 13.13], [80.15, 13.08]]]}
    rf = {"rateMmHr": 10, "durationHr": 1, "zones": [
        {"id": "wb", "mode": "variable", "unit": "rate", "totalTime": 1, "maxRain": 200,
         "points": [{"time": 0, "amount": 0}, {"time": 0.5, "amount": 200}, {"time": 1, "amount": 0}],
         "polygon": poly_w}]}
    kw = dict(width=20, height=20, steps=6)
    snaps, _, st = generate_flood([80.15, 13.08, 80.20, 13.13], rf, **kw)
    base, _, _ = generate_flood([80.15, 13.08, 80.20, 13.13], {"rateMmHr": 10, "durationHr": 1}, **kw)
    last, lastb = np.asarray(snaps[-1]), np.asarray(base[-1])
    assert last[:, :10].mean() > lastb[:, :10].mean() * 2.0
    assert st["mass_error"] < 0.25
    z = next(z for z in st["zones"] if z["id"] == "wb")
    assert z["mode"] == "variable" and z["peakMmHr"] > z["rateMmHr"] > 0

def test_variable_zone_invalid_points_dropped():
    from app.services.rainfall_zones import parse_zones
    poly = {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]}
    rf = {"rateMmHr": 10, "durationHr": 1, "zones": [
        {"id": "bad", "mode": "variable", "points": [{"time": 0, "amount": 5}], "polygon": poly}]}
    zones, dropped = parse_zones(rf)
    assert zones == [] and dropped == ["bad"]
