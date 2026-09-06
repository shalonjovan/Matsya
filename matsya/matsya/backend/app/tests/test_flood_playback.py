def test_playback_steps_rule():
    from app.services.flood import _playback_steps, _playback_minutes_per_frame
    assert _playback_steps(1.0) == 6      # 10 min/frame
    assert _playback_steps(2.0) == 8      # 15 min/frame
    assert _playback_steps(6.0) == 24     # 15 min/frame
    assert _playback_steps(30.0) == 73    # capped
    assert _playback_steps(0) == 6        # floored
    assert abs(_playback_minutes_per_frame(2.0, 8) - 15.0) < 1e-9

def test_ensure_flood_writes_version_and_npy(tmp_path):
    from app.services.flood import ensure_flood
    import json, numpy as np
    from app.models.simulation import Simulation
    sim = Simulation.model_validate({"name": "pb", "area": {"bbox": [80.15, 13.08, 80.20, 13.13], "crs": "EPSG:4326"},
                                     "rainfall": {"rateMmHr": 100, "durationHr": 2}})
    ensure_flood(sim, width=10, height=10)
    from app.services.simulation_store import store
    fj = json.loads((store.base_path / sim.id / "flood" / "flood.json").read_text())
    assert fj["floodVersion"] == 2 and fj["steps"] == 8
    assert abs(fj["minutesPerFrame"] - 15.0) < 1e-9
    arr = np.load(store.base_path / sim.id / "flood" / "snapshots.npy")
    assert arr.shape == (8, 10, 10)

def test_frames_are_distinct():
    from app.services.flood import generate_flood
    import numpy as np
    snaps, _, _ = generate_flood([80.15, 13.08, 80.20, 13.13], {"rateMmHr": 100, "durationHr": 2},
                                 width=10, height=10, steps=8)
    assert len(snaps) == 8
    assert not np.allclose(snaps[0], snaps[-1])
