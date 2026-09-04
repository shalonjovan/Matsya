"""Rainfall curve interpolation — smooth spline, rate/total toggle, random presets."""
import math
import random
from typing import List, Dict, Any

def _linear_interpolate(points: List[Dict[str, float]], times: List[float]) -> List[float]:
    # Simple linear interpolation between sorted points
    points_sorted = sorted(points, key=lambda p: p["time"])
    res=[]
    for t in times:
        # Find segment
        for i in range(len(points_sorted)-1):
            p0, p1 = points_sorted[i], points_sorted[i+1]
            if p0["time"] <= t <= p1["time"]:
                # linear
                span = p1["time"] - p0["time"]
                if span == 0:
                    res.append(p0["amount"])
                else:
                    frac = (t - p0["time"]) / span
                    res.append(p0["amount"]*(1-frac) + p1["amount"]*frac)
                break
        else:
            # beyond last point, clamp to last
            if t < points_sorted[0]["time"]:
                res.append(points_sorted[0]["amount"])
            else:
                res.append(points_sorted[-1]["amount"])
    return res

def _spline_interpolate(points: List[Dict[str, float]], times: List[float]) -> List[float]:
    # Try CubicSpline, fallback to linear
    try:
        from scipy.interpolate import CubicSpline
        import numpy as np
        xs = [p["time"] for p in sorted(points, key=lambda p: p["time"])]
        ys = [p["amount"] for p in sorted(points, key=lambda p: p["time"])]
        # Need at least 2 points, and for CubicSpline at least 4 for good, but we can use with bc_type
        if len(xs) < 2:
            return [ys[0] if ys else 0]*len(times)
        # If only 2-3 points, use linear to avoid overshoot
        if len(xs) < 4:
            return _linear_interpolate(points, times)
        cs = CubicSpline(xs, ys, bc_type='natural', extrapolate=True)
        vals = cs(times)
        return [float(v) for v in vals]
    except ImportError:
        # Fallback to linear
        return _linear_interpolate(points, times)
    except Exception:
        return _linear_interpolate(points, times)

def interpolate(points: List[Dict[str, float]], totalTime: float, maxRain: float, unit: str = "rate", steps: int = 72) -> Dict[str, Any]:
    """
    Interpolate points to values per step.
    points: [{time, amount}] where time in hours, amount in mm/hr (rate) or mm total
    totalTime: total duration hours
    maxRain: max y
    unit: "rate" or "total"
    steps: number of steps (e.g., totalTime*12 for 300s steps over 6hr)
    Returns: {values: number[steps], method:"spline", unit, totalTime, maxRain}
    values are rate mm/hr per step
    """
    if not points:
        points = [{"time":0,"amount":0}]
    # Sort and clamp
    points = sorted(points, key=lambda p: p["time"])
    # Clamp points to bounds
    clamped=[]
    for p in points:
        t = max(0, min(totalTime, float(p["time"])))
        a = max(0, min(maxRain, float(p["amount"])))
        clamped.append({"time": t, "amount": a})
    # Ensure start at 0 and end at totalTime
    if clamped[0]["time"] != 0:
        clamped.insert(0, {"time":0, "amount": clamped[0]["amount"]})
    if clamped[-1]["time"] != totalTime:
        clamped.append({"time": totalTime, "amount": clamped[-1]["amount"]})

    # Generate times for steps
    dt = totalTime / steps if steps>0 else totalTime
    times = [i*dt for i in range(steps)]

    if unit == "total":
        # Interpret amount as cumulative total mm, interpolate total, then derive rate
        # Interpolate total
        totals = _spline_interpolate(clamped, times)
        # Clamp total to 0..maxRain*totalTime? Actually total should be 0..maxRain*totalTime, but maxRain is max total, so clamp
        # For total mode, maxRain is max total mm
        totals = [max(0, min(maxRain*2, v)) for v in totals]  # allow up to 2*maxRain for safety
        # Derive rate: rate = d(total)/dt
        values=[]
        for i, t in enumerate(times):
            if i==0:
                # rate at t0 is 0 or first total/dt
                rate = totals[0] / dt if dt!=0 else 0
            else:
                rate = (totals[i] - totals[i-1]) / dt if dt!=0 else 0
            # Clamp rate to 0..maxRain*2? But maxRain for total mode is max total, rate could be higher
            # For total mode, maxRain is max total, so rate max is maxRain/totalTime*2
            values.append(max(0, rate))
        # Clamp values to 0..maxRain (for rate, maxRain is max rate, but for total mode maxRain is max total, so rate max is ambiguous)
        # We clamp to 0..maxRain*2 for total mode? Keep as is
    else:
        # rate mode: amount is rate
        values = _spline_interpolate(clamped, times)
        values = [max(0, min(maxRain, v)) for v in values]

    return {"values": values, "method": "spline", "unit": unit, "totalTime": totalTime, "maxRain": maxRain, "points": clamped}

def sample(values: List[float], totalTime: float, time: float) -> float:
    """Sample interpolated values at a specific time."""
    if not values:
        return 0
    steps = len(values)
    dt = totalTime / steps if steps>0 else 1
    idx = int(time / dt)
    idx = max(0, min(steps-1, idx))
    return values[idx]

def random_preset(preset: str, totalTime: float, maxRain: float, unit: str = "rate") -> List[Dict[str, float]]:
    """Generate random preset points."""
    import random
    # Use fixed seed for deterministic? No, random
    if preset == "burst":
        # High early, then decay
        return [
            {"time": 0, "amount": 0},
            {"time": totalTime*0.1, "amount": maxRain*0.9},
            {"time": totalTime*0.3, "amount": maxRain*0.4},
            {"time": totalTime*0.6, "amount": maxRain*0.2},
            {"time": totalTime, "amount": 0},
        ]
    elif preset == "gradual":
        # Linear ramp
        return [
            {"time": 0, "amount": 0},
            {"time": totalTime*0.3, "amount": maxRain*0.3},
            {"time": totalTime*0.6, "amount": maxRain*0.6},
            {"time": totalTime, "amount": maxRain*0.8},
        ]
    elif preset == "double-peak":
        # Two humps
        return [
            {"time": 0, "amount": 0},
            {"time": totalTime*0.2, "amount": maxRain*0.8},
            {"time": totalTime*0.5, "amount": maxRain*0.2},
            {"time": totalTime*0.7, "amount": maxRain*0.9},
            {"time": totalTime, "amount": 0},
        ]
    elif preset == "random":
        # 5 random points sorted
        pts = [{"time": 0, "amount": random.uniform(0, maxRain*0.5)}]
        for _ in range(3):
            pts.append({"time": random.uniform(0.1, totalTime*0.9), "amount": random.uniform(0, maxRain)})
        pts.append({"time": totalTime, "amount": random.uniform(0, maxRain*0.3)})
        pts = sorted(pts, key=lambda p: p["time"])
        # Ensure sorted and clamp
        for p in pts:
            p["time"] = max(0, min(totalTime, p["time"]))
            p["amount"] = max(0, min(maxRain, p["amount"]))
        return pts
    else:
        # default random
        return random_preset("random", totalTime, maxRain, unit)
