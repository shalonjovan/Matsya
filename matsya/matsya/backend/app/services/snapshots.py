"""Shared snapshot-stack loader for analysis services.

Extracted so new code (segments, routes, alerts) shares one path instead of
copying the store-.npy-else-regen block a fourth time. point_query and the
Phase-0 functions keep their inline copies — working code stays untouched.
"""
from typing import Any


def load_snapshots(sim: Any):
    """Return (snaps list of arrays, minutesPerFrame, bbox). snaps None on total failure."""
    bbox = [80.15, 13.08, 80.20, 13.13]
    try:
        if isinstance(sim, dict):
            bbox = sim.get("area", {}).get("bbox", bbox)
        elif hasattr(sim, "area"):
            _a = sim.area
            bbox = _a.bbox if hasattr(_a, "bbox") else _a.get("bbox", bbox)
    except Exception:
        pass
    mpf = 5.0
    try:
        _f = sim.get("flood") if isinstance(sim, dict) else getattr(sim, "flood", None)
        _st = (_f.get("stats") if isinstance(_f, dict) else getattr(_f, "stats", None)) or {}
        if isinstance(_st, dict) and _st.get("minutesPerFrame"):
            mpf = float(_st["minutesPerFrame"])
    except Exception:
        pass
    try:
        import numpy as _np
        from app.services.simulation_store import store as _store
        _sid = sim.get("id") if isinstance(sim, dict) else getattr(sim, "id", None)
        _npy = _store.base_path / f"{_sid}" / "flood" / "snapshots.npy" if _sid else None
        if _npy is not None and _npy.exists():
            return [a for a in _np.load(str(_npy))], mpf, list(bbox)
    except Exception:
        pass
    try:
        from app.services.flood import generate_flood
        _rf = sim.get("rainfall", {}) if isinstance(sim, dict) else getattr(sim, "rainfall", {})
        _rf = dict(_rf) if isinstance(_rf, dict) else {"rateMmHr": 50, "durationHr": 1}
        _fill = 75.0
        try:
            _p = sim.get("parameters") if isinstance(sim, dict) else getattr(sim, "parameters", None)
            _fill = _p.get("initialFillPct", 75.0) if isinstance(_p, dict) else getattr(_p, "initialFillPct", 75.0)
        except Exception:
            pass
        snaps, _, _ = generate_flood(list(bbox), _rf, width=60, height=60, steps=6,
                                     initial_fill_pct=_fill)
        return [a for a in snaps], mpf, list(bbox)
    except Exception:
        return None, mpf, list(bbox)
