#!/usr/bin/env python3
import pathlib, json, numpy as np, rasterio
BASE=pathlib.Path(__file__).parent.parent
INPUT=BASE/"input"
OUTPUT=BASE/"output/V0"
VIZ=BASE/"visualization"
BBOX=(80.15,13.08,80.20,13.13)

# Load
snap=np.load(OUTPUT/"snapshots.npy") # 73,180,180
vel_u=np.load(OUTPUT/"vel_u.npy")
vel_v=np.load(OUTPUT/"vel_v.npy")
times=np.load(OUTPUT/"times.npy")
print(f"snap {snap.shape} vel {vel_u.shape}")

# Quantize depth 0-2m -> 0-255
depth_q=np.clip(snap/2.0*255,0,255).astype(np.uint8)
# Velocity -2 to 2 m/s -> 0-255
vel_q_u=np.clip((vel_u+2)/4*255,0,255).astype(np.uint8)
vel_q_v=np.clip((vel_v+2)/4*255,0,255).astype(np.uint8)
# Save web JSON in quantized + base64? For now save as nested lists with uint8 -> smaller
# We'll save as JSON with base64 compressed via Python's json + zlib? Simpler: save as JSON with list per snapshot as flat list
# To keep size moderate, save depth_q as list of lists
import base64, zlib
# Option: save depth_q as base64 per snapshot
def encode(arr):
    # arr is uint8 2D
    b=zlib.compress(arr.tobytes())
    return base64.b64encode(b).decode()

web={
    "bbox": BBOX,
    "rows": snap.shape[1],
    "cols": snap.shape[2],
    "dx": 30,
    "times": times.tolist(),
    "depth_scale": 2.0/255,
    "vel_scale": 4/255,
    "vel_offset": -2,
    "snapshots_b64": [encode(depth_q[i]) for i in range(depth_q.shape[0])],
    "vel_u_b64": [encode(vel_q_u[i]) for i in range(vel_q_u.shape[0])],
    "vel_v_b64": [encode(vel_q_v[i]) for i in range(vel_q_v.shape[0])],
    "stats": json.loads((OUTPUT/"stats.json").read_text()) if (OUTPUT/"stats.json").exists() else []
}
# Also save meta
VIZ.mkdir(parents=True, exist_ok=True)
with open(VIZ/"snapshots_web.json",'w') as f:
    json.dump(web,f)
print(f"Web JSON {len(str(web))} chars, saved to {VIZ/'snapshots_web.json'} size {pathlib.Path(VIZ/'snapshots_web.json').stat().st_size/1e6:.2f} MB")
# Also save a small preview PNG for static
import matplotlib.pyplot as plt
with rasterio.open(INPUT/"dem_clipped.tif") as ds:
    dem=ds.read(1)
    bounds=ds.bounds
# Plot final depth
import matplotlib.colors as mcolors
plt.figure(figsize=(10,5))
plt.subplot(1,2,1)
plt.imshow(snap[-1], cmap='viridis', vmin=0, vmax=1.5, origin='upper', extent=[bounds.left,bounds.right,bounds.bottom,bounds.top])
plt.colorbar(label='depth m')
plt.title(f"Big Square V0 final {snap[-1].max():.2f} m 06:00")
plt.xlabel("lon"); plt.ylabel("lat")
plt.subplot(1,2,2)
plt.imshow(dem, cmap='terrain', vmin=4, vmax=35, origin='upper', extent=[bounds.left,bounds.right,bounds.bottom,bounds.top], alpha=0.8)
flood=np.where(snap[-1]>0.05, snap[-1], np.nan)
plt.imshow(flood, cmap='Blues', vmin=0, vmax=1.5, origin='upper', extent=[bounds.left,bounds.right,bounds.bottom,bounds.top], alpha=0.6)
plt.title("DEM + flood >5cm")
plt.colorbar(label='depth m')
plt.tight_layout()
plt.savefig(VIZ/"depth_final.png", dpi=150)
print("Saved depth_final.png")
# Timeseries
import json
stats=json.loads((OUTPUT/"stats.json").read_text())
times_hr=[s['t']/3600 for s in stats]
max_h=[s['max_h'] for s in stats]
flooded=[s['flooded']/324 for s in stats] # percent (32400/100=324)
plt.figure(figsize=(8,4))
plt.plot(times_hr, max_h, label='max depth m', color='#38bdf8')
plt.plot(times_hr, flooded, label='flooded %', color='#22c55e')
plt.axvspan(0,1, color='gray', alpha=0.2, label='rain 50 mm/hr')
plt.xlabel("hr"); plt.legend(); plt.grid(alpha=0.3)
plt.title("Big Square V0 (180x180 @30m) 50mm/hr 1hr")
plt.tight_layout()
plt.savefig(VIZ/"timeseries.png", dpi=150)
print("Saved timeseries.png")
