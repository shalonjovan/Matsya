"""Live rainfall forecast (Open-Meteo) with file cache + offline fallback.

Optional input layer only: fills constant rate/duration in the wizard.
Never required: any failure raises ForecastUnavailable (endpoint -> 503).
"""
import json
import pathlib
import time
import urllib.request

CACHE_TTL_S = 24 * 3600


class ForecastUnavailable(Exception):
    pass


def _cache_path(bbox, hours):
    key = "%.3f_%.3f_%.3f_%.3f_%d" % (tuple(float(x) for x in bbox) + (int(hours),))
    import hashlib
    d = pathlib.Path(__file__).parents[2] / "data" / "forecast_cache"
    return d / (hashlib.md5(key.encode()).hexdigest()[:16] + ".json")


def _fetch_open_meteo(lat, lon, hours):
    url = ("https://api.open-meteo.com/v1/forecast?latitude=%.4f&longitude=%.4f"
           "&hourly=precipitation&forecast_days=2&timezone=UTC" % (lat, lon))
    req = urllib.request.Request(url, headers={"User-Agent": "matsya/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def forecast_rain(bbox, hours=6, _fetch=None):
    """Return {source, rateMmHr, durationHr, hourly[], fetched_at, cached}."""
    minLon, minLat, maxLon, maxLat = [float(x) for x in bbox]
    hours = max(1, min(48, int(hours)))
    cp = _cache_path(bbox, hours)
    try:
        if cp.exists() and (time.time() - cp.stat().st_mtime) < CACHE_TTL_S:
            d = json.loads(cp.read_text())
            d["cached"] = True
            return d
    except Exception:
        pass
    lat, lon = (minLat + maxLat) / 2.0, (minLon + maxLon) / 2.0
    try:
        fetch = _fetch or _fetch_open_meteo
        data = fetch(lat, lon, hours)
        hourly = (data.get("hourly") or {}).get("precipitation") or []
        vals = [float(v or 0.0) for v in hourly[:hours]]
        if len(vals) < hours:
            vals += [0.0] * (hours - len(vals))
        peak = max(vals) if vals else 0.0
        out = {"source": "open-meteo", "rateMmHr": round(peak, 1),
               "durationHr": hours,
               "hourly": [{"hour": i, "mm_hr": v} for i, v in enumerate(vals)],
               "lat": round(lat, 4), "lon": round(lon, 4),
               "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "cached": False}
        try:
            cp.parent.mkdir(parents=True, exist_ok=True)
            cp.write_text(json.dumps(out))
        except Exception:
            pass
        return out
    except Exception as e:
        raise ForecastUnavailable("forecast-unavailable: %s. Use constant mode." % e)
