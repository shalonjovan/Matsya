"""Live weather sources for the realtime sim.

Swap point for real broadcasts: implement `WeatherSource.fetch` against the
provider API (same return contract) and register it in `_REGISTRY` / extend
`get_source`. The manager never knows which source is active.
"""
import hashlib
from datetime import datetime


class WeatherSource:
    """fetch(window_start, window_end, bbox) -> dict.

    Returns {"rain": [{"t0": iso, "t1": iso, "rateMmHr": float,
    "polygon": GeoJSON|None}], "lakes": [{"id": str, "fillPct": float}],
    "source": str}. Rain polygon None means whole-bbox base rate.
    """

    def fetch(self, window_start: datetime, window_end: datetime, bbox):
        raise NotImplementedError


class DummyWeather(WeatherSource):
    """Deterministic drizzle: zero base, 0-3 small blips (<=1mm/hr, <=10%
    of domain each), lake fills 40-80%. Seeded by the window start hour."""

    def fetch(self, window_start, window_end, bbox):
        try:
            minLon, minLat, maxLon, maxLat = [float(x) for x in bbox]
        except Exception:
            minLon, minLat, maxLon, maxLat = (80.15, 13.08, 80.20, 13.13)
        try:
            _h = window_start.replace(minute=0, second=0, microsecond=0).isoformat()
        except Exception:
            _h = "epoch"
        seed = int(hashlib.md5(_h.encode()).hexdigest()[:8], 16)
        try:
            _t0 = window_start.isoformat()
            _t1 = window_end.isoformat()
        except Exception:
            _t0, _t1 = "", ""
        rain = [{"t0": _t0, "t1": _t1, "rateMmHr": 0.0, "polygon": None}]
        n_blips = seed % 4  # 0-3
        for i in range(n_blips):
            h = hashlib.md5(f"{_h}:blip{i}".encode()).hexdigest()
            n = int(h[:8], 16)
            # blip box: <=10% of domain each axis, placed deterministically
            fx, fy = ((n >> 8) % 80) / 100.0, ((n >> 16) % 80) / 100.0
            w, d = (maxLon - minLon) * 0.1, (maxLat - minLat) * 0.1
            x0 = minLon + fx * (maxLon - minLon - w)
            y0 = minLat + fy * (maxLat - minLat - d)
            rate = 0.3 + ((n >> 24) % 71) / 100.0  # 0.3-1.0
            rate = min(1.0, rate)
            assert 0.0 <= rate <= 1.0
            rain.append({
                "t0": _t0, "t1": _t1, "rateMmHr": round(rate, 2),
                "polygon": {"type": "Polygon", "coordinates": [[
                    [x0, y0], [x0 + w, y0], [x0 + w, y0 + d], [x0, y0 + d], [x0, y0]]]}},
            )
        lakes = []
        for j in range(5):
            h = hashlib.md5(f"{_h}:lake{j}".encode()).hexdigest()
            fill = 40.0 + (int(h[:4], 16) % 4001) / 100.0  # 40-80
            lakes.append({"id": f"lake-{j}", "fillPct": round(fill, 1)})
        assert all(40.0 <= l["fillPct"] <= 80.0 for l in lakes)
        return {"rain": rain, "lakes": lakes, "source": "dummy"}


_REGISTRY = {"dummy": DummyWeather}


def get_source(name="dummy"):
    """Source instance by name (default dummy). Never raises."""
    try:
        cls = _REGISTRY.get(name or "dummy", DummyWeather)
        return cls()
    except Exception:
        return DummyWeather()
