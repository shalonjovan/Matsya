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
        _ids = _real_lake_ids() or []
        for j in range(5):
            h = hashlib.md5(f"{_h}:lake{j}".encode()).hexdigest()
            fill = 40.0 + (int(h[:4], 16) % 4001) / 100.0  # 40-80
            _lid = _ids[j % len(_ids)] if _ids else f"lake-{j}"
            lakes.append({"id": str(_lid), "fillPct": round(fill, 1)})
        assert all(40.0 <= l["fillPct"] <= 80.0 for l in lakes)
        return {"rain": rain, "lakes": lakes, "source": "dummy"}


_LAKE_IDS: list | None = None


def _real_lake_ids():
    """Asset lake ids (cached). None when assets unavailable (fallback ids used)."""
    global _LAKE_IDS
    try:
        if _LAKE_IDS is not None:
            return _LAKE_IDS
        from app.services.hydro.asset_loader import load_assets
        gdf = load_assets("assets").get("waterbodies")
        ids = []
        if gdf is not None:
            for _, row in gdf.iterrows():
                try:
                    _id = row.get("id", None) if hasattr(row, "get") else None
                    ids.append(str(_id) if _id is not None else None)
                except Exception:
                    continue
        ids = [i for i in ids if i]
        _LAKE_IDS = ids or None
        return _LAKE_IDS
    except Exception:
        return None


_REGISTRY: dict = {"dummy": DummyWeather}


def _default_fetch(url, timeout=15):
    import json
    import urllib.request
    with urllib.request.urlopen(url, timeout=timeout) as res:
        return json.loads(res.read().decode("utf-8"))


class OpenMeteoWeather(WeatherSource):
    """Real precipitation from Open-Meteo Forecast API (no key, non-commercial).

    Fetches hourly `precipitation` (preceding-hour mm = mm/hr) for a grid
    over the bbox with past_days=1 + forecast_days=1, slices the tick window,
    and emits one variable-curve zone per grid cell. Lake levels are NOT
    published by Open-Meteo, so lakes come back empty (global fill default).
    """

    BASE = "https://api.open-meteo.com/v1/forecast"

    def __init__(self, timeout=15, grid=3, cache_s=300, _fetch=None):
        self.timeout = timeout
        self.grid = max(1, min(5, int(grid or 3)))
        self.cache_s = max(0, int(cache_s or 0))
        self._fetch = _fetch or _default_fetch
        self._cache = {}

    def _grid_points(self, bbox):
        minLon, minLat, maxLon, maxLat = [float(x) for x in bbox]
        pts = []
        for i in range(self.grid):
            for j in range(self.grid):
                pts.append((minLon + (i + 0.5) / self.grid * (maxLon - minLon),
                            minLat + (j + 0.5) / self.grid * (maxLat - minLat)))
        return pts

    def _cell_polygon(self, bbox, lon, lat):
        minLon, minLat, maxLon, maxLat = [float(x) for x in bbox]
        w, d = (maxLon - minLon) / self.grid, (maxLat - minLat) / self.grid
        x0 = max(minLon, lon - w / 2.0)
        x1 = min(maxLon, lon + w / 2.0)
        y0 = max(minLat, lat - d / 2.0)
        y1 = min(maxLat, lat + d / 2.0)
        ring = [[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]
        return {"type": "Polygon", "coordinates": [ring]}

    def fetch(self, window_start, window_end, bbox):
        import time as _time
        try:
            minLon, minLat, maxLon, maxLat = [float(x) for x in bbox]
        except Exception:
            minLon, minLat, maxLon, maxLat = (80.15, 13.08, 80.20, 13.13)
            bbox = [minLon, minLat, maxLon, maxLat]
        try:
            _ck = (window_start.replace(minute=0, second=0, microsecond=0).isoformat(),
                   round(minLon, 3), round(minLat, 3), round(maxLon, 3), round(maxLat, 3))
        except Exception:
            _ck = ("epoch",)
        now_s = _time.time()
        try:
            _ts, _cached = self._cache.get(_ck, (0, None))
            if _cached is not None and (now_s - _ts) < self.cache_s:
                return _cached
        except Exception:
            pass
        pts = self._grid_points(bbox)
        lats = ",".join(f"{la:.4f}" for _, la in pts)
        lons = ",".join(f"{lo:.4f}" for lo, _ in pts)
        url = (f"{self.BASE}?latitude={lats}&longitude={lons}"
               f"&hourly=precipitation&past_days=1&forecast_days=2&timezone=UTC")
        # NOTE: timezone=UTC (not auto) so the naive ISO timestamps Open-Meteo
        # returns are truly UTC and window slicing needs no offset math.
        # forecast_days=2 (not 1: that ends at today 23:59): the +12h half of
        # the tick window must exist even late in the UTC day.
        raw = self._fetch(url, timeout=self.timeout)
        blocks = raw if isinstance(raw, list) else [raw]
        try:
            _w0 = window_start.timestamp() if hasattr(window_start, "timestamp") else 0
            _w1 = window_end.timestamp() if hasattr(window_end, "timestamp") else 0
        except Exception:
            _w0, _w1 = 0, 0
        rain = []
        for i, (_lon, _lat) in enumerate(pts):
            try:
                blk = blocks[i] if i < len(blocks) else {}
                hourly = (blk or {}).get("hourly") or {}
                times = hourly.get("time") or []
                vals = hourly.get("precipitation") or []
                points = []
                for t, v in zip(times, vals):
                    try:
                        import datetime as _dt
                        _tt = _dt.datetime.fromisoformat(str(t))
                        if _tt.tzinfo is None:
                            _tt = _tt.replace(tzinfo=_dt.timezone.utc)
                        _ts = _tt.timestamp()
                    except Exception:
                        continue
                    if not (_w0 <= _ts < _w1):
                        continue
                    try:
                        _v = float(v) if v is not None else 0.0
                    except Exception:
                        _v = 0.0
                    points.append({"time": round((_ts - _w0) / 3600.0, 2),
                                   "amount": round(max(0.0, _v), 2)})
                if not points:
                    continue
                rain.append({
                    "id": f"om-{i}", "mode": "variable", "unit": "rate",
                    "totalTime": round((_w1 - _w0) / 3600.0, 2),
                    "maxRain": max([p["amount"] for p in points] + [0.0]),
                    "points": points,
                    "polygon": self._cell_polygon(bbox, _lon, _lat),
                })
            except Exception:
                continue
        out = {"rain": rain, "lakes": [], "source": "openmeteo"}
        try:
            self._cache[_ck] = (now_s, out)
        except Exception:
            pass
        return out


_REGISTRY["openmeteo"] = OpenMeteoWeather


def get_source(name="dummy"):
    """Source instance by name (default dummy). Never raises."""
    try:
        cls = _REGISTRY.get(name or "dummy", DummyWeather)
        return cls()
    except Exception:
        return DummyWeather()


def is_known(name):
    """True when name is a registered source."""
    try:
        return str(name or "") in _REGISTRY
    except Exception:
        return False
