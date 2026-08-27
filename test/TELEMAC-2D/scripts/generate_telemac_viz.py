#!/usr/bin/env python3
"""
Generate TELEMAC-2D V0/V1 visualization: PNG maps + HTML
"""
import pathlib, json, numpy as np, rasterio
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

BASE=pathlib.Path(__file__).parent.parent
INPUT=BASE/"input"
OUTPUT=BASE/"output"
VIZ=BASE/"visualization"
BBOX=(80.155,13.11,80.175,13.13)

def plot_depth(depth_path, dem_path, drain_mask_path, road_mask_path, out_png, title, vmin=0, vmax=1.5, cmap='viridis'):
    with rasterio.open(depth_path) as ds:
        depth=ds.read(1)
        bounds=ds.bounds
        transform=ds.transform
    with rasterio.open(dem_path) as ds:
        dem=ds.read(1)
    drain=np.load(drain_mask_path)
    road=np.load(road_mask_path)
    # Mask nodata depth where depth 0 => transparent
    # Create figure
    fig, (ax1,ax2)=plt.subplots(1,2, figsize=(14,6))
    # Depth map
    im=ax1.imshow(depth, cmap=cmap, vmin=vmin, vmax=vmax, origin='upper', extent=[bounds.left,bounds.right,bounds.bottom,bounds.top])
    ax1.set_title(f"{title}\nWater Depth (m)")
    ax1.set_xlabel("Longitude"); ax1.set_ylabel("Latitude")
    # Overlay drains and roads
    # Drain cells in red dots
    ys,xs=np.where(drain==1)
    # Convert row col to lon lat via transform
    lons, lats=rasterio.transform.xy(transform, ys, xs)
    ax1.scatter(lons,lats,s=1,c='red',alpha=0.3,label='drains')
    # Roads in white?
    ys,xs=np.where(road==1)
    lons,lats=rasterio.transform.xy(transform, ys, xs)
    ax1.scatter(lons,lats,s=0.5,c='white',alpha=0.2,label='roads')
    plt.colorbar(im, ax=ax1, label='depth m', shrink=0.7)
    ax1.legend(loc='lower left', fontsize=8)

    # DEM + flood extent
    # Hillshade? just dem
    im2=ax2.imshow(dem, cmap='terrain', vmin=9, vmax=31, origin='upper', extent=[bounds.left,bounds.right,bounds.bottom,bounds.top], alpha=0.8)
    # Overlay depth contours
    # Where depth >0.05 flood
    flood=np.where(depth>0.05, depth, np.nan)
    im2b=ax2.imshow(flood, cmap='Blues', vmin=0, vmax=1.5, origin='upper', extent=[bounds.left,bounds.right,bounds.bottom,bounds.top], alpha=0.6)
    ax2.set_title(f"DEM + Flood extent (>5cm)")
    ax2.set_xlabel("Longitude")
    plt.colorbar(im2, ax=ax2, label='DEM m', shrink=0.7)
    # Stats box
    max_h=depth.max(); mean_h=depth[depth>0].mean() if np.any(depth>0) else 0
    flooded=(depth>0.05).sum()
    total=depth.size
    ax2.text(0.02,0.98,f"max {max_h:.2f} m\nmean {mean_h:.2f} m\nflooded {flooded}/{total} ({flooded/total*100:.1f}%)", transform=ax2.transAxes, va='top', ha='left', bbox=dict(boxstyle="round",fc="white",alpha=0.8), fontsize=9)

    plt.tight_layout()
    VIZ.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_png, dpi=160, bbox_inches='tight')
    plt.close()
    print(f"Saved {out_png}")

def plot_timeseries():
    import json
    v0_stats=json.loads((OUTPUT/"V0"/"stats_V0.json").read_text())
    v1_stats=json.loads((OUTPUT/"V1"/"stats_V1.json").read_text())
    times=np.load(OUTPUT/"V0"/"times_V0.npy")/3600 # hr
    # Extract max_h, vol, flooded
    v0_max=[s['max_h'] for s in v0_stats]
    v1_max=[s['max_h'] for s in v1_stats]
    v0_vol=[s['vol']/1000 for s in v0_stats] # m3 -> k m3? keep m3
    v1_vol=[s['vol']/1000 for s in v1_stats]
    v0_flood=[s['flooded']/51.84 for s in v0_stats] # percent? Actually flooded cells count, convert to % of domain? 5184 cells => %
    v1_flood=[s['flooded']/51.84 for s in v1_stats]
    # Actually flooded is count, /51.84 = percent (since 5184/100=51.84)
    fig, axes=plt.subplots(3,1, figsize=(10,8), sharex=True)
    axes[0].plot(times, v0_max, label='V0 terrain+rain', color='#38bdf8', lw=2)
    axes[0].plot(times, v1_max, label='V1 + infinite drain', color='#ef4444', lw=2, ls='--')
    axes[0].set_ylabel('Max depth (m)')
    axes[0].legend(); axes[0].grid(alpha=0.3)
    axes[0].set_title('TELEMAC-2D prototype V0 vs V1 (72x72@30m, 50mm/hr 1hr)')

    axes[1].plot(times, v0_vol, label='V0', color='#38bdf8')
    axes[1].plot(times, v1_vol, label='V1', color='#ef4444', ls='--')
    axes[1].set_ylabel('Total volume (k m3)')
    axes[1].legend(); axes[1].grid(alpha=0.3)

    axes[2].plot(times, v0_flood, label='V0', color='#38bdf8')
    axes[2].plot(times, v1_flood, label='V1', color='#ef4444', ls='--')
    axes[2].set_ylabel('Flooded % (>5cm)')
    axes[2].set_xlabel('Time (hr)')
    axes[2].legend(); axes[2].grid(alpha=0.3)
    # Rain bar
    ax2=axes[0].twinx()
    rain=np.where(np.array(times)<1, 50, 0)
    ax2.fill_between(times, 0, rain, color='gray', alpha=0.2, step='mid', label='rain')
    ax2.set_ylabel('Rain mm/hr', color='gray')
    plt.tight_layout()
    plt.savefig(VIZ/"timeseries_V0_V1.png", dpi=160)
    plt.close()
    print(f"Saved timeseries")

def plot_diff():
    with rasterio.open(OUTPUT/"V0"/"depth_final_V0.tif") as ds:
        v0=ds.read(1); bounds=ds.bounds; transform=ds.transform
    with rasterio.open(OUTPUT/"V1"/"depth_final_V1.tif") as ds:
        v1=ds.read(1)
    diff=v0 - v1
    # Positive = V0 deeper than V1 (drain effect)
    fig, ax=plt.subplots(figsize=(8,6))
    im=ax.imshow(diff, cmap='RdBu_r', vmin=-0.5, vmax=0.5, origin='upper', extent=[bounds.left,bounds.right,bounds.bottom,bounds.top])
    ax.set_title("Drain effect: V0 depth - V1 depth (m)\nRed = V0 deeper (drain reduces flood)")
    plt.colorbar(im, label='depth diff m')
    ax.set_xlabel("Longitude"); ax.set_ylabel("Latitude")
    # Overlay drains
    drain=np.load(INPUT/"drain_mask.npy")
    ys,xs=np.where(drain==1)
    lons,lats=rasterio.transform.xy(transform, ys, xs)
    ax.scatter(lons,lats,s=1,c='k',alpha=0.2)
    plt.tight_layout()
    plt.savefig(VIZ/"diff_V0_V1.png", dpi=160)
    plt.close()
    print(f"Saved diff")

if __name__=="__main__":
    plot_depth(OUTPUT/"V0"/"depth_final_V0.tif", INPUT/"dem_clipped.tif", INPUT/"drain_mask.npy", INPUT/"road_mask.npy", VIZ/"depth_V0.png", "V0 — Terrain + Rain (no drain)", vmax=1.5)
    plot_depth(OUTPUT/"V1"/"depth_final_V1.tif", INPUT/"dem_clipped.tif", INPUT/"drain_mask.npy", INPUT/"road_mask.npy", VIZ/"depth_V1.png", "V1 — + Infinite Drain (sink)", vmax=1.5)
    plot_timeseries()
    plot_diff()
    print("Viz done")

