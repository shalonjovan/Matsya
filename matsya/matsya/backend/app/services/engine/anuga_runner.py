
import threading, time, uuid, json, pathlib
from datetime import datetime, timezone
import numpy as np

# In-memory run store
_runs: dict = {}

def _mock_snapshots(rows=180, cols=180, steps=73):
    # generate synthetic depth snapshots for demo (quantized mock)
    snaps = []
    for t in range(steps):
        # wave: depth increases then drains
        base = 0.3 * np.sin(np.pi * t/steps) + 0.1
        arr = np.random.rand(rows, cols).astype(np.float32) * base
        # add hot spot at center
        arr[80:100,80:100] += base*2
        snaps.append(arr)
    times = [i*300 for i in range(steps)]  # 5 min steps
    stats = {"maxDepth": float(np.max(snaps[-1])), "floodedArea": float(np.sum(snaps[-1]>0.05)*900/1e6), "maxVelocity":0.8}
    return snaps, times, stats

def run_simulation(sim_id: str, sim: dict) -> str:
    run_id = str(uuid.uuid4())
    _runs[run_id] = {"runId": run_id, "simId": sim_id, "status":"Running", "progress":0, "created": datetime.now(timezone.utc).isoformat()}
    def bg():
        time.sleep(0.5)  # quick mock
        for p in [30,60,90,100]:
            _runs[run_id]["progress"]=p
            time.sleep(0.4)
        snaps, times, stats = _mock_snapshots()
        _runs[run_id]["status"]="Completed"
        _runs[run_id]["progress"]=100
        _runs[run_id]["results"]={"times":times, "stats":stats}
        # optionally save to disk
        outdir = pathlib.Path(__file__).parents[2] / "data" / "runs" / run_id
        outdir.mkdir(parents=True, exist_ok=True)
        try:
            np.save(outdir / "snapshots.npy", np.array(snaps))
            (outdir / "stats.json").write_text(json.dumps(stats))
        except: pass
    threading.Thread(target=bg, daemon=True).start()
    return run_id

def get_run(run_id: str):
    return _runs.get(run_id)

def list_runs(sim_id: str):
    return [r for r in _runs.values() if r["simId"]==sim_id]
