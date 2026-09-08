SIM = "72b53b60-54ad-4b1b-a500-378498b329c4"


def _client():
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


def test_palette_param_serves_variant():
    from PIL import Image
    import io
    c = _client()
    r = c.get(f"/api/simulations/{SIM}/flood?time=0&palette=greenred")
    assert r.status_code == 200, r.text
    img = Image.open(io.BytesIO(r.content))
    assert img.mode == "RGBA"
    r2 = c.get(f"/api/simulations/{SIM}/flood?time=0&palette=blue")
    assert r2.status_code == 200
    assert r.content != r2.content  # genuinely different ramps


def test_default_palette_unchanged_bytes():
    c = _client()
    a = c.get(f"/api/simulations/{SIM}/flood?time=0").content
    b = c.get(f"/api/simulations/{SIM}/flood?time=0&palette=blue").content
    assert a == b  # legacy fast path preserved


def test_near_zero_depth_transparent():
    from PIL import Image
    import io
    import numpy as np
    from app.services.flood import render_depth_png
    depth = np.zeros((10, 10), dtype=np.float32)
    depth[5, 5] = 1.0
    for pal in ("blue", "greenred"):
        img = Image.open(io.BytesIO(render_depth_png(depth, {"maxDepth": 1.0}, pal)))
        assert img.mode == "RGBA"
        assert img.getpixel((0, 0))[3] == 0  # dry cell fully transparent
        assert img.getpixel((5, 5))[3] == 255  # wet cell opaque


def test_unknown_palette_400():
    c = _client()
    r = c.get(f"/api/simulations/{SIM}/flood?time=0&palette=neon")
    assert r.status_code == 400
