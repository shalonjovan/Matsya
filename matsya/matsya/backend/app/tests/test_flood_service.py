def test_generate_flood():
    from app.services.flood import generate_flood, depth_color
    snaps, pngs, stats = generate_flood([80.15,13.08,80.20,13.13], {"rateMmHr":50,"durationHr":1}, width=10, height=10, steps=3)
    assert len(snaps)==3 and snaps[0].shape==(10,10)
    assert stats["maxDepth"] > 0
    assert pngs[0][:8]==b"\x89PNG\r\n\x1a\n"
    assert depth_color(0, stats)[0] != depth_color(stats["maxDepth"], stats)[0]

def test_different_bbox_rainfall():
    from app.services.flood import generate_flood
    _, _, s1 = generate_flood([80.15,13.08,80.20,13.13], {"rateMmHr":50,"durationHr":1}, width=10, height=10, steps=2)
    _, _, s2 = generate_flood([80.25,13.00,80.30,13.05], {"rateMmHr":100,"durationHr":2}, width=10, height=10, steps=2)
    assert s1["maxDepth"] != s2["maxDepth"] or s1["floodedArea"] != s2["floodedArea"]
