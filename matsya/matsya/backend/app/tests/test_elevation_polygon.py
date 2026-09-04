def test_clip_polygon():
    from app.services.elevation import clip_and_render
    poly = {"type":"Polygon","coordinates":[[[80.15,13.08],[80.20,13.08],[80.20,13.13],[80.15,13.13],[80.15,13.08]]]}
    arr, png, stats = clip_and_render([80.15,13.08,80.20,13.13], polygon=poly, width=10, height=10)
    assert arr.shape == (10,10)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    poly2 = {"type":"Polygon","coordinates":[[[80.25,13.00],[80.30,13.00],[80.30,13.05],[80.25,13.05],[80.25,13.00]]]}
    arr2, _, s2 = clip_and_render([80.25,13.00,80.30,13.05], polygon=poly2, width=10, height=10)
    assert stats["mean"] != s2["mean"]

def test_clip_polygon_bbox_fallback():
    from app.services.elevation import clip_and_render
    # No polygon should still work (bbox only)
    arr, png, stats = clip_and_render([80.15,13.08,80.20,13.13], width=10, height=10)
    assert arr.shape == (10,10)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
