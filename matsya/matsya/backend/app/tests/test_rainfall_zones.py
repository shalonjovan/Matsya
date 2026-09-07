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
    assert zone_at(0.5, 0.5, zones)["id"] == "a"
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
