def test_coupled_mass_and_wb():
    from app.services.flood import generate_flood
    snaps, pngs, stats = generate_flood([80.15, 13.08, 80.20, 13.13], {"rateMmHr": 100, "durationHr": 2}, width=20, height=20, steps=3)
    assert stats["maxDepth"] > 0
    assert "mass_error" in stats and stats["mass_error"] < 0.25
    assert "wbCount" in stats and "surchargedDrains" in stats
    assert pngs[0][:8] == b"\x89PNG\r\n\x1a\n"


def test_heavier_rain_deeper_or_wider():
    from app.services.flood import generate_flood
    _, _, s1 = generate_flood([80.15, 13.08, 80.20, 13.13], {"rateMmHr": 20, "durationHr": 1}, width=20, height=20, steps=3)
    _, _, s2 = generate_flood([80.15, 13.08, 80.20, 13.13], {"rateMmHr": 120, "durationHr": 2}, width=20, height=20, steps=3)
    assert s2["maxDepth"] >= s1["maxDepth"]
    assert s2["totalRainMm"] > s1["totalRainMm"]
