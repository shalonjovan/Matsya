def test_clip_and_render():
    from app.services.elevation import clip_and_render
    arr, png, stats = clip_and_render([80.15,13.08,80.20,13.13], 180, 180)
    assert arr.shape == (180,180)
    assert stats["min"] < stats["max"]
    assert 0 < stats["mean"] < 100
    assert stats["min"] >= -10 and stats["max"] <= 100
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    from app.services.elevation import hypsometric_color
    c_low = hypsometric_color(stats["min"], stats["min"], stats["max"])
    c_high = hypsometric_color(stats["max"], stats["min"], stats["max"])
    assert c_low != c_high

def test_clip_different_bbox():
    from app.services.elevation import clip_and_render
    arr1, _, s1 = clip_and_render([80.15,13.08,80.20,13.13], 10, 10)
    arr2, _, s2 = clip_and_render([80.25,13.00,80.30,13.05], 10, 10)
    assert s1["mean"] != s2["mean"] or s1["min"] != s2["min"]

def test_sample():
    from app.services.elevation import sample_dem
    elev = sample_dem(80.17, 13.08)
    assert elev is not None and -10 < elev < 100
    # ocean should be maybe nan/None or negative, but not crash
    elev2 = sample_dem(80.25, 13.02)  # Bay
    assert elev2 is None or -500 < elev2 < 100  # allow ocean
