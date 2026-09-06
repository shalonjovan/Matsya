"""SWMM <-> river backwater iteration (Phase 4).

Lumped, documented scope: all SWMM outfalls share one representative river
reach (longest in bbox); river stage from Manning normal depth at routed
flow; SWMM re-runs with FIXED outfall stages, damped until convergence.
Proves the choking mechanism; per-reach mapping is future work.
"""
import tempfile

DAMPING = 0.5
TOL_M = 0.05
MAX_ROUNDS = 5
MANNING_N = 0.035
RIVER_INVERT_M = 5.0


def normal_depth_m(q_cms, width_m=5.0, slope=0.001, n=MANNING_N):
    """Trapezoidal 1:1 normal depth by bisection. Returns meters."""
    import math
    q = max(0.0, float(q_cms or 0.0))
    if q <= 0:
        return 0.0
    w = max(1.0, float(width_m or 5.0))
    s = max(0.0002, min(0.02, float(slope or 0.001)))
    n = max(0.008, float(n or MANNING_N))

    def flow_at(d):
        a = d * (w + d)
        p = w + 2.0 * d * math.sqrt(2.0)
        r = a / p if p > 0 else 0.0
        return (1.0 / n) * a * (r ** (2.0 / 3.0)) * math.sqrt(s)

    lo, hi = 1e-4, 50.0
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if flow_at(mid) < q:
            lo = mid
        else:
            hi = mid
    return round(0.5 * (lo + hi), 4)


def iterate_backwater(bbox, rainfall, opts=None):
    """Iterate SWMM outfall stages against river stage. See module docstring."""
    from app.services.engine.swmm_runner import drains_for_bbox, run_network_sync
    from app.services.hydro.river_capacity import build_reaches
    opts = opts or {}
    forced = opts.get("force_river_stage_m")
    workdir = tempfile.mkdtemp(prefix="backwater-")
    drains = drains_for_bbox(list(bbox))
    if not drains:
        return {"converged": False, "drain_outflow_m3": 0.0, "river_stages": [],
                "rounds": 0, "audit": {"mode": "blocked-no-drains-in-bbox"}}

    def _river_reach():
        try:
            reaches = build_reaches(list(bbox), max_n=10) or []
        except Exception:
            reaches = []
        if not reaches:
            return {"length_m": 2000.0, "slope": 0.001, "width_m": 5.0,
                    "source": "assumed-defaults"}
        rep = max(reaches, key=lambda r: r.get("length_m", 0))
        return {"length_m": rep.get("length_m", 2000.0), "slope": rep.get("slope", 0.001),
                "width_m": rep.get("width_m", 5.0),
                "source": rep.get("source", "assumed-defaults")}

    reach = _river_reach()
    # outfall inverts follow junctions in swmm_inp (z1 - 2%*50m, floor 0);
    # river invert tracks their mean so FIXED stages sit in a sane datum
    try:
        _zs = [max(0.0, float(d.get("z1", 10.0)) - 1.0) for d in drains]
        river_invert = round(sum(_zs) / len(_zs), 2) if _zs else RIVER_INVERT_M
    except Exception:
        river_invert = RIVER_INVERT_M
    last_flood_vol = 0.0
    stages, outflows = [], []
    # round 0: FREE outfalls (today's behavior, byte-identical INP)
    base = run_network_sync(drains, rainfall or {}, workdir + "/r0")
    if not base.get("solved"):
        return {"converged": False, "drain_outflow_m3": 0.0, "node_flood_volume_m3": 0.0,
                "river_stages": [], "rounds": 0, "audit": {"mode": "solver-failed-round-0"}}
    last_out = float(base.get("outfall_volume_m3", 0.0))
    last_flood_vol = round(sum(v.get("volume_m3", 0) for v in base.get("node_flood", {}).values()), 1)

    def _stage_for(outflow_m3, duration_hr):
        if forced is not None:
            return float(forced)
        q = outflow_m3 / max(1.0, float(duration_hr) * 3600.0)
        return river_invert + normal_depth_m(q, reach["width_m"], reach["slope"])

    try:
        _dur = float((rainfall or {}).get("durationHr") or (rainfall or {}).get("totalTime") or 1.0)
    except Exception:
        _dur = 1.0
    stage = _stage_for(last_out, _dur)
    stages.append(round(stage, 3))
    outflows.append(round(last_out, 1))

    converged = True
    for _ in range(1, MAX_ROUNDS + 1):
        stages_in = {i: stage for i in range(len(drains))}
        res = run_network_sync(drains, rainfall or {}, workdir + "/r%d" % _, outfall_stages=stages_in)
        if not res.get("solved"):
            converged = False
            break
        last_out = float(res.get("outfall_volume_m3", 0.0))
        last_flood_vol = round(sum(v.get("volume_m3", 0) for v in res.get("node_flood", {}).values()), 1)
        outflows.append(round(last_out, 1))
        new_stage = _stage_for(last_out, _dur)
        if forced is None:
            new_stage = DAMPING * stage + (1.0 - DAMPING) * new_stage
        if abs(new_stage - stage) < TOL_M:
            stage = round(new_stage, 3)
            stages.append(stage)
            converged = True
            break
        stage = round(new_stage, 3)
        stages.append(stage)
        converged = False

    return {"converged": bool(converged), "drain_outflow_m3": round(last_out, 1),
            "node_flood_volume_m3": last_flood_vol,
            "river_stages": stages, "rounds": len(stages),
            "audit": {"mode": "lumped-representative-reach",
                      "reach": reach, "forced_stage_m": forced}}
