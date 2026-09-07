SIM = {"id": "72b53b60-54ad-4b1b-a500-378498b329c4", "area": {"bbox": [80.15, 13.08, 80.20, 13.13]},
       "rainfall": {"rateMmHr": 50, "durationHr": 1},
       "flood": {"width": 180, "height": 180, "steps": 12,
                 "stats": {"minutesPerFrame": 5.0, "maxDepth": 1.2}}}


def test_affected_areas_computed_not_mock():
    from app.services import analysis
    areas = analysis.affected_areas(SIM)
    assert len(areas) >= 1
    # the exact mock triple must be gone (name + depth + duration fabricated together)
    vel = [a for a in areas if a["name"] == "Velachery"]
    assert not any(v["maxDepth"] == 1.24 and v["duration"] == "3h 12m" for v in vel)
    depths = [a["maxDepth"] for a in areas]
    assert depths == sorted(depths, reverse=True)
    assert all(a["duration"] and a["lat"] and a["lon"] for a in areas)


def test_road_impact_uses_real_names():
    from app.services import analysis
    roads = analysis.road_impact(SIM)
    assert len(roads) >= 1
    assert all(r["name"] and r["id"] not in ("R-GST-1", "R-OMR-2") for r in roads)
    assert all(r["maxDepth"] >= 0 and r["firstFlood"] for r in roads)


def test_drain_impact_no_mock_ids():
    from app.services import analysis
    drains = analysis.drain_impact(SIM)
    assert all(d["id"] not in ("D-42", "D-43") for d in drains)
    assert all(d["capacity"] is None and "overCapacity" in d for d in drains)
