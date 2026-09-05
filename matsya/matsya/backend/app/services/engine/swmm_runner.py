"""Real SWMM engine behind the run contract (Slice 1). Mirrors anuga_runner shapes."""
import threading
import time
import uuid
import json
import pathlib
from datetime import datetime, timezone

from app.services.engine import swmm_inp

_runs: dict = {}


def _parse_flooding(rpt_path):
    """Return (flooded_node_count, total_flood_volume_m3) from Node Flooding Summary."""
    try:
        text = pathlib.Path(rpt_path).read_text(errors="ignore")
    except Exception:
        return 0, 0.0
    i = text.find("Node Flooding Summary")
    if i < 0 or "No nodes were flooded" in text[i:i + 600]:
        return 0, 0.0
    count, vol = 0, 0.0
    for line in text[i:].splitlines()[6:60]:
        parts = line.split()
        if len(parts) >= 6 and parts[0][0] in "JN":
            try:
                count += 1
                vol += float(parts[5])
            except ValueError:
                continue
    return count, vol


def run_simulation(sim_id: str, sim: dict) -> str:
    run_id = str(uuid.uuid4())
    _runs[run_id] = {"runId": run_id, "simId": sim_id, "engine": "swmm",
                     "status": "Running", "progress": 10,
                     "created": datetime.now(timezone.utc).isoformat()}
    payload = dict(sim)

    def bg():
        try:
            drains = payload.get("_test_drains")
            if drains is None:
                drains = []  # Task 3 wires real bbox drains; empty => honest fail
            rainfall = payload.get("rainfall") or {}
            audit = swmm_inp.audit_inputs(drains, rainfall)
            _runs[run_id]["audit"] = audit
            _runs[run_id]["progress"] = 30
            if not audit["ready"]:
                _runs[run_id].update({"status": "Failed",
                                      "error": audit["mode"] + ": " + "; ".join(audit["missing"])})
                return
            outdir = pathlib.Path(__file__).parents[2] / "data" / "runs" / run_id
            outdir.mkdir(parents=True, exist_ok=True)
            inp = swmm_inp.build_inp(drains, rainfall,
                                     (payload.get("area") or {}).get("bbox", [80.15, 13.08, 80.20, 13.13]),
                                     str(outdir / "network.inp"))
            _runs[run_id].update({"inp": inp, "progress": 50})
            from pyswmm import Simulation, Links, Nodes
            peak_flow, peak_flood = 0.0, 0.0
            times = []
            with Simulation(inp) as sim_obj:
                links, nodes = Links(sim_obj), Nodes(sim_obj)
                step_times = []
                for step in sim_obj:
                    try:
                        step_times.append(sim_obj._model.getCurrentSimulationTime() if hasattr(sim_obj._model, "getCurrentSimulationTime") else len(step_times) * 300)
                    except Exception:
                        step_times.append(len(step_times) * 300)
                    for lid in list(links)[:50]:
                        try:
                            f = abs(links[lid].flow)
                            peak_flow = max(peak_flow, f)
                        except Exception:
                            pass
                    for nid in list(nodes)[:60]:
                        try:
                            peak_flood = max(peak_flood, nodes[nid].flooding or 0)
                        except Exception:
                            pass
                times = step_times
            _runs[run_id]["progress"] = 90
            rpt = inp.replace(".inp", ".rpt")
            n_count, n_vol = _parse_flooding(rpt)
            solved = "Analysis ended" in pathlib.Path(rpt).read_text(errors="ignore")
            stats = {"solved": bool(solved), "floodedNodeCount": n_count,
                     "totalFloodVolumeM3": round(n_vol, 2),
                     "peakLinkFlowCMS": round(peak_flow, 4),
                     "peakFloodRateCMS": round(peak_flood, 4), "engine": "swmm"}
            stride = max(1, len(times) // 73)
            _runs[run_id].update({"status": "Completed", "progress": 100,
                                  "results": {"times": times[::stride][:73] if times else [],
                                              "stats": stats},
                                  "rpt": rpt})
        except Exception as e:
            _runs[run_id].update({"status": "Failed", "error": "swmm-error: %s" % e})
    threading.Thread(target=bg, daemon=True).start()
    return run_id


def get_run(run_id: str):
    return _runs.get(run_id)


def list_runs(sim_id: str):
    return [r for r in _runs.values() if r["simId"] == sim_id]
